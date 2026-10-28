# Pooling 满上下文少调度最后一个 token

2026-10-23，PPU-01 / minicpm-jev-vllm / vLLM 0.24.0+empty / `/opt/vllm-plugin-FL` 源码安装。用户脚本 max_model_len 默认 262144、max-num-seqs=64、LAST classify、PIECEWISE/eager backend。

双图 32768/131072 token 正常，精确 262144-token 请求在 1800 秒后超时；不是通过 health=200 可以排除的问题。只读堆栈显示 EngineCore 停在原生 `core.py::_process_engine_step` 的“未执行模型但仍有请求”循环。当前原生 Scheduler 为非 diffusion 一律设置 `num_sampled_tokens_per_step=1`，运行请求预算扣除该数；pooling 不生成 token，却也被截在 max_model_len-1。原生调度器小上下文负对照直接复现 64-token 请求只能调度 63 token。

修复位于 Plugin 既有 scheduler_cls 扩展。`vllm_fl/platform.py::_configure_pooling_scheduler` 仅在 runner=pooling、同步调度、未指定自定义 scheduler 时选择 `vllm_fl.worker.pooling_scheduler.PoolingSchedulerFL`。子类完整继承原生调度器，只在 pooling 初始化后把 `num_sampled_tokens_per_step` 设为 0。模型长度、输入校验、KV cache 长度和用户启动脚本不变，没有扩大为 262145；不复制原生调度代码、不修改 vLLM、不按模型名称/路径分支。异步与显式自定义 scheduler 保留既有选择，生成路径保留一个输出 token 的预留。

复用已有数值/worker 回归，并新增原生 KV cache manager + Scheduler.schedule 的 63/64 边界测试（本地生成微型模型配置，不下载或加载模型权重），检查生成预留、选择守卫和幂等性。用原生 Scheduler.__init__ 作为独立负对照时，64 边界准确报 `assert 63 == 64`；正常 Plugin 代码 17 passed。初次测试夹具缺少当前版本必填 is_encoder_decoder 字段，已补齐并重测，初次失败日志保留，不能将其当作缺陷负对照。

设计审查：作用域为默认同步 pooling 的调度语义，沿用正式扩展点；没有全局替换、接口变化、SDK 新依赖、宽泛异常 fallback 或更改 graph 模式。vLLM 保持只读。对应 upstream 已把 pooling 预留设为零后可以移除此兼容选择。其他实际硬件、异步 pooling 与自定义 scheduler 的真实推理未测；守卫只做保留行为测试，不宣称这些路径已完成硬件回归。

证据相对工作根：`04-runs/opt-source-long-context-20261023-1/` 中的 `long-context-results.json`（原 262144 超时）、`engine-pyspy-stack.txt`、`native-negative-v2.log`、`fixed-tests-v2.log`、`pooling-fix-review.json` 和源码快照。修复后相同双图长度、独立冷缓存重复、超限拒绝和短样例恢复验证在其 `fixed/` 子目录：262144 两次完整消费，各约 120 秒、概率完全一致；262145 正确 HTTP 400；12 短样例最大误差仍为 0.004417300 < 0.005；最终 health 200，无 OOM。完整摘要见 [003 源码安装与容量验证](../environment/003-opt-source-installation.md)。

本次新增 diff 仅为 platform 的选择辅助函数及调用、新 pooling scheduler 子类和一个测试文件，位于实际安装的 `/opt` checkout；其余继承修改保留。最终源码、完整 tracked diff、untracked 状态与文件哈希在 `fixed/` 保存。当前设计审查可作为声明范围内的 PR 候选，未提交或推送；其他物理平台和完整正式验收仍未完成。
