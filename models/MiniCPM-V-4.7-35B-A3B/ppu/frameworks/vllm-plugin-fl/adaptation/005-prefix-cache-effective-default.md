# 005：非性能服务的前缀缓存生效值与启动假设不符

## 元数据与签名

- 状态：`verified`，eager/graph 修正及最小请求复测完成，正式验收待独立执行；首次出现和最后核查：2026-09-29。
- 模型/平台/Host：MiniCPM-V-4.7-35B-A3B / PPU / `PPU-13`。
- 容器：`minicpmV4.7-35B`，ID
  `145f15078dc1c953d9e136ce595e3185003a6606c28993e30061a2047d3f3653`。
- 软件：vLLM `0.24.0+empty`，Plugin HEAD
  `3a27a6fb2d514cdf55c00481bf813225dac63319` 加当前未提交适配。
- 范围：eager 与请求 `FULL` 后实际 `decode-full` 的所有此前非性能服务。

## 现象与证据

此前两个启动脚本均无 `--no-enable-prefix-caching`，记录误认为默认开启。
直接检查 EngineCore 的生效配置，
`04-runs/eager-tp2-sdpa-data-product-v2/service.log` 与
`04-runs/graph-tp2-full-v1/startup-capture.log` 均明确显示
`enable_prefix_caching=False`。这比脚本参数缺省更直接。graph 启动快照
SHA-256 `eb5ca836c6e3b3024375818c67b1b2760f084311923d3fc0fa72f4ca64cebdd6`。
安装的 vLLM `engine/arg_utils.py` 提供 `--enable-prefix-caching` 开关。

项目规则要求架构、环境、适配、执行模式、sanity、精度等非性能工作开启
服务端前缀缓存；只允许正式性能和 profiling 专用服务通过
`--no-enable-prefix-caching` 明确关闭。因此原 eager/graph 请求作为定位
和功能诊断保留，不能作为符合 profile 的执行模式正式回执。原部署指纹
`9ceae54ecba53f019fec4dc466cdcfb5609d186759af1d286d4b4c01e3a73226`
所声明的开启状态与生效服务不一致；环境和适配回执已失效，必须基于新部署
身份与重新运行的证据核验，不能只刷新哈希。

## 受控修正与退出条件

本轮仅改变服务端前缀缓存开关：在独立 eager 与 graph 启动脚本中显式加入
`--enable-prefix-caching`，并分别使用新的 `04-runs/`、`05-tmp/`、`06-cache/`
路径。先读生效 EngineCore 配置确认 `True`，再复测文本、视觉和图捕获；
若配置仍为 `False` 或出现新的正确性/资源问题，不得标记执行模式通过。
已有图 full→decode-full 的 GDN 限制须在开启缓存的新实例重新确认。

2026-09-29，新的 eager 脚本
`01-environment/start-eager-tp2-sdpa-data-product-v3-cache-on.sh`
SHA-256 为 `cf26fb18eb1b23f4b9f18960032810817bb086783ca21f56281e5dd829a8b3fc`。
EngineCore PID `896503` 的生效日志确认 `enable_prefix_caching=True`，
API PID `895730` 的实际命令包含 `--enable-prefix-caching`，`/health` 为 200。
进程完整退出后的启动及请求日志为
`04-runs/eager-tp2-sdpa-data-product-v3/service.log`，SHA-256
`052c88092e271a9e6e1cf130859470cd70bc8acc2ae02326af165ed28aa79b1c`。
在 `04-runs/eager-tp2-sdpa-data-product-v3/` 下重新执行的文本、红图、蓝图
请求分别回答 `42`、`红色`、`蓝色`，均为 HTTP 200、`finish_reason=stop`；
原始结果 SHA-256 依次为
`4685a05c70e3a81e318b9843d756720dff40a2be81db28b790f9df9b645f3fac`、
`1273d2e2d1002883b651e2d901b60ed56201ad20a3302c03cead872d89911c55`、
`9f5102d9ab7a578684c289492028a0418e0dedfed6b1e6709c3f55eac56311de`。
红图首次请求耗时 219.298 秒；该单个观测不构成性能分布。
为测试 graph，仅对已核实身份的本任务 API PID 发送 TERM，确认 EngineCore
和两个 worker 均退出；适配容器保持运行，随后启动独立的缓存开启 graph 服务。
graph EngineCore 生效值同样为 `True`。该实例复现双 rank 的 GDN
full→decode-full 限制，decode 捕获 4/4，文本、红/蓝单图、双图和两帧视频
最小请求全部通过；准确路径与哈希见[004](004-gdn-full-graph-limit.md)。

这是**服务配置修正**，不涉及 Plugin、vLLM 或 FlagGems 源码。正式性能阶段
仍需独立明确关闭缓存，并在性能结束后恢复上述开启配置。知识库处理状态：
`local-only`，复盘再定。
