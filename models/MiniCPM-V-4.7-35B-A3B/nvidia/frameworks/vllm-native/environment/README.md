# H100-149 NV-native 环境分析

2026-09-28 只读核实：SSH alias `H100-149` 连接到
`p-jn-sz-dell-h1-su8-gpu11-401-11o-12u-208-149`；
`./scripts/connectivity-check --limit H100-149` 成功。
8 张 NVIDIA H100 80GB HBM3，驱动 `580.105.08`、CUDA 驱动 API `13.0`。
GPU 占用需要在每次服务启动前重新确认；一次检查时 8 卡均为 0 MiB。

目标容器 `MinicpmV4.7-35B-native` 运行中，容器 ID
`d4b68bdbb6e994b8b6aa95626fcfe5409b5131a8335d6c2ae49a1898d803051e`，
镜像 `vllm/vllm-openai:v0.24.0-cu129-ubuntu2404`，image ID
`sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`。
容器使用 host network；`/public` 与 `/data` 由宿主机可写 bind mount 进入容器。
已在宿主机及容器内核实工作根同路径
`/public/flagos/jinghao/MiniCPMV4.7-35B/native`，权重同路径
`/data/models/MiniCPM-V-4.7/weights/35b-a3b`。权重保持只读。
工作根 Host/容器的设备号:inode 同为 `45:242118947849`；权重目录同为
`64768:2147497685`，不是仅凭路径字符串推断映射。
七个规定用途的过程目录在 Ansible `--check --diff` 后于单 Host 建立。

容器中 PyTorch `2.11.0+cu129`、Transformers `5.12.1`、vLLM
`0.24.0+cu129`。vLLM 由本地 wheel 安装，`import vllm` 指向
`/usr/local/lib/python3.12/dist-packages/vllm/__init__.py`；镜像内没有
editable Git 树或 `git` 命令，`_version.py` 只有短标记 `gee0da84ab`。
用户于本任务明确要求**直接修改该容器的 vLLM 安装代码**，此特定授权覆盖
共享 `vllm-native` profile 的通常 editable-source 前置条件；不扩展到其他容器。
以镜像 ID、wheel 版本和逐文件原始/修改后 SHA-256 代替不存在的 Git HEAD，
不得声称有 PR base 或干净工作树。改动前 `minicpmv4_6.py` SHA-256 为
`fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`，
registry 为 `ab52495073a046b79d00a314cbc96e719e3ed916ea8a8bf6f3202015062b5676`。

现有 registry 只列 `MiniCPMV4_6ForConditionalGeneration`；目标是
`MiniCPMV4_7ForConditionalGeneration`，文本配置为 `qwen3_5_moe_text`，
而 4.6 adapter 使用 dense Qwen3.5 和简单三通道顺序位置。
候选扩展点是模型专用 adapter、注册表、多模态 processor、权重映射和
`Qwen3_5MoeForCausalLM`，不能仅加注册别名。已检索相近 1B 工作记录和
`docs/troubleshooting/`；1B 的静态 M-RoPE 差距相似，但文本骨干和 checkpoint
不同，仍需分别验证。
