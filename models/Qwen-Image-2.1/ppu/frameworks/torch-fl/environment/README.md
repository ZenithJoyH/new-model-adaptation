# 推理环境分析

最后核实时间：2026-09-22（Asia/Shanghai）。

- Host：`PPU-07`，T-Head PPU-ZW810E，Driver `2.1.1-rbd225`。
- 容器：`qwen-image-flagos`，镜像 `qwen-image-flagos:from-qwen-image-20260920`，image ID `sha256:f6456946e47200146d498ff19e884f55cee2c07c4c58eb4480063ed80769f907`。
- 远程工作根：Host 和容器内均为 `/mnt/nfs/users/jinghao/qwen-image`；`docker inspect` 已核实 `/mnt => /mnt`。
- 可写产品源码：`/workspace/PyTorch-Plugin-FL`，分支 `fix/qwen-image-21-ppu-followups`，基线 `7298bfbd14c604f260bd84052dd1d8b2dd7ddc82`，容器内 HEAD `30ff88f431b80fa20fca0476ea7094f0470948af`；相同 tree 的首个发布 commit 为 `da75e80519509ad52f05c03c330901badd590912`，PR 当前 HEAD `a3e6031e2c29fe1c583921e40360a0e390d9589d` 另含重复 manifest 键删除和 Ruff 格式修正。
- 安装身份：`torch-fl 0.1.0+ppu` 从上述源码树导入；`torch 2.10.0+cpu`。
- 导入 `torch_fl` 后，加载的 PPU libtorch 报告 CUDA ABI `13.0`，`torch.flagos.is_available()` 为 `True`。
- 执行协议为 Python API，主模式为 eager；本 profile 为 experimental。
- 部署指纹 `fb643e377b3220d634328c076e1b7d7c86282db2bd24003f679393a43f3f6237` 由已核实的模型 `Qwen-Image-2.1`、权重路径 `/mnt/cpfs/models/Qwen-Image-2.1`、Host/镜像 digest、Torch/Torch-FL revision、Driver、eager 模式和 single-PPU 拓扑的规范化字符串计算。
- 只允许修改 Torch-FL 源码。PPU vendor libtorch、CPU PyTorch、SDK/Driver、Diffusers 实现和模型权重均按只读依赖处理。
- `torch_fl/lib_ppu/` 中的本机 `.so` 只用于当前容器运行，未跟踪、未进入提交或 PR。
