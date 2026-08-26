#!/bin/bash
# MCCL 通信库性能测试脚本 (MTT S5000 / MooreThreads)
#
# 使用方式：
#   单机串行：  ./mccl_check.sh --mode single
#   单机并发：  ./mccl_check.sh --mode single --threads 4
#   跨机串行：  ./mccl_check.sh --mode multi
#   跨机并发：  ./mccl_check.sh --mode multi  --threads 4
#   混合并发：  ./mccl_check.sh --mode mixed        ← AR + SendRecv 同时跑，模拟 PP+TP
#   全量串行：  ./mccl_check.sh --mode all
#   快速：      ./mccl_check.sh --mode all --quick
#   持久压测：  ./mccl_check.sh --mode marathon
#
# --threads N 说明（-t 参数）：
#   N 个 CPU 线程各自持有独立 communicator 同时运行，等价于 N 个模型副本并行。
#   注意：这与 SGLang 的"并发请求数"无关。
#   SGLang 的 50 个并发请求最终合成 1 个 batch、1 次 forward、1 次 AllReduce，
#   其效果体现在消息大小（-b/-e）上，而非线程数。
#   --threads 适合测试多副本/多租户场景下的 GPU 资源竞争。
#     --threads 1  →  -t 1 -g 8  （SGLang TP8 单副本，推荐用这个）
#     --threads 2  →  -t 2 -g 4  （2 个独立副本同时跑，各占 4 卡）
#     --threads 4  →  -t 4 -g 2  （4 个独立副本同时跑，各占 2 卡）
#
# 数据范围（对应 SGLang Qwen3-27B TP8）：
#   消息大小 = batch_size × seq_len × hidden_size × dtype_size
#   512K  ≈ decode 阶段（batch=50, seq=1,   hidden=7168, fp16 → ~700KB）
#   8M    ≈ prefill 阶段（batch=50, seq=256, hidden=7168, fp16 → ~7MB）
#   32M   ≈ 大 prefill chunk 峰值

set -uo pipefail
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
# =============================================================================
# ★ 按环境修改这里 ★
# =============================================================================
MCCL_TEST_DIR="/usr/local/musa-4.3.5/mccl_test"
MCCL_LIB_DIR="/usr/local/musa-4.3.5/lib"

NODE1="10.1.15.176"
NODE2="10.1.15.61"
GPUS_PER_NODE=8
HOSTS="${NODE1}:${GPUS_PER_NODE},${NODE2}:${GPUS_PER_NODE}"
SSH_PORT=62288

RESULT_DIR="./mccl_perf_$(date +%Y%m%d_%H%M%S)"
# =============================================================================

BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[INFO]${NC} $*"; }
err()  { echo -e "${RED}[ERR ]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

MODE="all"
QUICK=0
NTHREADS=1   # -t 参数，控制并发 communicator 数

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)    MODE="$2";     shift 2 ;;
        --quick)   QUICK=1;       shift   ;;
        --threads) NTHREADS="$2"; shift 2 ;;
        -h|--help) sed -n '2,25p' "$0" | sed 's/^# \{0,2\}//'; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

if [[ $QUICK -eq 1 ]]; then
    ITERS=500;  WARMUP=5
else
    ITERS=5000; WARMUP=50
fi

# 单机每线程持有的 GPU 数（总 8 卡均分给 NTHREADS 个线程）
GPUS_PER_THREAD=$(( GPUS_PER_NODE / NTHREADS ))
if (( GPUS_PER_THREAD < 1 )); then
    err "--threads $NTHREADS 超过 GPU 数 $GPUS_PER_NODE"
    exit 1
fi

# 运行一项测试，tee 日志，检查校验错误
# $1=标题  $2=日志名  $3+=命令
run_test() {
    local title="$1"
    local logfile="$RESULT_DIR/$2"
    shift 2

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "[$title]"
    log "CMD: $*"

    set +e
    "$@" 2>&1 | tee "$logfile"
    local rc=${PIPESTATUS[0]}
    set -e

    if [[ $rc -ne 0 ]]; then
        err "$title 退出码=$rc"
        return
    fi

    local wrong
    wrong=$(grep -oP '(?<=# Out of bounds values : )\d+ \w+' "$logfile" | tail -1)
    if [[ -n "$wrong" && "$wrong" != "0 OK" ]]; then
        err "$title 数据校验: $wrong  ← 通信结果有误！"
    fi

    grep -E "Avg bus bandwidth|Out of bounds" "$logfile" || true
}

# Populate a bash array (passed by name) with the full mpirun argv.
# Avoids word-splitting issues that broke quoted args (e.g. plm_rsh_args).
build_mpi_prefix() {
    local -n _arr=$1
    _arr=(
        mpirun
        -H "${HOSTS}"
        --mca plm_rsh_args "-p ${SSH_PORT} -o StrictHostKeyChecking=no"
        --mca btl_tcp_if_include bond0
        --mca oob_tcp_if_include bond0
        --allow-run-as-root
        -x MCCL_IB_QPS_PER_CONNECTION=8
        -x MCCL_IB_SPLIT_DATA_ON_QPS=1
        -x MCCL_MIN_NCHANNELS=16
        -x MCCL_MAX_NCHANNELS=32
        -x MCCL_NET_GDR_LEVEL=5
        -x MCCL_IB_GID_INDEX=3
        -x MCCL_IB_TIMEOUT=23
        -x MCCL_IB_RETRY_CNT=7
        -x MCCL_DEBUG=WARN
        -x PATH
        -x "LD_LIBRARY_PATH=${MCCL_LIB_DIR}:${LD_LIBRARY_PATH:-}"
    )
}

check_multi_node() {
    if ! command -v mpirun &>/dev/null; then
        warn "mpirun 不在 PATH，跳过跨机测试"
        return 1
    fi
    for node in "$NODE1" "$NODE2"; do
        if ! ssh -p "$SSH_PORT" -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
                "root@${node}" true 2>/dev/null; then
            warn "SSH 连接失败: ${node}:${SSH_PORT}，跳过跨机测试"
            return 1
        fi
        log "SSH 连通: ${node}:${SSH_PORT}"
    done
}

# =============================================================================
# 单机 8 卡
# -t NTHREADS -g GPUS_PER_THREAD：N 个 communicator 同时跑，各持 8/N 张卡
# =============================================================================
run_single_node_tests() {
    log "======= 单机 8 卡 (MTLink P2P, -t ${NTHREADS} -g ${GPUS_PER_THREAD}) ======="
    local C=(-b 512K -e 32M -f 2 -t "$NTHREADS" -g "$GPUS_PER_THREAD" -n "$ITERS" -w "$WARMUP" -c 1)

    run_test "单机 AllReduce"     "single_allreduce.log"     "${MCCL_TEST_DIR}/all_reduce_perf"     "${C[@]}"
    run_test "单机 AllGather"     "single_allgather.log"     "${MCCL_TEST_DIR}/all_gather_perf"     "${C[@]}"
    run_test "单机 ReduceScatter" "single_reduce_scatter.log" "${MCCL_TEST_DIR}/reduce_scatter_perf" "${C[@]}"
    run_test "单机 AllToAll"      "single_alltoall.log"      "${MCCL_TEST_DIR}/alltoall_perf"       "${C[@]}"
    run_test "单机 SendRecv"      "single_sendrecv.log"      "${MCCL_TEST_DIR}/sendrecv_perf"       "${C[@]}"
}

# =============================================================================
# 跨机 2×8=16 进程（RoCE 200G，-g 1）
# -t NTHREADS：每进程 N 个并发 communicator，共享该进程的 1 张卡
# =============================================================================
run_multi_node_tests() {
    log "======= 跨机 2×8=16 卡 (RoCE 200G, -t ${NTHREADS} -g 1) ======="
    check_multi_node || return

    local MPI_ARR=()
    build_mpi_prefix MPI_ARR
    local C=(-b 512K -e 32M -f 2 -t "$NTHREADS" -g 1 -n "$ITERS" -w "$WARMUP" -c 1)

    run_test "跨机 AllReduce"     "multi_allreduce.log"      "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/all_reduce_perf"     "${C[@]}"
    run_test "跨机 AllGather"     "multi_allgather.log"      "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/all_gather_perf"     "${C[@]}"
    run_test "跨机 ReduceScatter" "multi_reduce_scatter.log" "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/reduce_scatter_perf" "${C[@]}"
    run_test "跨机 SendRecv(PP)"  "multi_sendrecv.log"       "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/sendrecv_perf"       "${C[@]}"
    run_test "跨机 AllToAll"      "multi_alltoall.log"       "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/alltoall_perf"       "${C[@]}"
}

# =============================================================================
# 混合并发（--mode mixed）：模拟 SGLang PP2TP8 同时跑 TP+PP 通信
#
# 单机版：GPU 0-3 跑 AllReduce（TP），GPU 4-7 同时跑 SendRecv（PP）
# 跨机版：mpirun AllReduce 和 mpirun SendRecv 同时后台启动
#
# 注意：跨机混合模式两个 mpirun 共用同一批 GPU，会产生 GPU 资源竞争，
#       这正是 SGLang 真实场景下 TP 和 PP 通信互相抢占带宽的状态。
# =============================================================================
run_mixed_tests() {
    log "======= 混合并发：AR(TP) + SendRecv(PP) 同时运行 ======="

    # ── 单机混合：物理分卡，各跑各的 ──────────────────────────────────────────
    local half=$(( GPUS_PER_NODE / 2 ))
    local dev_tp=""
    local dev_pp=""
    for (( i=0; i<half; i++ )); do dev_tp+="${i},"; done
    for (( i=half; i<GPUS_PER_NODE; i++ )); do dev_pp+="${i},"; done
    dev_tp="${dev_tp%,}"; dev_pp="${dev_pp%,}"

    local C=(-b 512K -e 32M -f 2 -t 1 -g "$half" -n "$ITERS" -w "$WARMUP" -c 1)

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "[单机混合] TP AllReduce (GPU ${dev_tp})  &&  PP SendRecv (GPU ${dev_pp})  并行"

    MUSA_VISIBLE_DEVICES="$dev_tp" \
        "${MCCL_TEST_DIR}/all_reduce_perf" "${C[@]}" \
        2>&1 | tee "${RESULT_DIR}/mixed_single_ar.log" &
    local pid_ar=$!

    MUSA_VISIBLE_DEVICES="$dev_pp" \
        "${MCCL_TEST_DIR}/sendrecv_perf" "${C[@]}" \
        2>&1 | tee "${RESULT_DIR}/mixed_single_sr.log" &
    local pid_sr=$!

    wait $pid_ar $pid_sr
    grep -E "Avg bus bandwidth|Out of bounds" "${RESULT_DIR}/mixed_single_ar.log" || true
    grep -E "Avg bus bandwidth|Out of bounds" "${RESULT_DIR}/mixed_single_sr.log" || true

    # ── 跨机混合：两个 mpirun 同时后台启动，共用 GPU ─────────────────────────
    check_multi_node || return

    local MPI_ARR=()
    build_mpi_prefix MPI_ARR
    local MC=(-b 512K -e 32M -f 2 -t 1 -g 1 -n "$ITERS" -w "$WARMUP" -c 1)

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "[跨机混合] TP AllReduce 和 PP SendRecv 同时后台启动（共享 GPU，模拟真实竞争）"

    "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/all_reduce_perf" "${MC[@]}" \
        2>&1 | tee "${RESULT_DIR}/mixed_multi_ar.log" &
    local pid_mar=$!

    "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/sendrecv_perf" "${MC[@]}" \
        2>&1 | tee "${RESULT_DIR}/mixed_multi_sr.log" &
    local pid_msr=$!

    wait $pid_mar $pid_msr
    grep -E "Avg bus bandwidth|Out of bounds" "${RESULT_DIR}/mixed_multi_ar.log" || true
    grep -E "Avg bus bandwidth|Out of bounds" "${RESULT_DIR}/mixed_multi_sr.log" || true
}

# =============================================================================
# Marathon 压测（检测偶发 hang）
# =============================================================================
run_marathon_test() {
    log "======= Marathon 压测 (跨机 SendRecv 100000 iter，约 60~90 分钟) ======="
    check_multi_node || return

    local MPI_ARR=()
    build_mpi_prefix MPI_ARR

    run_test "Marathon SendRecv" "marathon_sendrecv.log" \
        "${MPI_ARR[@]}" "${MCCL_TEST_DIR}/sendrecv_perf" \
        -b 512K -e 32M -f 2 -t "$NTHREADS" -g 1 -n 100000 -w 100 -c 1
}

# =============================================================================
# 主流程
# =============================================================================
mkdir -p "$RESULT_DIR"
export LD_LIBRARY_PATH="${MCCL_LIB_DIR}:${LD_LIBRARY_PATH:-}"

for bin in all_reduce_perf all_gather_perf reduce_scatter_perf alltoall_perf sendrecv_perf; do
    if [[ ! -x "${MCCL_TEST_DIR}/${bin}" ]]; then
        err "二进制缺失: ${MCCL_TEST_DIR}/${bin}"; exit 1
    fi
done

echo "════════════════════════════════════════════════════════════════════"
echo "  MCCL 性能测试  |  模式: ${MODE}  |  迭代: ${ITERS}"
echo "  并发线程: ${NTHREADS}  |  单机每线程 GPU: ${GPUS_PER_THREAD}"
echo "  数据范围: 512K ~ 32M  |  结果目录: ${RESULT_DIR}"
echo "  时间: $(date)"
echo "════════════════════════════════════════════════════════════════════"

case "$MODE" in
    single)   run_single_node_tests ;;
    multi)    run_multi_node_tests  ;;
    mixed)    run_mixed_tests       ;;
    marathon) run_marathon_test     ;;
    all)
        run_single_node_tests
        run_multi_node_tests
        ;;
    *)
        err "未知 mode: $MODE (可选: single|multi|mixed|all|marathon)"
        exit 1
        ;;
esac

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  全部完成  |  $(date)"
echo "  日志保存至: ${RESULT_DIR}/"
echo "  校验错误汇总: grep -r 'Out of bounds' ${RESULT_DIR}/"
echo "  带宽汇总:     grep -r 'Avg bus bandwidth' ${RESULT_DIR}/"
echo "════════════════════════════════════════════════════════════════════"