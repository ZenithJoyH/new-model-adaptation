# 015：mx-59 排序算子与 Plugin 调度吞吐优化

## 范围与身份

2026-10-10，用户选择适配优化，目标仅 `mx-59` 的 `qwen3.6-27B`；不是正式验收。容器 ID `1f62bdcb818d7119ed6595133dc64c3f14c194ae565c95dba18ef89bbd4fe657`，镜像标签 `flagos/qwen3.6-27b-metax:public-flash-20261008`。完整 `/public-flash` 同路径 RW bind，工作根 `/public-flash/jinghao/qwen3.6-27B`；`/workspace` 与 `/opt/conda` 为容器内部文件系统。

实际 Python `/opt/conda/bin/python3`。editable Plugin `/workspace/vllm-plugin-FL`，HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`；editable FlagGems `/workspace/FlagGems`。保留已有 attention/GDN/worker 修改，不覆盖其他工作。vLLM `/workspace/vllm` HEAD `bc150f50299199599673614f80d12a196f377655` 只读，继承 `fused_recurrent.py` 修改。

按 profile 要求核对 clean `master` / `origin/master` 后，执行 `git fetch origin master`、`git pull --ff-only origin master`，FlagGems 从 `c778fea4ab7825e5461d44fd5131eab2d3df9811` 快进到 `7599dd130046f84df099aa771e91d35d5991e69a`。更新包含522个文件；随后重新启动基线，基线与优化测量均使用后一个 HEAD，不将同步收益计作本轮算子优化。

## 冻结场景与实施方案

现场启动脚本已经被用户调整：加入 `mm_out` 黑名单，显存预算0.9，图捕获最大batch64。不能继续用前一日0.8预算、未关闭 `mm_out` 的结果作受控基线。

本轮保持 GPU6/7、TP2、BF16、端口8002、alias `qwen36-27b-somegems-noatten-nogdn-prefillopt-nommout`、max model len262144、batched tokens16384、显存0.9、`FULL_AND_PIECEWISE` / max capture size64。黑名单为 `gdn_prefill,gdn_decode,index_select,mm,max,exponential_,attention_backend,mm_out`，连续单请求prefill开启；temperature1/top-k20/top-p0.95模型默认值不变。不重新选图模式。

性能专用实例显式 `--no-enable-prefix-caching`；不是通用生产最终 launcher。独立维护 runner 放在工作根 `03-acceptance/throughput-mx59-20261010/`，原始结果在 `04-runs/throughput-mx59-20261010/`。调用 `single-scenario`，4096输入/1024输出/并发64/128请求，runs3/skip-first1，先dry-run再执行，无profiler。Skill bundle SHA256 `3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff`。历史服务的编译缓存位置保持继承；新增独立诊断的隐式缓存明确放在工作根 `06-cache/throughput-mx59-20261010/`，不删除旧缓存。

### FlagGems 公共实现

已安装 `src/flag_gems/ops/sort.py` 的 `compute_global_hist_kernel`：用 `tl.histogram` + 一维 int32 bins 替换二维 `(TILE_R,TILE_N)` int64 比较矩阵，减少寄存器和归约成本。沿用原 order-key、radix位数、稳定sweep、indices、排序方向与调用入口。

采用无mask histogram接口，尾部padding填入bin0，再精确减掉padding计数，避免仅新Triton支持的masked接口；当前输入长度上限 `<2**30`，单CTA计数不可能溢出int32。公共优化没有增加模型/平台开关或绕开 FlagOS。未验证非MetaX硬件，不推断其性能或正确性通过。

源文件 SHA256：`4f63aadbe42f7dbfab0f0fb295c9dea09d749e292ce1b1e61340f68978e8fab9` -> `be54de41003acd872334e0a095e7af7fc5361f2f4d261439e3053fd17f3ca3dd`。

### Plugin 现有调度器

`vllm_fl/dispatch/manager.py` 增加 `_ready_pid`，仅在锁内注册及初始化完成后发布；同进程后续初始化检查直接返回，fork后失效。不是新调度抽象，不改策略、epoch、黑白名单、fallback或IO hooks。GDN hook与backend注册保持不变；vendor packed decode和原 attention链路保留。

源文件 SHA256：`2884b063a0a4d2890eb63ac32fa929b62ce79af0d701860d1ecc8d126ad9e64c` -> `59f5fa67d0d698206baa00d1486b59467e7895cb60a726a7414773f44f5ced50`。

## 定向验证与失败保留

- 补丁首次 `git apply --check` 因缺少充分上下文拒绝，未应用产品变更；补齐上下文后检查和应用成功。备份为工作根 `02-issues/throughput-mx59-20261010/{sort,manager}.before.py`，不是第二份源码树。
- 初次排序测试未启用FlagGems上下文，触发MetaX原生Torch UInt32 copy不支持：39 failed/12 passed，证据 `sort-regression-no-gems.log`。随后fixture误用 `use_gems(unused=...)`，纠正为真实API `exclude=`；证据 `sort-replay-fixture-error.log`。不改产品UInt32调用或数值容差。
- 独立图测试曾等待并最终超时，栈定位 `torch/cuda/streams.py:37`、`graphs.py:196` 的默认capture stream创建，尚未开始capture。只结束自有测试进程PID1525289；其余尝试用timeout180自动结束。保留 `sort-replay-preinit-hang.log`、`sort-replay-device-init-timeout.log`、`sort-replay-stream-init-timeout.log`。
- 基线测量结束后，停止本任务API PID1499851，释放GPU6/7，再在FlagGems接管前初始化设备/seed/default capture stream。改变输入的完整sort capture/replay检查通过。不能仅据这些联合调整断言底层等待根因；工作根 `07-bugs/metax-flaggems-stream-init-20261010/reproduce_metax_stream_init.py` 的简化独立控制（不含sort warmup）plain/prewarm均rc0，未复现原等待，标记为诊断线索而非已复现bug。
- `tests/test_sort_histogram.py`：**51 passed in 85.75s**，FP16/BF16/FP32、int8/int32/int64，双方向、1/1023/9333/248320宽度、重复值稳定索引、strided/nonlast dim、两次变输入图重放；与CPU参考逐值/索引精确比较。回归时SHA256 `4b3af0a31b0f83528f208f614cae2ca23e9e376c530db5e7f66277af4181cce5`；审查仅澄清stream预建的注释，不变更行为，最终SHA256 `10fe34fada01b8ba48afb9fec82a444376e8280d37b0d42a62ae38973e32d6f7`。
- `tests/unit_tests/dispatch`：**280 passed in 28.89s**，包括新增并发注册完成后发布、无锁ready检查、fork失效、policy epoch回归，以及现有GDN黑名单/vendor/FlagOS/IO/fallback。新测试 `test_manager_fast_init.py` SHA256 `93f4e8d56d2b22ee489a29e168ab154cdcfe5187afb2e589100a59385c7b4d01`。
- 微基准（GPU6、FP32词表248320、3预热/10次事件计时取中位数、同FlagGems黑名单）：batch1排序2.281->1.107ms，batch8 5.447->3.306ms，batch64 **31.001->14.285ms，2.17x**。调度选中GDN impl查询1.104->0.864μs，下降21.75%。证据 `baseline-operators.log` / `optimized-operators.log`。前者在基线模型占有显存但空闲时执行，后者在模型结束后执行；微基准只作辅助证据，不替代模型受控测量，也不量化单项端到端贡献。
- 变更后的 FG/Plugin `git diff --check` 均通过。vLLM完整diff SHA256仍为 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`，继承文件SHA256仍为 `5c21e23e2a4ffcc1b1c72544836c5f5a345ab8259d66006515b37bfd8e67bd36`。

## 端到端测量结果

基线原生报告：工作根 `04-runs/throughput-mx59-20261010/baseline/qwen36-27b-somegems-noatten-nogdn-prefillopt-nommout/20261010_101110_080735/benchmark-result.json`。

每轮128成功/0失败，输入524288、输出131072 tokens。计入均值两轮：总吞吐 **2419.18 tok/s**，输出 **483.84 tok/s**，耗时270.90s，平均TTFT16663.20ms，平均TPOT115.91ms，中位ITL88.21ms。两轮输出吞吐484.30/483.38 tok/s。

优化原生报告：工作根 `04-runs/throughput-mx59-20261010/optimized/qwen36-27b-somegems-noatten-nogdn-prefillopt-nommout/20261010_111101_967332/benchmark-result.json`。首轮总吞吐2672.56 tok/s，仅预热，不计均值；第二/三轮2727.51/2756.78 tok/s，耗时240.28/237.73s。每轮128成功/0失败，输入524288、输出131072 tokens，与基线一致。

| 指标（跳过首轮后两轮均值） | 基线 | 优化后 | 变化 |
| --- | ---: | ---: | ---: |
| 总吞吐 tok/s | 2419.18 | 2742.15 | +13.35% |
| 输出吞吐 tok/s | 483.84 | 548.43 | +13.35% |
| 请求集耗时 s | 270.90 | 239.00 | -11.78% |
| 平均TPOT ms | 115.91 | 99.44 | -14.21% |
| 中位ITL ms | 88.21 | 71.94 | -18.44% |
| P99 ITL ms | 2240.06 | 965.79 | -56.89% |
| 平均TTFT ms | 16663.20 | 17498.22 | +5.01% |

主要观测收益在生成阶段，TTFT没有改善，反而增加约5%；不能表述为所有延迟指标均改善。排序算子微基准与生成间隔下降相符，但未做两个产品补丁分别启停的端到端消融，不量化两者各自对总吞吐的贡献。共享主机其他GPU有独立工作负载，因此这是该冻结场景的重复测量结果，不推断全机隔离条件或其它输入长度的收益。

已在容器内调用维护runner的 `perf_common.validate_report`，两组原生报告、所有轮次（含预热）、stdout/stderr与CSV的SHA256/命令/解析/汇总均通过完整性核验；除output目录外request一致，各轮命令与producer相同。报告SHA256：基线 `9a349442a1f8a5d077150b21aa10f184e76100fbfca9346089b8358c94da01ba`，优化 `4257ab7595eb4d9fcc834ea44c7fc9c5cab562d49f610ca0d645a34ab4d3c6fe`。复核产物 `04-runs/throughput-mx59-20261010/comparison-verification.json`，时间2026-10-10 11:26:06 +08:00；其中 `performance_integrity=passed` 仅表示单场景原生结果完整性，不是正式模型验收。

优化服务按同一冻结脚本重新启动，Host API PID1547970，容器API PID218250，engine218607，worker218875/218876。复核时8002健康HTTP200，`/v1/models`返回相同alias，测量完成后Running/Waiting均0。两组KV cache均884154 tokens，两名worker的mixed PIECEWISE和decode FULL分别11/11图捕获完成。gdn_prefill/attention_backend实际选vendor.metax，rms_norm仍选default.flagos；FlagGems启用日志包含 `sort` / `sort_stable`。实际进程GPU6/7、原黑名单、连续单prefill开启，未设置PYTHONPATH；安装源SHA256与上述产品补丁一致。容器与优化后的服务保持运行。

## 审查与边界

改动所有权分别为公共FG kernel、现有Plugin调度器，约束和fallback不扩张；新测试留在实际安装源码中，运行计划、临时诊断、完整日志留在批准根。容器未停止/重启/替换，其他GPU服务未操作；未修改共享 `start-model-flagos.sh`，未修改vLLM/FGV、提交、推送或打包镜像。

这是限定优化及回归，不更新历史 `framework.yml` 或正式验收状态。16K/64K吞吐、其他平台、正式全量精度、镜像验证仍未完成。知识库处理：local-only。新代码位于容器内部安装树，现有launcher重启可直接加载，无新增环境开关；但尚未重新提交/保存镜像，不能声称旧镜像已包含本轮优化。

`./scripts/audit-workspace` 返回1：既有12个profile revision错误、78项待复核，与014的审计数量相同；未扩大范围刷新旧证据或修复其他模型记录，不表述为整体审计通过。
