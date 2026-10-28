# 适配问题索引

- [001：GDN 状态索引读写 int32 地址偏移修复](001-gdn-index-int32-offset.md)：
  当前容器直接修复，12 项 eager/graph 边界回归及两个 quick 模块通过；模型服务未启动或重启。
- [002：PPU 厂商 Flash Attention 接入](002-ppu-flash-attention.md)：
  修复 vLLM 0.24 参数兼容及视觉 OOT 路由，57 项回归、6 例 OCR 通过；新增 PPU5/8015 服务，原服务保留，性能未重测。

按发生顺序维护 `NNN-short-title.md`。每条记录只描述一个问题的现象、诊断、受控对照、根因、
解决方法、验证结果和限制，不保存过程脚本或原始日志。
