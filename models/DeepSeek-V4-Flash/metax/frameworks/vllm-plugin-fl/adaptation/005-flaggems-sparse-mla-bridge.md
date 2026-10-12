# 005：FlagGems sparse MLA 路径错误转发 NVIDIA 扩展

## 元数据与签名

- 状态：`blocked`；2026-09-21；Host `mx-59`、容器 `deepseek`。
- 工作根：主机、容器同路径 `/public-flash/jinghao/deepseekV4`；Plugin base `fd5c727fcdb607bc4354cd11384761bb5d5ecfba`、PR ref `da62cddeb538f3d9d203e4e07cbc164e94f76869`，FlagGems-vllm `c0ffa628e945dc6b51af466d4f1a9b81df9ac4b8`，vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 基线：`04-runs/pr427-eager-tp8-20260921-19-qnorm-abi/service.log`，16:11:54 首个报错 rank6。TP8/EP、BF16 activation、INT8 权重、FP8 KV、eager，mixed 16-token kernel warmup。
- 调用链：Plugin `_forward_prefill` → default.flagos → `_reference_kwargs` → vLLM `flash_mla_sparse_fwd` → `_raise_flashmla_unavailable`。异常：`vllm._flashmla_C is not available`。

## 所有权、选择与受控验证

PR 的 FlagGems backend 实际转发 CUDA reference，未接入已安装的 FlagGems-vllm。该问题是 Plugin 后端接线缺失，不证明 FlagGems 内核数值错误。已有知识库未发现完整签名匹配。

修复候选保留 OpManager 注册和模型调用契约，只在现有 FlagGems backend 调用 FlagGems-vllm 的稀疏 MLA。后者返回三元组但不接受 `out`，adapter 校验目标 shape/dtype/device，将结果复制到调用方缓冲区并保留返回别名；不忽略 `out`，不安装 NVIDIA 扩展，不修改 vLLM 或 FlagGems-vllm。该版本会产生一次临时输出分配和复制，性能影响未测。

- 补丁：`05-tmp/pr427-flaggems-sparse-mla.patch`。
- 单测：同一 Plugin `test_deepseek_v4_ops.py`，模拟可选依赖并覆盖有/无输出缓冲区、非连续输出切片、统计量保留和调用参数。
- 设备复现：`07-bugs/sparse-mla-adapter/reproduce.py`，BF16 `[2,64,512]`、64 个 KV、动态 topk length 和 attention sink。结果 `04-runs/pr427-sparse-mla-device-20260921/output.txt`：rc=1，FlagGems-vllm `ops/flashmla_sparse.py:1178` 的 Triton 内核启动失败，Required 163840 B、Hardware limit 65536 B。未执行数值比较，不能报告数值正确。
- 回归：`04-runs/pr427-related-unit-after-sparse-mla-20260921/`：51 passed、3 skipped（worker 硬件测试 skip）；这只验证 Python 接口，不验证真实 MLA 可运行。
- 只读核对：generic sparse MLA 的两个 autotune 候选均为 BK=64、BH=64、8 warps，stages=2/4；当前 MetaX 后端未发现该算子的定制实现。现有 vendor MLA 是旧接口，缺少 V4 所需的 sink/extra cache 参数，不可直接替换。
- 下一步内核适配属于 FlagGems-vllm 依赖源码，而当前 profile 只允许编辑 Plugin，因此未修改依赖，未盲目重跑整模，待用户授权扩展边界。

## 未解决范围

Decode MLA 也仍转发 reference；upstream sparse SWA builder 的调度元数据创建依赖 NVIDIA FlashMLA。须单独核对并受控适配，不能把 prefill 单测成功当成 decode/graph 可用。没有真实请求成功，不能标记模型 functional；CUDA 和其他平台未验。经验暂留 local-only。

## 差异审查

实际审阅本轮 Plugin 两文件 unstaged adapter/test diff，`git diff --check` 通过；无广泛 fallback、无环境全局 monkey patch。可选 FlagGems-vllm 导入保持 lazy，测试用模块桩隔离。未声明全 PR 4991 行设计审查通过。已有 35 个 staged 路径包含 PR 及此前修复，HEAD 未变，未提交/推送；继承 `metax.yaml` 的 linear 黑名单保持不动。本轮 adapter 保留为尚未设备通过的候选。vLLM 和 FlagGems-vllm 工作树保持干净。扩大源代码修改范围前先处理授权和元数据桥接设计；候选退出条件为小规模设备数值验证、eager 真实请求及 graph 验证通过。
