# 002：M3.1 compressed-tensors 融合投影映射

## 元数据与范围

- 状态：`hypothesis / isolated contract validated`，2026-09-29；Host `PPU-07`，容器 `minimaxM3.1`。
- 基线：Plugin detached `cafe6363c8c3de5ba4693b91643089c17b3ab87c`，vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems 尚未同步，当前 `3c6f7537d2d5d3aa680c55bbee5c70f2100c5b85`。
- 当前层级：Plugin 的 `vllm_fl/patches/minimax_m31_w8a8.py`，通过 vLLM 已有 compressed-tensors model/quant config 入口适配 metadata；尚未接入 `register_model()`，未触发生产推理。

## 现象、依据与选择

权重索引有 45,856 个 tensor/48 分片，原始名称分列文本 `q_proj/k_proj/v_proj/index_q_proj/index_k_proj`、视觉 Q/K/V、gate/up、shared/routed experts；没有预先融合的 `qkv_proj` 权重。当前模型类的 packed mapping 与 vision/text 的五路/三路区分尚未在此 checkpoint 的 W8A8 loader 验证。参考 Plugin 补丁给出五路文本、三路视觉的压缩张量映射。缺少实际加载前后对照，此问题仍是待证假设，不能把 CPU contract 当成权重成功装载。

已选用 Plugin 自有的 M3.1 W8A8 metadata helper，而非改只读 vLLM 或权重 `config.json`。已核实 Plugin editable import 指向 `/workspace/vllm-plugin-FL`，该容器只挂载 `/mnt:/mnt`，`/workspace` 产品树属于目标容器。`git apply --check` 对所选两文件通过后，以 Ansible 在现有 checkout 应用参考补丁中的 `vllm_fl/patches/minimax_m31_w8a8.py` 和 `tests/test_minimax_m31_w8a8.py`；未应用 GPTQ/W8A16 示例、公共注册入口或 FlagGems 补丁。继承的四个 `.orig` 未跟踪文件原样保留。

## 已做验证

- 在容器内运行 `python -B -m pytest -q -p no:cacheprovider tests/test_minimax_m31_w8a8.py -k 'not bridge'`，临时/缓存目录分别限定到批准根 `05-tmp/`、`06-cache/`；Ansible 回执 PPU-07 `ok=1 changed=0 failed=0 unreachable=0`。
- 结果为 **7 passed、1 deselected**；原始输出 `04-runs/metadata-tests-20260929.log`，SHA-256 `aeeab66507284318e3e755527044bcfd4766719c1673c692305246d911280b17`。被排除项是依赖尚未实施的 W8A8 MoE bridge，并非通过。
- `git diff --check` 返回 0，但新增文件尚为 untracked，不代表最终 diff 设计审查完成。

## 未完成与影响面

需要在 FlagGems 同步/算子归属确认后接入注册与 MoE 路径，实测真实 weight loader、文本/视觉路径、守卫未命中及老 M3/其他平台导入行为。当前 helper 在模型类和 compressed-tensors 方法上安装兼容 hook，最终审查必须确认适用范围不会改变未量化/GPTQ 模型、其他平台或已有 W8A8 调用方。尚未确认 PR base，不能标记可作为 PR 候选或适配完成。vLLM 源码未修改，容器和旧服务均未停止。

经验处理：`needs-validation`；尚无可推广故障签名。

## 2026-09-30 接入与剩余验证

已在 Plugin `register_model()` 的既有注册入口安装 `install_minimax_m31_w8a8_compat()` 和视觉三路映射 hook；重复调用的幂等性由聚焦测试覆盖。新 helper SHA-256 `0cf4c5a5dfec46b1c75765a34b6e9d57c790909139d1aa535ed25ff4a693d71c`，更新后的测试 SHA-256 `34ef1f287640b704d141364ff09d50eb50555cdd2e721f3f02a7ff57f065459f`。同一容器内 `tests/test_minimax_m31_w8a8.py` 与 `tests/unit_tests/quantization/test_w8a8_moe_experts.py` 合计 **18 passed**，原始日志 `04-runs/plugin-tests-20260930.log` SHA-256 `aae4bf4edf62622b80df95217fcb848a9acb23d5e57190fc061661823af3a195`。已现场重新采集 Plugin diff/未跟踪文件及四组件 revision，绑定部署指纹 `54fa39437e4336f556bc1b8cca3bc2fa7b3d3dcf85f26d85556e6ec5fb66194c`。

现有测试证明模型类元数据映射、视觉/文本作用域、非 compressed-tensors LM head 守卫和 gate 参数转发，但还不能证明真实 checkpoint 完整装载。需查看 TP16 eager 首次服务日志，确认 45,856 个索引张量的实际装载、权重 dtype/scale 和文本/视觉推理，再分别验证 graph。当前服务尚未给出正式通过回执，问题不关闭。

## 2026-09-30 真实加载与影响范围复审

当前 Plugin 注册 helper 后，TP16 BF16 引擎在 eager、FULL 首试自动降级和显式 decode-full 三轮均完成 48/48 shard 加载，真实聊天请求得到合理答案。表明当前 checkpoint 的 compressed-tensors 映射至少足以完成文本路径；尚无图片/视频请求，视觉三路仅有聚焦单元测试。`packed_modules_mapping` 目前安装在共享 MiniMax-M3 模型类上，`quant_config` 仅在 compressed-tensors 时设置 BF16 head 标记，vision `get_scheme_dict` 仅在 M3.1 五路映射与 vision `qkv_proj` 同时匹配时改用三路；未在旧 M3 checkpoint 或其他平台整模运行验证。后续评审应缩小或验证共享模型影响，不能从当前 Host 的服务成功推断全部旧模型/平台兼容。

旧 `/mnt/cpfs/models/MiniMax-M3/config.json` 现场只读核对无 `quantization_config`，而本目标为 compressed-tensors；上游 `initialize_model()` 仅在 `quant_config is not None` 时调用 `configure_quant_config()` 传递 packed mapping。因此旧 M3 的无量化配置不会走这一量化配置映射步骤；但 model loader/旧模型实推仍未验证，不能据此宣称所有共享调用方已回归。
