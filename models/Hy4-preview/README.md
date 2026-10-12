# Hy4-preview

PPU-07 历史服务的 strict 90.91% 精度由用户按 87% 业务阈值接受；原生通过回执缺失，部分性能场景超时且用户已停止继续测试。新版 BF16/INT8 来源分析与旧运行结果分别保留。

本页于 2026-10-12 按已有文件整理；所有运行结论均来自历史记录，本次没有重新执行模型。

## 当前导航

| 平台 | 记录入口 | 已记录 Host | 状态口径 |
| --- | --- | --- | --- |
| ppu | [legacy 平台记录](ppu/README.md) | PPU-07 | functional |

[架构与推理链路](architecture-and-inference.md) · [跨平台资料](_shared/README.md) · [整理说明与人工接续](_shared/local-record-maintenance.md)

模型来源与身份仍以原 `model.yml` 及具体记录为准；其早期登记状态不替代平台/框架阶段证据。历史文档中的 Host、PID、容器与日期不代表当前现场状态。

## 整理前概览（原文保留）

以下原文保留当时的范围和结论；最新目录入口及 v2 状态口径见上方。

核对日期：2026-08-28。来源为 [Tencent-Hunyuan/Hy4-preview](https://www.modelscope.cn/models/Tencent-Hunyuan/Hy4-preview/files)，本次固定仓库 revision 为 `ada7b1faf9b70585edc90a9ef552d0059fb246e7`。本目录与旧 `Hy4-preview-Testing-W8A8-attn-moe` 分开，避免混用权重来源和历史验收结果。

## 模型分析结论

- **主体结构未变**：78 层，hidden size 6,144；首层 dense、其余 77 层 MoE；256 routed experts、top-8、1 shared expert；gated sparse MLA、4-stream IHC、1 层 MTP。新版明确增加 `use_dsa=true`、`use_mla=true`。
- **参数规模未缩小**：全部 131 个 Safetensors 分片头合计 779,960,992,733 个参数元素，与旧 INT8 权重扣除 scale 后的元素数一致。官方“770B”是主模型口径，另有约 10B MTP。
- **源权重布局不同于旧 INT8 产物**：新版 2,006 个张量，专家按 `[256,4096,6144]` gate/up 和 `[256,6144,2048]` down 打包；旧 INT8 为逐专家权重和 scale。新版无 `quantization_config`，还不是可直接使用的 INT8 checkpoint。
- **不是所有张量都为 BF16**：1,380 个 BF16、626 个 F32 张量，完整分片约 1.560 TB / 1,452.85 GiB。IHC、主模型 sink 和路由 correction bias 等保留 F32。
- **分词内容一致，模板有变化**：新旧 tokenizer 的全部顶层 JSON 字段规范化后哈希相同；新版类名为 `TokenizersBackend`，模板只接受 `high` / `no_think`，取消 `low`。
- **不能直接继承旧版精度结论**：新版仍声明 `swiglu_limit=10`；是否执行截断必须对照新版官方实现或 BF16 输出确认。相同结构和元素数不代表相同权重值。

## 文档与证据

- [完整架构、推理链路与算子清单](architecture-and-inference.md)
- [固定版本与跨平台参考资料分析](_shared/README.md)
- [PPU 容器适配可复用性与风险](ppu/README.md)

当前仅完成静态分析及既有容器只读核对。未下载权重主体、未量化、未修改或重启服务，未验证新版 INT8 推理。其他平台没有开展分析或适配。
