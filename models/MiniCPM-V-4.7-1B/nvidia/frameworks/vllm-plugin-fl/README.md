# MiniCPM-V-4.7-1B / NVIDIA / vllm-plugin-fl

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

## 2026-10-10：共享 DSpark 容器运行 35B 双卡服务

当前容器 ID 保持 `a650538a4c01fe79d59d0bbacac4edc4cec52046e1072f3255f56c0161f23b11`。
按用户要求，35B 服务改为 GPU6/7、TP2、64 序列、默认 batch token 8192 和上下文 262144，
18349 的图捕获及 73/73 功能验证通过，服务保持运行。1B 服务仍暂停，1B 启动器未改。
详见[35B 双卡记录](../../../../MiniCPM-V-4.7-35B-A3B/nvidia/frameworks/vllm-plugin-fl/acceptance/dspark-tp2-validation-2026-10-10.md)。
下方各轮设备、服务和评测状态保留为历史证据。

## 2026-10-10：当前 DSpark 容器映射全部显卡

按用户要求同名重建，当前 ID 为 `a650538a4c01fe79d59d0bbacac4edc4cec52046e1072f3255f56c0161f23b11`。
PyTorch 核实 8 张 H100 80GB，CUDA0–7 的 UUID 与主机 GPU0–7 一致；完整 jinghao
挂载、适配和依赖保留。1B/35B 启动器显式选择原 GPU6，宿主脚本已有用户改动保留。
操作前服务已停止，本轮保留停止状态，仅做设备与文件验证。
详见[最新挂载和显卡记录](environment/dspark-jinghao-mount-2026-10-10.md)。

## 2026-10-10：当前 DSpark 容器补齐 jinghao 挂载

按用户明确授权停止并同名重建 `MiniCPMV4.7-1B-DSpark-gpu6`，新增完整
`/public/flagos/jinghao` 读写挂载；新 ID 为 `41a889964f15fd51b3e2a7944f4579bbd086974938d1b6ab44057cbfee0711ce`。
安装适配、脚本和依赖哈希保持一致。当前运行 35B-A3B DSpark，端口 18349，
FULL_AND_PIECEWISE 捕获与 9/9 图文回归通过；1B 服务仍暂停，旧容器停止保留为备份。
详见[挂载与恢复记录](environment/dspark-jinghao-mount-2026-10-10.md)。
下方精度及服务记录属于各自历史轮次，未作为本轮新容器的精度验收。

## 2026-10-09：128 客户端并发精度重测

Plugin `0.4.0-dev@e88e4db` 的 DSpark 服务完成指定数据集重测：
MATH500 **72.4%（362/500）**，MMLU-Pro 14 科各 50 题原生
**42.0%（294/700）**。两项超时均为 0，长度截断分别为 31/17 条；
MMLU-Pro 91 条选项提取失败按原生规则计错，未追加人工恢复计分。
全部 1200 题完整性、原生评分、API 回复与样本核对通过。

客户端并发上限 128；服务端保持 max_num_seqs=4，MATH500 峰值 128 条在途，
MMLU-Pro 按科顺序运行，单科峰值 50。首轮评测缓存挂载消失后已保全失败现场，
改用独立评测容器本地 overlay 缓存从零完整重跑，耗时约 103.15 分钟。
服务未重启，前后进程与组件哈希一致、health=200；容器持续运行。
此为指定子集测量，正式验收/性能/镜像状态未升级；详见
[测量记录](acceptance/dspark-c128-plugin04-20261009.md)和
[缓存故障记录](adaptation/009-evaluator-cache-mount.md)。

## 2026-10-09：DSpark 改用 Plugin 0.4.0-dev

H100-149 的 `MiniCPMV4.7-1B-DSpark-gpu6` 已在原安装源切换为
`0.4.0-dev@e88e4db75ece36e482a5fcc288929d4461d53184`，安装版本
`0.4.0.dev0+ge88e4db`。使用该分支原生 NVIDIA Worker/V2 runner，
仅迁移 MiniCPM 模型扩展；vLLM 0.28.0 与 FlagGems 文件哈希保持不变。
33 项聚焦测试通过；eager 与独立缓存 `FULL_AND_PIECEWISE` 各完成 9/9
文本、单图及并发请求。health=200，服务为 `127.0.0.1:18348`，上下文上限 50000。
数数用例受到 128 token 客户端上限截断；eager/graph 有两条措辞差异，未证明逐 token 等价。

当前容器内启动器为 `/opt/flagos/dspark/start-model.sh`，SHA-256
`b7f21d0274b2810204cb03d21f3a5ad1ce2f3642fd8fa1b766c2d3778188c36c`。
宿主证据副本为
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/04-runs/dspark-plugin04-20261009/model-service-fresh/start-model.sh`。
Plugin 与启动器均在容器内部，不设 `PYTHONPATH`；新增 `VLLM_CACHE_ROOT`
用于隔离新分支的编译缓存。容器持续运行、restart_count=0。

下方数据集分数及人工复核结果属于旧 Plugin 0.3 环境；新分支完整精度、性能及
镜像打包验证未执行。完整迁移、源码审查及证据见[008](adaptation/008-dspark-plugin04.md)。

## 2026-10-08：独立 DSpark 试跑

H100-149 新容器 `MiniCPMV4.7-1B-DSpark-gpu6` 使用 GPU6、vLLM 0.28.0 和
容器内安装的 Plugin/FlagGems，主模型与 DSpark draft 已通过 eager 及显式
`FULL_AND_PIECEWISE` 功能验证。独立脚本 `/opt/flagos/dspark/start-model.sh`
实启后 health=200，文本/单图/4 并发共 9/9 请求完成，草稿接受 306/1386 token；
服务保持在 H100-149 的 `127.0.0.1:18348`，配置上下文上限 50000。
脚本 SHA-256 为 `42acfca5fb034d9cb89313d6babcb5e4d6e8d79c5518c9e6b8675049b21e1e2a`；
证据副本在远端 root 的 `04-runs/dspark-20261008/model-service/start-model.sh`。
原容器、既有服务及 root 级启动器未修改。

无 draft 对照 7/9 回答逐字一致，另两项措辞不同，未证明逐 token 等价。
未执行正式精度/性能、50K 长输入或镜像打包验证，不更改 `framework.yml` 的历史状态。
环境兼容修复、源码审查及完整限制见[007](adaptation/007-dspark-draft-service.md)。

随后按用户确认的贪心、32768 token 评测端配置完成指定数据集测量：
MATH500 **71.6%（358/500）**；MMLU-Pro 每科顺序前 50 题、14 科共 700 题，
原生得分 **40.0%（280/700）**。两项超时均为 0；长度截断分别为 41/20 条，
MMLU-Pro 有 90 条无效选项提取按原生规则计错。服务未重启并保持运行。
配置、逐科分数、缓存失败后的独立重跑及证据见
[测量记录](acceptance/dspark-math500-mmlu-pro-20261008.md)；本轮不代表正式精度验收。

## 2026-10-08：双模型共用代码

已在 `H100-149` 新容器 `MinicpmV4.7-unified-20261008` 安装共用 Plugin，按配置选择
1B dense / 35B MoE；不设置 `PYTHONPATH`。两模型均完成 TP2 eager 6/6、
`FULL_AND_PIECEWISE` 19/19 API 回归，正常 pytest 14/14、checkpoint 位置对照 8/8。
新容器继承 FlagGems 广播 mask 修复，整模验证不设置旧 attention 黑名单。
覆盖真实大图切片、变输入、多图、双帧视频和十并发；原两容器及现有服务未修改。
详见[整合设计](adaptation/006-unified-dense-moe-adapter.md)和
[共同功能验证](acceptance/unified-code-validation-2026-10-08.md)。
本轮不等同正式精度/性能验收，未升级 `framework.yml` 的历史状态。

随后从最终容器快照创建 `minicpmV4.7-1B-new` 和 `minicpmV4.7-35B-new`，
两容器保持运行，镜像内安装与 GPU 映射检查通过，未启动模型服务；
后续按用户要求补齐 `/data:/data` 并映射全部 GPU0–7，两个容器均经 PyTorch 核实识别 8 张卡。
见[新容器环境记录](environment/model-containers-2026-10-08.md)。

## 原独立容器的历史记录

下列描述及进程/脚本状态属于此前独立容器的各轮记录；新共用容器结果以以上链接为准。

目标为 `H100-149` 的 `MinicpmV4.7-1B` 容器、权重
`/data/models/MiniCPM-V-4.7/weights/1b` 和独立运行根
`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`。2026-09-28 已核实容器与
Host 映射并开始实施。文本和单图 eager 与 decode-full 最小推理已成功；
多图和短视频功能也已验证。full graph 受 GDN backend 限制，复杂输入的
canvas 位置等价性、正式精度和性能验收仍未完成。
当前运行的服务使用进程级 FlagGems cuDNN attention 过滤，见问题 003；
它由此前已验证的根级脚本启动。用户随后修改了磁盘上的 `start-model.sh`，
该版本仅通过语法检查，尚未实启且有端口与写入边界问题，见
[005](adaptation/005-launcher-minimality.md)。功能结果见
[功能与服务验证](acceptance/functional-validation.md)。正式精度、性能及原生
framework-check 回执仍待执行。
2026-09-30 按要求复核必要参数：此模型省略 `--enable-prefix-caching` 会实际关闭
前缀缓存，故保留它；其余参数用于固定服务身份、Plugin 实现、资源边界和图模式。
此前根级脚本合并端口检查与目录准备代码，删除三项冗余缓存变量及缓存目录预建；
容器内重装适配后 Plugin 后又删去 `PYTHONPATH`，由 48 行缩为 28 行。
当轮重新实启、缓存路径核对和文本/图片冒烟测试通过，详见
[005](adaptation/005-launcher-minimality.md)。

## 本轮结果与限制

默认 Python 导入曾命中安装目录中的空 namespace package；已在容器内从原
checkout 以兼容模式 editable 重装 Plugin，当前服务不需要 `PYTHONPATH`。
4.7 缺少独立架构注册和 canvas
位置桥接，已在 Plugin 中用模型专用 shim 实现，并修正参考实现与 vLLM
decode delta 的一位基准差；测试、文本、单图、多图和短视频功能均通过。
FlagGems 两个 cuDNN attention 注册函数在初始化视觉路径触发 CUDA 错误，
此前通过本服务进程过滤规避。2026-10-08 已独立复现两个入口的 CUDA illegal memory
access 并确认广播 mask stride 根因；修复已应用于容器实际安装的 FlagGems，
56 项新增与 4 项原有算子测试通过，原崩溃用例的 eager/graph 复验均通过。
已提交 [issue #6869](https://github.com/flagos-ai/FlagGems/issues/6869) 和
[PR #6871](https://github.com/flagos-ai/FlagGems/pull/6871)，详见
[003](adaptation/003-flaggems-cudnn-attention.md)。现有服务未重启，黑名单保留到整模去过滤复验。
GDN backend 使 full graph 请求降级，故首次服务采用显式 decode-full。
2026-09-28 用户要求后，现存服务及当轮根级 `start-model.sh` 均已切换到显式
`FULL_AND_PIECEWISE`，由当轮脚本实启后文本/图片 API 再次通过。
prefill 仍是 PIECEWISE，不记为 `full` graph 或正式验收通过；
切换和证据见 [004](adaptation/004-gdn-full-graph.md)。

`framework.yml` 使用当前 schema 允许的 `model_loading`，因为用户先选服务与
功能验证，正式精度计划和 framework-check 原生回执尚未冻结/生成；
这是流程状态，不否定旧脚本的实测功能结果。当前用户修改的脚本未实启，
须先处理 [005](adaptation/005-launcher-minimality.md) 中的安全与证据问题。
下一步在用户确定精度目标后，
按 profile 完成原生证据绑定、正式准确率，再决定性能验收；
同时验证 FlagGems 修复后的整模去过滤路径、复杂图片/长上下文和并行拓扑。

- [环境分析](environment/README.md)
- [适配问题索引](adaptation/README.md)
- [验收记录](acceptance/README.md)
