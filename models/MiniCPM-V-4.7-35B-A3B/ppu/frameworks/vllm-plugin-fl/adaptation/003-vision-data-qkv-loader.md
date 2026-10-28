# 003：视觉 data 模式的 fused QKV 权重加载失败

## 元数据与签名

- 状态：`mitigated`；首次出现、最后验证：2026-09-28。
- 模型：`MiniCPM-V-4.7-35B-A3B`；Host `PPU-13`；容器 `minicpmV4.7-35B`，
  镜像 `sha256:52536a088a055b2c24cdfca21d0ea9e8d68c1f5f82fee7a40f7ec8f72e4a`。
- Plugin 基准 HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`，
  vLLM HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`；
  FlagGems checkout `1a38df24f72ca5a4a6a24650b5d66356709750ba` 未同步。
- eager、TP2、PPU 0/1、50,000 token 上限；前缀缓存当时未显式设置，
  后查明生效值为关闭，见[005](005-prefix-cache-effective-default.md)；视觉后端
  `TORCH_SDPA`，视觉 TP 模式由默认 `weights` 改为 `data`。
- 原始日志：`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/04-runs/eager-tp2-sdpa-data-v1/service.log`。
  两个 Worker 均在 17 个 shard 完成加载后报
  `KeyError: 'encoder.layers.0.self_attn.k_proj.bias'`，API 未就绪。

## 已有经验及诊断

检索 `docs/troubleshooting/` 和同权重 NVIDIA 历史问题，未发现匹配此
`Idefics2VisionTransformer` data 模式加载签名的已验证条目。
只读核对 vLLM `idefics2_vision_model.py`：构造器在 data 模式仍建立
`QKVParallelLinear(..., disable_tp=True)` 的 fused `qkv_proj`；`load_weights`
却用 `or self.use_data_parallel` 跳过 `q_proj/k_proj/v_proj` 到 fused 参数的
映射，随后从 `params_dict` 查找不存在的独立 `k_proj`。上述异常与分支
直接对应，属于加载逻辑不一致；未修改 vLLM 源码。

## 受控尝试与修正

| 轮次 | 唯一变量 | 结果 |
| --- | --- | --- |
| 1 | 从健康的 eager TP2/SDPA 服务仅改 `--mm-encoder-tp-mode data` | 加载报上述 `KeyError`；失败证据保留在 `eager-tp2-sdpa-data-v1/`。 |
| 2 | 在 4.7 Plugin 适配层，仅在 `load_weights` 时临时把视觉塔 `use_data_parallel` 设为 `False`，`finally` 恢复原值 | 两个 Worker 均加载全部 17 个 shard，`/health` 返回 200；`eager-tp2-sdpa-data-v2/` 红图仍产生连续 `!`，视觉正确性未通过。 |

选用模型专属 `MiniCPMV4_7ForConditionalGeneration.load_weights` 扩展点，
是因为该模型复用 4.6 视觉塔，但需兼容本栈的 data 模式加载缺口。
普通 `weights` 模式保留原有 `super().load_weights` 行为；data 模式只在
加载调用的作用域修改标记，异常时也会恢复。运行时执行模式不改变。
源文件 `/workspace/vllm-plugin-FL/vllm_fl/models/minicpmv4_7.py` 从 SHA-256
`910c551d4f2694534c7f8046842781ac6a48020c5c4ce7b94c59d7a89e011b61`
变为 `db2bc92342d81f7877759e6565d5bf3a9339fa652e54526c738bb817acab206b`；
在确认 Plugin HEAD、预期两项本任务工作树改动和 12 行差异后安装。
一次性安装脚本位于批准工作根 `02-issues/install-data-loader.py`，候选单文件
位于 `05-tmp/minicpmv4_7_data_load.py`；没有复制源树。

该修正属于**加载阶段 workaround**，退出条件是 vLLM 上游修复该分支并在
本模型 TP2/data 模式验证。与 002 的独立数值修正合用后，data 模式的 eager
及 decode-full graph 文本、单图、双图和两帧视频短请求已通过；不能从加载
修正单独推断视觉正确性。
普通 `weights` 模式先前能加载且文本推理通过；新增 data 分支未覆盖 graph。
未同步或修改 FlagGems；未修改 vLLM；未停止或重启容器。

## 限制与后续

原有图像回答异常的诊断与修正见[002](002-visual-garbage.md)。当前配置继续
采用 data 模式，因此该加载分支仍需保留；若最终配置回到默认 `weights`，
应撤回此 workaround。长输入和其他模型未验证。知识库状态：`local-only`。
