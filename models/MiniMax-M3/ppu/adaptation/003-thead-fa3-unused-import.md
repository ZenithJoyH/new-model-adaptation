# 003：T-Head FA3 backend 导入引用不存在的符号

## 元数据

- 状态：`resolved`
- 首次/最后验证时间：2026-09-15
- 模型/平台：MiniMax-M3，T-Head PPU-ZW810E，Host `PPU-13`
- revisions：Plugin 基线 `29712e42dba86680577aef9f2f6b5b7f04050a89`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`

## 现象、根因与修复

首轮 fused-op 测试因 Python 包导入链进入 `thead.impl.__init__`，随后 `attention.py` 从当前 vLLM `fa_utils` 导入不存在的 `flash_attn_supports_fp8` 而失败。检索实际文件确认该名字只在 import list 中出现，后端实现从未调用它；同组其余三个符号存在。

修复分两层：MiniMax 专用 kernel 移到 `thead/` 根层，避免不相关 FA3 可选依赖急切导入；同时从 `attention.py` 删除唯一的未使用 import。没有增加 fallback 或改 attention 行为。

## 验证与限制

- `/mnt/nfs/users/jinghao/minimaxM3/04-runs/001-fused-preprocess/pytest-initial.log` 保留修复前失败。
- `/mnt/nfs/users/jinghao/minimaxM3/04-runs/thead-fa3-import.log` 显示 `TheadFlashAttentionBackend` 与 `TheadFlashAttentionImpl` 导入通过。
- 尚需整模 dense attention eager/graph 验证 FA3 runtime，而非只依据 import 宣称功能完成。
- vLLM 未修改；知识库处理状态 `local-only`。
