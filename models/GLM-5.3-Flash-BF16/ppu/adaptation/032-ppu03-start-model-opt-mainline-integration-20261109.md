# 032：PPU-03 的 start-model-opt 主线集成修复

## 元数据与范围

- 状态：`resolved`，仅限用户指定脚本的启动与代表性推理功能修复；开始于 2026-11-09，最终核验于 2026-11-10 01:48:47 CST。未完成正式精度或性能验收，不提升历史适配状态。
- 后续 PR 范围收敛版本为 `1597b9e6`，并在正式 CI 发现上下文查询回归后追加修复至 `9ea4bec2`，现为 Ready for review。范围测试与 PPU prefill 数值/图验证通过；未重启当前服务来复测新树的整模型启动。前述 `resolved` 和 TP16 响应只对应原启动修复版本，不能移用到此新树，详见末节。
- 用户指定 Host：`PPU-03`；容器 `glm5.3-flash`，ID `e154be78a8f847655ce575f13746c674d68a740023c0a909f173c588e9ac4220`。
- Profile：隐式 `vllm-plugin-fl`。这是 PPU-03 的启动修复记录，不沿用或提升 `platform.yml` 中 PPU-13 的历史验收状态。
- 宿主机与容器工作根均为 `/mnt/nfs/users/jinghao/glm5.3-flash`；核验 `/mnt:/mnt` 可写映射，容器持续运行、restart count 为 0。
- 用户指定入口为 `start-model-opt.sh`。第四次启动前 SHA-256 为 `8fdae3f4f200be2e46d9c8a3120380181961844c5125b1e9bda771847fa22bdb`；第五次启动仅删除失效的 FlagGems 数据库 export，新 SHA-256 为 `6c2f2bdb47e09b999c8375fdb3262bd422d03a04fc2eb71d91cfdbf38264bf38`。TP16、BF16、80K、seq64、port8011、`FULL_DECODE_ONLY` 及关闭 prefix caching 均来自用户指定脚本；本任务不执行正式精度或性能验收。
- Plugin editable 源：`/workspace/vllm-plugin-FL@7cd610c96b2c44291e843833cf94e1578f2b4e5a`，本轮修改前干净。FlagGems `9c1046e19` 本轮开始时干净；FlagGems-vllm 构建源 `93fd1b0c` 保留上一轮四文件导入隔离修复，实际普通安装位于 `/usr/local/lib/python3.12/site-packages/flaggems_vllm`。

## 已验证问题与受控尝试

| 证据 | 已验证根因 | 最小修复与结果 |
|---|---|---|
| 用户原 `service.log`，已备份为 `02-issues/start-model-opt-repair-20261109/service-before.log` | spawn 只传递 CUSTOM 枚举，进程内仍注册旧默认 prefill 类；原 adapter 未遵循算子库开关 | 仅对 GLM 的已知 Plugin 默认 CUSTOM 类重新绑定；保留外部 CUSTOM 和其他显式枚举；prefill 依照现有开关调用公开 API。7 项接线回归通过。 |
| `04-runs/start-model-opt-repair-20261109/attempt01/service.log` | general plugin 先注册 PR 的 `models.glm5`，随后又调用旧 `apply_glm5next_patches`，覆盖模型及 config 类，引出旧 API 缺失 | 删除重复注册调用及其 import，保留旧模块和其他模型注册。独立进程连续两次注册验证文本/VLM 两个入口及 config 所有者。未为未使用的旧 API 添加兼容实现。 |
| `04-runs/start-model-opt-repair-20261109/attempt02/service.log` | GLM 私有 KDA 适配器仅提供 FlagOS ABI，但继承 vendor-only 平台默认策略 | 通过既有模型激活计划为 causal conv / chunk KDA 指定 FlagOS；不改全平台 YAML，显式用户策略仍由原 policy 优先级处理。 |
| `02-issues/start-model-opt-repair-20261109/glm-regression.log` | 共享 `mhc_post` 的纯张量 ABI 混入含 CustomOp 状态参数的模型绑定，导致 5/4 参数冲突 | mHC 的模型绑定关闭 shared builtins；兼容共享 ABI 的 clamp 继续沿用 shared binding。原异常传播回归无需削弱，修复后通过。 |
| `02-issues/start-model-opt-repair-20261109/mhc-gpu-tests.log` 与 `07-bugs/mhc-post-optional-compiler-knob-20261109/before.log` | FlagGems-vllm 的 mHC post 无条件访问当前 Triton 3.5 没有的 `autotuning.adjust_block_size` | 仅在选项存在时临时设置，并在 finally 恢复；用算子库既有 vendor 身份选择相同 PPU kernel。独立公开 API 修复后通过；算子库最终 14 项通过；Plugin 的 pre/post/fused-post-pre/clamp 四项真实数值、Inductor 与变输入图回归通过。4 个 NVIDIA 原生参数未执行，不声称 NVIDIA 硬件验证。4 个 kernel/reference 定义 AST 未改。 |

| `attempt04/service-final.log` | 权重加载完成后，视觉 profile 的 ATen linear 首次持久化调优数据，脚本硬编码不存在的 `/opt/glm53-flash/flaggems`，触发 SQLite unable to open database file | 仅移除旧 Triton 3.6 DB export，使用已存在的当前 3.5 默认目录；实际 SQL `SELECT 1` 通过。不伪造调优数据库，不改 FlagGems 代码。第五次启动使用修改后的同一入口。 |

| `attempt05/service.log`、`attempt05/stop.json`、`07-bugs/ppu-narrow-fp32-mm-20261109/compile.json` | 完成图编译后，实际 profile 的窄列 FP32 矩阵乘触发过大的通用调优候选，16 个编译器对单个候选持续超过 15 分钟，HTTP 未就绪 | 仅在 FlagGems PPU 后端为有效、无重叠、稠密 FP32 的窄列 `mm/mm_out` 复用相同 IEEE kernel，使用厂商目录中的三个小块候选和独立调优缓存；不改共享 kernel、其他 dtype/布局/平台。已保存慢编译输入，仅 SIGTERM 停止本次服务树 51 个进程，容器不重启。 |

## 验证与源码边界

- 第六次启动已越过 FP32 长编译，完成模型 profile 后在采样器温度缩放失败：生成的通用 `true_divide_` 硬编码 `torch.gcu.current_device()`。证据为 `attempt06/service-final.log` 与 `07-bugs/true-divide-device-stream-20261110/before.log`。
- 曾尝试修复生成 wrapper 的 host/缓存，107 个小尺寸与元数据用例通过，但实际 `[64,154880]` 的 GCU 风格大块仍编译超过 5 分钟；实验已撤回。通用 `ops/true_divide_.py` 恢复至 HEAD 字节，实验 patch/测试保留在 issue 的 `experiments/`，不属于最终产品 diff。
- 最终通过 PPU backend 两个既有公开别名复用 `flag_gems.ops.div.true_divide_` 的标准 pointwise/LibEntry 实现；补齐原地整数/复数写入实数、非法广播的前置报错契约。无新增数值 kernel，无执行后异常重试。`fg-div-portable-tests-final.log`：123 passed，包含 117 个新用例和原仓库 6 个选定用例，覆盖公开数值、偏移/转置、原地别名、自动替换、变输入图、双设备恢复及错误输入不修改数据。
- 除法修复阶段的 FlagGems 六文件版本通过范围检查与普通 wheel 安装核验；后续 clone 注册修复后的最终八文件版本见下文，保留各阶段原始 manifest，不将中间 wheel 当作最终安装版本。
- `fg-div-final-benchmark.results.json`：实际采样器 `[64,154880]` 对 CPU 数值通过；同一 Benchmark/CUDA graph、双方逐次 clone 重置且均含 copy，native 0.07723 ms / FlagGems 0.06252 ms，约 1.235 倍。四组实测 speedup 1.018 至 1.235；该结果仅限除法组件，不替代模型性能验收，也不覆盖前述矩阵乘相对 native 的不足。

- `glm-regression-r2.log`：89 passed，20 个 GPU 参数未在这轮 CPU/接线选择中执行；不把 deselected 当作通过。
- `prefill-gpu-tests.log`：9 passed，包含实际 PPU 上 FP16/BF16、QK/V 宽度 256、varlen causal output/LSE 独立 CPU 参考，以及两次变输入的真实图重放；通过真实 Plugin 分发并观察公开算子命中。
- `all-glm-capabilities.log`：完整 GLM adapter preflight 通过。既有 BF16 reference 组合仍按现有策略运行；没有将 reference 伪装为 vendor 实现。
- `mhc-wheel-manifest.json`：mHC 阶段普通安装 wheel 的 485 个 RECORD 文件哈希通过，其他运行包版本未改变。后续 MLA cache 修复后的最终 wheel 见下文；mHC 改动继续保留。
- `kda-conv-tests.log`：提前运行现有 bounded KDA（含模型 head_dim128）、causal conv 状态/边界与 recurrent 新输入状态回归，74 passed。未改这些算子或原测试。
- 第三次启动进入 120 个 safetensors 分片的权重加载，并推进至 74/120；期间独立 mHC 设备回归提前发现上述编译器选项故障。为让 worker 加载修复，已按精确 PID/start-time 核验停止本次服务根进程 38439 及其 19 个相关进程，仅使用 SIGTERM；证据为 `attempt03/stop.json`，容器未停止或重启。第三次启动未达到就绪，不能作为推理通过证据。
- 产品修改位于实际安装的 Plugin editable 树，以及普通安装的 FlagGems、FlagGems-vllm；两算子库同步到已核验的 `/workspace/FlagGems`、`/workspace/FlagGems-vllm` 构建源并正常重建 wheel。FlagGems-vllm 本轮修改 mHC host capability 与 MLA cache 行数校验；FlagGems 修改 PPU 窄列 FP32 调优接线、原地除法厂商接线和 clone 注册元数据。没有修改 vLLM、Torch、Triton 或 TileLang；最终复核 vLLM 1886 个 Python 文件哈希全部不变。
- 适用规范：`plugin:A1/A2/A4/B1/B3/B4/C1/C2/F1/F2/F3/F4/F7`；算子库 host 兼容与校验修复适用 `operator:B3/D1/D3/D5/E1/E3/E4/F3/F4`。mHC/cache 修复未改变数值 kernel 或 launch 参数，不做其组件提速声明；FlagGems 厂商调优的额外规范与实测限制见下文。先前在同一 `93fd1b0c` 源确认缺少 `optimization.md` / `deep_opt.md`；沿用现存 workflow 与项目规范，本轮不声称执行缺失的优化协议。

- `fg-mm-scalar-tests-r3.log`：26 passed，公开 `flag_gems.mm/mm_out` 对照 CPU FP64 参考，覆盖模型真实形状、尾部、转置与 storage offset；独立验证 ATen 替换和两次变输入图重放。初版测试错误导入厂商第二命名空间、以及使用过时 `only=` 参数的失败保留在 r1/r2 证据，已按实际 API 修复；未修改参考或容差。固定版本 black 26.5.1、isort 5.12.0 与范围 flake8 检查通过。
- FlagGems 当前 revision 的 `docs/contribution.md` 链接已核验缺失；实际读取 AGENTS.md、CONTRIBUTING.md，按现存工程约定和项目算子规范继续，不声称读取不存在文件。新增厂商调优进一步适用 `operator:A1/A2/A3/C1/C2/C3/D3/D6/E2/E7/F1/F2/F5`；组件 benchmark 与功能服务结果分别记录，不替代正式性能验收。

## 源码审查与最终结果

- FlagGems 的矩阵乘阶段 wheel、字段/导出/标记/ATen 名称检查与 patch 均保存在远端 issue；后续除法与 clone 修改叠加在同一已核验构建树中，最终安装身份见下文。
- `fg-mm-public-benchmark.results.json`：使用仓库 `Benchmark.get_latency`，同设备 CUDA graph、关闭 TF32、同样 rep30ms，覆盖 4 个形状的 NN/NT。计数验证 native 基线不命中候选、公开候选实际命中 PPU 接线。模型形状 NN：native 0.382 ms / FlagGems 0.719 ms；NT：0.376 / 2.770 ms。全部 8 组仍慢于 native，speedup 0.0157 至 0.686；不声称原生性能提升、正式性能验收或全场景 PR 性能准入通过。旧计时入口触发范围外大块，身份未确定，已停止并保留无效证据，不计入结果。
- 第六次启动于 2026-11-10 00:00:47 CST，API PID 315115，使用修复数据库 export 后同一脚本；在采样器失败，未通过服务功能验证。
- 第七次启动于 2026-11-10 00:50:36 CST，API PID 402791，同一脚本 SHA-256 不变。已通过采样器，进入 19 个尺寸的图捕获。实际图模式是 `PIECEWISE`：日志 `compilation.py:1385` 明确说明 `FlagGemsSparseMLABackend` 的支持级别为 `AttentionCGSupport.NEVER`，框架自动将请求的 `FULL_DECODE_ONLY` 改为 piecewise；本任务未改该声明或手动下调参数，不申报 full-decode 图或完整图优化通过。
- 第七次于 00:58:45 CST 完成启动且 `/health` 为 200，但首个算术请求在 01:00:36 返回 500，引擎退出，不能作为功能通过证据。Inductor 保存 RNG 时的 CPU clone 被 FlagGems 全局 Autograd 注册拦截，进入 CUDA-only clone；最小复现保留于 `07-bugs/clone-autograd-device-registration-20261110`。
- 仅将 clone 的特殊注册改为当前 backend 的 `Autograd + dispatch_key`，保留 CPU 原生 autograd 与 GPU 自定义节点；不改 clone kernel、不添加 CPU 计算 fallback、不改通用 registrar。`fg-clone-tests.log`：16 passed，覆盖 CPU/GPU 分发、CPU 原生梯度、GPU 命中及梯度、真实 Inductor RNG 编译、变输入图及原 clone 回归。
- 最新 FlagGems 普通 wheel SHA-256 `aa935d3a4bf4964ccbdf6692b96bd8e4772f6ba4f4380d2e3bac99df46a74d88`，6751 项 RECORD 哈希通过，运行依赖版本未变。最终八文件 patch SHA-256 `30931783b64ccc23452bf2a64a9575a26e5867365c1e2125bd6b17033a83fe7f`。clone 修复只改注册元数据，数值/launch 未改，不增加性能声明。
- 第八次启动于 01:23:29 CST，01:25:45 `/health` 为 200，但首个请求于 01:28:16 在 MLA KV cache 写入失败。CPU clone 与 KDA 已越过；框架图输入补齐行数，而 slot_mapping 仅含有效 token。FlagGems-vllm 原入口误要求两者等长；既有 kernel 和 grid 本已按 slot 数写入。证据为 `attempt08/service-final.log`、`cache-padding-before.log`。
- 仅放宽 FlagGems-vllm `ConcatAndCacheMla.forward` 的 host 校验：KV/RoPE 物理行数仍相等、slot 必须一维、输入行数不得少于 slot 数；允许多余补齐行。数值 kernel AST、grid、其余 dtype/device/stride 检查未改，Plugin/vLLM 无需增加裁切适配。
- `cache-padding-tests.log`：92 passed，包含既有测试与新增独立 CPU 完整 cache 参考，覆盖 FP16/BF16/FP32、int32/int64 slot、负 slot、零 RoPE、3D/4D cache、偏移及大行跨度、空有效 token、错误输入不修改 cache，以及变化输入与 slot 后的真实图重放。所有适用范围 pre-commit 通过；FP8 与其他硬件未验证，不作性能声明。
- 最新 FlagGems-vllm 普通 wheel SHA-256 `98fae2c723b4e5a17555856a519a8cf593568d5233130fe71d6be688ddab49ab`，485 项 RECORD 哈希通过，运行依赖未变；此前 import 和 mHC 修复保留。cache 两文件 patch SHA-256 `674c29e9ba5be22dc6c32865bf3bc3605ac0840d031f67e27440e4b210abf696`。
- 第九次于 01:39:29 CST 使用同一脚本启动，API PID 731626。三个实际请求均为 HTTP 200、`finish_reason=stop`：算术回答 `17 + 25 = 42`；中文解释准确描述水蒸气遇冷凝结成小水滴；图像准确识别左侧红色圆形与右侧蓝色正方形。无空回答、截断或明显重复。原请求、响应、图片与逐项内容审查在 `attempt09/probes/`，`attributed-review.json` 绑定各响应、请求、图片 SHA-256。
- 实测耗时：首次文本含冷编译 162.01 秒；后续中文解释 43 个输出 token 用时 41.21 秒；首次图像请求 111.71 秒。功能已跑通，但速度明显偏慢，不能据此宣称优化完成或通过模型性能验收。
- `02-issues/start-model-opt-repair-20261109/final-verification.json`：2026-11-10 01:48:47 CST 复核 `/health=200`、模型名 `glm5.3-flash-opt1`、端口 8011、API 及其 16 个 TP worker 仍运行；本次 service.log 无 traceback 或 ERROR。Plugin/两算子库最终源码哈希、普通安装与源文件一致性、FlagGems 6751 项及 FlagGems-vllm 485 项 RECORD 均通过。容器仍为原 ID，restart count 为 0，已保留运行。
- 实际图模式仍是框架自动选择的 `PIECEWISE`，不是脚本请求的 `FULL_DECODE_ONLY`；未修改 backend 能力声明。正式精度/性能、FP8 cache 模式、其他硬件及全仓库检查未验证。

- 修改与测试清单先记录在远端 `plan.json`，每次扩展先更新原因、文件、符号和回归。
- 原始失败日志、脚本备份及一次性诊断均在批准工作根；不进入产品仓库。本地仅保留本 Markdown 摘要。
- 启动修复结束时尚未发布；用户随后明确要求将 Plugin 修改同步至 PR #572，已按下述记录完成。FlagGems、FlagGems-vllm 与启动脚本的修复仍未发布到该 PR。原始失败和中间版本证据均保留，未计作通过。
- 保留缺少可选 T-Head native extension bundle 的既有警告；它不等于实际算子调用失败。其他硬件和完整精度/性能未验证。
- 经验状态：`local-only`。历史 029 的公共分发整合提供检查方向，但主机、版本和模型注册不同，未套用旧通过结论。

## PR #572 首次增量同步（历史版本，2026-11-10）

- 用户明确授权发布 Plugin 改动；在既有 `ZenithJoyH/vllm-plugin-FL:support-glm5.3-flash` 分支追加提交 [`8e69f25a7c61261a784581e96893654eeb2dc99f`](https://github.com/ZenithJoyH/vllm-plugin-FL/commit/8e69f25a7c61261a784581e96893654eeb2dc99f)，父提交为 `7cd610c96b2c44291e843833cf94e1578f2b4e5a`，未改写历史。仅包含四个 Plugin 源码文件及三个新增测试，不含算子库、启动脚本或执行产物。
- 发布前在实际安装树重跑：GLM 回归 89 passed / 20 deselected；主线共享分发回归 66 passed / 3 deselected；七文件所有适用 pre-commit、605 个 tracked Python 文件 AST 与 whitespace 检查通过。检查前后七文件哈希不变。
- GitHub 七文件逐项回读一致；容器按基线 Git entries 加当前七文件内容计算出的完整 tree 与发布 tree 均为 `634f430b4fcb17a3ed06a32a95233494273f47a1`。容器 Git HEAD 仍为原 `7cd610c9` 加既有工作树修改，未暂存、移动容器 refs、重装包或修改服务；这里声明的是完整源码内容一致，不是容器 Git 元数据已切到新提交。
- [PR #572](https://github.com/flagos-ai/vllm-plugin-FL/pull/572) 代码和说明均已更新并回读核验，保持 Draft。说明列出修复、测试、实际 `PIECEWISE`、生成速度偏慢，以及独立算子库本地补丁与公开依赖版本未对齐的限制；不宣称该 PR 单独即可复现验收通过。
- [CI run 42739015086](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/42739015086) 在 `ci-gate` 失败：当前工作流因 Draft 跳过 lint，随后 build/discover/硬件任务均被跳过，而无条件 gate 要求前三项成功。没有实际运行 GitHub lint/build/硬件测试，不能声称 CI 通过；未顺带修改 CI 或将 Draft 标记 ready。
- 同步期间只读检查发现服务已在前次验证后由外部重新启动，当前 API PID 为 990639、16 个 TP worker、模型名和完整启动参数与原入口一致，`/health=200`。最初审查因沿用旧 PID 731626 而失败；改为核对当前实际进程后通过，保留历史证据，不将旧请求验证重新绑定到新服务实例。本次 PR 同步没有停止或重启服务。
- 同步原始检查、发布清单、PR 说明和 CI gate 日志保存在已批准远端 issue 的 `pr572-sync-20261110/`。本地仍只保留本 Markdown 摘要。

## PR #572 范围与测试收敛（1597b9e6，2026-11-10）

- 用户指出 PR 仍夹带 HY4 且测试存在问题。完整核对相对主线的 66 文件后确认：早期分支遗留旧 `models/hy_v4.py`、config/loader/reasoning 及测试；同时携带旧 GLM config/model/processor/patch 副本。当前主线已分别在 `8b2033e`（HY4）和 `7094141`（GLM）提供正式实现，实际服务注册的是主线 `models/glm5`。此前只审查七文件增量，没有收敛完整 PR，属于范围审查遗漏。
- 已将无关或重复内容恢复为主线 `d6d83803980fb78d84dcc1b3bc5b915b1fddb237`：旧模型及其独立分发/参考适配、native bundle、W8A8 修改、全局 T-Head 黑名单、CachedOp 扩展及仅针对这些旧实现的测试。保留主线原有模型与测试；对应注册重复与 ABI 冲突由移除重复实现消除，不再叠加 workaround。
- 最终相对主线仅 **8 文件**：`attention/mla_prefill.py`、FlagGems backend/注册/公开 prefill adapter、`platform.py` 共五个生产文件；两个 GLM 测试模块和一个现有 ARM CPU 注册 fixture 共三个测试文件。GitHub Files changed 已回读核对，没有 HY4 文件差异；主线原有 HY4 继续保持原样。
- 生产修改只补齐 PPU GLM prefill 的选择缺口：复用主线 dense prefill 的 metadata、padding、out buffer 和数学实现；通过既有 dispatch 及算子库开关接入公开 varlen API；在执行前检查 PPU/可调用 API，缺少 vendor 的原生平台不导入 provider；保留外部 CUSTOM、显式其他枚举及非 GLM/非 PPU 路径。worker 钩子移到 GLM 激活计划提前返回之前，原位置可能完全执行不到。
- 旧 prefill 数值测试只调用底层 dispatcher，未覆盖真实 backend 的 metadata 与输出处理；旧辅助测试还包含面向废弃实现的文件路径/PR 编号断言、无 GPU 标记或不足的图输出检查。相关废弃实现及测试一并移除，新增测试从实际 backend 构造、`prepare_metadata`、new-token/context-chunk 入口发起；FP16/BF16、V 宽度 128/256、因果/非因果、输出 buffer identity 均对独立 CPU attention/LSE 参考比较。每次图重放更新 Q/K/V，并将两个输出填为 NaN，核对新结果。
- 配置测试在独立子进程反序列化真实 CUSTOM 枚举并操作真实 registry，只对 provider discovery 使用 stub；另验证 early return 前的 worker 钩子与其他模型/平台保护。一般注册测试使用新进程真实验证 canonical GLM 文本/VLM/config 所有者，并设置超时。
- 扩大主线回归时发现五个 ARM 注册测试失败：测试及注册生产代码与主线逐字节相同，但 fake platform 缺少 GPU `dispatch_key`，未隔离新增 GLM/Qwen3.8 模型 hook。只在该测试类 setUp 隔离这两个无关模型入口，并逐条恢复原 sys.modules 项；十个原测试函数 AST 与断言完全不变。该文件单独新进程运行也通过，不依赖其他测试提前导入 GPU 模块。这是接线 fixture 修复，不是 ARM 实机验收。
- 最终检查：GLM **102 passed / 26 deselected**；真实 PPU backend **8 passed / 22 CPU cases deselected**；既有分发/激活/跨平台/注册回归 **216 passed / 2 deselected**；ARM 文件单独 **10 passed**（已包含在前述 216 项内，不重复累计）；完整 GLM capability preflight 通过，已声明的 BF16 reference 选择仍如实记录；570 个现存 Python 文件 AST 与 PR 主线基准 whitespace 检查通过。八文件所有适用 pre-commit 通过，不宣称全仓库风格门禁通过。
- [PR #572](https://github.com/flagos-ai/vllm-plugin-FL/pull/572) 已追加提交 [`1597b9e6e672bdad00bb0291134b0291cb50e8f6`](https://github.com/ZenithJoyH/vllm-plugin-FL/commit/1597b9e6e672bdad00bb0291134b0291cb50e8f6)，父提交 `8e69f25a`，没有强推或改写历史；最终 tree `ee603dcf51c54dbc90bc486a602d772b129c8d8a` 由主线 tree 加八文件构造，与实际安装源码计算的完整 tree 相同。八文件均经 GitHub 逐项回读，标题与说明已改为实际 PPU prefill 修复范围，保持 Draft。
- [CI run 42744932854](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/42744932854) 仍因 Draft 跳过 lint/build/discover 而由无条件 ci-gate 判失败；没有实际 GitHub 构建/硬件测试运行，未改 CI，也不申报 CI 通过。
- 最终复核：vLLM 1886 个 Python 文件哈希不变；FlagGems 6751 项、FlagGems-vllm 485 项 RECORD 通过，本轮没有改动算子库。当前 API PID 990639、16 worker、`/health=200`，没有停服或重启；当前进程健康不作为新源码的整模型验证。公开算子库补丁/固定依赖、干净安装、新树整模型启动、其他硬件与正式精度/性能仍未验证。
- 原始计划、代码备份、初始回归失败、最终检查、发布清单及 CI gate 日志留在已批准远端 issue 的 `pr572-scope-review-20261110/`。旧 `source-review.json` 已归档，该记录现指向八文件新树；原 TP16 `final-verification.json` 保留历史绑定，不改为新树通过。

## PR #572 转为正式评审与 CI 修复（9ea4bec2，2026-11-10）

- 用户明确要求将 PR 改为正式 PR，已从 Draft 转为 **Ready for review**，未执行合并。首次非 Draft [CI run 42746415869](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/42746415869) 的 lint、wheel 构建、平台发现及八个平台 setup 通过；对应 [Code Scan](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/42746414662) 的 CodeQL 和 Dependency Review 通过。
- T-Head 单元测试实际发现一项回归：**1 failed / 1441 passed / 164 skipped**。既有 GPU 标记测试 `test_fresh_process_attention_dispatch_and_vision_import_isolation` 激活 GLM plan 后，在未设置当前 VllmConfig 的上下文查询 backend；新增 worker hook 强制调用 `get_current_vllm_config()`，提前触发 AssertionError。此前 CPU 选择排除了这个 GPU 标记测试，而八项新增 GPU 数值测试未包含它，因此先前范围检查未覆盖到此契约。
- 已在实际安装 Plugin 树按 CI 默认算子库开关原样复现失败；保持既有测试内容和断言不变。仅将 `PlatformFL.get_attn_backend_cls` 的 hook 改为 vLLM 0.24 公开的 `get_current_vllm_config_or_none()`，有配置时才配置 prefill，无上下文时仍完成 plan backend 查询。配置本身的错误继续传播，没有宽泛异常捕获或执行失败重试；vLLM 保持只读。
- 对应新增测试覆盖目标/非目标平台与 plan、有/无上下文，并验证真实配置错误不能被静默忽略。修复后当前源码验证：GLM **106 passed / 26 deselected**；原 CI 失败用例 **1 passed**（未设置 `VLLM_FL_USE_FLAGGEMS_VLLM`）；真实 PPU prefill 数值/变输入图 **8 passed / 26 CPU cases deselected**；既有主线兼容选择 **216 passed / 2 deselected**；ARM fixture 独立 **10 passed**（包含于 216 项内）；完整 GLM preflight、八文件适用 pre-commit、570 个现存 Python 文件 AST 和基准 whitespace 检查通过。
- 正常追加提交 [`9ea4bec2fae71d10dd5d9b770735c08747b90c7b`](https://github.com/ZenithJoyH/vllm-plugin-FL/commit/9ea4bec2fae71d10dd5d9b770735c08747b90c7b)，父提交 `1597b9e6`，没有改写历史。本次增量只改 `platform.py` 与 prefill 配置测试；整个 PR 相对 main 仍为八文件，没有 HY4 差异。完整源码 tree `fd69fb31652383c9157b2756fb62a48113f53e01` 与容器安装树计算值相同，八文件 GitHub 回读完全一致。容器 Git HEAD/index/refs 未移动，仍以原 HEAD 加已核验工作树表达安装内容。
- 新提交触发 [CI run 42749929348](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/42749929348) 与 [Code Scan run 42749928964](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/42749928964)。11:35 CST 快照：CI 为 pending，尚无 jobs 开始；Code Scan 的 Dependency Review 通过，CodeQL 运行中，尚无新失败但没有整轮结论。不将上一提交的 lint/build/security 通过移作新提交的通过结论。旧运行被 synchronize 自动取消的排队任务不是测试失败，也不算硬件验证通过。
- 最终环境复核：vLLM 1886 个 Python 文件未变，FlagGems 6751 项和 FlagGems-vllm 485 项安装 RECORD 通过。API PID 990639、16 个 worker、`/health=200`，本轮未停止或重启服务。公开算子库补丁/固定依赖、干净安装、新树整模型和正式验收仍保留未完成状态。
- 原始 CI 失败复现、两文件备份、修复后日志、源码审查和发布证据保存在远端批准 issue 的 `pr572-scope-review-20261110/ci-current-config-fix/`。适用 `plugin:B3/B4/C1/C2/F1/F2/F3/F4/F6`，没有引入数值 kernel 或跨组件修改。

## FlagGems-vllm 修复独立发布（PR #1134，2026-11-10）

- 用户明确要求将当前跑通适配所需的 FlagGems-vllm 修复提交为独立 PR，并关联 Plugin #572。已创建正式 [FlagGems-vllm #1134](https://github.com/flagos-ai/FlagGems-vllm/pull/1134)，初始提交 [`bc5f3fe605b4cfaebd08a5c043fdda581f3137ed`](https://github.com/ZenithJoyH/FlagGems-vllm/commit/bc5f3fe605b4cfaebd08a5c043fdda581f3137ed) 的父提交为已安装源码基线 `93fd1b0c1dc3b084dbf6872630fc9bb6113218ed`；随后为参考函数静态审查说明追加 [`3c413007dc2ed0a2dd0420de766b4fab2ff52c71`](https://github.com/ZenithJoyH/FlagGems-vllm/commit/3c413007dc2ed0a2dd0420de766b4fab2ff52c71)，没有改写历史。五个生产文件、三个测试文件，没有数值 kernel、launch/grid、调优配置或第三方依赖修改。
- 生产修改包含：依照现有 TLE 能力检查隔离 PPU AIU INT8 的可选导入/公开导出；仅 NVIDIA 初始化 FlashInfer MNNVL；mHC post 对可选 `adjust_block_size` 先检查、在 finally 恢复，并以现有 runtime vendor 身份选择原 PPU kernel；MLA cache 允许输入含图补齐行，仍要求 KV/RoPE 物理行一致、一维 slot、slot 不多于输入行，原 kernel/grid 仅按 slot 数写入。
- 发布前在原 PPU-03 容器正常安装包上重跑，显式关闭 pytest.ini 的 `pythonpath=src`，没有 `PYTHONPATH` 覆盖：可选导入/公开 non-TLE MoE 数值与变路由图测试 **13 passed**；MLA cache 原有与新增独立参考、错误输入禁写和变 KV/RoPE/slot 图测试 **92 passed**；mHC post 原有数值/布局及编译器选项恢复测试 **80 passed / 68 unrelated deselected**。共 **185 passed，无 skips**；NVIDIA 的导入契约与部分 host 分支使用 stub，不算 NVIDIA 硬件验证。
- 八文件仓库配置 pre-commit（black 24.8.0、isort 5.12.0、flake8 7.1.0 与适用文件钩子）、AST、whitespace 检查通过；cache/mHC 的数值 kernel AST 不变。普通安装的五个生产文件与发布内容一致，485 项 RECORD 校验通过。重新 `pip wheel --no-deps --no-build-isolation` 成功，构建产物 SHA-256 `d546b07e5d0a1e87f0e9cae4b2111dc8f5c4c3f47de67a6e3dfc72fb7fab6d0f`；未重装，该构建产物不替代历史安装 wheel 身份。
- 初始完整 tree `60db74a7ed7883109b488b7c96b963be474c7c73` 与容器源码计算值一致，八文件 GitHub 回读完全一致。参考函数注释后最终 tree 为 `2535da3e213a194d3e056e4140d4afd95f5b3411`，再次与容器源码完整计算值及 GitHub 回读核对一致；增量仅一个文件、注释和等价排版。容器源码仍是基线 HEAD 加工作树补丁，未移动其 Git HEAD/index/refs。当前上游 main `7598812baf1a64e7d297161f281cad65ab33ff05` 比该基线多两个提交，与本 PR 八文件没有交集；GitHub 确认 mergeable，但没有声称对合并后的整树做过硬件验收。
- PR #1134 正文链接 #572；#572 的依赖说明已反向链接 #1134 和固定公开提交，并注明这对应当前实际安装的修复。Plugin 源码与既有 `glm5` extra 的 `80a8e971...` 依赖 pin 未改变；后续 pin 对齐、干净安装与 TileLang 兼容检查仍待完成。FlagGems ATen 补丁仍未发布，本次 PR 不覆盖它们。
- 首次 [basic ci](https://github.com/flagos-ai/FlagGems-vllm/actions/runs/42766656172) 的全仓库 pre-commit 和 CI helper 测试通过，但新引入的全文件静态检查将既有 `mhc_post_ref` 中的 `torch.bmm` 报为生产计算。全仓调用方检索确认只有原数值测试调用及既有 re-export，生产 `mhc_post` 不调用该参考函数。仅给这一行使用检查器既有的 `allow-torch-compute` 标记，并明确注释“independent test reference”；保留公开参考接口，没有修改检查器/CI、豁免生产调用或移动/删除测试。
- 注释增量前后整个模块的 AST 完全一致，包括参考计算、所有 kernel、wrapper 和异常分支；原检查器先复现一项报告、注释后对五个生产文件报告零违规。该文件 configured pre-commit 再次通过，正常重建并安装纯注释变化的 wheel，SHA-256 `faf11a26b7ce506510f509e070d58ec85a701193635034485c6a65eef41e2c3c`；五个生产文件与安装内容一致，485 项 RECORD 校验通过，其他运行依赖版本不变。没有重复计入数值测试；前述 185 项对应相同的可执行 AST。
- 14:19 CST 最新 [rule-check](https://github.com/flagos-ai/FlagGems-vllm/actions/runs/42767444869) 已通过；[basic ci](https://github.com/flagos-ai/FlagGems-vllm/actions/runs/42767445170) 的全仓库 pre-commit、CI helper/pin、变更文件 no-torch 检查、测试目标选择与 multi-backend summary 均通过。五个 vendor container smoke 任务运行或排队中，NVIDIA/legacy non-NVIDIA 算子任务由工作流路由跳过，不将 summary 通过解释为额外硬件验证；完整 CI 与其他硬件仍未确认通过。性能基线没有新增测量，不作数值 kernel 或模型提速声明；当前服务及容器保持运行，本轮没有重启，不将健康检查当作新 Plugin 树的整模型验证。
- 计划、原始测试日志/逐项结果、构建产物、发布清单和双向关联说明保存在批准远端 issue 的 `flaggems-vllm-pr-20261110/`，`source-review.json` 的 FlagGems-vllm 部分已补入公开 PR 身份。现存 `workflow.md` 和项目规范作为依据；基线确实缺少 `optimization.md` / `deep_opt.md`，不声称执行缺失流程。适用 `operator:A1/A3/A4/B1/B2/B3/C1/C2/C3/C5/C7/D1/D2/D5/E1/E2/E3/E4/E5/E6/F3/F4` 与 `plugin:D3/F4/F5`。
