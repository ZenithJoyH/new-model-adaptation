# 002：MetaX hash top-k 输出无效导致 MoE align 越界

## 元数据

- 状态：`resolved`（已越过该启动故障，整模未完成）
- 最后验证：2026-09-21；Host `mx-59`，容器 `deepseek`，MetaX C550 x8。
- 模型：`/public-flash/models/DeepSeek-V4-Flash-Quant-W-INT8-PerChannel-A-INT8-PerToken`。
- Framework：`vllm-plugin-fl`；Plugin `fd5c727f` 加 PR427 `da62cdde` 与本任务未提交修复；FlagGems `711cf839`、FlagGems-vllm `c0ffa628`、vLLM `ee0da84a`。
- 工作根：宿主和容器均为 `/public-flash/jinghao/deepseekV4`，已验证 `/public-flash` 同路径绑定。

## 问题现象

eager TP8/EP8 在 profile 阶段报 cooperative launch/非法地址；run14 最早设备错误指向
`moe_align_block_size_stage1`，`Xnack Error/ATU Fault(0x8)`。
run15 的临时诊断显示第一个 MoE 调用收到 `(16,6)` int32 专家编号，包含负数和十亿级值，
而合法范围为 0—255。模型 hash 表本身合法，token0 的期望编号为 `[254,222,245,200,53,35]`。

## 已有经验匹配与诊断

仓库未找到相同 hash-topk 签名条目。不能依据最终 RPC 失败归类为分布式超时。
合法编号下的 FlagGems-vllm W8A8 MoE 单卡 16/1024/8192 token、TP8 并发及每 rank 64 次调用均通过；
排除了已测试有效输入下的 align kernel 故障。上游 router 调用 `vllm._custom_ops.topk_hash_softplus_sqrt`，
当前 MetaX 栈没有有效填充输出。精确归因到 mcoplib 哪个内部实现尚需独立原调用复现。

## 受控尝试与解决方法

Plugin worker 在 local device 初始化后，仅对 MetaX 安装 custom-op 桥接，复用 `CachedOp("topk_softplus_sqrt")`、
OpManager 注册和 FlagGems-vllm 实现。保留 op 黑名单策略、重复安装幂等性和可选依赖延迟导入。
相关代码位于 Plugin `dispatch/backends/vendor/metax/patches/topk_softplus_sqrt.py`、FlagGems backend 注册以及 worker 加载入口。
其他厂商 worker 不安装该桥接。未修改 vLLM 或 FlagGems 源码。

## 验证结果与证据

- 原始诊断：工作根 `04-runs/pr427-eager-tp8-20260921-15-moe-route-sync/service.log`。
- 单卡真实 custom-op→OpManager→FlagGems-vllm：`07-bugs/metax-hash-topk-dispatch/reproduce.py`；结果
  `04-runs/pr427-metax-hash-topk-dispatch-20260921/output.txt` 为 PASS，专家编号和 token-expert 索引完全一致，最大权重误差 `1.1920928955078125e-07`。
- 相关单测：`04-runs/pr427-related-unit-after-hash-topk-20260921/`，49 passed、3 skipped。
- run16、17 中八个 rank 都选择 `default.flagos`，完整 forward 到达 hc_head，原 align 越界消失；之后遇到问题 003。
- 临时 route 打印补丁已精确反向撤回；只有生产修复和测试保留。继承的 `metax.yaml` 改动保持未暂存。

## 限制、审查与经验沉淀

变更仅在当前 MetaX 硬件验证，graph 和真实请求尚未通过；性能未知。
退出条件为当前扩展提供经回归验证的原生 hash top-k 后再评估是否移除桥接。
设计需继续审查 vendor patches 包导入副作用及缺失 FlagGems-vllm 时的报错契约。
知识库状态 `local-only`，尚不推广为跨平台结论。
