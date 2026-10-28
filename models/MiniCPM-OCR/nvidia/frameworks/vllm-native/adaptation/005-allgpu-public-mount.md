# 005：全部GPU与完整/public挂载

2026-10-21，用户要求为149原生容器接入全部显卡，并将主机整个/public目录挂载进容器。仅操作H100-149；写入仍限定/public/flagos/jinghao/MiniCPM-OCR。Docker update没有GPU或bind mount追加接口，主机未安装可用nvidia-container-runtime二进制，因此延用显式设备透传；不修改主机Docker配置、不热改cgroup或运行时元数据。

检查时旧容器minicpm-ocr-vllm-native（917cfd5ed14be7e4ee321d7c8db7810e93178cd4c46eadf8025457697bfdf8af）已被外部重启，容器内无运行中的模型服务，8000/8010均不通。原工作根start-model.sh和MiniCPM-OCR-1.0目录已不在原位置，目录结构已有人工整理；没有覆盖或恢复这些改动。容器内部/opt/minicpm-ocr及九个vLLM适配文件仍在，九文件哈希与上轮一致。

对当前旧容器执行不暂停快照，基于镜像minicpm-ocr-vllm-native:allgpu-public-snapshot-20261021创建新容器minicpm-ocr-vllm-native-allgpu。image ID sha256:1fc45195d4aead204a2585a5f621db39c2ff4388cd58d4b052807b566a240077；新container ID 0c40733804a719e8d3ea9259cd21fe092eb8f650137305aae3aec602d658aa9b。旧容器继续运行且未删除、改名或重启，未停止其他服务。

新容器/public为主机/public的RW bind，设备号/inode双方45:259；原批准工作根双方仍45:225185087240。仅挂载目录不扩展Agent在其他/public路径的写入权限。GPU0–7、nvidiactl、nvidia-uvm和nvidia-uvm-tools显式rwm透传；只读保留nvidia-smi、libcuda、libnvidia-ml挂载，host network/IPC与旧环境相同，不增加privileged权限。新容器PID1为sleep infinity，未自动启动模型或改成TP8。

验证：nvidia-smi -L列出8张H100，CUDA Driver cuDeviceGetCount与torch.cuda.device_count均为8。九个已适配vLLM文件、/opt/minicpm-ocr全部文件哈希及vLLM/Torch/Transformers版本与旧容器完全一致。未在其他GPU分配模型或运行负载。新部署指纹777e1de98391c1bd86859b1c88b865c4d183ce26dc09409e97ae45bfde34ce02。

证据保留在批准工作根01-environment/allgpu-public-20261021/：before.json、identity-probe.py、plan.json、snapshot-result.json、create-argv.json、create-result.json、verification.json、deployment-identity.json。快照不包含/public bind内容；仅验证资源和源码保留，未验证新容器模型服务，旧服务精度/容量结果保留为历史。后续如需恢复服务，必须核实人工整理后的模型和脚本位置，重新绑定和验证。
