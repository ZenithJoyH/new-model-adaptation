# 001：MiniCPM-V 4.7 注册与 canvas M-RoPE 接口差距

## 元数据

- 状态：功能修复已验证；正式数值/精度回归待完成
- 首次出现/最后验证：2026-09-28
- 模型：`/data/models/MiniCPM-V-4.7/weights/1b`
- 平台、Host、容器：NVIDIA H100 × 8，`H100-149`，`MinicpmV4.7-1B-native`
- vLLM：wheel `0.24.0+cu129`，`_version.py` 仅给短 commit `gee0da84ab`；无 Git checkout
- 执行模式与负载：eager 及显式 `FULL_DECODE_ONLY`，单卡 TP1，文本/单图/双图/视频和十并发

## 现象及证据

`config.json` 的 architectures 为 `MiniCPMV4_7ForConditionalGeneration`、
`model_type=minicpmv4_7`、`mrope_mode=canvas`，配置 SHA-256 为
`0d2f763cf97a0a5beec8f52b13b4cbf7262680df6fd35e1f0e48c09288c4bb12`。
实际导入的 vLLM registry 仅有 `MiniCPMV4_6ForConditionalGeneration`，没有 4.7。
4.6 adapter 的 `get_mrope_input_positions` 明确使用三个通道相同的顺序位置，
而 4.7 参考实现的 processor 构造 `image_bounds`、`target_sizes_mrope`；
模型 prefill 用 `compute_canvas_rope_index` 生成空间位置、decode 延续 `rope_deltas`。
参考模型源码 SHA-256 为
`398ec5cf6a8b31d136fbcaf3671c1be2bc25d3ffc77aa457feec185d26999bd2`；
现有 vLLM 4.6 adapter SHA-256 为
`fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`。
未注册导致直接架构解析不支持；借 4.6 架构别名虽然能加载权重，但不能验证 4.7
canvas 位置语义，因此它只作加载基线，不作为正确性基线。

## 已有经验匹配

仓库的其他 NVIDIA 原生适配曾在 wheel 安装中直接修改代码，但模型结构、revision 和
源码管理条件不同；不能用作本任务的源码授权或 M-RoPE 解决方案。知识库 TP timeout、
Plugin fullgraph 条目均没有本任务的失败签名，当前不复用。

## 设计假设与待验证接口

`vllm/model_executor/models/registry.py` 是架构分派点；4.6 adapter 的视觉塔、
Qwen3.5 主干、权重前缀映射、图像/视频处理接口与 1B checkpoint 对齐。
模型专属 `minicpmv4_7.py` 继承这些可复用组件，单独注册 4.7 ProcessingInfo
及 MultiModalProcessor，版本返回 `(4, 7)`。其 `SupportsMRoPE` 实现从
`MultiModalFeatureSpec` 提取视觉 patch grid，按 prompt 顺序与图像边界配对，
读取 checkpoint 自带且已核实 SHA 的 `mrope_minicpmv4_7.py` 计算三通道位置和
decode delta。尺寸数量不一致即报错，不静默退化为 4.6 顺序位置。
替代方案是复制 600 行 canvas helper 到 wheel，增加维护分叉；或只注册 4.6 别名，
会保留错误位置语义，故均未采用。

用户明确允许直接修改已安装 wheel；容器无 Git 源树。应用前核对导入路径、
registry 和 4.6 文件哈希、目标文件不存在；原 registry 保存在
`02-issues/registry.before.minicpmv4_7.py`。工作根的 `02-issues/install_minicpmv47.py`
在原哈希不符或目标已存在时拒绝写入。修改只涉及 registry 增加四行和一个
89 行模型适配器。权重、processor 参考实现及 4.6 文件只读。

## 验证计划

1. 4.6 别名基线在 `04-runs/baseline-46-alias-driver-20260928/` 成功加载真实权重，
   但只验证了兼容层可加载，未验证 canvas 语义。
2. 新适配器在 `04-runs/native-eager-20260928/` 由正式 4.7 架构解析并加载相同
   权重；文本答 42、红图答 Red，视频识别 red/blue。视频首次 96-token 回复截断，
   保留在原始结果中，不当作完整正确性通过。
3. 显式 `FULL_DECODE_ONLY` 的 `04-runs/native-decode-full-20260928/` 捕获 51
   个 decode 全图，十并发变长文本、红/蓝图、双图、视频均 HTTP 200、
   `finish_reason=stop`，预期关键词全部命中。此为小样本功能和回放验证，
   不代替冻结的正式准确率阈值。
4. `vllm.model_executor.models.ModelRegistry.get_supported_archs()` 保持 4.6
   与 4.7 可解析，未知 4.8 不被误注册。4.6 adapter 哈希仍是
   `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`。

## 当前结论

功能适配已验证；模型数值与参考实现逐 token 对照、正式准确率及性能尚未完成。
实际 diff：原 registry SHA
`ab52495073a046b79d00a314cbc96e719e3ed916ea8a8bf6f3202015062b5676`
→ `58ea925cd79c7771b35455d48c5d991928fd019539d8e0e61e100af541d55d43`；
新 adapter SHA `e1bddd8ee92576ff8260ef8e5362a8a7fb7d47c3f4f70584e63944695c2cf86d`。
审查确认 registry 仅添 4.7 映射，不改共享执行热路径；作用域为本容器的
1B 模型。无 Git HEAD、PR base、dirty/untracked 可供审查；本轮未提交或建 PR。
回退须在停掉本任务服务后核对上述新文件哈希，再以备份恢复 registry、移除新 adapter；
涉及删除时需按仓库规则单独确认。知识库处理为 `needs-validation`，暂不提升。
