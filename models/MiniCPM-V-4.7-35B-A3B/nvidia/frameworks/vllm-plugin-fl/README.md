# MiniCPM-V-4.7-35B-A3B / H100-149 / vllm-plugin-fl

本工作区由旧模型目录合入；旧名 `MiniCPM-V-4.7-35B` 与本模型为同一模型。见[合并记录](../../../_shared/model-directory-merge.md)。历史容器、路径和回执保留原值。

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

## 2026-10-10：当前 DSpark 服务使用双卡与默认上下文

当前同名容器的 18349 服务已使用 GPU6、GPU7、TP2、`max_num_seqs=64`；
删除批次 token 和长度覆盖，实际默认值分别为 8192、262144。
`FULL_AND_PIECEWISE` 三组图捕获全部完成，图文/多轮 9/9、64 客户端 64/64，
DSpark 草稿实际参与，服务保持运行。两类缓存逐进程隔离解决本轮启动阻碍，底层责任尚未确定。
组件版本及推理源码未改，详见[问题 010](adaptation/010-dspark-tp2-default-context.md)和
[双卡服务验证及脚本指纹](acceptance/dspark-tp2-validation-2026-10-10.md)。
内部脚本 `/opt/flagos/dspark/start-35b-model.sh`，SHA-256
`d126721db2dfd4a5008f11d5a5b65d5c97b1410c7c63ad48f45d0799bdac98aa`；
宿主 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-dspark-35b.sh`，SHA-256
`db6ecd772e18a1ed8146c40a89fa881117cf8fe2c22c41c2d515a4a689561f29`。
未做正式精度/性能、满长度输入或镜像发布验证，历史 framework 状态不提升。

## 2026-10-10：当前容器映射全部显卡

同名容器现为 `a650538a4c01fe79d59d0bbacac4edc4cec52046e1072f3255f56c0161f23b11`。
已核实全部 8 张 H100 可见，完整 jinghao 挂载和适配源码保留。
35B 启动器新增明确选择 GPU6 的环境变量，其余参数和用户宿主脚本改动保留。
操作前服务已停止，本轮未启动推理或进行多卡验证。
详见[共享显卡与挂载记录](../../../../MiniCPM-V-4.7-1B/nvidia/frameworks/vllm-plugin-fl/environment/dspark-jinghao-mount-2026-10-10.md)。

## 2026-10-10：同名重建并恢复 DSpark 服务

按用户明确授权，为当前 DSpark 容器添加完整 `/public/flagos/jinghao` 读写挂载。
从当前安装快照同名重建后，容器 ID 为
`41a889964f15fd51b3e2a7944f4579bbd086974938d1b6ab44057cbfee0711ce`。
源码、依赖和启动器哈希不变，18349 的 35B-A3B DSpark 服务已恢复；
FULL_AND_PIECEWISE 捕获与九项图文/多轮回归通过。旧容器停止保留为备份。
详见[共享挂载与恢复记录](../../../../MiniCPM-V-4.7-1B/nvidia/frameworks/vllm-plugin-fl/environment/dspark-jinghao-mount-2026-10-10.md)。
未重测数据集或性能，历史 framework 状态保持原样。

## 2026-10-09：当前 DSpark 容器支持 35B-A3B

已在 `MiniCPMV4.7-1B-DSpark-gpu6` 中使用 Plugin `0.4.0-dev` 与 vLLM `0.28.0`
跑通 35B-A3B 主模型和 DSpark 草稿。修复安装 Plugin 的 MoE padding 接口；单卡 TP1
eager 9/9、`FULL_AND_PIECEWISE` 19/19，DSpark 草稿真实参与解码。
当前服务 `127.0.0.1:18349`，容器内启动器 `/opt/flagos/dspark/start-35b-model.sh`。
1B 服务按授权暂停；当前配置一个驻留序列，十客户端并发排队。未做正式精度/性能。
详见[问题 009](adaptation/009-dspark-plugin04-single-gpu.md)及
[DSpark 服务验证](acceptance/dspark-service-validation-2026-10-09.md)。

## 2026-10-08：双模型共用代码

已在新容器 `MinicpmV4.7-unified-20261008` 安装与 1B 共用的 Plugin，按模型配置选择
dense / MoE，无 `PYTHONPATH`。两模型均通过 TP2 eager 6/6、
`FULL_AND_PIECEWISE` 19/19；35B graph 由容器内部共用脚本实际启动。
继承 1B 环境的 FlagGems 广播 mask 修复，不设置旧 attention 黑名单，开启 prefix caching。
详见[整合设计](adaptation/008-unified-dense-moe-adapter.md)和
[共同功能验证](acceptance/unified-code-validation-2026-10-08.md)。
原两容器和服务未改；本轮未运行正式精度/性能或发布镜像验证，保留历史 framework 状态。

随后从最终容器快照创建 `minicpmV4.7-35B-new` 与 1B 新容器，
两容器保持运行，镜像内安装和 GPU 映射检查通过；本轮未启动新模型服务。
后续按用户要求补齐 `/data:/data` 并映射全部 GPU0–7，两个容器均经 PyTorch 核实识别 8 张卡。
见[新容器环境记录](environment/model-containers-2026-10-08.md)。

## 原独立容器的历史记录

下列脚本哈希、PID 和 profile 判断属于相应历史轮次，不能作为新容器的当前状态。

目标为 `MinicpmV4.7-35B` 容器中的
`/data/models/MiniCPM-V-4.7/weights/35b-a3b`。工作根的宿主机与容器路径均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`，映射已通过设备号与 inode 核实。

- [环境分析](environment/README.md)：组件身份、目录映射和适配差距。
- [问题索引](adaptation/README.md)：Plugin 模型适配、图模式限制和运行时问题。
- [历史服务验证记录](acceptance/service-validation-2026-09-30.md)：先前端口 8019 脚本的实际启动、图文与十并发结果。
- [2026-09-30 已安装 Plugin 的服务验证](acceptance/service-validation-installed-plugin-2026-09-30.md)：当时端口 8021 脚本的图捕获和回归结果。
- [2026-10-01 启动脚本精简验证](acceptance/launcher-simplification-2026-10-01.md)：上一版脚本的启动和图文回归结果。
- [2026-10-01 用户新脚本验证](acceptance/user-revised-launcher-validation-2026-10-01.md)：当前原文脚本的启动、有效配置及图文结果。
- [验收索引](acceptance/README.md)：正式验收边界与后续工作。

2026-09-28 已在 GPU 4、5 上完成 TP2 eager 文本、单图推理，以及
`FULL_DECODE_ONLY` 的文本、红/蓝图与变输入 replay 最小回归。直接请求 `FULL`
时，当前 vLLM 的 GDN backend 将其改为 `FULL_AND_PIECEWISE`，见
[问题 005](adaptation/005-gdn-full-graph-limit.md)。按用户最新选择，现已显式启动
TP2 `FULL_AND_PIECEWISE`，2026-09-30 重新连接后完成实际验证。当时脚本在
GPU 4、5 上运行：mixed prefill/decode 分段图 5/5、纯解码全图 4/4，API 就绪，
最小图文 6/6 和十并发混合请求 10/10 正确。此模式的分段 prefill 不能写成当前
profile 的正式 graph 验收通过。

随后已在容器内以 `editable_mode=compat` 安装适配后的 Plugin，并在不设置
`PYTHONPATH` 的新进程中核实导入路径。用户改写候选经逐进程缓存隔离后完成
图文 6/6 和十并发 10/10；最终根目录脚本补齐目录、缓存和资源占用保护，
2026-09-30 在端口 8021 实际启动，重新完成图捕获、图文 6/6、十并发 10/10。
2026-10-01 精简脚本曾实际启动并通过图文 6/6；用户再次修改后，当前脚本 SHA-256
为 `88ff63628fbdb5f0c863e46bc36a962b070b756346a475c0e2ff64244d284bb1`。
原文实际启动后的服务 PID `43939` 保持运行，图捕获和图文 6/6 通过，有效上下文
上限变为 262,144；本轮未重复十并发。脚本缺少占用保护，缓存落在容器默认目录，
不能视为可重复的最终启动器。详见[用户新脚本验证](acceptance/user-revised-launcher-validation-2026-10-01.md)
及[问题 007](adaptation/007-user-edited-launcher-self-containment.md)。
正式精度、性能和 profile 汇总尚未完成；`framework.yml` 保持
`environment_ready`，直到部署指纹和正式原生证据重新绑定齐备。
