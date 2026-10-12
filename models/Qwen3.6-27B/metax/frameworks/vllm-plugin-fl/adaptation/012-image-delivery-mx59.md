# 012：适配镜像保存与 mx-59 容器交付

## 范围与状态

- 日期：2026-10-08；用户要求保存当前适配镜像并在 `mx-59` 启动容器。
- 来源：`mx-58` 的运行中容器 `qwen3.6-27B`。本轮不修改 FA/GDN 实现，不启动模型服务，不执行正式验收。
- 状态：`verified`（仅镜像保存与容器交付）；镜像已保存，mx-59 容器已启动并通过限定验证。
- 继承 [011](011-flash-attention-splitkv.md) 的 FA 优化；不扩大历史数值/性能结论。
- 后续用户要求完整挂载 `/public-flash`，已完成；当前容器/挂载以文末追加记录为准，初次交付证据保持不变。

## 打包边界

- 镜像标签：`flagos/qwen3.6-27b-metax:adapted-20261008`。
- 两端一致的 image ID：`sha256:17523db510149bad9c4c6a8f9dcb1d788cc06bc849c74c0de48606fb7785f091`。
- 持久归档：`/public-flash/jinghao/qwen3.6-27B/01-environment/image-delivery-20261008/qwen3.6-27b-metax-adapted-20261008.tar.zst`。
- 归档大小：15,757,543,776 字节；SHA256 `ad6a22cf7ecdc925d8621468a53a72313e053cf7c32802cb50ff377b0d803049`，mx-59 校验通过。
- 原生证据：`/public-flash/jinghao/qwen3.6-27B/04-runs/image-delivery-20261008/`；过程脚本位于同工作根 `02-issues/image-delivery-20261008/`。
- `/workspace` 和 `/opt/conda` 已核实为容器内部路径，并非 bind mount；已安装组件与其 editable 源码直接打包，没有另选 checkout、版本或设置 `PYTHONPATH`。
- 新增镜像内部启动器 `/opt/flagos/qwen3.6-27b/start-model.sh`，SHA256 `c8a5cccbf59d39cb885e91dc40d9aba0771fa52eb0e52b7fcd502aaff8822a45`；原有 host 启动脚本未覆盖。
- 模型权重作为明确外部依赖，只读挂载 `/public-flash/models/Qwen3.6-27B` 到 `/models/Qwen3.6-27B`。
- 共享工作根仅挂载到同名路径用于证据；不挂载 `/workspace`、`/opt/conda` 或 `/data` 作为源码依赖。
- `docker commit --pause=false` 保存源容器；实际核对仍为 running、unpaused。Docker 的弃用提示保留在 `commit-output.log`，权威 image ID 单独由 inspect 读取。

## 组件与关键文件

| 组件 | 已安装版本 | 源码 HEAD |
|---|---|---|
| vLLM | `0.20.2+empty` | `bc150f50299199599673614f80d12a196f377655` |
| vllm-plugin-FL | `0.2.0` | `675548ab2ee52b8124b0b6a82a2f795c0553e1fa` |
| FlagGems | `5.4.0.dev588+gaf5291a06` | `c6f46cc970ea0bef8927ee657c021bd8621e3bb0` |
| FlagGems-vllm | `0.1.0` | `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777` |

HEAD 不能代表未提交内容；组件 diff、origin 与关键文件 SHA 以 `source-imports.log` 和最终 `delivery-result.json` 为准。源容器继承的 vLLM dirty 文件未在本轮修改。

FA 关键文件复核与 011 一致：

- MetaX `scheduling.py`：`4802a4dfe3fe60bf0c4bbe592c147a2b414adb8565522cd4fb81314a8965963a`。
- MetaX `splitkv.py`：`489d526b7c58597c0d31e60fd8570d42826c2bbc9401c86ec6ca6c78bdc791e2`。

## 验证与限制

- 两台主机连通、源容器映射、目标可用设备与磁盘空间已核实。目标预设 `CUDA_VISIBLE_DEVICES=4,5`，不停止任何已有容器/服务。
- 来源与目标四个组件的安装版本、import origin、HEAD、Git status、tracked diff SHA 及关键文件 SHA 一致；无 `PYTHONPATH`，未依赖开发源码挂载。
- 目标组件导入、启动器 `bash -n` 和 MetaX C550 设备 smoke 均通过。
- FA 回归：`test_metax_swapped_decode_paged_graph[1-0-784-6]`、`[4-0-784-6]`，`2 passed in 5.32s`；涵盖 eager 与 graph capture/replay，不等于重新执行 011 的完整 78+4 回归。
- mx-59 容器 ID：`1d9b1f5afb26d701437e2a8fcd6ae78aaed24f8fb4170e22c53f93904a921d5b`，最终 running、unpaused；默认可见设备 `4,5`，本轮 smoke/FA 测试仅使用物理卡 4。
- mx-58 原容器 ID：`fbff98cc36ac7fce4026538d33455a66c6ae165aa19496ed738790616f0f92e9`，交付后仍 running、unpaused；未停止任何已有容器/服务。
- 最终机器可读回执：证据根 `delivery-result.json`。原生 async job：commit `j813625250088.3083330`、save `j858462268094.3088181`、load `j168209550293.4051801`，均 finished / rc=0；位于工作根 `05-tmp/ansible-async-image-delivery-20261008/`。
- 通用离线检查：workflow 测试 252 passed / 1 skipped，operations 测试 6 passed；整体退出码 1，原因为既有结构审计的 12 errors / 78 review（旧 profile/模型记录），未修复无关记录，也不将该检查表述为整体通过。
- 本轮不声称 mx-59 完成模型启动、全模型准确率或性能验收；`framework.yml` 的正式验收状态不变。

## 使用方式

在 `mx-59` 执行 `docker exec -it qwen3.6-27B /bin/bash` 进入容器。
容器工作目录为 `/opt/flagos/qwen3.6-27b`，内部启动器为该目录的 `start-model.sh`；本轮未运行它。
启动器使用只读权重路径 `/models/Qwen3.6-27B`，TP2/BF16、默认图模式及独立内部 cache/log 目录；默认监听 `127.0.0.1:8001`，端口被占用时直接退出，不停止其他服务。

## 后续：完整挂载 /public-flash（2026-10-08）

- 范围仅 `mx-59`，不修改产品实现、不启动模型服务。用户明确要求完整挂载 `/public-flash`，该目录读写映射到容器同名目录。
- 保留 `/public-flash/models/Qwen3.6-27B` → `/models/Qwen3.6-27B` 的只读别名，兼容镜像内部启动器；该别名不限制从完整 `/public-flash` 路径写入权重，完整挂载本身为读写。
- 原容器存在交互式 Bash 会话。按远程操作 Skill/政策保持原容器运行，`docker commit --pause=false` 保存其当前可写层，创建新容器验证后仅切换名称；未停止、重启或删除容器。
- 当前容器：`qwen3.6-27B`，ID `1f62bdcb818d7119ed6595133dc64c3f14c194ae565c95dba18ef89bbd4fe657`，running、unpaused。
- 当前派生镜像：`flagos/qwen3.6-27b-metax:public-flash-20261008`，ID `sha256:f7b2d280fd5ae061db1d66d9707273969c4c8c9508cd4167d0e15a9b8e2c4957`；仅 mx-59 本地快照，未替换初次交付归档。
- 原容器保留为 `qwen3.6-27B-before-public-flash-20261008`，ID 仍为 `1d9b1f5afb26d701437e2a8fcd6ae78aaed24f8fb4170e22c53f93904a921d5b`，running、unpaused；已有终端仍连接旧容器。重新 `docker exec -it qwen3.6-27B bash` 进入新容器。
- 新旧 Config.Env 一致（含默认 GPU `4,5`）。四组件版本、HEAD、origin、status、tracked diff SHA 及 FA/GDN/启动器关键 SHA 一致；新容器导入与 GPU4 MetaX C550 设备 smoke 通过，无 `PYTHONPATH`。
- Docker inspect 确认仅完整 `/public-flash` 与权重别名两项 bind mount；host/container 的 `/public-flash` stat 均为 `53:3145731`。未新增 `/workspace`、`/opt/conda` 或 `/data` 源码挂载。
- 原生回执：`/public-flash/jinghao/qwen3.6-27B/04-runs/full-public-flash-20261008/result.json`；同目录保留 original/new imports、commit log 与 original diff。过程脚本在工作根 `02-issues/full-public-flash-20261008/`，无产品源代码改动。
- 保留失败：第一次预检查 `docker top -eo comm` 返回 `Couldn't find PID field in ps output`，修正为 `pid,ppid,comm`；旧版本保留为 `preflight-v1.py`。第二次在留存旧脚本时，Ansible remote_src copy 返回 NFS `Input/output error`；源/临时副本 SHA 相同，空间充足，元数据处理为待验证原因。改用硬链接保留旧版本后通过，失败临时文件 `tmp0setr0to` 未删除。两次失败均发生在容器变更前。
- playbook syntax/check-mode 与最终实际执行通过；离线检查仍因既有 12 errors / 78 review 返回 1，252 workflow（1 skipped）和 6 operations 测试通过。未重跑 FA 全量或全模型验收，历史结论不扩大。

知识库处理状态：`local-only`。
