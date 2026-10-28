# 2026-10-08：从最终共用容器创建两个模型容器

## 范围与结果

按用户指定名称，在 `H100-149` 从最终 `MinicpmV4.7-unified-20261008` 创建两个新容器。
状态为 `containers-created-environment-verified`：容器保持运行，安装与设备检查通过；
本轮没有启动模型服务，没有重新执行整模验收。
创建完成时，源容器及原 `MinicpmV4.7-1B`、`MinicpmV4.7-35B` 容器均继续运行。
源容器随后按用户明确授权删除，见下方后续操作。

| 项目 | 已核实身份 |
|---|---|
| 源容器 | `MinicpmV4.7-unified-20261008` / `9013fa8b0a35c97db645d8bd57ec7bbc055bda1b8fab758a2f294907ff5804d3` |
| 新镜像 | `minicpmv47-unified:aa4228e-20261008` |
| 镜像 ID | `sha256:5f7e2b468f40f4995438f8641ff0ffbd656a7de07adea3b7420ccd11b1630acd` |
| 1B 新容器 | `minicpmV4.7-1B-new` / `ccaeae625d2cc0ac20cce12fb2b5baa1f080b6167a06ede32112ae1deb9d2f3d` |
| 35B 新容器 | `minicpmV4.7-35B-new` / `11a3f9215e02a0c9d023cc1344c0326a3c0e191e90db18ed13318af38ca5f873` |
| Plugin | `support-minicpmV4.7@aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`，工作树干净 |

上表为创建时身份；补挂载 `/data` 和全部 GPU 后的当前容器 ID 见文末。

快照使用 `docker commit --pause=false`，源容器未暂停。
镜像仅修正默认 `CUDA_VISIBLE_DEVICES=0,1`：此设备限制下 CUDA ordinal 0/1 对应物理 GPU6/7，
避免继承源容器创建时的 UUID 字符串触发 Plugin 整数映射限制。产品源码未改。

## 工作目录、挂载与设备

- 1B 默认工作目录：`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`；
  对应权重 `/data/models/MiniCPM-V-4.7/weights/1b`，文本类型 `qwen3_5_text`。
- 35B 默认工作目录：`/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`；
  对应权重 `/data/models/MiniCPM-V-4.7/weights/35b-a3b`，文本类型 `qwen3_5_moe_text`。
- 两容器均显式挂载上述两个已批准工作根，Host/容器路径相同且设备号、inode 核对一致。
  `/data/models/MiniCPM-V-4.7/weights` 为只读挂载；驱动依赖只读挂载
  `/usr/lib/x86_64-linux-gnu/{libcuda.so.1,libnvidia-ml.so.1}` 和 `/usr/bin/nvidia-smi`。
- 两容器均沿用源容器的 host 网络、private IPC、16 GiB shm、IPC_LOCK 和 runc。
  仅提供物理 GPU6/7 及必要 NVIDIA 控制设备节点；CUDA 0/1 的原始 UUID 分别为
  `21b327d9-c547-49e9-25e6-58c785af00d6`、`d508af44-d081-7d8d-0ebe-1a2d15266369`。
- 两容器的主进程为 `/bin/sleep infinity`，没有自动启动推理服务。
  两者共享同一对 GPU；继承的共用启动器也使用同一端口 18347，本轮没有并行服务部署声明。

## 镜像内文件与检查

从新镜像创建的两个容器，均在全新 `/usr/bin/python3` 进程且无 `PYTHONPATH` 下检查：

- `vllm_fl` / 模型 adapter 实际导入 `/vllm-workspace/vllm-plugin-FL`；
  两种文本类型分别选择 dense / MoE 类。
- FlagGems 实际导入 `/vllm-workspace/FlagGems/src/flag_gems`，Git
  `0dddb4628ae215931171a7f6e04a1183777dcd8a`，继承已验证的广播 mask 修复；
  FlagGems-vllm Git `e13419a429bfba65f4757a7671b1aebfe25c61a2`。
- Plugin 五个已冻结文件、内部缓存 helper 与 `/opt/minicpmv47-unified/start-model.sh`
  哈希均与整合验证版本一致；启动器语法检查通过。
- vLLM 2057 个 `.py/.so` 路径/内容聚合 SHA-256 均为
  `8fb38bcb183ed0d912e9ce107a1269865dca66a67d849f5f4469d4c53117ba8d`。
- 实际导入路径、部署 helper、启动器及 FlagGems-vllm 源码均不位于 bind mount 中，
  属于新镜像内部。权重、工作根、驱动依赖属于明确的外部挂载。
- CUDA 检测到两张 H100 80GB，UUID 与分配设备相符；各自权重配置文件可读、类型正确。
  探针退出后物理 GPU6/7 无计算进程。

首次探针错误地将 PyTorch UUID 与含 `GPU-` 前缀的 nvidia-smi 表示直接比较，导致断言失败；
设备实值一致。仅修正探针表示后完成两容器检查，首次日志与 `verification-attempt-v1.json`
保留。未改变镜像、模型代码或放宽设备身份条件。

## 证据与边界

原生证据在
`H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/container-clones-20261008-aa4228e/`：
`source-configuration.json`、`image.json`、`creation-result.json`、两个容器的配置 JSON、
`*-environment.json`、`*-probe*.log`、`*-processes.txt`、`verification-result.json`。
一次性创建/核验程序位于该工作根 `02-issues/`，未复制进本地模型目录。

本轮验证容器创建、镜像内安装、挂载、权重配置和 CUDA 映射；新镜像的模型服务启动/就绪
验证仍为 pending。原共用容器 50 项 API 回归见
[双模型功能验证](../acceptance/unified-code-validation-2026-10-08.md)，不当作两个新容器已实启的证明。
正式精度、性能和 framework 状态未变。

## 后续操作：按授权删除源容器

2026-10-08 07:32 UTC，在 `H100-149` 按用户明确授权，对上表源容器的完整 ID
执行 `docker stop --time 10` 和 `docker rm`，未使用卷删除参数。
操作前确认源容器只有 `sleep infinity` 与空闲 shell；操作后确认源容器名称和 ID 均不存在。
两个新容器的 ID、镜像身份保持一致且均运行，共用镜像及六个 bind mount 的宿主路径保留。
原生回执为上述证据目录中的 `unified-container-removal.json`；之前的验证快照作为历史证据保留。

## 后续操作：补齐完整 `/data` 挂载

2026-10-08，按用户要求为两个新容器添加宿主 `/data` 到容器 `/data` 的可读写 bind mount。
原权重子目录只读挂载保留。Docker 需要重建容器，沿用原创建参数和同一镜像；
原容器改名并停止保留，其可写层未删除。

| 补挂载时的容器（后续全卡映射已重建） | 当次完整 ID | 保留的停止容器 |
|---|---|---|
| `minicpmV4.7-1B-new` | `a1ce4bfd403f1a38d017c6b3a6232cb865b3fb9b05c1387491376e628b5e3553` | `minicpmV4.7-1B-new-before-data-20261008` |
| `minicpmV4.7-35B-new` | `bef254cbd90f8409082203761ff27e18afce5db1868694912bee0aa3bed7ab2e` | `minicpmV4.7-35B-new-before-data-20261008` |

核实两个当前容器均运行；容器 Config 除自动生成的 Hostname 外一致，HostConfig 仅新增该挂载。
从容器内部核对 `/data`、权重及两个工作根的设备号/inode 与宿主路径一致；
`/proc/self/mountinfo` 确认 `/data` 为 rw、权重子目录为 ro。
Plugin 模型文件、注册入口、镜像内部启动器和缓存 helper 的哈希与重建前一致。
未启动模型服务或重复整模验收。

前两次操作均在容器变更前检查失败：先是 Docker 返回 Mounts 列表顺序改变，后是
`docker top -eo args` 缺少 Docker 要求的 PID 列。改为按目标路径比较完整挂载字段，
并使用 `pid,stat,args` 后完成操作；失败程序及最终 v3 程序保留在远端 `02-issues/`。
最终原生回执为上述证据目录的 `data-mount-result-20261008.json`，
两容器分别另有 `*-data-mount-20261008.json`；原创建与删除回执保持为历史证据。

## 后续操作：两个容器均映射全部 8 张 GPU

2026-10-08，按用户要求解除此前仅映射物理 GPU6/7 的限制。
两个容器均映射宿主 `/dev/nvidia0` 至 `/dev/nvidia7`，保留原 NVIDIA 控制设备；
容器环境设置 `CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7`、`NVIDIA_VISIBLE_DEVICES=all`。
继续使用同一镜像与 runc，全部目录挂载、其余配置和适配文件保持一致。

| 当前容器 | 当前完整 ID | 保留的停止容器 |
|---|---|---|
| `minicpmV4.7-1B-new` | `86a19f7e33be6a7388c0d4ec63b4d9f12bd9a432702d8cb71c3d446d2ce89b70` | `minicpmV4.7-1B-new-before-all-gpus-20261008` |
| `minicpmV4.7-35B-new` | `586cee7805a3f0c859a0c2e0d6425d2e93b0e6c314d7615babaa46b2bbd10e6a` | `minicpmV4.7-35B-new-before-all-gpus-20261008` |

两个当前容器均运行。各自在无 `PYTHONPATH` 的新 Python 进程中，
`torch.cuda.device_count()` 为 8，全部 CUDA 设备 UUID 与宿主 8 张 H100 的 UUID 集合一致；
容器内 `nvidia-smi` 同样核对全部 UUID。
`/data`、权重和工作根的设备号/inode 匹配，`/data` 为 rw、权重子目录仍为 ro；
Plugin 入口和模型文件、镜像内部启动器与缓存 helper 的哈希未变。
仅查询 CUDA 属性，未运行推理；启动器和 TP2 参数未修改。
全卡映射后容器默认 CUDA 编号覆盖全部 GPU，启动器显式选择的 `0,1` 不再指此前物理 GPU6/7。
本轮没有启动服务或执行整模验收。

原生回执为共享证据目录 `all-gpus-result-20261008.json`，
另有两个 `*-all-gpus-20261008.json`；操作程序为远端 `02-issues/map-all-gpus-model-containers-20261008.py`。
此前容器分别停止并改名保留，未删除可写层；历史回执未覆盖。
