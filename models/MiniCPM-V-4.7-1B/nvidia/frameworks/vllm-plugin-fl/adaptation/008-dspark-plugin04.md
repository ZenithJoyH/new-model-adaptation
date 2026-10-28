# 008：DSpark 切换至 Plugin 0.4.0-dev

## 范围与问题

2026-10-09，用户明确要求 vLLM 0.28.0 使用官方 Plugin `0.4.0-dev` 分支。
此前 DSpark 容器继承 `support-minicpmV4.7@aa4228e`（0.3.0 系列），
并添加了临时 0.28 兼容代码，版本基线不符合此次要求。

- Host：`H100-149`。
- 容器：`MiniCPMV4.7-1B-DSpark-gpu6`，ID
  `8645e61dddfaac3712ec27afaa1efce8b008e9f6f24a263a9e6380dce43cb640`。
- `workspace.roots`：host root `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos`
  映射 container root `/work`；本轮已核对实际 bind mount、RW 与容器持续运行状态。
- 唯一 Plugin 产品目录：容器 editable 安装的 `/vllm-workspace/vllm-plugin-FL`。
- 目标：`flagos-ai/vllm-plugin-FL` 的 `0.4.0-dev`，当前 SHA
  `e88e4db75ece36e482a5fcc288929d4461d53184`；本地及 H100-149 经授权代理
  `git ls-remote` 均得到该值。
- 保持 vLLM 0.28.0 安装只读，保留 FlagGems 既有安装及修复。
  原普通模型容器及其启动器不属于本次变更对象。

## 迁移计划与职责

已阅读目标分支 README、NVIDIA 使用指南、dispatch 文档、测试入口，
并检查 `NvidiaPlatformFL`、`NvidiaWorkerFL` 与 runner 选择契约。
该分支已原生提供 CUDA 平台语义、0.28 MoE 接口、V2 runner 和 DSpark workspace 支持。
迁移采用其公共实现，不带入旧平台/Worker/MoE/Qwen 注册兼容补丁。

MiniCPM-V 4.7 尚无目标分支注册，拟仅迁移模型专用 shim、正式 registry 注册及维护测试：
复用上游 4.6 视觉处理、原生 Qwen3.5 backbone，保留 4.7 canvas M-RoPE、
merger packed 权重映射与 DSpark 隐藏态接口。影响范围为该模型架构；
正常注册流程应幂等，已有 Qwen/其他模型注册保持目标分支行为。

验证顺序：安装身份/注册 → 聚焦契约与已有 runner 测试 → eager 文本/图片 →
FULL 能力复核与最终图模式文本/图片/变输入并发 → 启动器实启及组件哈希复核。
本次不启动新的完整数据集评测；此前 MATH500/MMLU-Pro 结果只证明旧 Plugin 环境。

## 保存与当前状态

本轮证据使用远端 `01-environment/dspark-plugin04-20261009/`、
`02-issues/dspark-plugin04-20261009/`、`04-runs/dspark-plugin04-20261009/`。
临时 Git 工具置于批准的 `05-tmp/dspark-plugin04-20261009/git-runtime/`，
仅用于操作原容器的同一 checkout，不安装系统包、不创建第二份源码仓库。
代理凭据仅在下载进程环境中使用，不写入 Git 配置、启动器或证据文件。

旧工作树 6 个已修改文件、2 个新增文件已保存为独立补丁、选定文件归档及 Git stash
`ce883d726c137b2763dee54d7c10aac6c6f69987`，没有丢弃原改动。
随后在同一 checkout 创建并跟踪 `0.4.0-dev`，HEAD 为上述官方提交。
安装使用 `pip install --no-build-isolation --no-deps -e`，构建版本标识为
`0.4.0.dev0+ge88e4db`；该标识用于绑定本轮分支源码，不是上游正式发布标签。

当前差异仅有 `vllm_fl/__init__.py` 中的幂等模型注册、新增模型 shim 和三个模型测试。
shim 与 backbone 测试直接使用 vLLM 0.28 原生 Qwen3.5 类。
旧 `worker_v2.py`、`models/qwen3_5.py`、`patches/qwen3_5_text.py` 均不再存在。

- 模型 backbone/canvas/DSpark 契约与目标分支 NVIDIA/runner 聚焦测试：33/33 通过，
  原生入口 `python3 -B -m pytest`；另有 4 个非本轮选择项未运行。
- 独立进程模型注册两次，目标条目身份不变、其他既有模型注册不变；
  平台实际为 `vllm_fl.nvidia_platform.NvidiaPlatformFL`，Worker 继承原生 GPU Worker，
  backbone 模块为 `vllm.model_executor.models.qwen3_5`。
- 安装后 vLLM/FlagGems 全部 `.py/.so` 文件哈希与本轮 baseline 一致；
  导入路径仍为核实的容器安装目录，没有 `PYTHONPATH`。
- 已核实旧 API 12778/Engine 13319 及其唯一进程组，在无运行/等待请求时 SIGTERM；
  全部非僵尸进程退出，容器持续运行。随后启动新 eager API 15725。

证据：`baseline.json`、`branch-switch.json`、`installed-plugin.json`、
`state-after-install.json` 位于本轮 `01-environment` 目录；`unit.log`、
`unit-result.json`、`registration-result.json`、`stop-old-service.json` 位于本轮 `04-runs`。

## 服务验证与缓存隔离

Eager API 15725/Engine 16605 完成既有固定请求 9/9，包含 5 个顺序请求与 4 个并发
文本请求。翻译为“苹果”、乘法为“84”、纯红图识别为“红色”；数数用例受客户端
128 token 上限截断，不能宣称完整答题正确。请求 JSON 与旧固定用例完全相同。

本轮复核未修改的 `gdn_attn.py`：`GDNAttentionMetadataBuilder._cudagraph_support`
仍为 `UNIFORM_BATCH`。结合 007 的实际 FULL 自动回退证据，确认原阻塞仍适用，
采用已选定的 `FULL_AND_PIECEWISE`，不重复执行已证明不支持的全 prefill FULL。
具体依据、作用域、未解决能力及重试条件保存于 `graph-capability.json`。

首次通过容器内启动器启动的 graph API 18086/Engine 18636 已完成 9/9 请求，
捕获 target PIECEWISE 6 档、FULL decode 3 档、DSpark FULL 3 档。
日志显示复用了旧运行目录的 AOT 编译缓存，因此保留该轮证据并在完成请求后仅停止
对应进程组，改用新建空目录 `/work/06-cache/dspark-plugin04-20261009/vllm` 重新实启。
最终脚本增加 `VLLM_CACHE_ROOT` 的理由是绑定新分支编译来源并保全旧缓存。
其余模型参数与 FlagGems 缓存保持原配置；日志/operator-list 指向新的运行子目录。

最终启动器仍为 `/opt/flagos/dspark/start-model.sh`，独立缓存版本 SHA-256
`b7f21d0274b2810204cb03d21f3a5ad1ce2f3642fd8fa1b766c2d3778188c36c`，
`bash -n` 通过，证据副本位于本轮 `04-runs/.../model-service-fresh/start-model.sh`。
2026-10-09 02:48:53 UTC 最终核验：API 19415 / Engine 20619，health=200，
模型 ID 正确且服务上限 50000，容器保持运行、restart_count=0。
独立缓存下 target PIECEWISE 6 档、FULL decode 3 档、DSpark FULL 3 档均捕获完成；
前缀缓存开启，API 环境无 `PYTHONPATH`。固定请求 9/9 完成，苹果/84/红色检查通过；
顺序与并发的两个数数回复均触及 128 token 客户端上限，保留该限制。
本组 99 次 draft、1386 个 draft token、306 个 accepted token（22.08%）；
该计数仅证明本组 DSpark 实际执行，不代表性能或一般接受率。

独立缓存 graph 与首次复用缓存的 graph 9/9 回复逐字一致；与本轮 eager 7/9 一致，
差异均为天空解释的措辞（顺序和并发各一次）。没有定位 eager/graph 逐 token 差异根因，
不宣称两种执行模式逐 token 等价。独立缓存验证用于固定源码编译来源；本组没有观察到
更换 AOT 缓存目录后的回复变化。

最终 `.py/.so` 清单与安装后清单一致，vLLM/FlagGems 全文件哈希仍与 baseline 相同。
安装组件及启动器均在容器内部，不属于宿主 bind mount；镜像打包及 fresh-image 验证未执行。
最终启动器保留一个新增 `VLLM_CACHE_ROOT` 以隔离分支 AOT 缓存，其他参数的用途继承
007 中的必要性说明；脚本没有安装、补丁、探针、评测、自动杀进程或性能专用关缓存参数。

- 最终核对：`04-runs/dspark-plugin04-20261009/model-service-fresh/final-verification.json`，
  SHA-256 `afb6b4258005db380ed9fbc6657e411ca94242ffdcc2d60f24d72c439d75d077`。
- 最终源文件身份：`01-environment/dspark-plugin04-20261009/state-final.json`，
  SHA-256 `7be4b9142e1ac5d29576dbe85cc5d65f7656f92fdc2d217ea25dc51f60e99832`。
- 完整 source review：`02-issues/dspark-plugin04-20261009/source-review-final.json`。
- 28 项固定证据清单：`04-runs/dspark-plugin04-20261009/evidence-manifest.json`，
  SHA-256 `323b4b7d08fd2f8c292693d9a8570410be2d8e0147a23ea420c339fa4e133d77`。
  清单使用固定启动日志摘录，运行中的 `server.log` 不作为固定哈希证据。

相对目标分支的完整补丁（含新增模型/测试）为本轮 `02-issues/.../candidate-final.patch`，
SHA-256 `cfe13ea5e046134fd6b0ea12dd36d14585b3c1650e410435f522dbd0461aeefd`。
基线公共实现属于上游目标分支，本轮仅增加一个幂等懒注册、一个模型文件和三个维护测试；
尚未提交、推送或创建 PR。33 项与真实 eager 结果支持本 H100/BF16/TP1 范围；
35B MoE 整模、多 GPU、其他平台未执行。本轮保留的 CUDA13/Triton3.7.1 环境与
分支文档的 CUDA12.9/FlagTree 提供 Triton3.6 基线不同，不宣称完整匹配其 CI 镜像。

当前状态：分支迁移、33 项聚焦回归、eager 与独立缓存 graph 功能和最终启动器实启完成。
服务保持在 `127.0.0.1:18348`。新分支完整精度、性能及镜像验证未执行；
此前 71.6%/40.0% 与人工复核 45.57% 均仍属于旧 Plugin 环境。
不更新历史 `framework.yml` 或宣称正式适配完成。

本地布局审计仍报告 12 项既有 profile revision 错误及 78 项历史警告，
其中本框架为 revision 变化；未重绑旧验收，不记为审计通过。
本次记录未引入布局问题；本框架范围 `git diff --check` 无输出。

后续 2026-10-09 按用户要求完成 128 客户端并发指定数据集测量：
MATH500 72.4%、MMLU-Pro 14 科各 50 题原生 42.0%；服务与组件身份前后相同。
这补充了新分支精度测量，未升级正式验收或性能状态；
详见[新测量记录](../acceptance/dspark-c128-plugin04-20261009.md)。
