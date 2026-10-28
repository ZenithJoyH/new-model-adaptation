# 推理环境分析

2026-10-23，已完成 PPU-01 / minicpm-jev-vllm 的实际身份、根目录映射与源码归属核验，详见[环境分析](environment-analysis.md)。

最终身份在批准工作根 `01-environment/deployment-identity.json`，指纹为 `8ce80f553f0ab4dfbfe91bfb097c68c0bb995b3594fa60ce2930c4da73c8ed10`。完整 checkpoint SHA-256 为 `6e8e43049340a9d18f711634dcc88eb5880a3cd69c852815e76d5de3aea28dcc`。当前实际安装路径及 git/dirty/未跟踪文件详见 `04-runs/source-review-final-20261023/manifest.json`；PYTHONPATH 为空，vLLM 1886 个安装文件未变，继承 Plugin diff 未变。

新容器仅 `/mnt:/mnt` 挂载；工作根 Host/容器同路径且 RW。模型权重作为外部输入只读使用。交付路径 `/opt/minicpm-jev-vllm`、实际组件 `/workspace/...` 均在容器文件系统内，见 `01-environment/delivery-files-final.json`。镜像打包及新镜像验证未执行。
