# 当前修复环境与边界

2026-10-23，仅操作 `PPU-01` / `minicpm-ocr`。容器 ID
`7bad43aab32e6386c34c9e46ec602ab4df955b0198997503886043bed055c6c3`，保持运行。
Host/容器批准根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR`，真实 `/mnt:/mnt`
RW bind，根目录 device:inode 同为 `41:5457325353`。
实际 `/workspace/FlagGems` 位于容器文件系统，没有 PYTHONPATH 导入覆盖。

服务入口使用 `/usr/local/bin/python3.12`；FlagGems 5.5.0.dev0+g367d19367 为
editable 安装，实际导入 `/workspace/FlagGems/src/flag_gems/__init__.py`。
Torch 2.10.0、FlagTree 0.7.0+ppu3.6，PPU-ZW810E、驱动 2.1.1-rbd225。

| 组件 | 起始 HEAD / 状态 | 本轮范围 |
| --- | --- | --- |
| FlagGems | `367d19367880eaf8843449abe11db4cfb7d47e03`，干净 | 两个实际安装算子文件及两个现有测试模块 |
| Plugin | `06014201f8ea8cd7092a56a945d8fc7998c5a46c`，已有差异 | 只读并保留差异 |
| vLLM | `ee0da84ab9e04ac7610e28580af62c365e898389`，干净，安装包 0.24.0+empty | checkout 和安装目录只读 |

读取 FlagGems CONTRIBUTING、当前实现和现有 pytest 入口后，对已冻结版本实施局部修复；
不升级依赖、切换版本或改服务配置。仅使用空闲物理 PPU0 做独立测试。
起始服务已退出，本轮没有启动、重启模型服务或停止其他进程。

起始源码/包身份见批准根 `04-runs/ocr-index-fix-20261023/baseline.json`，
最终不变项与真实导入见同目录 `final-verification.json`。本记录不是完整模型环境验收回执。
