# 003：PPU prefill index top-k 的 Triton autotune 编译断言

## 元数据

- 状态：`workaround-integrated-and-service-validated`；正式十题、精度和性能仍未完成。
- 首次及最后验证：2026-09-30，Host `PPU-07`，容器 `minimaxM3.1`，镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`。
- 模型：`/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；sparse `topk=16`、4 index heads、128 token block。
- 基线：Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加本任务未提交修改；FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。模式为 TP16 eager，prefix cache enabled。

## 签名与顺序

完整 48/48 权重加载、KV cache 及 eager 初始化后，第一次 HTTP completions 请求返回 500；首个 Python 异常来自 `vllm.models.minimax_m3.common.ops.index_topk.minimax_m3_index_topk` 的 prefill `_topk_index_kernel`，PPU Triton 在 `tl.static_assert(BLOCK_SIZE_K > BLOCK_SIZE_T)` 报 `CompileTimeAssertionFailure`。EngineCore/API 随后自行退出，容器仍运行，16 卡释放至约 1 MiB。原始日志 `/mnt/nfs/users/jinghao/minimaxM3.1/04-runs/eager-service-20260930.log`，SHA-256 `585c0f0537f2d93163f14caa5903218f82f8d6f40a6f88b7f37e5fb299ef8f05`。失败请求的 Ansible 回执为 HTTP 500，未写成功 JSON。

## 经验匹配与受控对照

旧 M3 的 [002 记录](../../../../../MiniMax-M3/ppu/adaptation/002-prefill-index-topk-compile-assert.md)具备相同 vLLM revision、PPU Triton 3.6、prefill 栈和断言，差别是模型、容器与 FlagGems/Plugin revision。其 `FLAGTREE_AABS=0` 只是候选解；当前容器证实 `triton.knobs.autotuning.adjust_block_size=False`，但相同最小算例仍在同一断言失败，日志 `04-runs/index-topk-aabs0-20260930.log`。默认环境同样失败，日志 `04-runs/index-topk-default-20260930.log`。故此处不能沿用旧 M3 的 AABS0 workaround。

当前 `_topk_index_kernel` autotune 有 K=2048、1024、512、256、128、64 六组候选；模型 `BLOCK_SIZE_T=16`。只将候选改成 K=128、warps=4、stages=2，`topk=6` 在默认及 AABS0 均通过，实际模型 `topk=16`、4 heads、两个前缀长度、7 个 query 的输出索引集合和无效位置填充通过：`04-runs/index-topk-fixed16-20260930.log`，SHA-256 `de901625d78edd42a8cc422b08848bbabdf3c21c80ab6bb84b7e9987b31622ff`。单靠 `early_config_prune` 在现有 autotune 磁盘缓存下仍复现断言：`04-runs/index-topk-prune-20260930.log`；因此不采用该办法。用原上游 JIT 直接按固定 K=128 启动通过：`04-runs/index-topk-proxy-20260930.log`，SHA-256 `5f1d02a79907e4ceb4de52db6bb09ee665153783f69185d4e13d34e8a90a6917`。

这些对照说明此容器的失败在 autotune 候选/缓存选择路径，固定合法配置可执行；尚未定位具体哪一组候选或编译器内部 constexpr 处理是根因。所有复现代码只在该工作根 `07-bugs/`，检查器在 `02-issues/`，原始结果在 `04-runs/`；未修改 vLLM 或 FlagGems 源码。

## Plugin 局部 workaround

在 editable Plugin 的 `vllm_fl/patches/minimax_m3.py` 增加 PPU vendor 守卫，只针对上游 MiniMax-M3 家族 prefill kernel 且 `topk=16` 调用原上游 JIT 的固定 K=128/warps=4/stages=2；其余 top-k、其他 vendor 仍走原路径。`vllm_fl/__init__.py` 在 general plugin 注册时安装，缺失预期上游 kernel 布局时显式报错。该方案不改模型语义、不引入复制的上游 kernel，也不依赖 autotune 磁盘缓存；退出条件是上游 PPU Triton 修复并在本模型相同 TP16 eager/full graph、数值及性能路径重验。

Plugin 聚焦守卫测试 `tests/unit_tests/dispatch/test_minimax_m3_topk_compat.py` 为 3 passed，日志 `04-runs/topk-plugin-tests-20260930.log`，SHA-256 `04eae2e921ef8d30c4f667a5cfd0ba5bf219647868f1a6276b20f0da2e688d1e`。通过标准 general plugin loader 安装后的单卡 `topk=16` 输出通过，`04-runs/index-topk-general-plugin-20260930.log`，SHA-256 `50cc1940ef6791332f9003fc52df6ddae03f00d5a5693b9c4e3bb7a92a2e3449`。无 general plugin loader 的过程脚本只激活 platform plugin，补丁未装载，断言失败；已另用标准装载复核，不将此视为产品缺陷。

## 待验证

- 重启同参数 TP16 eager 服务并复测首个真实请求；若出现下一故障，按首个 rank/组件另立或续记问题，不掩盖。
- full graph 优先测试、decode-full 降级证据（若必要）、sanity/精度/性能及最终 launcher 均待正式验收。
- 该固定配置的长序列性能影响尚未测量。经验保留 `local-only`，不得推断其他 PPU Triton revision 或平台适用。
- 最终设计审查需复核 Plugin HEAD/dirty、正式 PR base、全部 diff、共享 MiniMax-M3 调用、graph replay 和失败退出条件。
