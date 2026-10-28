# MiniCPM-V-4.7-35B-A3B 原生 vLLM TP2 功能验证

验证日期：2026-09-28；Host `H100-149`；容器 `MinicpmV4.7-35B-native`；
模型 `/data/models/MiniCPM-V-4.7/weights/35b-a3b`；vLLM wheel
`0.24.0+cu129`，短标记 `gee0da84ab`；镜像 ID
`sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`。
Host 与容器的获批工作根同为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native`，设备号:inode 同为
`45:242118947849`。权重目录的设备号:inode 同为 `64768:2147497685`。

## 执行模式与请求

| 模式/轮次 | 原始证据（上述工作根下） | 核实结果 |
| --- | --- | --- |
| eager TP2 初始接入 | `04-runs/eager-tp2-v1/service.log`、`smoke.json`、`image-smoke.json` | 17/17 权重 shard 加载；健康/模型列表 200；32-token 文本回复截断，保留为未通过；红图最终答案 Red |
| eager TP2 canvas 修正 | `04-runs/eager-tp2-v2/`、`02-issues/positions-v2.py` | 文本 `17+25=42`、红图 Red、两帧视频先红后蓝均 stop；位置三通道与 checkpoint 的 canvas 算法一致，解码 delta 已核对 |
| 请求 full graph | `04-runs/graph-tp2-full-v1/service.log` | GDN backend 报仅支持 `UNIFORM_BATCH`，自动降至 `FULL_DECODE_ONLY`；decode FULL 4/4 捕获，prefill 未覆盖 full graph，详见 003 |
| decode-full 回放 | `04-runs/graph-tp2-full-v1/smoke.json`、`image-smoke.json`、`video-smoke.json`、`concurrency-10.json` | 文本、图像、视频答案与 eager 对应请求一致；8 个算术与 2 个红图并发请求 10/10 返回 200、stop 且答案符合预期 |
| 移除 Triton 进程隔离 | `04-runs/graph-tp2-noisolation-v1/service.log` | 启动及图捕获完成，但首个请求在 TP1 的 Triton cache 清理中报 `EBUSY`，客户端超时；该配置失败，详见 002 |
| 根级最终脚本 | `start-model.sh`、`04-runs/start-model.log`、`04-runs/final-tp2-v2/` | TP2，显式 decode-full，prefix caching 开启；文本、图像、视频和十并发请求通过；占用端口时脚本拒绝替换服务 |

根级脚本的 Host/容器路径均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，
SHA-256 `5c12ac80b434444b124c7c9613ae951f3adbc2a1d8641abc11b0fae02bf85940`。
已在容器中 `bash -n`，并用该脚本实际启动、捕获 decode FULL 图及探测 API。
最终进程组为 `2917445`，容器原 `/bin/bash` 进程未变化。`/health` 为 200；
重复执行脚本返回 1 并报告端口占用，随后 `/health` 仍为 200。
`06-cache/python-pycache` 和 `06-cache/xdg/torch/kernels` 均已存在于批准根下。
脚本只写 `04-runs/` 日志、`05-tmp/` 临时文件与 `06-cache/` 缓存；
不停止或重启容器。`CUDA_VISIBLE_DEVICES=2,3` 固定本轮验证的设备；
`LD_LIBRARY_PATH` 解决该镜像中 `libcuda.so.1` 默认不可定位；
`HF_HOME`、`XDG_CACHE_HOME`、`TRITON_CACHE_DIR`、`VLLM_CACHE_ROOT`、
`PYTHONPYCACHEPREFIX` 和 `TMPDIR` 限定隐式写入范围。
`PYTHONPATH` 与 `MINICPM47_TRITON_PER_PROCESS=1` 保留在本轮对照中验证必需的
Triton 进程隔离。`--max-model-len 2048`、`--max-num-batched-tokens 2048`、
`--max-num-seqs 8`、`--gpu-memory-utilization 0.8` 固定已实测资源与并发边界；
`--reasoning-parser qwen3` 将模型思考段置于 `reasoning` 字段，使 `content`
只保留最终回复。端口 `127.0.0.1:8107` 是本轮核验的本机接口，脚本在被占用时退出。

最终独立结果的 SHA-256：`04-runs/final-tp2-v2/smoke.json` 为
`7bc3d5ab2520da2800fa453adb7c4d7dc4312630863ca97b930c23adb6f58e99`，
`image-smoke.json` 为
`20fd728de9dd6e88e046bfbfbc23356941e02ce1b10572877b1e7a441c6d1728`，
`video-smoke.json` 为
`bda1a61f74af51866047efc8ef354fc766e9dd6f260bc802e223ca84165d95da`，
`concurrency-10.json` 为
`846ad8c07aedbc4d5d708dce2496fcbbde2799af5d1a24e2feb65e072488e8f5`。

## 代码审查与限制

wheel 中 `registry.py` 的原/新 SHA-256 为
`ab52495073a046b79d00a314cbc96e719e3ed916ea8a8bf6f3202015062b5676` / 
`58ea925cd79c7771b35455d48c5d991928fd019539d8e0e61e100af541d55d43`，
实际 diff 只增加 4.7 架构映射；原 4.6 adapter SHA-256 始终为
`fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`。
新增 4.7 adapter SHA-256
`91696f38a69091e45bd75fe1c35dd86ca32837c2827dd4d9251fda469ed2931f`。
4.7 的 MoE、canvas、视觉/视频处理集中在模型 adapter 与既有扩展点，未改 vLLM
共享执行代码；对 4.6 的静态未改证据已核实，其他模型的运行回归未做。
容器没有 Git checkout；无法给出 HEAD、PR base 或原有工作树 dirty/untracked
清单。本轮以镜像 ID、安装路径、原/新文件哈希及备份/diff 记录代替，未提交、
推送或建 PR。

这些请求只能证明已测输入的功能，不是项目固定 GPQA sanity，也不是正式精度或性能。
用户明确要求先不做正式精度评测，因此精度、性能和完整验收保持未完成。
2048-token 以上上下文、复杂高分辨率切片、跨模型/跨平台和长期稳定性仍未验证。

## 原生绑定核验

2026-09-28 将架构、环境、适配与 execution-mode 的原生回执绑定到
`framework.yml`，部署指纹
`9e488a3901d292ceb7e7af18f9690e47da45f9e790b5215b1a07f0780fd3bcd5`。
远端回执目录为 `04-runs/framework-functional-20260928/`，环境、适配、
execution-mode 回执 SHA-256 依次为
`26517625a8ae8c657a94e5de63d39dc494abb6d6dfdfbb049a1fcc8b2eb1cf97`、
`6b2b3d9dd2d5a79a0df5006768d3a13122142e3e827c6ea5a8536d41d8407a53`、
`88576f60daee16c7cc21872bb8788e456dce9d685bdc781fb3e184357cde67ec`。
使用工作根 `03-acceptance/functional-verifier/` 中的仓库原生框架校验器，
在目标容器指定 `--artifact-root H100-149=<已核实容器工作根>` 后运行
`acceptance --acceptance-substeps execution-mode --check-only --verify-records`，
返回 `Framework gate passed`。这证明本轮执行模式回执及其原始文件可读取，
不代表后续 sanity、accuracy 或 performance 已通过。
