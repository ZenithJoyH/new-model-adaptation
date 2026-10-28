# 2026-10-10：DSpark 容器完整挂载 jinghao

## 范围与授权

用户要求当前 `H100-149` DSpark 容器完整挂载 `/public/flagos/jinghao`。
检查发现原容器只有部分子目录挂载，Docker update 不支持在线追加 bind mount。
remote-operations Skill 的默认规则要求适配容器保持运行；本轮用户随后明确选择
“授权停止并重建当前同名容器”，作为本次停止和重建的独立授权。
先对原容器 `docker commit --pause=false`，再停止、改名保留原容器，以相同名称重建。

| 项目 | 当前核实身份 |
| --- | --- |
| 容器名称 | `MiniCPMV4.7-1B-DSpark-gpu6` |
| 新容器 ID | `41a889964f15fd51b3e2a7944f4579bbd086974938d1b6ab44057cbfee0711ce` |
| 快照镜像 | `minicpmv47-dspark:jinghao-full-mount-20261010-165008` |
| 镜像 ID | `sha256:a9e17809a26dfd288c662647ea2295aaff56a11e06b005d3595b6bd72f4ba983` |
| 停止的原容器备份 | `MiniCPMV4.7-1B-DSpark-gpu6-backup-20261010-165008` |
| 原容器 ID | `8645e61dddfaac3712ec27afaa1efce8b008e9f6f24a263a9e6380dce43cb640` |

原容器及其可写层未删除。新容器保持运行，restart count 为 0。

## 挂载、安装与设备验证

- 新增 Host `/public/flagos/jinghao` → 容器同路径的读写 bind mount，rprivate。
  Host/容器设备号、inode 同为 `45:200090921992`，14 个顶层条目一致。
- 原工作根 Host `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos` → `/work` 保留，
  设备号、inode 同为 `45:232972481026`。通过完整路径在批准根内写入探针，
  `/work` 别名读取一致；未在其他 jinghao 子目录写入。
- 原 1B 主/草稿和驱动只读挂载保留；完整父目录为 rw，原草稿子目录仍为 ro。
  保留 host 网络、private IPC、8 GiB shm、runc、非 privileged 和原设备映射。
- 只提供物理 GPU6，PyTorch 核实一张 H100 80GB；其他容器和 GPU 服务未操作。
- vLLM `0.28.0`、Plugin `0.4.0.dev0+ge88e4db`、FlagGems `5.4.0.dev0+g0dddb462`、
  Torch `2.13.0+cu130`、Transformers `5.12.1` 保持一致。
- 包导入路径、完整 `.py/.so` 聚合哈希、35B 启动器及新增 padding 测试均与快照前一致。
  Plugin 实际路径 `/vllm-workspace/vllm-plugin-FL`，FlagGems 实际路径
  `/vllm-workspace/FlagGems/src/flag_gems`，仍位于容器内部；未更换源码或依赖。

## 服务恢复

使用原容器内 `/opt/flagos/dspark/start-35b-model.sh` 实际启动；哈希仍为
`1e1964fad3ae24064c60cc2782fa129e83c4916f25fe66bca1d1442cdc3f843b`。
没有 `PYTHONPATH` 或 `CUDA_LAUNCH_BLOCKING`。API PID 87、EngineCore PID 621。
服务仍为 `127.0.0.1:18349/v1`，model `MiniCPM-V-4.7-35B-A3B-DSpark`；
TP1、50K 配置上限、max_num_seqs 1、prefix caching 和原 DSpark 参数保留。

重新捕获 `FULL_AND_PIECEWISE`：目标分段图 2/2、全图 decode 1/1、DSpark 全图 1/1。
九项文本、四色图、重复图、变化算式和多轮验证 9/9 正确，以 stop 结束。
草稿计数 9、生成草稿 token 126、接受 token 17；最后 health 200、运行及等待队列均为 0。
当前 1B 服务仍暂停，1B 启动器保留；本轮没有重测 1B 或任何数据集，也没有正式性能结论。

## 原生证据

上述批准 Host 根下 run 名 `jinghao-full-mount-20261010-165008`：

- `01-environment/`：脱敏前后容器配置、重建计划、组件前后完整指纹。
- `02-issues/`：一次性同名重建控制程序，含失败保全与回退逻辑。
- `03-acceptance/`：独立九项功能回归脚本，只更换证据输出目录。
- `04-runs/`：快照/重建进度、服务进程、启动日志截取、功能完整响应、metrics、
  `final-verification.json`、`evidence-manifest.json`。
- `05-tmp/`：批准根内的挂载写入探针。

原启动器继续追加既有 `dspark-35b-20261009/graph-server.log`；本次记录起始 byte offset
487519，单独保存本次启动部分，避免把旧进程成功当作重建服务成功。
历史精度分数、旧容器证据和 `framework.yml` 绑定未刷新；本次是挂载重建与恢复验证。

## 后续：35B 启动器格式整理

同日按用户要求整理 `/opt/flagos/dspark/start-35b-model.sh` 及 `/work/start-dspark-35b.sh`：
启动参数逐行排列，统一缩进与路径引用。整理前后 shell token 完全一致，`bash -n` 通过。
新 SHA-256 为 `8d0c30a834266824b03147d71f8b4531e2d0351eaf5602b6f6b90cc9cc8bc677`。
未重启服务，API PID 87 及 argv 保持一致，health 200；不声称格式修改后重新实启。
原文、新文及校验回执在批准根的 `04-runs/launcher-format-35b-20261010/`。

## 后续：当前容器映射全部 8 张显卡

同日用户明确要求映射主机全部显卡；沿用本次容器调整中已给予的同名停止/重建授权。
检查时原容器仅有 `sleep infinity`，35B 服务已停止，GPU6 无显存占用。
本轮保留该服务状态，没有自动启动任何推理服务或其他 GPU 工作负载。

- 当前同名容器 ID：`a650538a4c01fe79d59d0bbacac4edc4cec52046e1072f3255f56c0161f23b11`，
  保持运行，restart count 为 0。
- 快照镜像：`minicpmv47-dspark:all-gpus-20261010-171333`，ID
  `sha256:a8666329e1019ded45cf668cd1625526d49343be5786a78b9ea2d321599c8408`。
- 前一容器停止保留为 `MiniCPMV4.7-1B-DSpark-gpu6-before-all-gpus-20261010-171333`，
  ID `41a889964f15fd51b3e2a7944f4579bbd086974938d1b6ab44057cbfee0711ce`。
- 映射 `/dev/nvidia0` 至 `/dev/nvidia7` 及原 NVIDIA 控制节点；容器默认不设置
  `CUDA_VISIBLE_DEVICES`，`NVIDIA_VISIBLE_DEVICES=all`，
  `CUDA_DEVICE_ORDER=PCI_BUS_ID` 用于固定 CUDA 序号与主机索引的对应关系。
- PyTorch 实测 8 张 H100 80GB；逐张 UUID 与主机 GPU0–7 完全对应。
  所有原有挂载、网络、shm、runtime、非 privileged 等 HostConfig 保留。
  `/work` 与完整 jinghao 路径的设备号/inode 仍与 Host 一致。
- vLLM、Plugin、FlagGems 完整 `.py/.so` 哈希与版本、导入路径保持不变；没有修改产品代码。

两份容器内 1B/35B 启动器与宿主 35B 入口只新增 `export CUDA_VISIBLE_DEVICES=6`。
这是全卡可见后保留原物理 GPU6 选择所需的设置，避免脚本默认改用主机 GPU0。
容器默认仍可见全部八卡；单独使用该环境后，PyTorch 实测唯一设备 UUID 对应主机 GPU6。
脚本其他 shell token 保持一致，`bash -n` 通过，均可执行。

宿主 35B 入口已由用户改为 nohup/后台及相对日志路径，本轮保留全部用户改动，
未拿容器内脚本覆盖宿主版本。当前启动器哈希：

| 路径 | SHA-256 |
| --- | --- |
| `/opt/flagos/dspark/start-35b-model.sh` | `297b7770f01e4d3db2782666d45c687bbc1cfbc1148b6be023ac88df156ff22f` |
| `/opt/flagos/dspark/start-model.sh` | `c710d122f3fcdd6c504cc419513c3f724ad51a1112443b04b8bbfce26c2cca8e` |
| `/work/start-dspark-35b.sh` | `861ce718b2a8f3bbd75fa4992dc6e934aa4c07bac18594b5d2ada1377770735b` |

原生证据 run 为 `all-gpus-20261010-171333`，仍位于前述批准根：
`01-environment/` 中保存前后配置/组件指纹与计划，`02-issues/` 保存重建及回退控制代码，
`04-runs/` 保存逐脚本原文/改文、快照、进度、八卡及单卡 mask 验证和证据清单。
本次仅验证显卡可见性、身份和文件保留，未重新启动或验证整模推理，未测试 TP8。
历史精度/功能结果及 framework 绑定不作为当前新容器已经实启的证据。

## 随后：35B DSpark 双卡服务验证

同一容器保持运行，在 GPU6/7 上启动 TP2 的 35B DSpark，64 序列、默认 batch token 8192、
模型默认上下文 262144；图捕获和 73/73 短请求功能验证通过。1B 服务仍暂停。
35B 两份脚本及按需启用的逐进程缓存钩子已更新，1B 启动器未改；上述表格属于八卡映射轮次。
本轮新脚本指纹、失败与缓存缓解、实际服务与双卡 PID 的完整记录见
[35B 双卡服务验证](../../../../../MiniCPM-V-4.7-35B-A3B/nvidia/frameworks/vllm-plugin-fl/acceptance/dspark-tp2-validation-2026-10-10.md)。
