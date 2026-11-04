# DeepSeek-V4.1-Flash-W8A8-Text 结构与推理链路

日期：2026-11-03。对象是 `mx-102`、`mx-103` 的
`/public-flash/models/DeepSeek-V4.1-Flash-W8A8-Text`，不沿用旧 V4 或 NVIDIA 验收。

## 身份与证据

`config.json` SHA-256：`5d716883e320def43c473bde82030f13f3b806c4411437975e94b3a29de3c0e7`；
权重索引：`3ca46c734ab2a61daf0821d34cb48f3902f5e81769d5c8faf8c85b620f93b644`；
tokenizer：`c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b`。
批准根 `01-environment/model-identity-20261103.json` 保存配置、文件大小及48个分片头摘要，
SHA-256 `9fafc01cfb69666a188dcf872676193059be7c1807f228a4b5d72f412cb0c707`。
未对全部权重载荷做内容哈希。

参考固定为 [vLLM 43067f6](https://github.com/vllm-project/vllm/tree/43067f6df60e2eafba5797908484cc1c12e4a48b/vllm/models/deepseek_v41)。
主线 NVIDIA/AMD 代码仅作语义依据，不是本次 MetaX 0.28 通过证据。
现场既有 `DeepSeek-V4.1-Flash-W8A8-BF16/inference`、`encoding` 仅只读参考，不沿用其权重或结果。

## 架构与量化

- 架构 `DeepseekV41ForCausalLM`，类型 `deepseek_v41`，文本参数嵌套在 `text_config`。
- 主干40层、hidden size 5120、词表129280、64个query heads、latent KV头维512、RoPE维64。
- 每层384个routed experts，每token选6个，另有1个shared expert；expert intermediate size 2304。
  router 为 `sqrtsoftplus`，归一化后乘1.5，SwiGLU limit 10。
- mHC为4路residual、20次Sinkhorn。文本RMSNorm epsilon为 `1e-20`，不得替换成通常默认值。
- CSA2：0–1层SWA-only，2–19层压缩比2，20–39层压缩比1；额外3个draft层压缩比0。
  KV source为2/8/14/20，index source为2/8/14/20/24/28/32/36。
  第20层发布2048个候选block（每块8位置），后续indexer在候选池中选top-k 512。
- CED要求跨层共享KV/index及decoder窗口replay，不能当作V4普通逐层attention。
- Engram在1/14层，最大n-gram 4，8 heads、每头256维；表为INT8并带FP32 row scale。
- 保留3个DSpark/MTP层，初始目标不启用speculative decoding。

量化为动态 `w8a8_int8`：权重per-channel、activation per-token。转换清单要求 `wo_a` 加载时解量化为BF16、
Engram保持INT8+FP32 row scale；需要验证scale shape、映射及舍入，不能只映射量化名称。

48个实际分片共769,013,987,088字节，均为普通文件；manifest的历史“symlinks”措辞不描述当前文件类型。
96,085个张量按名称分组：MoE 559,307,393,024字节、Engram 200,000,882,440字节、vision 823,685,120字节、
其余8,871,704,392字节。包含scale，不能等同于逻辑参数量。

顶层、text_config、vision_config的视觉层数均为0，manifest标记 `text_only=true`。
分片仍含259个vision张量，模型卡仍写Image-Text；不能据此认定本派生配置启用图像能力。
需在加载器明确验证这些保留张量的处理。本次目标模态为文本。

## 推理链路与资源规划

消息经V4.1专用编码、tokenizer、embedding、Engram hash/lookback、mHC pre-mix、CSA2与共享缓存、
mHC post-mix、MoE、最终norm/head、采样和解码。一般HF tokenizer能读取token ID，
不代表专用消息格式和reasoning模式已经正确。

两机各8×C550 64GiB；全部分片超过单机显存，TP16是初始候选。
需另核算Engram/expert分片、复制参数、KV、激活、通信与图池，不能简单用磁盘大小除以16推断峰值显存。
最大位置1,048,576（YaRN factor16、original65536），按profile初始服务上下文为50,000。

0.28缺少V4.1注册及部分接口。后续需通过Plugin扩展点接入模型metadata、CED和C1A/C2A；
数值kernel归FlagGems-vllm，ATen自动替换归FlagGems。先验证实际容器内MCCL双机前置，
再做eager与逐级graph、sanity、正式精度/性能。尚未加载整模或完成运行验收。
