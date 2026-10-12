# 004：mx-59 的 Plugin 兼容分支更新

2026-10-10，按用户要求，将 mx-59 的 `qwen3.6-35B` 容器中的已安装 Plugin 更新到与
27B 相同的兼容分支。范围仅为适配阶段的局部版本迁移，不升级其他组件，不执行正式
整模精度、端到端性能或镜像打包。003 的性能数字属于此前冻结配置，不代表更新后的性能。

## 现场与版本

- Host/container 工作根均为 `/public-flash/jinghao/qwen3.6-35B`，同路径 RW `/public-flash`
  bind；另有 `/data` RW bind。`/workspace`、`/opt/conda` 没有 Host bind，修改的是容器内部
  实际 editable 安装源码，不使用 PYTHONPATH 或第二个 checkout。
- 容器 ID `6821737fcd966f3026820b1a5d6122125bc5faa0750313771b1a052ce7129867`；
  镜像 `flagos/qwen3.6-27b-metax:public-flash-20261008`，镜像 ID
  `sha256:f7b2d280fd5ae061db1d66d9707273969c4c8c9508cd4167d0e15a9b8e2c4957`。
  容器始终保持运行；镜像本身未更新。
- `/workspace/vllm-plugin-FL`：`675548ab2ee52b8124b0b6a82a2f795c0553e1fa` →
  官方 `origin/release/0.2@8b059122e32b9ac47b9820a9c7b1bb95077481a4`。
  经用户授权的临时代理 fetch 成功，认证信息未写入 Git 配置、日志或本地模型记录。
  采用兼容 vLLM 0.20.2 的 release/0.2，而不是依赖 vLLM 0.24.0 的当前 main。
- 同一 `/opt/conda/bin/python3.12` 环境重新 editable 安装：
  `pip install --no-index --no-deps --no-build-isolation -e .`；未重装依赖或构建 CUDA 扩展。
  安装元数据从 0.2.0 更新为 `0.2.2rc2.post1+g8b059122e.d20261010`。
  TMP 使用已验证安装树的标准 ignored `build/mx59-upgrade-20261010`，避免此前 27B 已确认的
  `/public-flash` setuptools copy2 I/O 问题，不复制源码绕过安装。
- FlagGems 保持 `c6f46cc970ea0bef8927ee657c021bd8621e3bb0`；
  FlagGems-vLLM 保持 `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777`；
  vLLM 保持 `bc150f50299199599673614f80d12a196f377655`。
  三者 HEAD/status/default diff SHA 均与入场一致；FlagGems-vLLM 的 13 个 modified/untracked
  文件另经逐文件 SHA 复核，没有按 27B 的 FlagGems revision 覆盖 35B。

## 更新与保留的职责

上游 release/0.2 的 MetaX vendor attention `fa_utils.reshape_and_cache_flash` 直接绑定
`vllm._custom_ops.reshape_and_cache_flash`，由当前环境的 mcoplib 原生注册提供 CUDA kernel。
这里仅改变 vendor attention 的 KV cache 写入入口；既有 FlagOS attention backend 自己的
FlagGems cache 路径和 Flash Attention 算法接入未重做，不能推断所有 attention 都改用原生。

原树 9 个 tracked 修改和 8 个 untracked 文件已先备份 tar、binary diff、逐文件 SHA，
再保留 stash 并在同一安装树切换 frozen commit；不是 fast-forward，没有使用 reset/强制覆盖。
stash apply 在 `flaggems.py`、`register_ops.py` 的相邻 cache/GDN 区域发生两处冲突。
人工核对后只删除上游已移除的 14 行 cache 方法和 14 行注册块，完整保留 35B 自己的
GDN prefill/decode、paged state/layout、黑名单回退、MoE 完整入口与 caller workspace 逻辑。

release/0.2 同时删除了原 worker 的 vLLM 0.20 KV config list 解包及 current-config context。
本环境仍是 vLLM 0.20.2，所以将原兼容段保留在 Plugin worker，没有改 vLLM。
该 worker 文件和原备份逐字节相同。新 HEAD 相对上游的 worker diff 包含此兼容段，
不应误认为全部都是本轮新功能。

备份内容对照验证 17/17：15 文件逐字节相同，两个 cache 文件恰好为“原文件减去官方删除块”。
已验证删除块能从旧官方文件重建新官方文件，再比较继承内容；未只凭 HEAD 推断补丁保留。
没有新增产品抽象、旁路 dispatch、修改默认 GDN 选择或跨平台注册条件。
现有 GDN 安装 hook 仍在 `patches/gdn_linear_attn.py`，由 worker 加载模型时安装。
未提交、推送、创建 PR 或删除 stash。

保留的 stash OID 为 `eecc60196c87a24da15c7ae752a1f547a0142f8c`；逐文件保留回执
`02-issues/plugin-upgrade-mx59-20261010/preservation-result.json` 的 SHA256 为
`90ce688f0d4934ad34abf2dd7dfc643801a9b489e213de8390b11bf010998f0d`。
最终 Plugin binary diff SHA256 为
`c88e54dbcb37cd556d04017da80d1e2bee78eb39cb7e520258927d7a2ee3fd3d`；
仍为 9 个 tracked 修改、8 个 untracked 文件，无冲突或暂存变更，17 文件保留对照再次通过。
FlagGems-vLLM default diff SHA256 `83c205c8e9176feb8115768e68896157d95e64274162c5bb10c3b31d6d79d538`，
vLLM default diff SHA256 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d` 均未变。

## 已完成局部回归

- Plugin `tests/unit_tests/dispatch`：293 passed，包含平台隔离、策略、MoE 契约、packed GDN
  的黑名单/native 回退、caller buffer 和有状态错误传播；mock 选择测试不冒充设备计算验证。
- 未修改的已安装 FlagGems-vLLM：MoE workspace、paged GDN 两个测试文件共 147 passed，
  包含真实设备 FP32 对照、caller ownership、非法布局及两次变输入 graph replay。
- Plugin 实际 MoE/GDN/layout functional：23 项全部通过，包含完整/分阶段 MoE、GDN
  prefill 与动态 varlen metadata、连续/strided/padded state 的 eager 与变输入 replay。
- 原生 KV cache：8/8 实际 GPU 用例通过；FP16/BF16、连续/strided K/V、block16/1056，
  TP2 实际每 rank 一个 KV head、head_dim256，包含负 slot 和跨页边界、eager 与每例两次
  变输入 replay。断言 native CUDA kernel 存在、函数 identity 为 vLLM native，而非空 schema。
  使用现场 GDN/attention 黑名单验证 vendor 选择，cache 不再依赖 FlagOS cache op 注册。
- 算子/契约检查合计 471 项；TP2 BF16 真实模型诊断服务启动通过，使用现场黑名单，
  显式 prefix caching/align，FULL_AND_PIECEWISE/capture64，实际 attention page1056。
  日志记录 mixed PIECEWISE 11/11 和 decode FULL 11/11 capture 完成。
  四个短请求全部 HTTP200、finish_reason=stop，实际答案分别为 `2`、`21`、`北京`、`Paris`；
  不是仅检查 HTTP 状态，也不据此宣称正式整模精度通过。

第一次逐文件校验 helper 在提取 `git diff -U0` 删除行时失败：Git 将相同 OpImpl 末尾字段
与上一注册对齐，得到非完整块。修正为按官方完整接口块提取，并独立证明旧→新官方内容一致；
不是产品源码或算子数值失败。初次失败与修正后的回执均保留。

## 服务生命周期与边界

入场时实际 API 为容器 PID614490/startticks455072767、GPU4/5、TP2 BF16、port8010、
名称 `qwen36-35B-begin`、mem0.9、FULL_AND_PIECEWISE/capture64，无显式 batch 参数。
现场 `start-model-flagos.sh` 关闭 prefix cache，黑名单为
`gdn_prefill,gdn_decode,mm,mm_out,copy,copy_,linear,attention_backend`；它不是 003 的
8192/无黑名单/prefix-align 优化 launcher。入场 metrics running/waiting 均0，校验 PID/startticks、
完整模型命令与 idle metrics 后，仅停止该 API 并确认其所有已冻结子进程退出。

本轮不更改 Host `start-model-flagos.sh` 或内部 `/opt/flagos/qwen3.6-35b/start-model.sh`。
Host 的 `start-model.sh` 入场已不存在，不自动重建。模型短样例用独立 port18010、
GPU4/5，显式 prefix caching/align 验证；完成后仅停止该诊断 API/子进程，再以原现场
argv 和必要环境恢复8010服务，保留用户的 prefix-disabled 性能配置及黑名单。

收尾实际 API **PID711159/startticks455845150**，完整 argv 与原 API 逐项一致，
原 CUDA/FlagGems/Plugin 环境逐项一致；仅增加不写 bytecode 的环境保护，不引入 PYTHONPATH。
实际 import 仍分别位于原 `/workspace/vllm-plugin-FL`、`/workspace/FlagGems`、
`/workspace/FlagGems-vllm`、`/workspace/vllm` 的安装源码。Host/内部两个原 launcher SHA 均未变。
HTTP health200、models 名称 `qwen36-35B-begin`、running/waiting均0，容器仍 running。
新服务的本轮启动日志保存在
`04-runs/plugin-upgrade-mx59-20261010/updated-original-service.log`，没有覆盖原 `service.log`。
这是保留用户现场性能配置的恢复，不宣称当前启用了 FlagOS GDN 或继承 003 的端到端收益。

首次收尾命令的 YAML flow argv 将未加引号的 `CUDA_VISIBLE_DEVICES=4,5` 拆成两个参数，
docker exec 在进程启动前报 `exec "-e" not found`，实际校验脚本未执行，未修改产品或服务。
修正为单个引号字符串，增加目标容器完整 ID guard；最终校验成功。
该失败回执保留于 `finalize-command-v1-failure.txt`；7 个本轮临时 playbook、4 个 Python
脚本与 9 个 Docker argv 的本地结构/目标检查通过，不把它们混入模型目录。

## 证据与未验证范围

以下相对批准工作根，完整日志、测试代码和 native 产物不进入本地模型目录：

- `02-issues/plugin-upgrade-mx59-20261010/`：官方 diff 审查、原/新 Plugin diff/status、
  17 文件备份/逐文件保留回执、其他组件 diff/hash/untracked、launcher SHA、stash OID。
- `04-runs/plugin-upgrade-mx59-20261010/`：pip、dispatch/library/native-cache/functional
  测试日志、helper 初次失败、服务租约/停止证明、图捕获日志、请求与最终结果。
- `05-tmp/plugin-upgrade-mx59-20261010/`：本轮精确 PID 生命周期控制与校验过程脚本；
  不进入最终生产 launcher，也不放入产品源码。

设计审查结论：兼容版本更新及现有局部补丁迁移可用于所声明 mx-59 环境；共享 worker
compat 属于保留的 workaround，跨版本移除需另行验证。没有实际其他平台硬件、其他模型、
量化/LoRA整模、多 token/speculative/KDA、正式整模精度、新版本端到端性能或 fresh-image
证据。框架五阶段继续 not_started，本轮不构成完整适配验收或 optimized 状态。

本地 `./scripts/syntax-check --offline` 的 workflow 252 项（1 skip）、operations 6 项及
13 个 shell/13 个既有 playbook 检查通过；最后 audit 仍有 12 个其他模型 profile revision
错误和 78 个历史问题，未改无关文件，不称全仓通过。无参数 syntax-check 在本机旧 Bash
的空数组 nounset 处失败，保留该限制，没有扩展本轮范围修复管理工具。
