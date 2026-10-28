# GLM-5.3-Flash-BF16 / MetaX

双机适配进行中，范围为 `mx-101`、`mx-102` 的16张C550及 `glm5.3-flash` 容器，
工作根为两机同路径 `/public-flash/jinghao/glm5.3-flash`。

已核实双机通信与算子/模型编排回归；首次TP8/PP2 eager已读取完整权重，profiling暴露的
PP公共工厂缺口正在修复复验。尚无完整服务、graph、GPQA或性能通过结论。
正式精度约定为GPQA Diamond全198题、strict-match≥88%，性能目标未冻结。

当前工作见 [vllm-plugin-fl工作区](frameworks/vllm-plugin-fl/README.md)；
[返回模型概览](../README.md)。历史PPU结果不作为本平台验收证据。
