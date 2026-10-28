# 当前服务：8001 Graph 已恢复（2026-10-23）

H100-149 / `minicpm-ocr-vllm-native-allgpu` / GPU2，API `http://127.0.0.1:8001/v1`，模型 `MiniCPM-OCR-native`。使用 FULL_AND_PIECEWISE + `--gdn-prefill-backend triton` 规避持续 OCR 停滞，保留 64/0.55/262144。根级和 native 启动脚本已更新，根脚本实际重启及文本、图像、视频、64 路并发 256 项复验通过。8000 未重启。

全量 1651 页/30594 请求零失败，Overall **96.45848131**，较 eager 提高 **0.06621131** 个百分点。该配置规避未修改 FlashInfer 内核；完整框架验收与性能目标仍未完成，不标 optimized。详见[Graph 回归与当前启动脚本](acceptance/graph-triton-8001-20261023.md)。以下均为历史部署记录。

# 历史容器调整：全部GPU及/public（2026-10-21）

使用minicpm-ocr-vllm-native-allgpu，已验证完整/public挂载与8张H100的CUDA/PyTorch可见性，保留原生vLLM适配源码和内部交付文件。旧minicpm-ocr-vllm-native保持运行。原生模型服务在此次检查前已不运行，原根脚本与模型路径已有外部改动，新容器未自动启动服务。以下服务交付结果为原部署历史，不能当作当前服务就绪证明。详见[005](adaptation/005-allgpu-public-mount.md)。

# MiniCPM-OCR / NVIDIA / 原生 vLLM

2026-10-20 已在 H100-149 的 `minicpm-ocr-vllm-native` 容器交付可用服务。基于指定 vLLM 0.24.0 CU129 镜像，直接修改实际安装的 vLLM；同机其他服务未停止，适配容器持续运行。

149 本机 API：`http://127.0.0.1:8010/v1`，模型名 `MiniCPM-OCR`。GPU 0、TP1、BF16，262144 token、最多 64 序列。本次64路客户端并发的128项OCR全部匹配参考，采样running峰值59。另验证262143输入+1输出正常返回，超限被正确拒绝；这是容量验证，长上下文质量及满长并发尚未验证。最终模式 FULL_AND_PIECEWISE，正常前缀缓存开启。文本/图像/多图/小图选项、4x/16x 混合批处理和视频验证通过；七组参考请求的文本、输入 token 数与生成 token ID 完全一致。

Host/容器工作根：`/public/flagos/jinghao/MiniCPM-OCR`。根级 `start-model.sh` 保留已有人工改动（8000端口、MiniCPM-OCR-native、nohup及日志），仅更新长度，SHA-256 `c95d796ed95f738837540b8a669bb0a6f0eb261c4ff455c69c9ce2166d4ec9ca`。容器内 `/opt/minicpm-ocr/start-model.sh` 与持久交付副本实际用于8010服务，SHA-256 `257f68ae6b0bb2b2ae1fcbeff6cc794020313c747cb07153023387003240594b`，已实际启动复验。两份脚本现不相同；8000脚本未做实际就绪验证。补丁、配置、依赖锁和恢复说明位于内部交付目录，持久副本在工作根 `01-environment/delivery/`。

FULL 尝试因 GDN 后端能力声明自动降档，已保留失败与诊断后显式验证下一档；不宣称 FULL 通过。用户选择正式精度与性能另安排；完整 v2 execution-mode 计数/数值测量回执也未生成，因此框架按已绑定原生证据保留 environment_ready，不标完整验收或 optimized。镜像尚未打包，新镜像验证 pending。

- [架构与推理链](../../../architecture-and-inference.md)
- [环境与修改边界](environment/README.md)
- [适配问题与源码审查](adaptation/README.md)
- [验证、启动脚本及限制](acceptance/README.md)
