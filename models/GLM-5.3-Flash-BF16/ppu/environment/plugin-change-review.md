# Plugin 修改设计审查与 PR 准备

> 按仓库 `docs/plugin-contribution-policy.md` 审查真实代码；模板存在不代表审查通过。
> 此材料属于 environment/，不包含源码、补丁或临时脚本。代码仍留在适配容器的插件仓库。

## 范围与版本

- 模型、平台、Host、容器和插件 checkout 路径：`GLM-5.3-Flash-BF16` / T-Head PPU /
  `PPU-13` / `glm5.3-flash` /
  `/workspace/vllm-plugin-FL-glm53-hy4-adaptation`。
- 审查日期及审查执行者（含 agent 自审时的说明）：2026-09-06，Codex 自审；不代表
  上游维护者批准。
- 目标 repository / PR base branch / base revision（未确认则明确标注）：
  `https://github.com/ZenithJoyH/vllm-plugin-FL.git` / 用户指定 `support-hy4-preview` /
  `5329cb1293f397fd194852496cfcc710c35f1bfc`。
- 当前 HEAD、branch、暂存/未暂存/新增文件状态：`support-hy4-preview` /
  `5329cb1293f397fd194852496cfcc710c35f1bfc`；无 staged，11 个 tracked modified、41 个
  untracked，共 52 个文件。
- 本任务初始 revision / dirty 状态及既有改动归属：本轮专用 checkout 从用户指定的 clean
  HY4 revision 建立；当前 52 文件属于本模型适配与随后精简/修复，没有发现另一主体在该
  专用树中的独立修改。此前不同 checkout 已归档，不合并为当前 diff。
- 完整 PR diff 与本任务新增差异的命令、摘要/哈希和清单位置（需覆盖新增文件）：上述
  `FULL_FILE_INVENTORY` 是逐文件行数/SHA 清单；52 文件当前内容合计 11714 行，稳定排序的
  每文件 SHA 清单摘要为
  `f89d602c991dad9d0e9be9c4bdb69fb7a6b5bb5a6ec1ccf16abc0559e6459648`。仅 tracked
  `git diff --binary` SHA 为
  `a760b27644a02b376b3ca3ac6a79160bb544b767646d1158fea43790e2ef0503`，不能替代完整摘要；
  `git diff --check` 通过。
- 当前 vLLM / FlagGems revision；vLLM 未变化证据：vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`、工作树 clean；FlagGems
  `34bd6d68928c8b0039c42987840929da52aa6a62`、工作树 clean。
- 插件 checkout 的两层范围内没有 `AGENTS.md` 或贡献指南；本审查使用控制端
  `docs/plugin-contribution-policy.md` 和现有 dispatch/registry 设计。

真实 checkout 的贡献约束、完整工作树和最终 diff 用以下只读命令复核；不修改、提交或推送：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''repo=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; echo GUIDES; find "$repo" -maxdepth 2 -type f \( -name AGENTS.md -o -name CONTRIBUTING.md -o -name CONTRIBUTING.rst \) -print; for f in $(find "$repo" -maxdepth 2 -type f \( -name AGENTS.md -o -name CONTRIBUTING.md -o -name CONTRIBUTING.rst \) -print); do echo FILE=$f; sed -n "1,260p" "$f"; done; echo IDENTITY; git -C "$repo" remote -v; git -C "$repo" branch --show-current; git -C "$repo" rev-parse HEAD; git -C "$repo" status --short; echo DIFF; git -C "$repo" diff --stat; git -C "$repo" diff --name-status; git -C "$repo" diff --check; git -C "$repo" diff --binary | sha256sum; git -C "$repo" diff -- vllm_fl/kernels/glm5_next/kpool_compress.py vllm_fl/kernels/glm5_next/prefill_tail.py tests/unit_tests/test_glm5_tail_graph.py; echo STACK; git -C /workspace/vllm rev-parse HEAD; git -C /workspace/vllm status --porcelain; git -C /workspace/FlagGems rev-parse HEAD; git -C /workspace/FlagGems status --porcelain'\'''
```

由于基线不含 GLM 文件，普通 `git diff` 不覆盖 untracked 适配代码；继续用 Git 的完整
modified+untracked 清单生成每文件行数/SHA256，并读取本轮 padded-slot 三文件和公共 tracked
改动，确保审查不是只看 HEAD：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''repo=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$repo"; echo FULL_FILE_INVENTORY; git ls-files -m -o --exclude-standard | sort | while read -r f; do sha=$(sha256sum "$f" | cut -d" " -f1); lines=$(wc -l <"$f"); printf "%7d %s %s\\n" "$lines" "$sha" "$f"; done; echo TRACKED_DIFF_NUMSTAT; git diff --numstat; echo PADDED_SLOT_FILES; for f in vllm_fl/kernels/glm5_next/kpool_compress.py vllm_fl/kernels/glm5_next/prefill_tail.py tests/unit_tests/test_glm5_tail_graph.py; do echo FILE=$f; sed -n "1,320p" "$f"; done; echo TRACKED_DIFF_CONTENT; git diff -- vllm_fl/__init__.py vllm_fl/attention/mla_prefill.py vllm_fl/dispatch/__init__.py vllm_fl/dispatch/backends/flaggems/register_ops.py vllm_fl/dispatch/backends/reference/register_ops.py vllm_fl/dispatch/backends/vendor/thead/register_ops.py vllm_fl/dispatch/config/thead.yaml vllm_fl/dispatch/manager.py vllm_fl/dispatch/types.py vllm_fl/ops/fused_moe/activation.py vllm_fl/ops/fused_moe/fused_moe_utils.py'\'''
```

完整 modified+untracked 内容摘要哈希和规模使用稳定排序的每文件 SHA 清单计算：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; files=$(git ls-files -m -o --exclude-standard | sort); printf "FILES="; printf "%s\\n" "$files" | sed "/^$/d" | wc -l; printf "LINES="; printf "%s\\n" "$files" | sed "/^$/d" | xargs wc -l | tail -n 1; printf "%s\\n" "$files" | sed "/^$/d" | xargs sha256sum | sha256sum; printf "UNTRACKED="; git ls-files -o --exclude-standard | wc -l; printf "TRACKED_MODIFIED="; git ls-files -m | wc -l'\'''
```

历史 318 项回归曾有一个 `register_impl` mock 契约失败；先只读定位其当前测试与注册调用，
确认后再决定能否在正式评测并行期间执行该 CPU-only 单测：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; grep -RIn -E "test_flaggems_quantization_registers_ordered_fallbacks|register_impl" tests vllm_fl/dispatch/backends/flaggems vllm_fl/dispatch/backends/model_ops.py | head -n 240; file=$(grep -Rl "def test_flaggems_quantization_registers_ordered_fallbacks" tests | head -n 1); echo TEST_FILE=$file; test -n "$file"; line=$(grep -n "def test_flaggems_quantization_registers_ordered_fallbacks" "$file" | cut -d: -f1); start=$((line-40)); test "$start" -ge 1 || start=1; end=$((line+100)); sed -n "${start},${end}p" "$file"'\'''
```

继续只读审查 model-op 注册 helper 与三个 backend 的调用约定，判断应统一生产注册接口还是
修复测试 mock；正式评测运行期间不执行 GPU 单测、不改远端代码：

```bash
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''cd /workspace/vllm-plugin-FL-glm53-hy4-adaptation; sed -n "1,340p" vllm_fl/dispatch/backends/model_ops.py; sed -n "1,240p" vllm_fl/dispatch/registry.py; grep -RIn -E "register_mhc\(|register_flaggems_model_ops\(|register_reference_indexer\(|register_vendor_glm5\(" vllm_fl tests | head -n 240'\'''
```

当前 helper 已统一使用 `register_many`，与该测试的最小 Registry 契约一致。只运行这一项
CPU-only 回归，禁用 pytest cache/字节码且屏蔽设备可见性，不占用正式评测的 PPU：

```bash
ssh PPU-13 'docker exec --env CUDA_VISIBLE_DEVICES= --env PYTHONDONTWRITEBYTECODE=1 --workdir /workspace/vllm-plugin-FL-glm53-hy4-adaptation glm5.3-flash python3 -m pytest -q -p no:cacheprovider tests/unit_tests/dispatch/test_flaggems_quantization.py::test_flaggems_quantization_registers_ordered_fallbacks'
```

## 问题与设计选择

- 具体触发条件、修改前/后行为：HY4 基线不认识 `glm5_next` hybrid config/model，也没有
  GLM 的 KDA、mHC、clamped SwiGLU、BF16 compressed sparse indexer/KPool、混合 cache 和
  vLLM 0.24 兼容协议；加入受模型结构与 T-Head backend 限制的实现后可加载正确 BF16 120
  分片并完成 eager/graph 请求。最后一项 c64 非法访存由 padded physical tail page 768 与
  logical pool 4 混用导致；现在按 tensor stride 推导物理页宽，ring offset 仍按 pool 4。
- 对应问题台账与最小复现：`adaptation/017-bf16-gap-analysis-20260906.md`、
  `adaptation/010-hy4-glm53-scope-review-20260904.md`、
  `adaptation/014-shared-prefill-refactor-20260904.md`、
  `adaptation/001-graph-c64-enginecore-crash.md`。FlagGems 缺陷复现统一保留在工作根 `08-bugs/`
  并通过容器对应路径原地执行；已有用例不再复制到 `/bug`，
  不进入插件树。
- 当前框架扩展点和调用链：模型 config/registry → GLM model orchestration → `CachedOp` →
  既有 dispatch manager → reference/FlagGems/vendor.thead；vLLM 0.24 cache/runner 不兼容通过
  版本守卫的幂等 patch 入口安装，vLLM 源码不改。
- 候选方案、最终选型及其职责依据：复用 HY4 的公共 MLA prefill 和 dispatch；模型独有
  数学/缓存布局留在 GLM 模型与 kernel；FlagGems 有兼容算子时通过 backend lazy binding，
  PPU 独有实现放 vendor.thead，portable/reference 只承担明确对照或 fallback。已删除重复
  GLM MLA prefill 与 CUDA 专属增量；未用服务名、权重路径或启动脚本开关在公共热路径分支。

| 文件/共享符号 | 修改目的 | 所属层级 | 影响的调用方/模型/平台 | 未命中时的行为 | 必要性与替代方案 |
|---|---|---|---|---|---|
| `configs/glm5_next.py`、`models/glm5_next*.py`、`transformers_utils/processors/glm5_next.py`、`__init__.py` | 注册 checkpoint 的 hybrid/conditional 架构、权重和 processor | 模型/config/registry | GLM5Next；文本已验，多模态未验 | 非 GLM model type 不安装 GLM patch/registry | 不能改为纯文本或复用 HY4 模型数学；conditional checkpoint 需要保留 wrapper |
| `patches/glm5_next*_v024.py`、`models/glm5_next_kpool.py` | 对接 vLLM 0.24 的混合 cache、runner、slot/page 语义 | 版本兼容/cache adapter | 仅 vLLM 0.24 + GLM config；TP worker 幂等安装 | 版本/模型守卫不命中时透传原 vLLM | 当前 vLLM 无正式扩展点可表达全部 compressed KPool/Mamba state；不得直接改 vLLM |
| `dispatch/types.py`、`manager.py`、`dispatch/__init__.py`、`test_input_support.py` | 每次按输入 shape/layout 评估 `supports`；有状态 kernel 禁止失败后重复写 | 公共 dispatch | 所有使用带 predicate/side-effect OpImpl 的调用方 | 既有无 predicate 实现仍走原缓存和 fallback | 共享能力是多个 GLM backend 的统一选择边界；测试覆盖缓存失效、guard 两侧和异常传播 |
| `dispatch/backends/model_ops.py` 与三类 `register_ops.py` | 在既有 registry 注册 GLM reusable ops | dispatch/backend registration | GLM KDA/mHC/indexer；PPU vendor 限定 thead | 后端不可用时 lazy availability/候选顺序处理 | helper 统一使用 `register_many`，不再另建注册系统；不应从模型直接 import FlagGems |
| `flaggems/impl/*`、`reference/impl/*`、`vendor/thead/impl/*` | FlagGems bindings、数值 reference 与 PPU vendor kernels | backend | 按 dtype/shape/layout 与配置选择；vendor 仅 T-Head | supports false 跳过；有副作用错误不重试 | FlagGems 缺能力的 causal-conv/KPool 等留 PPU 实现；reference 不伪装 vendor |
| `kernels/glm5_next/*` | KDA、compressed KPool/tail、sparse indexer portable/Triton 实现 | GLM kernel | GLM5Next BF16 PPU，部分 portable 契约可复用 | 未由 GLM CachedOp 选择时不执行 | 训练语义和缓存布局不同于 HY4；`PROVENANCE.md` 记录来源。最新 padded-slot 仅改 `kpool_compress.py`、`prefill_tail.py` |
| `ops/fused_moe/{activation,fused_moe_utils}.py`、`flaggems/impl/bounded_activation.py` | 传递 `gemm1_clamp_limit` 并实现训练时 clamped SwiGLU | MoE/activation | clamp 非空的 GLM；其他模型 | clamp 为 `None` 时维持基线 `_silu_and_mul` 和 CUDA fast path | 属模型数学语义，不能删除或用普通 SwiGLU 代替 |
| `dispatch/config/thead.yaml` | 仅增加 bounded activation 与 3 个 mHC backend 顺序 | 平台默认配置 | T-Head PPU | 其余 HY4 policy/blacklist 保持原对象语义 | 插件自动读取的唯一部署配置；不保留重复 NFS/示例 YAML |
| `tests/unit_tests/test_glm5_*`、`test_flaggems_bindings_graph.py`、`examples/glm5_next/*` | 正常测试与 backend/cache 契约说明 | 测试/文档 | 目标模型与共享 dispatch | 不参与生产 import 热路径 | 属维护性回归/契约文档，不是一键部署或诊断脚本；一次性 probe 均在插件外 |
|---|---|---|---|---|---|

## 接口与兼容性

- dtype/shape/layout/device、量化/cache、out/in-place/alias、边界输入契约：KDA QKV 为
  BF16、gate/state FP32；indexer cache/query 为 PPU BF16、compressed page 32；tail logical
  pool 4 可位于 768-token padded physical page，物理 page 由 stride 推导且零拷贝 alias；
  mHC 保留 Sinkhorn/RMSNorm；clamp 只在非空 limit 生效。空输入、非连续 view、高 block、
  prefill/decode 和变输入 graph replay均有专项覆盖。
- lazy import、可选 SDK、初始化、spawn、幂等注册、缓存失效：model-op 实现与依赖通过
  `lazy_op`/`lru_cache` 延迟解析；v0.24 patch 有版本/模型守卫并需在 spawn worker 重复安装；
  `supports` 存在时不跨 shape 缓存实现。基线 `vllm_fl.utils` 仍 eager import FlagGems，导致
  隐藏全部设备时 quantization 单测在收集阶段无 active driver；这不是本轮新增，但限制了
  无设备隔离验证。
- 新旧 backend 的实际命中证据及生产 fallback：服务日志/专项测试验证 PPU vendor、FlagGems
  与 reference 对照；input predicate 为 false 时按用户允许顺序选下一个实现；cache/state
  写算子 `allow_runtime_fallback=False`，真实 kernel 异常直接传播，避免重复写。
- 默认配置/公共行为是否变化、理由和影响：公共 OpImpl 新增可选字段，默认值保持旧行为；
  T-Head YAML 只新增 4 个 GLM 数学算子的 backend 顺序，没有扩大 blacklist；MoE clamp 为
  `None` 时保持 HY4 行为。
- workaround 的触发条件、最小作用域、性能代价、上游关联和移除条件：v0.24 patch 仅在
  `is_vllm_024()` 且 GLM config 路径安装，待上游提供等价 cache/runner 扩展点后移除；
  `eager_break_during_capture` 仅隔离有状态 sparse indexer，性能只做 sanity 未作正式结论。
  SQLite `timeout=1800` 是服务边界 mitigation，不属于插件 diff。

## 回归矩阵与结果

| 场景/共享调用方 | 模型结构 | 平台/依赖 | dtype/shape/并行 | eager/graph | 命令/测试位置 | 前后结果 | 已执行/未执行/不适用及依据 |
|---|---|---|---|---|---|---|---|
| shared MLA prefill | HY4/GLM MLA | PPU/FlagGems | BF16/FP16，V128/256 | eager + 2×graph replay | issue 014 / `test_shared_mla_prefill.py` | 8/8 组合通过；删除重复 GLM backend 前后等价 | 已执行 |
| GLM model/dispatch/component | GLM hybrid | PPU | KDA/mHC/indexer/MoE/cache | eager/graph | issue 014 的 318 项回归 | 317 passed；历史唯一注册 mock 失败，当前 helper 已改为相容的 `register_many` | 已执行历史；该单项当前 PPU 补跑待正式评测结束 |
| padded physical tail page | GLM KPool | PPU | page768/pool4，高 block、非连续 view | eager + graph replay | `test_glm5_tail_graph.py` | 修复前 bounds/非法访存；修复后 4 passed | 已执行 |
| 相邻 GLM/FlagGems graph | GLM hybrid | PPU/FlagGems | 多 shape | eager/graph | 3 个 unit test 文件 | 49 passed；与 tail 合计 53 passed | 已执行 |
| 整模 graph c8 | 正确 BF16 120 shards | PPU TP16 | 50K/seq32 | PIECEWISE | `acceptance/graph-sanity-results.md` | 8/8、零错误；最新轮 20.54 tok/s | 已执行；非正式性能 |
| 正式 GPQA | GLM BF16 | PPU TP16 | 198/c64 | PIECEWISE | `acceptance/gpqa-full-20260906.md` | 当前 bounded-wait 轮运行中，尚无最终成绩 | 正在执行，不作为插件 PR 设计通过条件 |
| CUDA/其他平台、多模态、MTP | 未授权/未选择 | 无目标硬件 | 未覆盖 | 未覆盖 | 无 | 不宣称支持已验证 | 未执行；扩展已按平台/模型守卫隔离 |
|---|---|---|---|---|---|---|---|

- 变更前失败或可靠负对照、变更后通过的证据：issue 001 的 bounds probe 复现 page/pool
  错解和高 block 越界；首版专项 1 passed/3 failed 暴露过严 stride 断言与 graph 测试顺序，
  未启动服务；修正后 4+49 全过，再完成整模 c8。
- 相关已有模型/调用方和不应受影响路径的代表性依据：HY4 公共 MLA 未复制；`None` clamp、
  无 supports 的 OpImpl、非 v0.24、非 GLM config 和非 T-Head vendor 均保留旧入口。历史 318
  项无新增广泛失败。
- 缺少其他硬件时已完成的隔离检查、未验证范围和剩余风险：没有连接未授权平台；CUDA、
  Ascend、MetaX 等真实硬件、多模态、MTP、1M context 未验证。当前单项 quantization 注册
  补跑因隐藏设备导致 FlagGems 基线收集失败，待正式 GPQA 结束后在空闲 PPU 上补验。
- 性能基线和差异（未测则明确标注；遵守正式验收顺序）：仅有 c8 sanity，不作优化或正式
  性能结论；accuracy 通过前不启动正式性能。

## 最终 diff 自检

- [x] 符合现有职责/dispatch 设计，共享层未依赖单个模型路径、服务名或厂商 SDK
- [ ] 已覆盖守卫命中和未命中、适用的导入/注册/数值/graph/共享调用方回归（历史唯一
  quantization 注册单测须在正式评测结束后补跑）
- [x] 未通过吞异常、空实现、扩大 skip/xfail 或无依据放宽容差掩盖问题
- [x] 未混入临时脚本、复制测试套件、原始日志、机器路径、预编译环境快照或无关重构
- [x] 已单独说明 inherited diff、本任务差异及不可合并的内容；未擅自处理他人改动
- [x] 审查结论对应当前 HEAD 与 dirty diff，变更后失效部分已重审

## 结论与 PR 材料

- 结论：`可作为 PR 候选（补验后）`。职责和 diff 自检未发现新的非必要生产路径；提交前
  仍须在正式 GPQA 结束后补跑历史唯一 quantization 注册测试并更新本记录。
- 阻塞问题、设计债务、未验证项和下一步：无设备导入受 HY4 基线 eager FlagGems import
  限制；v0.24 monkeypatch 等待正式扩展点；CUDA/其他平台、多模态/MTP/长上下文未验证。
- PR 问题与行为说明、设计理由、测试和限制：以 HY4 为 base 增加 GLM hybrid 模型及 PPU
  backend/cache 协议；公共 dispatch 只增加默认保持兼容的 input support 与 side-effect
  fallback 契约；列出 53 项最新回归、TP16 c8 和未验范围，不把 SQLite mitigation 写成代码修复。
- 建议的 PR 范围或拆分及依赖：建议拆为（1）公共 dispatch capability + MoE clamp；
  （2）GLM config/model/v0.24 cache adapter；（3）T-Head backend/KPool kernels + tests/docs。
  三者依赖顺序明确；当前未 commit/push。
- 完整适配验收状态（与设计审查结论分开）：功能性服务与 graph c8 已通过；正式 GPQA
  198/c64 正在运行，accuracy/performance/summary 尚未完成，平台只标 `functional`。

生成此记录不授权提交、推送或创建 PR；这些操作仍需用户明确要求。

## 2026-09-07 65K 定向重放前复核

本轮未修改 Plugin、vLLM 或 FlagGems。部署身份重新按 tracked diff 与 canonical untracked
manifest 采集：Plugin 仍为 `5329cb1`，tracked diff SHA256 仍为 `a760b276...503`，
untracked manifest SHA256 为 `50e1fb0a...5d0`；vLLM/FlagGems 仍为上述 revision 且 clean。
服务 `max_model_len 50000 → 65536` 属 runtime 配置，不进入 Plugin PR。因而原影响矩阵、
守卫边界和未验证平台结论不变；新的长上下文只作为 acceptance 证据，不宣称新增代码能力。

## 2026-09-09 dispatch 边界重审（当前结论）

本节取代上文关于 `OpImpl.supports`、`allow_runtime_fallback`、
`dispatch/backends/glm5next.py` 和 `ops/glm5next.py` 的设计结论。当前 Plugin 基线为
`support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`，editable 源码为
`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`。

- `dispatch/manager.py` 和 `dispatch/types.py` 已恢复到基线内容，不再为单一模型增加公共
  input-aware selection 或 stateful fallback 字段；对应专项 `test_input_support.py` 已删除。
- 删除 `dispatch/backends/glm5next.py`、`ops/glm5next.py` 及 reference/vendor 下两个
  `glm5next.py` 聚合文件。模型调用契约由 GLM model/indexer 自身持有，三类实现分别在
  FlagGems、reference、vendor.thead 的既有 `register_ops.py` 注册。
- 有状态 PPU 算子只注册 `vendor.thead` 一个候选，因此基线 manager 即使为 non-strict
  policy，也没有失败后切换到另一个实现并重复写 cache/state 的路径。
- FlagGems 仅注册固定 BF16 模型契约实际使用的 rotation、MQA、prefill/decode top-k、
  mHC 和 bounded activation；失去注册的 recurrent KDA、FP8/cache/pack wrappers 与
  `supports_*` 均已删除。核心 KPool/tail/safe-KDA 继续由 vendor 延迟导入。
- 唯一公共 dispatch 改动是 `dispatch/__init__.py` 的 27 行 graph 准备逻辑：弱引用收集
  `CachedOp`，在 FULL graph capture 前完成实现选择和 lazy import，从而不在 capture 中
  进入 manager `RLock`。该变更不修改选择顺序、fallback、类型或 policy。

重审验证：226 个 Plugin Python 文件通过 `compile()`；GLM 回归加共享
manager/types/registry/call-op 共 `101 passed, 1 warning in 11.07s`；`git diff --check`
通过。vLLM `ee0da84` 与 FlagGems `bca444b` 均保持 clean，既有服务 PID `2893015`
保持存活但未加载新源码。当前结论为“设计边界可作为 PR 候选”；冷启动、最小推理和 FULL
decode graph replay 尚未执行，因此不能把本次代码整理视为新一轮整模验收通过。未 commit、
未 push、未创建 PR。

## 2026-09-09 GLM 文件归并复核

当前模型/patch 文件结构进一步收敛为两个入口：

- `vllm_fl/models/glm5next.py` 单文件持有 checkpoint 所需的 text model、sparse indexer、
  KPool contract 与 `Glm5NextForConditionalGeneration` wrapper；
- `vllm_fl/patches/glm5next.py` 单文件持有配置转换、模型注册、graph metadata、KPool 与
  runner adapter。

原三个模型辅助模块和三个 patch 辅助模块已删除，生产源码中没有旧模块 import 或 registry
路径。合并没有新增共享 dispatch API，也未改变 backend 注册顺序、kernel 数学、cache layout
或 graph 准备逻辑。运行时注解保持主模型原语义，以满足 vLLM `support_torch_compile` 的动态
维度识别。

本轮受控验证为 102/102 项 GLM/共享 dispatch 测试通过、全 Plugin Python 内存编译通过、
`git diff --check` 通过。两个最终文件 SHA-256 分别为
`7d6338f958ec5de9f6885b760be1283b338daedc094a3edf362841d402038609` 和
`3e5ffa933e1d5f5a0f605b995b39c74c268dc54c80c30d09121c29d2ddd1b8de`。原文件备份位于远端
`05-tmp/glm-file-merge-backup-20260909`。服务未重启，故 PR 候选结构检查通过，但新源码的
冷启动、最小推理与 FULL decode graph replay 仍待维护窗口验证。

## 2026-09-09 Git 分支交付

- 目标仓库：`https://github.com/ZenithJoyH/vllm-plugin-FL.git`。
- PR base：`support-hy4-preview@939e07826bfec9cfa3da4a75af3ebaedfcef9af2`。
- 已发布分支：`support-glm5.3-flash`。
- 已发布 commit：`1bec1a407fac43304fcc84864999541e92590425`；提交说明为
  `feat: support GLM-5.3-Flash on T-Head PPU`，作者为
  `ZenithJoyH <1355922182@qq.com>`。
- 提交范围：33 个文件，7,381 行新增、107 行删除；提交前工作树内容无部署绝对路径、
  Host/服务名、符号链接或临时产物，staged `git diff --check` 通过。
- 发布方式：从 PPU-13 的精确 commit 创建 Git bundle，临时传到本机 `/private/tmp` 的裸仓库，
  使用用户授权的本机 GitHub 身份推送；远端分支 ref 已回读并与上述 40 位 SHA 完全一致。
- 没有创建 PR。远端临时 bundle 与无密钥 askpass helper 的清理未获执行审批，暂留在批准的
  `05-tmp/`；二者均不包含 GitHub token。

用户随后明确要求修正基线提交身份：原
`d56f7b285af2b3dd735847cb6d5a30f29beccfb8` 以相同 tree、parent、message 和时间重建为
`939e07826bfec9cfa3da4a75af3ebaedfcef9af2`，author/committer 均为
`ZenithJoyH <1355922182@qq.com>`；GLM 子提交因父 SHA 改变，以相同 tree、message、时间和
身份重建为 `1bec1a407fac43304fcc84864999541e92590425`。两个远端分支通过单次原子
`force-with-lease` 更新，old/new tree 的 `git diff --exit-code` 均为 0，GitHub ref 与 API
回读通过。PPU-13 本地两条 branch ref 及 GLM upstream 已同步，工作树保持 clean。

## 2026-09-09 upstream 同步

GitHub fork metadata 确认 upstream 为 `https://github.com/flagos-ai/vllm-plugin-FL.git`，默认
分支为 `main`。同步时 `upstream/main` 为
`8926c1188be20f805f62d42555697936ec781c20`：相对共同祖先包含 7 个新提交，Hy4 分支包含
3 个自有提交，GLM 再领先 Hy4 1 个提交。

为保留刚修正的提交身份和 SHA 历史，采用非破坏性 merge 而非 rebase：

- `support-hy4-preview@2f7bcc0bb653e24cf6b5558965ce6712e2002b60` 的两个父提交为
  `939e078` 与 `upstream/main@8926c118`；
- `support-glm5.3-flash@e1f941860bdc647aaab8928d6007391e8a0561d8` 的两个父提交为
  `1bec1a4` 与同步后的 Hy4 `2f7bcc0`。

两层 merge 均只在 `vllm_fl/dispatch/backends/reference/register_ops.py` 发生内容冲突。解决
方案保留 upstream 的逐项 `getattr` 注册，使缺失的可选 MoE helper 不再阻断其他 reference
fallback；同时保留 Hy4 BF16 indexer 及 GLM adaptation reference ops。其余 upstream 变更均
自动合并，没有整文件选择 ours/theirs。

本机临时 worktree 对 Hy4 207 个、GLM 229 个 Python 文件完成内存编译；同步结果传到 PPU-13
后，editable checkout 中 230 个 Python 文件完成内存编译，GLM、builtin registration 与共享
dispatch 聚焦回归 `107 passed, 1 warning in 11.42s`，同步 diff 的 `git diff --check` 通过。
两个分支以非 force 的单次原子 fast-forward 推送；GitHub refs、PPU-13 的 origin/upstream refs、
本地 branches 和 GLM tracking 均一致，工作树 clean。既有 8010 服务继续返回
`GLM-5.3-Flash-BF16`、`max_model_len=65536`；服务未重启，因此这仍不是新源码冷启动或 FULL
graph 整模验收。

## 2026-09-09 线性历史与 Hy4 squash（取代上述 merge 拓扑）

按用户要求重新整理两个发布分支，不再保留两层 merge commit。以同步时再次从 GitHub
确认的 `flagos-ai/vllm-plugin-FL@main` revision
`8926c1188be20f805f62d42555697936ec781c20` 为共同基线：

- 将 Hy4 的 `5329cb1`、`795f7c9`、`939e078` 三个自有提交合并为单提交
  `support-hy4-preview@06efe801ea3a47e20e492f048eef254ffcc337fa`；
- 将 GLM 适配重放为其唯一子提交
  `support-glm5.3-flash@424c0dd558f5c55619e68022de4f713d9b41b2a1`；
- 两笔新提交的 author 与 committer 均为
  `ZenithJoyH <1355922182@qq.com>`，最终 `upstream/main..support-glm5.3-flash`
  恰好只有这两笔线性提交。

唯一内容冲突仍是 reference backend 注册列表，解决结果沿用已验证的动态 optional
registration，同时保留 Hy4 BF16 indexer 和 GLM adaptation reference ops。新 Hy4 tree 与
原同步结果 `2f7bcc0`、新 GLM tree 与原同步结果 `e1f9418` 的 `git diff --quiet` 均为 0，
因此历史整理没有引入代码内容变化。

PPU-13 上先通过 validation refs 检出新 GLM 提交，不移动正式分支；全 Plugin Python
`compileall` 通过，GLM、builtin registration 与共享 dispatch 聚焦回归
`107 passed, 1 warning in 11.42s`，工作树保持 clean。随后以带旧 SHA 守卫的 Git ref
transaction 原子移动两个本地分支，并用单次 `git push --atomic --force-with-lease` 更新
GitHub。GitHub、PPU-13 本地 branches、origin tracking 与 upstream/main 均已回读一致；
8010 服务继续健康，未停止或重启容器及服务。本次只验证相同源码 tree 和专项回归，不新增
冷启动或 FULL graph 整模验收结论。

## 2026-09-10 GLM 支持提交再次合并

FlagGems 实现迁移和 provider 重分类最初形成第二笔 GLM 提交 `0990e2a`。按用户要求，已将
该提交与 GLM 初始适配 `1fe6a43` 合并为单提交：

`upstream/main@8926c118` →
`support-hy4-preview@cf07a83bb1ffcea6cce20652095dc1cc05333e73` →
`support-glm5.3-flash@601aa097494c98644ecc5019207f815472c859c9`。

新 GLM 提交直接父提交为 Hy4，`cf07a83..601aa09` 仅有一笔提交；源码 tree 仍为
`5e07d11103d9a7719443756cb4d3dfe686acbae2`，与合并前 `0990e2a` 完全一致。提交 subject 为
`feat: support GLM-5.3-Flash on T-Head PPU`，author/committer 均为
`ZenithJoyH <1355922182@qq.com>`。GitHub 更新使用精确旧 SHA `0990e2a` 的
`--force-with-lease`，没有覆盖竞态更新。

PPU-13 容器 checkout 已对齐到 `601aa09`，工作树 clean；FlagGems 保持
`187fc1f7bc59616d0c9eadd8d463e8d6068b22d9`。合并后 Plugin lazy-dispatch 聚焦回归
`5 passed, 1 warning`，既有模型服务继续 health 200，容器保持 running/restart 0。由于
源码 tree 未变化，本轮没有重复重启服务或重做 full graph；最近一次相同 tree 的 TP16
`FULL_DECODE_ONLY` 7/7 capture 和变更输入 replay 证据仍有效。

## 2026-09-10 通用能力命名与单 PR 终审

最终审查删除了无调用者的 `vllm_fl/kernels/` 和独立
`dispatch/backends/flaggems/impl/bounded_activation.py`。bounded SwiGLU 对外契约是通用
`silu_and_mul_with_clamp` 能力，因此 FlagGems adapter 与 PyTorch reference 均归入既有
`impl/activation.py`；注册辅助命名由 adaptation 改为 capability。模型仍通过 CachedOp
调用，backend provider 与可选依赖判断仍由既有 dispatch 承担，未修改 manager/types。

GitHub 当前 `support-hy4-preview` 已前进到
`ff87b683ec9c6c1925dbedf12261914e45569b52`。为避免 PR 夹带分叉的 Hy4 历史，唯一 GLM
提交已原样 rebase 到该提交，range-diff 等价；最终 HEAD 为
`163dd266174981dba3e00c41ff91e312c5e44655`，author/committer 均为
`ZenithJoyH <1355922182@qq.com>`。PR
[ZenithJoyH/vllm-plugin-FL#2](https://github.com/ZenithJoyH/vllm-plugin-FL/pull/2)
以 `support-hy4-preview` 为 base、`support-glm5.3-flash` 为 head，GitHub 回读为 1 个提交、
27 个文件、`MERGEABLE`，且该 head 只有这一个打开的 PR。

PPU-13 editable Plugin 工作树已精确对齐最终提交并保持 clean；聚焦回归 `17 passed`。
最终代码冷启动再次完成 120/120 shard、TP16 decode FULL graph 7/7、health 200；首次执行与
replay 返回 `2`、`5`，当前运行区间终止错误为 0，容器保持 running/restart 0。本轮是代码
职责和提交历史收口，未重跑 GPQA 或性能验收。

## 2026-09-10 共享 row-wise top-k 终审

跨模型调用审查发现，GLM 以 `sparse_indexer_topk_*` 名义直接使用 FlagGems 低层 ABI，
HY4 的 `bf16_indexer_decode` backend 又维护了一套独立 adapter。两者底层数学均是“在每行
有效 token 范围内选 top-k”，可以共享 capability；但 HY4 composite 还负责 paged MQA 和
最终候选排序，不能把 model 入口直接替换为裸 top-k。

本轮新增通用 `top_k_per_row_prefill/decode` dispatch 名和 FlagGems/reference adapter：

- GLM model 只传 logits、范围/长度和 caller-owned 输出，不再感知 provider 的 row count、
  stride 与 top-k 参数 ABI；
- HY4 prefill 已从本地 `torch.topk` 改为调用通用 capability；decode model 仍调用
  `bf16_indexer_decode`，该 composite backend 内部复用同一个通用 helper；
- 一维 `[batch]` 最终长度继续使用 FlagGems 的 `next_n` 推导；二维
  `[batch,next_n]` 显式长度 flatten 后以 provider `next_n=1` 调用，避免旧实现只取最后一列
  而丢失逐行语义；
- 删除 sparse-indexer 内重复 top-k wrapper 和旧 model-scoped 注册名；没有修改
  manager/types，没有新增 Plugin Triton kernel，FlagGems 仍按函数内惰性 import。

通用 capability 与 HY4 prefill/decode 调用面的 11 个文件已收敛为
`support-hy4-preview@4f9630ca0701d5a569d8c8ee7cff6e039f15a9c9`；当前唯一 GLM
提交为 `d07e87035b253ba407772a168d266ab22c23d845`，直接父提交是 `4f9630c`，
author/committer 均为
`ZenithJoyH <1355922182@qq.com>`；GitHub PR #2 回读为 1 commit、27 files、`MERGEABLE`。
FlagGems 为 `flaggems-for-day0@8fef991a6b97d85310f1a3cd9c6425e84d395e5d`，相对
`origin/master@749a6d2` ahead 2 / behind 0；本轮不改 FlagGems kernel。

聚焦回归为 `22 passed, 1 warning`，包含 HY4 prefill/shared-capability 与 composite
ownership、旧 op 未注册、1D/2D metadata 契约、真实 PPU prefill 无序集合对照，以及改变
logits 和二维长度后的 graph replay 数值对照。GLM
冷启动完成 120/120 shard、decode FULL graph 7/7，health 200，连续请求返回 `2`、`5`，
本轮日志终止错误 0，容器 running/restart 0。当前环境没有 HY4 权重，因此未宣称 HY4
整模服务、精度或性能通过；本轮也未重跑 GLM GPQA/性能验收。GLM 最终 tree hash 为
`4f6398523b0ff43fdf8a81be02502e2ad13ec98f`；GitHub PR #2 当前回读为 1 commit、
27 files、`MERGEABLE`，证明共享/HY4 文件已从 GLM diff 下沉到 base。详细证据见
[030](../adaptation/030-shared-rowwise-topk-20260910.md)。

## 2026-09-10 剩余 FlagGems capability 终审

本轮实际 diff 继续遵守“计算 kernel 归 FlagGems、框架只做通用调度”的边界：Plugin 仅在
`dispatch/backends/flaggems/register_ops.py` 增加六条 capability binding，并在既有 lazy
dispatch 测试中增加相同六项断言；未新增 Plugin kernel、模型目录、manager/types 修改或
机器名特判。依赖不存在或被策略禁用时，既有 `reference.torch` fallback 仍保留。

FlagGems 以 `origin/master@e15b22dc` 为基线拆成两个互不夹带的模型分支：
`support-glm5.3-flash@4a3cba02` 与 `support-qwen3.8-flash@ffb3a8bf`，各只有一笔自有提交。
GLM 分支复用 pack/unpack，新增通用 pool/tail mapping、varlen causal-conv 和 fused-gate chunk
KDA；Qwen 分支只含 `qwen3_8_flash_next` 相关文件和测试。两者均已发布到
`ZenithJoyH/FlagGems`，容器 checkout 与远端一致且 clean。

影响矩阵：新增 prefill 计算路径只影响 GLM KDA/indexer capability；decode 继续使用已验证的
`causal_conv1d_update`、`fused_safe_kda_gate` 和 `fused_recurrent_kda`。FlagGems 数值测试
11/11、Plugin 聚焦测试 9/9；六条真实 dispatch 均为 `default.flagos`。最终 TP16 冷启动完成
decode FULL graph 7/7、16/16 worker、health 200，smoke 返回 `2`，致命错误 0、容器 restart 0。
未执行 HY4 整模、GPQA 或正式性能验收，不能据此扩大支持范围或标记 optimized。完整记录见
[031](../adaptation/031-flaggems-day0-diverged-sync-blocker-20260910.md)。
