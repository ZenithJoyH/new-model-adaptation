# 003：显式开启 GDN 的 value head demo

2026-10-27，用户要求提供启用既有 GDN 优化的单样例推理 demo。范围为 PPU-01 / minicpm-jev / Torch-FL；framework.yml 当前 control.mode=agent。

计划仅新增容器内部交付文件 `/opt/minicpm-jev-transformers/demo_value_head_gdn.py`，复用同目录既有 `demo_value_head.load/score` 和已安装的 `torch_fl.compat.qwen3_5_gdn.enable_qwen3_5_gdn`。保留原图、OCR、渲染图和原生图像预处理契约；BF16、SDPA、eager，不新增计时或修改框架算子。优化未启用时拒绝继续，输出启用层数。既有模型源码、Torch-FL、权重和服务脚本不改。

已只读确认容器 ID `0ee63bbcec91264acfef52636b7a2983d53bf31ccb976c808fe827646673e069`，`/mnt:/mnt` RW，`/opt/minicpm-jev-transformers` 为容器内部路径。原 demo SHA-256 `306869a203b1b9249454529912929c7e14df3da8e3c69a28a92fe3a7a956f8e8`；新文件不存在。现有 8331 服务健康、启用 18 层 GDN；PPU3 15193/98304MiB，允许短暂额外单样例模型加载，无需停止服务。

验证计划：CLI help/语法检查；PPU3 上 s02 单样例推理，确认 18 层启用、237 tokens、prob_1 与既有优化结果约 0.9950946569 对齐；复核服务健康及既有文件哈希。运行证据置于既有远端工作根 `04-runs/gdn-demo-20261027-1/`。不执行正式精度/性能验收，不提交或推送。

验证结果：2026-10-27，新增文件逐行审查符合上述范围，SHA-256 `2823274086ff039fb32db898ebd16cf79e2264d0b48eab73682c2f32fa0927a6`。Ruff format/check、CLI help 和语法检查通过；PPU3 / BF16 / SDPA 上 s02 输出 `gdn_layers=18`、`n_tokens=237`、`prob_1=0.9950946569442749`，与既有优化结果一致。原 demo 和 server.py 哈希保持不变；8331 `/health` 仍为 ok、18 层 GDN。原生证据为工作根 `04-runs/gdn-demo-20261027-1/validation.json`、`s02.log`、`help.log`、`lint.log`、`format.log`。仅验证此单样例入口，不形成新的性能结论或完整精度结论；未执行镜像打包测试。

容器内使用 `CUDA_VISIBLE_DEVICES=3 HF_HUB_OFFLINE=1 python -B /opt/minicpm-jev-transformers/demo_value_head_gdn.py --checkpoint <权重目录> --orig-image <原图> --render-image <渲染图> --ocr-text-file <OCR文本>`；`--ocr-text` 可替代文本文件。脚本使用原 demo 的 inference_mode 打分，未改训练、权重或输入契约。

同日用户要求显式传入权重：范围仅限此新增 demo 的 `--checkpoint` 参数声明，将默认路径改为 required=True，增加参数说明；不改加载/打分逻辑。计划验证 help、缺少权重时的 argparse 拒绝行为、语法及 Ruff，并保留前次单样例结果作为此处未修改推理逻辑的历史证据。当前容器映射、control.mode 和文件哈希已复核，未发现外部改动。

参数调整已完成，最终 SHA-256 `060ee1bd05009a18b276ed0417091ad9e14b7517060e9a453ad96d460c34de33`，最终 diff 仅涉及上述参数声明。语法、Ruff check/format-check、CLI help 通过；缺少 checkpoint 时退出码 2，明确报告必填参数，不加载模型。首次 format-check 提示格式不符，按 Ruff 格式化后通过，原始日志保留。证据为工作根 `04-runs/gdn-demo-checkpoint-20261027-1/validation.json` 及同目录检查日志。本次未重复推理测试。
