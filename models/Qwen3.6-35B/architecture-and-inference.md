# Qwen3.6-35B 模型结构与推理链路

核实日期：2026-09-16。当前适配对象是 `mx-104` 上容器 `qwen3.6-35B` 可见的
`/data/Qwen3.6-35B-A3B-nomtp`。`config.json` SHA256 为
`93a4693fa9d8392fbfccd4b3c9873f4bfdcb14fdede978b123d07d19675efe99`，权重索引
SHA256 为 `b585a9a37853212b6a4e34f7c352c164206a191089167dff0e1ef147289a58cf`。
21 个 safetensors 分片合计 71,903,776,768 bytes；没有复制权重，也没有逐张量重算参数量。
目录名中的 35B 总参数、3B 激活参数暂记为产物标识，不视作本次独立验证结论。模型目录未携带可确认的上游提交号，因此用配置和索引摘要固定本次快照。

## 架构与边界

配置注册架构为 `Qwen3_5MoeForConditionalGeneration`、模型类型
`qwen3_5_moe`。这是带视觉配置的条件生成模型；当前任务仅调整文本主干中的 GDN 与 routed
MoE 算子，不声明视觉、MTP、量化或全上下文能力已通过。

文本主干 hidden size 2048、40 层、词表 248320，输入 embedding 与 LM head 不共享。
层型按 `[linear_attention, linear_attention, linear_attention, full_attention]` 重复十次，
即 30 个 Gated DeltaNet 线性注意力层和 10 个全注意力层。全注意力为 16 个 query
heads、2 个 KV heads、head dim 256；RoPE 只覆盖四分之一维度，theta 10000000。
模型配置的最大位置为 262144，不能仅由该声明推导当前后端可稳定服务到这一长度。

GDN 使用 16 个 key heads、32 个 value heads，key/value head dim 均为 128，因果卷积宽度
4，SSM state 为 FP32。prefill 需要 Q/K L2 normalization、chunk gated-delta 更新和最终
state；decode 需要依据 `A_log`、`dt_bias`、`a` 和 `b` 保持原门控/衰减语义，并按调度器
提供的 SSM state index 原位更新。cu_seqlens、chunk metadata、连续性和 graph replay 地址
均属于算子接口，替换实现时不能丢失。

每个文本层含稀疏 MoE：256 个 routed experts、每 token 选择 8 个，expert intermediate
size 512；另有 intermediate size 512 的 shared expert。routed expert 的 top-k 权重、专家
排列、gate/up 激活、down projection 与加权合并必须保持现有 vLLM/Plugin 接口；LoRA 路径
需要在中间张量处注入 adapter，不能被无条件的整算子快速路径绕过。

视觉配置为 27 层、hidden size 1152、16 heads、MLP 4304，patch size 16、temporal patch
size 2、spatial merge size 2，输出 hidden size 2048。`mtp_num_hidden_layers=1`，但给定目录名
标记为 `nomtp`；本轮不启用或验证 speculative decode。

## 端到端推理链路

1. tokenizer/chat template 生成 token IDs，embedding 得到 2048 维文本表示。
2. 线性注意力层先执行输入投影和宽度 4 的因果卷积，再形成 Q/K/V、门控与衰减；prefill
   走 chunk GDN 并输出最终 FP32 state，decode 从对应请求的 state 行读取并原位更新。
3. 每第四层执行 GQA 全注意力，写入和读取 paged KV cache；partial RoPE 只作用于指定维度。
4. 每层 router 选取 8/256 routed experts，执行 fused MoE，并与 shared expert 输出合并。
5. 最后一层归一化和 LM head 生成 logits，采样器产生下一个 token；调度器同步维护 KV、卷积
   与 GDN state。

## 本轮算子接入重点

| 组件 | 当前接口约束 | FlagGems-vLLM 接入检查 |
|---|---|---|
| GDN prefill | Q/K/V、FP32 gate、beta、初始/最终 state、cu_seqlens、chunk metadata | 返回值布局、变长序列和 chunk metadata 必须与 vLLM 0.20.2 一致 |
| GDN decode | 由 `A_log/dt_bias/a/b` 生成衰减和 beta，按 state index 原位更新 | 不得跳过 FP32 sigmoid/softplus 语义或破坏 speculative token 布局 |
| Routed MoE | top-k ids/weights、专家权重、in-place/out-of-place 输出 | 只在无 LoRA 快速路径切换；LoRA 继续保留分阶段调用 |
| Graph | 固定 workspace、无设备数据 host 分支、稳定 state/cache 地址 | eager 与 graph 均需 changed-input replay |

本文件完成模型结构与调用边界分析，不代表远端算子修改或整模正确性已经验证。平台版本、工作树身份、调用链与实施结果记录在 `metax/`。
