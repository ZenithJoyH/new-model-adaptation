# 010：完整 /public 工作容器

2026-10-21，用户要求容器挂载H100-149主机整个 `/public`。批准执行根仍为 `/public/flagos/jinghao/MiniCPM-OCR/flagos`；扩大可见挂载不扩大Agent对其他数据的写入范围。

Docker现有容器的bind挂载不能通过常规update持久追加，因此从当前 `minicpm-ocr-flagos-allgpu` 在线快照创建新工作容器，保留所有原容器运行。未停止或重启任何容器，未停止当前推理服务，也未操作其他GPU任务。

| 项目 | 已核实值 |
| --- | --- |
| 新工作容器 | `minicpm-ocr-flagos-public` |
| 容器ID | `7b125058368e142f4010df941e7020c3b26874a6552ec2a862a3286f9a6286f5` |
| 当前安装环境快照 | `minicpm-ocr-flagos:public-snapshot-20261021` |
| 镜像ID | `sha256:7c685493efa008e77a0f8db4d0567bf9f819710a202b34f3006286330dcf67ca` |
| 主机→容器 | `/public` → `/public`，RW，rprivate |
| 默认工作目录 | `/public/flagos/jinghao/MiniCPM-OCR/flagos` |
| GPU | `/dev/nvidia0`至7以及ctl/uvm/uvm-tools；CUDA枚举8张H100，UUID与主机一致 |
| 网络/IPC | host/host，非privileged |

实际mountinfo为 `/public rw ... - parastor JNJTQS_public rw`。主机与新容器的 `/public`、`/public/flagos` 和批准工作根均核对到相同device/inode，证明新增的是完整目录映射。驱动工具/库和 `/opt/ocr-reference` 的原只读映射保留；冗余的工作根bind不再需要。

核对原容器当前安装文件6543个，新容器全部哈希一致；vLLM、Plugin、FlagGems、FlagGems-vllm及FlagTree的版本、实际import路径和入口哈希一致，两个算子库仍为原容器的源码安装。没有升级依赖、修改产品代码或通过PYTHONPATH选择其他版本。快照没有包含 `/public` 内的主机数据，使用时仍需该外部挂载；本轮仅验证工作容器，不声明最终模型交付镜像通过。

## 人工变化与服务边界

检查发现主机 `start-model.sh` 已被人工改向 `/public/flagos/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`，原 `/public/flagos/jinghao/MiniCPM-OCR/MiniCPM-OCR-1.0` 路径在主机和旧容器均不存在。没有覆盖人工脚本、复制权重或擅自切换checkpoint。新容器已能读取新checkpoint的config，SHA256为 `90505bb0a5ca87b2fd8afc608bfc9c83d1cb8a0ba6e7a9d7ff29f20ff385322d`；这不代表新checkpoint已做推理验证。

首次创建尝试继承旧Docker配置中的权重bind，因host源路径不存在而失败。保留该失败，省略失效bind后创建成功；没有创建空权重目录或用其他模型冒充原模型。新容器使用整个 `/public`，可见主机实际存在的目录。

当前8011服务继续运行在原 `minicpm-ocr-flagos-allgpu` 中：API PID3699、start_ticks359670、实际argv均未变化，health200。它仍使用此前已经加载的模型；原权重路径已缺失，不能假定该旧命令现在可重启。新工作容器保持运行，没有启动第二个模型服务。是否按人工脚本切换新checkpoint已另行询问；挂载工作无需等待模型选择。

2026-10-20的处理器/eager/graph/OCR验收仍是原部署的历史证据，不迁移标签或作为新checkpoint通过。framework.yml的target仍准确指向原8011服务容器；本次新增工作容器只记录于此，不篡改原部署指纹或已冻结回执。

## 使用与证据

在H100-149执行 `docker exec -it minicpm-ocr-flagos-public bash`，默认进入批准工作根。原有已打开的旧容器shell不会自动切换到新容器。

原生证据保存在批准根的 `04-runs/public-mount-20261021/`：`before.json`、`installed-before.json`、`start-model-human-before.sh`、`attempt1-failure.json`、`new-container.json`、`new-container-verification.json`、`final-verification.json`、`progress.json`。创建脚本在 `01-environment/public-prepare-v2-20261021.py`，保存完整create argv、文件清单、挂载与设备取证。主机人工脚本、模型目录和原服务均保留。
