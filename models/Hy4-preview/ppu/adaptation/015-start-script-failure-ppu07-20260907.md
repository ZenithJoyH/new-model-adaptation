# 015：PPU-07 hy4 启动脚本报错

## 元数据

- 状态：`fixed-focused-verified`
- 首次出现时间：2026-09-07（用户报告，准确时间待核实）
- 最后验证时间：2026-09-07
- 模型：Hy4-preview
- 平台与 Host 别名：PPU / `PPU-07`
- 容器名称与镜像：`hy4`；`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`
- Plugin / FlagGems / vLLM revision：当前可编辑 Plugin `/workspace/vllm-plugin-FL` 由基线 `795f7c9a3b0c6a05b02b5b22b8e15e0e4b3fa0b2` 提交为 `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`；FlagGems / vLLM 本轮未改动
- 执行模式与负载：`FULL_DECODE_ONLY` graph，TP16，`max-model-len=100000`；错误发生在模型加载前

## 问题现象

- 错误签名或症状：`hy4-preview.log` 末尾是 `ModuleNotFoundError: No module named 'vllm._C_stable_libtorch'`，但直接调用 Plugin 平台入口捕获到更早的 `RuntimeError: Incomplete T-Head native extension bundle`，缺 `_C_stable_libtorch.abi3.so`、`_C.abi3.so`、`_moe_C.abi3.so`。
- 发生顺序：Plugin `register()` → `_patch_custom_ops()` → `register_op_schemas()` → `initialize_native_extensions()` → `load_all_native_extensions()` 因缺少三个 SO 失败；vLLM 平台发现第一轮吞掉该异常，随后选中内置 CUDA 平台，才产生末尾的二次错误。
- 影响范围：服务在模型加载前退出；容器仍运行，8010 未监听。
- 精简证据及原始证据位置：`/mnt/nfs/users/jinghao/hy4-preview/hy4-preview.log`；当前可编辑安装指向 `/workspace/vllm-plugin-FL`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| `docs/troubleshooting/distributed-sample-tokens-timeout.md` | 若日志出现 TP worker / EngineCore timeout 可能相关 | 当前尚无完整错误签名 | 低 | 仅在出现条目规定的完整连续症状时才复用 |
| `005-gpqa-corruption-triage-20260904.md` | 同 Host、容器、脚本和服务路径 | 历史记录是数值/输出问题，不是本次启动报错 | 中 | 用作历史基线，不直接套用根因 |

## 诊断与假设

已验证事实：本地运行配置将目标限定为 `PPU-07` / `hy4`，宿主与容器工作根均记录为 `/mnt/nfs/users/jinghao/hy4-preview`；适配阶段 `--check-only` 通过。

已验证：当前 `/workspace/vllm-plugin-FL/vllm_fl/dispatch/backends/vendor/thead/lib/` 原先只有 `PROVENANCE.md`；三个 SO 被 `.gitignore` 明确忽略，`pyproject.toml` 的 package-data 仅包含 dispatch YAML。因此新 checkout / 普通可编辑安装不会自带运行时强制要求的原生库。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 命令或准确位置 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 无（只读连通性） | 未核实 | 不改动现场 | `./scripts/connectivity-check --limit PPU-07` | 控制端 Ansible `Local RPC server did not start`，未触及远端；后续直接 SSH 连通 | 该工具异常与 hy4 故障无关 |
| 2 | 无（只读现场取证） | 用户报错 | 不重跑启动脚本 | `ssh PPU-07` 后只读核实容器、挂载、脚本内容、现有进程/端口和日志 | 容器运行，失败后无 vLLM/API/Engine worker，8010 未监听；日志显示平台初始化失败 | 排除端口冲突和已有服务干扰 |
| 3 | Plugin import 路径 | `/workspace/vllm-plugin-FL` 缺 SO，平台注册失败 | 仅在独立 Python 进程中将 `PYTHONPATH` 指向含完整 SO 的工作根副本 | 不启动服务，调用 `vllm_fl.register()` | 返回 `vllm_fl.platform.PlatformFL` | 缺 SO 与平台注册失败有直接因果 |
| 4 | 补齐原生库 | 三个 SO 缺失 | 用户执行 `cp -r /mnt/nfs/users/jinghao/lib/*` 到 Plugin `lib/` | 用户操作 | 启动脚本可执行 | workaround 有效；不等于可重现交付问题已修复 |

## 根因

- 已验证根因：T-Head bootstrap 未区分“可选 native bundle 文件缺失”与“ABI/依赖损坏”，将前者作为宽泛 `RuntimeError` 逃出 vLLM 平台探测，导致 PPU Plugin 未激活。SO 未被 Git/打包交付是触发条件和独立交付缺口。
- 次要可观测性问题：vLLM 平台探测将 Plugin 首次异常吞掉，误导为内置 CUDA 扩展缺失。

## 解决方法或 Workaround

- 用户已手工复制三个 SO 作为 workaround；目标文件 SHA-256 与 `PROVENANCE.md` 及 `/mnt/nfs/users/jinghao/lib/` 中源文件完全一致。
- 长期修复应在镜像/发布构建中交付完整 bundle 并校验大小、SHA-256、Torch/PPU SDK/vLLM ABI，而不是依赖启动前手工 `cp`。
- 本次授权修复的重复形式：在 `/workspace/vllm-plugin-FL` 仅修改 T-Head
  bootstrap/native loader 与对应 focused 测试；保留用户既有 `pyproject.toml`
  修改和 ignored SO。先对基线 HEAD `795f7c9a3b0c6a05b02b5b22b8e15e0e4b3fa0b2`
  执行变更前测试，部署前用单主机 Ansible `--check --diff`核对，再执行
  `python -m unittest tests/dispatch/test_vendor_bootstrap.py`、缺 bundle fresh-process
  注册和完整 bundle runtime 检查，最后仅暂存本轮三个文件并提交。
- 实现：`native_extensions.py` 以 `NativeExtensionBundleMissingError` 精确分类文件缺失；`bootstrap.py` 仅捕获该异常，每组缺失路径只 warning 一次并继续 FlagGems/reference fallback schema。其他原生加载异常仍传播。
- Plugin 路径与提交：`/workspace/vllm-plugin-FL`，`d56f7b285af2b3dd735847cb6d5a30f29beccfb8` (`fix(thead): fall back when native bundle is missing`)。仅提交三个目标文件；用户后续明确要求不保留 `pyproject.toml` 修改，已从 HEAD 恢复并验证 tracked worktree 干净；SO 仍 ignored。
- 远端推送：2026-09-07 通过本机已认证的 GitHub 身份做非强制快进推送；`github.com:ZenithJoyH/vllm-plugin-FL.git` 的 `refs/heads/support-hy4-preview` 已由 `795f7c9a3b0c6a05b02b5b22b8e15e0e4b3fa0b2` 更新至 `d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，并以 `git ls-remote` 独立核对。
- 审查补丁留存：`/mnt/nfs/users/jinghao/hy4-preview/03-issues/015-start-script-failure/hy4-native-bundle-warning.patch`，初始部署补丁 SHA-256 `03cb11e3c89bc05aa4d119262f41545b68db2c6cf10b70f0e964f16bc7b89115`；最终提交另含一处 `Path` 类型一致性修正，以 commit 为准。
- 服务停启操作及核对结果：无。
- vLLM 未修改证明：本轮诊断未修改 vLLM；未对当前 vLLM 工作树做完整身份收据。

## FlagGems 证据

- 本轮未定位到 FlagGems 缺陷；问题在 Plugin 原生依赖交付链路。

## 验证结果

- 无 SO 时，独立调用平台入口稳定复现 `Incomplete T-Head native extension bundle`。
- 仅将 import 路径指向含完整 bundle 的同代码副本后，`vllm_fl.register()` 返回 `vllm_fl.platform.PlatformFL`。
- 用户补齐三个经哈希核对的 SO 后，报告启动脚本已可执行。本轮未独立宣称完整模型服务或验收通过。
- 变更后 unittest 与 focused pytest 均 `9 passed`；`git diff --check` 与提交后 `git show --check` 通过。Ruff 未安装，未自动安装。
- 缺 bundle fresh-process 负对照：只输出一次明确 warning，portable schema 已注册，最终 `MISSING_BUNDLE_FALLBACK_OK PlatformFL thead`，未再落入 CUDA。
- 完整 bundle 正对照：`NON_PPU_IMPORT_ISOLATION_OK` 和 `PPU_EARLY_SCHEMA_AND_IDEMPOTENCY_OK`，早期加载顺序、幂等与真实 CUDA-dispatch kernel 保持。

## 限制与下一步

- 尚存限制：手工复制文件不会被 Git 发现，新 checkout、镜像或 wheel 仍会复现；且三个库来自固定的 Torch 2.10 / PPU SDK 2.1.0 / vLLM 0.23 镜像，必须保持 ABI 门禁。
- 后续动作：独立处理可重现的 bundle 交付与安装前哈希/ABI 校验；如需将本 focused 修复升级为整体适配证据，还需在真实缺 bundle 部署上运行最小服务及 graph sanity。
- 对 `environment/plugin-change-review.md` 的设计审查结论及 PR 范围的影响：构成交付/发布阻塞；PR 需明确 SO 由镜像、wheel 还是安装期 bootstrap 所有，并加入哈希与 ABI 回归。

## 经验沉淀

- 是否可跨模型或平台复用：可复用于依赖外部原生库的其他 PPU 模型，不推广为其他硬件平台结论。
- 知识库处理状态：`local-only`
- 候选知识库条目：暂无。
