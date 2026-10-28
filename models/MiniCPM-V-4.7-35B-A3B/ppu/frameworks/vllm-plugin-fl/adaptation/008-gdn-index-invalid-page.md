# 008：高并发长解码时 GDN 索引路径发生 PPU 非法页

## 元数据

- 状态：`hypothesis`；只读核对日期：2026-10-02。
- 模型、Host、容器：MiniCPM-V-4.7-35B-A3B、`PPU-13`、
  `minicpmV4.7-35B`，TP2/PPU 0、1，`FULL_AND_PIECEWISE`、前缀缓存开启。
- 运行时 Plugin HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`
  加既有差异；vLLM checkout HEAD
  `ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems checkout
  HEAD `1a38df24f72ca5a4a6a24650b5d66356709750ba`，运行包 5.3.5。

## 问题现象

2026-10-02 12:42:38，既有根级 `service.log` 首先在 4894、4943 行记录
PPU `Exception invalid page`，指令函数 `_index_jit_function`，写入指令
`vmem.st.b32x4`。随后 TP0/TP1 的 Python 栈在 vLLM GDN
`initial_state[~prefill_has_initial_state, ...] = 0` 附近报告
`torch.AcceleratorError: CUDA error: an illegal memory access was encountered`；
该处经 FlagGems `index_put_ → nonzero_numpy`，但错误可能异步报告，不能把
这个 Python 调用位置认定为首次越界写入。EngineCore 退出后 API 大量返回
HTTP 500，最终 35B 服务完全退出；适配容器保持运行。故障前日志显示
`Running: 64 reqs`、`Waiting: 0`、KV 使用约 4.2%，没有 OOM 证据。

该症状不同于单题答错或严格答案提取失败，不能计为普通 GPQA 错题后继续
声称样本完整。用户提供的两份 198 题文件没有包含该服务崩溃的完整运行回执；
不能推断哪些样本与此次故障属于同一轮。

## 已有经验匹配与假设

同 Host [MiniCPM-V-4.7-1B 的 006 问题](../../../../../MiniCPM-V-4.7-1B/ppu/frameworks/vllm-plugin-fl/adaptation/006-gdn-index-invalid-page-under-accuracy-load.md)
在 PPU2、TP1、32 并发、接近 28k token 的 mixed prefill/decode 下，
也首先在 `_index_jit_function` 的 `vmem.st.b32x4` 发生非法页，随后 GDN
索引栈报错。两个签名的先后顺序和内核函数相同；模型规模、TP 拓扑、设备、
并发及生成长度不同，因此只能作为强候选，不能直接继承其未证明的根因。
该问题中的小型原生/FlagGems eager 与 graph 索引对照均未复现，故简单
blacklist、降低并发或切换图模式尚不是经验证的根因修复。

当前最强假设是 GDN mixed 批处理中的 FlagGems `index` JIT 对某个真实
状态形状、索引或 graph replay 地址发生越界；还缺故障时精确张量/索引、
首个异步错误同步点以及在同一 35B 服务负载上的受控前后对照。

## 处理与验证边界

2026-10-02 的独立 35B 诊断服务保留原模型参数，仅使用批准工作根内的新
`04-runs/gpqa2/`、`05-tmp/gpqa2/` 和 `06-cache/gpqa2/`；启动及六道成对
单请求通过，未复现非法页。另有 32 并发的温度零全量 GPQA 诊断已在
`04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-temp0-diagnostic-20261002/`
完成，198 题覆盖且无非法页或 EngineCore 崩溃，但 41 题在 600 秒请求超时，
故此运行不能证明持续负载下完全稳定。随后按原 PPU 评测参数完成的
32 并发全量诊断在
`04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-original-params-diagnostic-20261002/`，
198 题全部完成，0 timeout、0 API 错误；服务日志无 `invalid page`、
Python traceback 或 RPC timeout，终态 `/health` HTTP 200。原故障没有
稳定复现，但其首错签名仍需要独立定位，不以本次成功等同于根因修复。
没有修改 Plugin、vLLM、FlagGems 或原始日志，也没有重启适配容器。

用户随后仅在根级启动脚本中增加
`VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index_put,nonzero,copy,index_put_,index`
并重启服务；新脚本 SHA-256
`62d97f6ec4b9be9bcd7ebefbaa37aa08b6685fabac9b683ba859be3f422806b7`。
与旧脚本逐行 diff 只有这一行，API PID `1709269` 的环境变量已核实，
Plugin 的 `vllm_fl/utils.py` 读取该值。新实例上按原参数完成
32 并发 GPQA 198/198、0 timeout、0 API 错误；`service.log` 无
`invalid page`、非法访存、EngineCore 崩溃或 RPC timeout，终态健康检查
HTTP 200。运行身份、样本和哈希见
[重启后 GPQA 报告](../acceptance/gpqa-32c-after-restart-20261002.md)。
旧实例按相同 GPQA 32 并发也曾完整通过，因此这一次成功不能证明
黑名单必要或修复了此前 64 请求故障；当前分类仍为诊断性缓解候选，
不是已验证根因修复。适配容器未重启。

下一步如果在 35B 本轮复现同签名，先冻结实际调度张量、索引和首故障日志，
再仅在独立服务中针对 `index` 派发做一个变量的原生对照，复验数值与
eager/graph 及相关共享调用方；在此之前不向全局 Plugin 策略添加
blacklist。知识库处理状态：`needs-validation`；正式验收不能据此通过。
