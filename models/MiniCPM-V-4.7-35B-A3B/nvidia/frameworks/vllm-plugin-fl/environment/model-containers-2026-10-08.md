# 2026-10-08：最终共用镜像的 35B 新容器

按用户要求，在 `H100-149` 基于最终 `MinicpmV4.7-unified-20261008` 快照创建
`minicpmV4.7-35B-new`，ID
`11a3f9215e02a0c9d023cc1344c0326a3c0e191e90db18ed13318af38ca5f873`。
镜像为 `minicpmv47-unified:aa4228e-20261008`，ID
`sha256:5f7e2b468f40f4995438f8641ff0ffbd656a7de07adea3b7420ccd11b1630acd`。
同镜像创建了 `minicpmV4.7-1B-new`。

35B 默认工作目录为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`，
权重 `/data/models/MiniCPM-V-4.7/weights/35b-a3b` 只读挂载。
容器保持运行，Plugin `aa4228e` 导入不需要 `PYTHONPATH`；镜像内源码、helper、启动器
和 vLLM 文件身份核对通过，CUDA 0/1 对应物理 GPU6/7。

状态 `containers-created-environment-verified`，未自动启动模型服务。
完整共享配置、两容器身份、挂载证明、UUID 探针格式修正与原生证据见
[两个新容器的环境记录](../../../../../MiniCPM-V-4.7-1B/nvidia/frameworks/vllm-plugin-fl/environment/model-containers-2026-10-08.md)。
创建完成时源容器及原容器仍运行；随后用户明确授权删除源容器，已于
2026-10-08 07:32 UTC 完成并核实源容器不存在。两个新容器仍运行，共用镜像及挂载数据保留；
回执见共享证据目录 `unified-container-removal.json`。
新镜像的整模服务启动/就绪验证尚未执行，
不升级正式精度、性能或 framework 状态。

## 后续补挂载 `/data`

2026-10-08 按用户要求补齐完整 `/data:/data` 可读写挂载，保留权重子目录只读挂载。
补挂载时重建的 `minicpmV4.7-35B-new` 当次 ID 为（后续全卡映射已再次重建）
`bef254cbd90f8409082203761ff27e18afce5db1868694912bee0aa3bed7ab2e`，已核实运行。
原 ID 对应容器改名为 `minicpmV4.7-35B-new-before-data-20261008` 并停止保留可写层。
镜像、工作目录、设备和其余配置沿用原设置；容器内部核对挂载设备号/inode、rw/ro 权限，
适配文件及启动器哈希保持一致。1B 容器同样完成。
完整身份、检查修正与回执 `data-mount-result-20261008.json` 见上方共享环境记录。
本次未启动模型服务或重复整模验收。

## 后续映射全部 GPU

2026-10-08 按用户要求将两个容器均改为映射宿主 GPU0–7 全部 8 张 H100。
`minicpmV4.7-35B-new` 当前 ID 为
`586cee7805a3f0c859a0c2e0d6425d2e93b0e6c314d7615babaa46b2bbd10e6a`，已核实运行。
原当次容器改名为 `minicpmV4.7-35B-new-before-all-gpus-20261008` 并停止保留。
`CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`、`NVIDIA_VISIBLE_DEVICES=all`；
两个容器各自的 PyTorch 实际检测到 8 张卡，全部 CUDA UUID 与宿主一致。
`/data` 可读写挂载、权重子目录只读挂载及其余配置保持，适配文件哈希一致。
启动器仍为 TP2，其显式 CUDA `0,1` 在全卡映射后不再对应此前物理 GPU6/7。
未启动模型服务或重复整模验收。完整身份和 `all-gpus-result-20261008.json` 回执见共享环境记录。
