# Qwen3.6-27B 模型结构与推理链路

核实日期：2026-09-23。对象为 `mx-58` 的 `qwen3.6-27B` 容器可见的
`/public-flash/models/Qwen3.6-27B`。`config.json` SHA-256 为
`69db4eb7196bc8190813231b3018ca05d8c2e3abc7b1af19d55c157af44a9d9c`，
`model.safetensors.index.json` SHA-256 为
`a8ad2c26fb707ff8c245806315b03e3b4b74595528492423af5dae0ce39b4d9b`。
索引列出 1199 个张量、15 个分片；分片总计 55,563,006,400 bytes，索引声明的
`total_size` 为 55,562,855,904 bytes。模型目录未提供可核实的 Git revision，
本轮用上述文件摘要固定快照。目录 README 声称 27B 参数；本轮没有逐张量重算。

## 结构与接口

配置的 `model_type` 为 `qwen3_5`，注册架构为 `Qwen3_5ForConditionalGeneration`。
vLLM `/workspace/vllm@bc150f50299199599673614f80d12a196f377655` 的
`vllm/model_executor/models/qwen3_5.py` 据 `text_config.layer_types` 建层：
`qwen3_5_text` 选 dense MLP，而非 35B-A3B 的 routed MoE。条件生成模型同时含视觉塔；
本轮 Flash Attention/GDN 接入先以文本链路验证，不能据此宣称图像和视频路径已通过。

文本主干 hidden size 5120、64 层，层型按三个 `linear_attention` 加一个
`full_attention` 重复 16 次，即 48 个 Gated DeltaNet 层与 16 个全注意力层。
每层 dense FFN 的 intermediate size 为 17408，词表大小 248320，embedding 与 LM head
不共享。全注意力为 24 个 Q heads、4 个 KV heads、head dim 256；RoPE 覆盖 1/4 head
维度，theta 为 10000000。配置最大位置数 262144；该声明不代表当前 MetaX 栈已验证
全长度。按项目初始启动规则，后续测试服务应先使用 `--max-model-len 50000`，
实际资源限制和可用上限仍需实测。

GDN 为 16 个 key heads、48 个 value heads，key/value head dim 均为 128，因果卷积宽度
4，SSM state 使用 FP32。prefill 必须传递变长序列的 `cu_seqlens`、`chunk_indices`、
`chunk_offsets` 并产出最终 state；decode 必须保持 `A_log`、`dt_bias`、`a`、`b` 的门控
语义和按 `ssm_state_indices` 原位更新的行为。MTP 配置为一层，但现行启动不使用
speculative decode；该路径仍属于替换算子时的兼容边界。

视觉塔配置为 27 层、hidden size 1152、16 heads、MLP 4304、patch size 16、
temporal patch size 2、spatial merge size 2，输出到文本 hidden size 5120。

## 推理链路与本轮影响

1. tokenizer/chat template 生成 token ID，经 embedding 进入 5120 维文本残差流；
   图像或视频输入还经过视觉塔和多模态合并。
2. 48 个 GDN 层执行输入投影、因果卷积、Q/K/V 与门控计算；prefill 做 chunk
   gated-delta 并保存最终 SSM state，decode 读取对应请求的 state 原位更新。
3. 16 个全注意力层执行 GQA、partial RoPE 与 paged KV cache 写读；Flash Attention
   主核的替换必须同时覆盖 prefill 与 decode/混合批次的 out、LSE 和 cache 契约。
4. 每层 dense FFN、末层归一化和 LM head 产生 logits；采样后调度器继续维护 KV、
   卷积和 GDN state。TP2 下 Q/KV heads 及 GDN heads 均能整除 2；实际数值和
   graph 行为仍需按当前容器验证。

现有 MetaX Plugin 路由和 FlagGems-vLLM 算子接口属于平台环境与适配记录，
不把 35B-A3B 的 MoE 验证外推到本模型。
