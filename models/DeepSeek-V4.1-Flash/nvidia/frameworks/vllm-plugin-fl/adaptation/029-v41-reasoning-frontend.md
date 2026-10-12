# 029：V4.1 思考强度与输出解析不一致

## 元数据

- 状态：`root-cause-fix`（前端局部；整模语义问题见 028）
- 首次出现／最后验证：2026-09-24
- 模型：`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`
- 平台与 Host：NVIDIA H100 × 8，`H100-149`
- 容器与镜像：`deepseek-v41-plugin-adapt-20260923`，`deepseek-v41-plugin-fl:h100145-20260923-r1`
- Plugin / FlagGems / FlagGems-vllm / vLLM HEAD：`fd5c727fcdb607bc4354cd11384761bb5d5ecfba` / `7cd137ccaf09f25ce3012ba86438682072a69bc9` / `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741` / `ee0da84ab9e04ac7610e28580af62c365e898389`
- 模式：TP8 eager、FP8 KV、前缀缓存启用，短消息 `reasoning_effort=high`。

## 问题现象

Plugin 512-token 服务的四个 high 推理请求在 200 个生成 token 处均以 `length` 结束，API 的 `content` 包含思考文本而 `reasoning_content` 缺失；原始回执在 `H100-149:/public/flagos/jinghao/deepseekV4.1/04-runs/h100149-fullcoverage-512-20260924/effort-high-probe/`。启动日志明确 `reasoning_parser=''`。另将 Plugin 提示编码与只读模型资料 `encoding/encoding.py` 比较，发现 Plugin 的 `low=25/high=50` 与资料 `low=50/high=75` 不同。两者不能解释 `reasoning_effort=none` 的短上下文失真；该失真仍由问题 028 跟踪。

## 已有经验匹配

已检索本模型问题 005、012、024、025、026–028 与 `docs/troubleshooting/`；没有与 V4.1 前端思考强度及解析缺失完全匹配的条目。锁定 vLLM 自带 V3/R1 思考解析接口，但其 V3 默认 `thinking=False`，与 V4.1 tokenizer 默认开启思考不同。

## 诊断与受控尝试

1. 模型资料的编码参考规定 `low=50/high=75/max=100`。Plugin 仅修正 `low/high`，保留向后兼容的 `xhigh=75`。对相同 system/user 文本，Plugin 与模型资料在非思考及 high 思考模式的完整提示字符串一致；`git diff --check` 通过。
2. 锁定 vLLM 的 `ReasoningParserManager` 支持惰性注册。Plugin 新增 V4.1 小型适配器，沿用锁定 vLLM 的 V3/R1 解析器，默认思考，`reasoning_effort=none` 或显式 `thinking=False` 时为非思考；仅在原版尚无 V4.1 parser 名称时注册，不覆盖既有实现。
3. 定向测试 `tests/models/deepseek_v4_1/test_reasoning_parser.py` 在容器内 `python3 -m pytest -q -p no:cacheprovider ...` 两例通过，覆盖默认/high 与 none/显式禁用，以及 `</think>` 后的正文提取。另直接调用 `_register_deepseek_v41_frontend()`，`ReasoningParserManager.get_reasoning_parser('deepseek_v41')` 返回 Plugin 新类。远端过程用单 Host Ansible staged 到 `05-tmp/h100149-v41-parser-stage/` 再写入已核实的 editable Plugin；未修改锁定 vLLM 或 FlagGems。部署用单文件副本保留在已批准的临时根，供复核。

## 实现边界与验证

- Plugin 源码：`/vllm-workspace/vllm-plugin-FL/vllm_fl/tokenizers/deepseek_v41_encoding.py`、`vllm_fl/tokenizers/deepseek_v41_reasoning_parser.py`、`vllm_fl/__init__.py`；定向测试同树 `tests/models/deepseek_v4_1/test_reasoning_parser.py`。
- 服务需显式使用 `--reasoning-parser deepseek_v41` 才能验证 API 的 `reasoning_content`。当前 Plugin 512-token 旧服务已停止，同机 NV-native 对照服务在加载；尚无新 Plugin 服务整模解析回执。因此局部测试通过不等于正式精度或整模适配完成。
- 旧模型和已有 parser 的注册守卫保持不变；当前变更未触及算子，FlagGems 优先级规则不适用。
- graph capture/replay、工具调用、流式 API 和多模态解析尚未整模验证。
- 知识库处理状态：`local-only`；此处是 V4.1 专属前端合同，不推广至其他模型。
