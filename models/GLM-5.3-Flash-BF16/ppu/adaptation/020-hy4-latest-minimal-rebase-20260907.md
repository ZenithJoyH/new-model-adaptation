# 020：基于最新 Hy4 基线重整 GLM-5.3-Flash 适配

## 元数据

- 状态：`mitigated-pending-no-padding-routing-fix`
- 首次出现时间：2026-09-07
- 最后验证时间：2026-09-07
- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU / `PPU-13`
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin：新 checkout
  `/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`，基线
  `support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8`
- 外部只读对照：旧 plugin `/workspace/vllm-plugin-FL-glm53-hy4-adaptation`，
  `5329cb1293f397fd194852496cfcc710c35f1bfc` 加 dirty GLM 实现；vLLM
  `ee0da84ab9e04ac7610e28580af62c365e898389`；新 FlagGems checkout
  `dcd0cfeae8187dee691656c0616c1ed95899c2ae` 保持干净。
- 执行模式与负载：源码归属/最小 diff、focused regression、TP16 graph 服务和最小真实
  推理；不重复未选择的正式精度验收。

## 问题现象

- 用户指出旧 GLM 插件适配代码过于杂乱，并提供更新后的 Hy4 基线。
- 旧树相对 `5329cb1` 有 11 个 tracked 修改、34 个未跟踪路径；其中可能包含已被
  `d56f7b2` 上游吸收的 Hy4/dispatch 能力、重复实现和仅为旧基线兼容的 patch。
- 影响范围是插件设计和可维护性；当前服务可运行不证明这些文件全部必要。

## 已有经验匹配

| 历史问题 | 相同点 | 差异 | 可信度 | 本次决定 |
|---|---|---|---|---|
| 009 Hy4 基线迁移 | 同一插件分支与模型族 | 当时基线为 `5329cb1`，本轮上游已到 `d56f7b2` | 高 | 只作候选清单，重新三方比较 |
| 014 共享 prefill/YAML 收敛 | 目标是删除重复路径 | 新基线可能已改变 dispatch/模型实现 | 中 | 不直接搬运旧结论 |
| 001/008 graph 修复 | 记录了 PPU KPool/indexer 实际故障 | 修复是否仍需以新基线代码为准 | 高 | 保留失败签名，逐项验证实现归属 |

## 诊断与假设

- 已验证：新 checkout 干净且精确位于批准的 `01-repos/`；上游 HEAD 为 `d56f7b2`。
- 假设：新 Hy4 基线已吸收一部分模型、dispatch 或 backend 能力，旧 GLM diff 可显著缩小。
- 不接受“旧文件曾跑通整模”作为保留依据；每项必须关联 GLM checkpoint 契约、PPU
  能力缺口、实际调用方和 focused regression。

先执行下列只读对比。所有远端 shell 都先进入已批准 root；容器内命令使用显式 `-w`：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$new" glm5.3-flash bash -lc '\''test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL; echo COMMITS; git log --oneline --decorate 5329cb1293f397fd194852496cfcc710c35f1bfc..HEAD; echo UPSTREAM_DIFF; git diff --stat 5329cb1293f397fd194852496cfcc710c35f1bfc..HEAD; git diff --name-status 5329cb1293f397fd194852496cfcc710c35f1bfc..HEAD; echo GLM_HY4_PATHS; find vllm_fl examples tests -type f | sort | grep -Ei "glm|hy_v4|hy4|kda|indexer|kpool|mhc"'\''; docker exec -w "$old" glm5.3-flash bash -lc '\''test "$(pwd -P)" = /workspace/vllm-plugin-FL-glm53-hy4-adaptation; echo OLD_TRACKED_DIFF; git diff --no-ext-diff -- vllm_fl; echo OLD_UNTRACKED; git ls-files --others --exclude-standard'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$old" glm5.3-flash bash -lc '\''git ls-files -m; git ls-files --others --exclude-standard'\'' | while IFS= read -r path; do test -n "$path" || continue; old_line=$(docker exec -w "$old" glm5.3-flash sha256sum "$path"); old_sum=${old_line%% *}; if docker exec -w "$new" glm5.3-flash test -f "$path"; then new_line=$(docker exec -w "$new" glm5.3-flash sha256sum "$path"); new_sum=${new_line%% *}; if test "$old_sum" = "$new_sum"; then state=SAME; else state=DIFF; fi; else new_sum=-; state=MISSING; fi; printf "%s %s %s %s\\n" "$state" "$old_sum" "$new_sum" "$path"; done'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; repo=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$repo" glm5.3-flash bash -lc '\''for file in README.md tests/README.md vllm_fl/dispatch/README.md; do echo FILE=$file; wc -l "$file"; sed -n "1,500p" "$file"; done; for file in vllm_fl/models/hy_v4.py vllm_fl/model_loader/hy_v4_loader.py vllm_fl/dispatch/config/thead.yaml vllm_fl/__init__.py; do echo FILE=$file; wc -l "$file"; sed -n "1,1200p" "$file"; done'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; repo=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; for spec in "README.md:1:260" "tests/README.md:1:420" "vllm_fl/dispatch/README.md:1:260" "vllm_fl/dispatch/README.md:261:620"; do file=${spec%%:*}; rest=${spec#*:}; first=${rest%%:*}; last=${rest##*:}; echo FILE=$file LINES=$first-$last; docker exec -w "$repo" glm5.3-flash sed -n "${first},${last}p" "$file"; done'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; for file in vllm_fl/dispatch/types.py vllm_fl/dispatch/manager.py vllm_fl/dispatch/__init__.py vllm_fl/dispatch/backends/flaggems/impl/bf16_indexer.py vllm_fl/dispatch/backends/reference/impl/bf16_indexer.py vllm_fl/dispatch/backends/vendor/thead/register_ops.py vllm_fl/dispatch/config/thead.yaml vllm_fl/attention/mla_prefill.py vllm_fl/configs/glm_moe_dsa.py vllm_fl/patches/glm_moe_dsa.py; do echo NEW_FILE=$file; docker exec -w "$new" glm5.3-flash sed -n "1,900p" "$file"; done; for file in vllm_fl/dispatch/backends/model_ops.py vllm_fl/ops/glm5_next.py vllm_fl/patches/glm5_next_v024.py vllm_fl/patches/glm5_next_kpool_v024.py; do echo OLD_FILE=$file; docker exec -w "$old" glm5.3-flash sed -n "1,1200p" "$file"; done'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; echo OLD_GLM_FILES; docker exec -w "$old" glm5.3-flash bash -lc '\''find vllm_fl examples/glm5_next tests -type f | sort | grep -E "glm5_next|glm5_(precision|support|tail)|flaggems_bindings_graph|input_support" | xargs -r wc -l'\''; echo OLD_IMPORT_GRAPH; docker exec -w "$old" glm5.3-flash bash -lc '\''rg -n "^(from|import) (vllm_fl|vllm)|glm5_next|CachedOp|allow_runtime_fallback|supports=" vllm_fl/configs/glm5_next.py vllm_fl/models/glm5_next.py vllm_fl/models/glm5_next_kpool.py vllm_fl/ops/glm5_next.py vllm_fl/patches/glm5_next_v024.py vllm_fl/patches/glm5_next_kpool_v024.py vllm_fl/__init__.py vllm_fl/dispatch/backends/model_ops.py'\''; echo LATEST_OWNERSHIP; docker exec -w "$new" glm5.3-flash bash -lc '\''rg -n "bf16_indexer|sparse_mla|supports=|allow_runtime_fallback|class CachedOp|class OpImpl|glm_moe_dsa|GLM" vllm_fl tests/dispatch examples/glm_5_offline_inference.py | head -n 1000'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; echo INIT_DIFF; docker exec -w "$old" glm5.3-flash git diff --no-ext-diff -- vllm_fl/__init__.py vllm_fl/attention/mla_prefill.py vllm_fl/dispatch/__init__.py vllm_fl/dispatch/manager.py vllm_fl/dispatch/types.py vllm_fl/ops/fused_moe/activation.py vllm_fl/ops/fused_moe/fused_moe_utils.py; echo MODEL_OPS; docker exec -w "$old" glm5.3-flash sed -n "1,500p" vllm_fl/dispatch/backends/model_ops.py; echo LATEST_BF16_TESTS; for file in tests/dispatch/test_bf16_indexer_backend_ownership.py tests/dispatch/test_flaggems_mla_sparse_no_padding.py; do docker exec -w "$new" glm5.3-flash sed -n "1,600p" "$file"; done'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; echo OLD_IMPORT_GRAPH; docker exec -w "$old" glm5.3-flash bash -lc '\''grep -nE "^(from|import) (vllm_fl|vllm)|glm5_next|CachedOp|allow_runtime_fallback|supports=" vllm_fl/configs/glm5_next.py vllm_fl/models/glm5_next.py vllm_fl/models/glm5_next_kpool.py vllm_fl/ops/glm5_next.py vllm_fl/patches/glm5_next_v024.py vllm_fl/patches/glm5_next_kpool_v024.py vllm_fl/__init__.py vllm_fl/dispatch/backends/model_ops.py'\''; echo LATEST_OWNERSHIP; docker exec -w "$new" glm5.3-flash bash -lc '\''grep -RInE "bf16_indexer|sparse_mla|supports=|allow_runtime_fallback|class CachedOp|class OpImpl|glm_moe_dsa|GLM" vllm_fl tests/dispatch examples/glm_5_offline_inference.py | head -n 1000'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; for file in vllm_fl/dispatch/backends/flaggems/impl/bf16_indexer.py vllm_fl/dispatch/backends/reference/impl/bf16_indexer.py vllm_fl/dispatch/backends/flaggems/register_ops.py vllm_fl/dispatch/backends/reference/register_ops.py vllm_fl/dispatch/backends/vendor/thead/register_ops.py vllm_fl/dispatch/backends/vendor/thead/thead.py vllm_fl/dispatch/config/thead.yaml vllm_fl/configs/glm_moe_dsa.py vllm_fl/patches/glm_moe_dsa.py; do echo NEW_FILE=$file; docker exec -w "$new" glm5.3-flash sed -n "1,700p" "$file"; done; echo OLD_REGISTRATION_DIFF; docker exec -w "$old" glm5.3-flash git diff --no-ext-diff -- vllm_fl/dispatch/backends/flaggems/register_ops.py vllm_fl/dispatch/backends/reference/register_ops.py vllm_fl/dispatch/backends/vendor/thead/register_ops.py vllm_fl/dispatch/config/thead.yaml'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; model=/mnt/cpfs/models/GLM-5.3-Flash-BF16; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash python3 -c '\''import json; p="/mnt/cpfs/models/GLM-5.3-Flash-BF16/config.json"; c=json.load(open(p)); keys=("model_type","architectures","torch_dtype","hidden_size","num_hidden_layers","num_attention_heads","head_dim","index_kpool","index_kpool_compress","index_topk","index_n_heads","index_head_dim","num_nextn_predict_layers","first_k_dense_replace","moe_layer_freq","n_routed_experts","num_experts_per_tok"); print({k:c.get(k) for k in keys}); print("text_config", {k:c.get("text_config",{}).get(k) for k in keys})'\''; echo OLD_PRODUCT_FILES; docker exec -w "$old" glm5.3-flash bash -lc '\''git ls-files --others --exclude-standard | grep -E "^(vllm_fl|tests)/" | grep -vE "(__pycache__|\.pyc$)" | sort'\''; echo OLD_PATCH_ENTRYPOINTS; docker exec -w "$old" glm5.3-flash bash -lc '\''sed -n "1,180p" vllm_fl/patches/glm5_next_v024.py; sed -n "1,180p" vllm_fl/patches/glm5_next_runner_v024.py; sed -n "500,570p" vllm_fl/models/glm5_next.py'\'''
```

首次逐文件哈希命令因 `awk` 引号转义错误产生了无效的 `SAME` 输出；未发生远端写入。
改用上方纯 shell 解析后重跑：11 个 tracked 修改相对新基线均为 `DIFF`，旧 GLM
未跟踪实现相对新基线均为 `MISSING`，因此不能把旧树整体判定为已被上游吸收。
远端镜像未安装 `rg`，第一次依赖图命令只输出了文件规模、没有得到 grep 证据；按仓库
规则改用可用的 `grep -RInE`（上方命令）复测，不把失败输出纳入结论。
第一条 mutation 前 clean 检查的命令替换发生在 host shell，因 host 未安装 `git` 而失败；
没有发生写入。紧随其后的修正版把替换限定在容器 `bash -lc` 中。
首次模型导入 one-liner 对 Python 字符串过度转义，解释器在模型路径处报 `SyntaxError`；
没有启动模型或写入状态。修正版改由 `docker exec -e PYTHONPATH` 直接调用 `python3 -c`。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 结果 | 结论 |
|---|---|---|---|---|---|
| 1 | Hy4 PR base | 旧 dirty tree @ `5329cb1` | 干净 `d56f7b2` checkout | 完成 | 上游新增 BF16 indexer ownership，但没有 `glm5_next` |
| 2 | 非 FlagGems 产品迁移 | 旧树全部 dirty 代码 | 只迁移模型/KPool/KDA、PPU/reference 和必要公共契约 | `compileall`、80 个 dispatch 单测和真实权重 config/import 通过 | 保留；不影响旧服务 |

第一批只迁移不依赖“最新 FlagGems checkout”结论的模型专属代码、PPU/reference
实现及其必要公共契约。FlagGems adapter 四个文件和 FlagGems backend 注册暂不迁移。
所有产品写入均指向新 checkout；旧服务使用的 `/workspace/...` 不变：

```bash
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase","state":"directory","mode":"0755"}' --check --diff
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase","state":"directory","mode":"0755"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; issue=$root/03-issues/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; test ! -e "$issue/non-flaggems-tracked.patch"; docker exec -w "$new" glm5.3-flash test -z "$(git status --porcelain)"'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; issue=$root/03-issues/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; test ! -e "$issue/non-flaggems-tracked.patch"; docker exec -w "$new" glm5.3-flash bash -lc '\''test -z "$(git status --porcelain)"'\'''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/workspace/vllm-plugin-FL-glm53-hy4-adaptation","glm5.3-flash","bash","-lc","git diff --no-ext-diff HEAD -- vllm_fl/__init__.py vllm_fl/attention/mla_prefill.py vllm_fl/dispatch/__init__.py vllm_fl/dispatch/manager.py vllm_fl/dispatch/types.py vllm_fl/dispatch/backends/reference/register_ops.py vllm_fl/dispatch/backends/vendor/thead/register_ops.py vllm_fl/dispatch/config/thead.yaml vllm_fl/ops/fused_moe/activation.py vllm_fl/ops/fused_moe/fused_moe_utils.py > /mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/non-flaggems-tracked.patch"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/non-flaggems-tracked.patch"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; patch=$root/03-issues/020-hy4-latest-minimal-rebase/non-flaggems-tracked.patch; cd "$root" && test "$(pwd -P)" = "$root"; test -s "$patch"; docker exec -w "$new" glm5.3-flash git apply --check --3way "$patch"'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","git","apply","--3way","/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/non-flaggems-tracked.patch"]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/workspace/vllm-plugin-FL-glm53-hy4-adaptation","glm5.3-flash","cp","--parents","vllm_fl/configs/glm5_next.py","vllm_fl/dispatch/backends/model_ops.py","vllm_fl/dispatch/backends/reference/impl/mhc.py","vllm_fl/dispatch/backends/reference/impl/sparse_indexer.py","vllm_fl/dispatch/backends/vendor/thead/impl/causal_conv1d.py","vllm_fl/dispatch/backends/vendor/thead/impl/gather_cache.py","vllm_fl/dispatch/backends/vendor/thead/impl/model_ops.py","vllm_fl/dispatch/backends/vendor/thead/impl/paged_mqa.py","vllm_fl/dispatch/backends/vendor/thead/impl/recurrent_kda.py","vllm_fl/dispatch/backends/vendor/thead/impl/sparse_indexer.py","vllm_fl/kernels/glm5_next/PROVENANCE.md","vllm_fl/kernels/glm5_next/__init__.py","vllm_fl/kernels/glm5_next/graph_metadata.py","vllm_fl/kernels/glm5_next/indexer_backend.py","vllm_fl/kernels/glm5_next/kpool_compress.py","vllm_fl/kernels/glm5_next/portable.py","vllm_fl/kernels/glm5_next/prefill_tail.py","vllm_fl/kernels/glm5_next/safe_kda.py","vllm_fl/kernels/glm5_next/sparse_attn_indexer_kpool.py","vllm_fl/models/glm5_next.py","vllm_fl/models/glm5_next_kpool.py","vllm_fl/models/glm5_next_multimodal.py","vllm_fl/ops/glm5_next.py","vllm_fl/patches/_version.py","vllm_fl/patches/glm5_next_kpool_v024.py","vllm_fl/patches/glm5_next_runner_v024.py","vllm_fl/patches/glm5_next_v024.py","vllm_fl/transformers_utils/__init__.py","vllm_fl/transformers_utils/processors/__init__.py","vllm_fl/transformers_utils/processors/glm5_next.py","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$new" glm5.3-flash bash -lc '\''git status --short; git diff --check; python3 -m compileall -q vllm_fl'\''; curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null && echo OLD_SERVICE_HEALTHY'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; for file in tests/unit_tests/dispatch/test_input_support.py tests/unit_tests/test_glm5_support.py tests/unit_tests/test_glm5_tail_graph.py tests/unit_tests/test_glm5_precision_graph.py tests/unit_tests/test_flaggems_bindings_graph.py; do echo FILE=$file; docker exec -w "$old" glm5.3-flash sed -n "1,700p" "$file"; done'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/workspace/vllm-plugin-FL-glm53-hy4-adaptation","glm5.3-flash","cp","--parents","tests/unit_tests/dispatch/test_input_support.py","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$new" glm5.3-flash bash -lc '\''PYTHONPATH="$PWD" pytest -q tests/unit_tests/dispatch/test_types.py tests/unit_tests/dispatch/test_manager.py tests/unit_tests/dispatch/test_call_op.py tests/unit_tests/dispatch/test_input_support.py'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$new" glm5.3-flash bash -lc '\''PYTHONPATH="$PWD" python3 -c "import vllm_fl; vllm_fl.register_model(); from vllm_fl.configs.glm5_next import Glm5NextConfig,Glm5NextTextConfig; from vllm_fl.models.glm5_next import Glm5NextForCausalLM; from vllm_fl.models.glm5_next_multimodal import Glm5NextForConditionalGeneration; c=Glm5NextConfig.from_pretrained(\\"/mnt/cpfs/models/GLM-5.3-Flash-BF16\\"); assert c.model_type==\\"glm5_next\\" and c.text_config.model_type==\\"glm5_next_text\\" and c.text_config.index_kpool==4 and c.text_config.index_kpool_compress; print(\\"GLM5_NEXT_REGISTRATION_IMPORT_CONFIG_PASS\\")"'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -e PYTHONPATH="$new" -w "$new" glm5.3-flash python3 -c '\''import vllm_fl; vllm_fl.register_model(); from vllm_fl.configs.glm5_next import Glm5NextConfig; from vllm_fl.models.glm5_next import Glm5NextForCausalLM; from vllm_fl.models.glm5_next_multimodal import Glm5NextForConditionalGeneration; c=Glm5NextConfig.from_pretrained("/mnt/cpfs/models/GLM-5.3-Flash-BF16"); assert c.model_type == "glm5_next" and c.text_config.model_type == "glm5_next_text" and c.text_config.index_kpool == 4 and c.text_config.index_kpool_compress; print("GLM5_NEXT_REGISTRATION_IMPORT_CONFIG_PASS")'\'''
```

## 根因

- 已确认：旧适配是在 `5329cb1` 上逐层补齐，而新基线已经把普通 BF16 Indexer 的
  cache-write/decode ownership、Thead native bundle fallback 和 sparse MLA 小 head 处理收回
  公共 backend；这些内容不应在 GLM5-Next 中重复实现。
- 同时确认目标权重不是新基线已有的 `glm_moe_dsa`：外层 `model_type=glm5_next`，文本
  配置为 `glm5_next_text`，包含 34 层 KDA、11 层 sparse MLA、`index_kpool=4` 且
  `index_kpool_compress=true`。因此模型类、KPool/tail cache、KDA、配置/处理器和 v0.24
  注册桥不能删除。
- 尚缺：FlagGems 专属 MHC/KDA/indexer adapter 必须在同步目标 FlagGems revision 后重新
  核对 ABI，不能直接把旧四个文件复制进新基线。

## 解决方法或 Workaround

- 选定层级：模型语义留在 GLM adapter/model；同语义算子沿用 dispatch/backend；PPU 限制留在
  `vendor.thead` 能力守卫；不在公共热路径按模型目录或权重路径分支。
- 新 checkout 是唯一修改目标；旧 checkout、vLLM 和 FlagGems 暂保持只读。
- 不复制旧树整体，不创建一键 patch 脚本；逐项迁移产品代码和可维护 focused tests。
- 已明确排除第一批非必要内容：`examples/glm5_next/` 两个历史说明、四个依赖设备的旧大
  测试文件，以及新 Hy4 已拥有的普通 BF16 indexer 实现；只保留 137 行 input-support
  契约测试。

## FlagGems 证据

- 当前外部 revision `34bd6d68` 干净但未在本轮同步；在检查或接入最新 FlagGems 算子前，
  需用户另行授权 `01-repos/FlagGems` checkout。
- 2026-09-07 用户已明确授权创建该 checkout。先确认既有 remote/branch 与上游 HEAD，
  再单 Host 创建，不覆盖意外目录：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; target=$root/01-repos/FlagGems; old=/workspace/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; test ! -e "$target"; docker exec -w "$old" glm5.3-flash bash -lc '\''git remote -v; git branch --show-current; git rev-parse HEAD; git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}"; git status --short; git ls-remote origin refs/heads/master refs/tags/v5.3.4'\'''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos","glm5.3-flash","git","clone","--branch","master","--single-branch","https://github.com/flagos-ai/FlagGems.git","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems/.git"}' --check --diff
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos","glm5.3-flash","git","clone","--branch","master","--single-branch","https://github.com/flagos-ai/FlagGems.git","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems/.git"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; repo=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; test "$(realpath "$repo")" = "$repo"; docker exec -w "$repo" glm5.3-flash bash -lc '\''git remote -v; git branch --show-current; git rev-parse HEAD; git rev-parse --abbrev-ref --symbolic-full-name "@{upstream}"; git status --short'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; repo=$root/01-repos/FlagGems; old_plugin=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$repo" glm5.3-flash bash -lc '\''echo COMMITS; git log --oneline --decorate 34bd6d68928c8b0039c42987840929da52aa6a62..HEAD; echo DIFF; git diff --stat 34bd6d68928c8b0039c42987840929da52aa6a62..HEAD; git diff --name-status 34bd6d68928c8b0039c42987840929da52aa6a62..HEAD | grep -Ei "mhc|kda|indexer|paged_mqa|top_k|pack_seq|hadamard|activation" || true'\''; echo ADAPTER_IMPORTS; docker exec -w "$old_plugin" glm5.3-flash bash -lc '\''grep -RInE "^(from|import) flag_gems|flag_gems\." vllm_fl/dispatch/backends/flaggems/impl/bounded_activation.py vllm_fl/dispatch/backends/flaggems/impl/mhc.py vllm_fl/dispatch/backends/flaggems/impl/recurrent_kda.py vllm_fl/dispatch/backends/flaggems/impl/sparse_indexer.py'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -e PYTHONPATH="$fg/src" -w "$fg" glm5.3-flash python3 -c '\''import importlib,inspect; specs={"flag_gems.fused.mhc":["mhc_pre","mhc_post"],"flag_gems.fused.silu_and_mul_with_clamp":["silu_and_mul_with_clamp_kernel"],"flag_gems.fused.indexer_k_quant_and_cache":["indexer_k_quant_and_cache"],"flag_gems.ops.per_token_group_quant_fp8":["per_token_group_quant_fp8"],"flag_gems.ops.hadamard_transform":["hadamard_transform"],"flag_gems.fused.fp8_fp4_mqa_logits":["fp8_fp4_mqa_logits"],"flag_gems.fused.bf16_paged_mqa_logits":["bf16_paged_mqa_logits"],"flag_gems.fused.cp_gather_indexer_k_quant_cache":["cp_gather_indexer_k_quant_cache"],"flag_gems.fused.top_k_per_row_prefill":["top_k_per_row_prefill"],"flag_gems.fused.top_k_per_row_decode":["top_k_per_row_decode"],"flag_gems.fused.pack_seq":["pack_seq_triton","unpack_seq_triton"],"flag_gems.fused.FLA.fused_recurrent":["fused_recurrent_gated_delta_rule_fwd_kernel"]}; [(print(m,n,hasattr(mod:=importlib.import_module(m),n),inspect.signature(getattr(mod,n)) if hasattr(mod,n) else "MISSING")) for m,names in specs.items() for n in names]'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -e PYTHONPATH="$fg/src" -w "$fg" glm5.3-flash python3 -c '\''import importlib,inspect; specs=[("flag_gems.fused.mhc","mhc_pre"),("flag_gems.fused.mhc","mhc_post"),("flag_gems.fused.silu_and_mul_with_clamp","silu_and_mul_with_clamp_kernel"),("flag_gems.fused.indexer_k_quant_and_cache","indexer_k_quant_and_cache"),("flag_gems.ops.per_token_group_quant_fp8","per_token_group_quant_fp8"),("flag_gems.ops.hadamard_transform","hadamard_transform"),("flag_gems.fused.fp8_fp4_mqa_logits","fp8_fp4_mqa_logits"),("flag_gems.fused.bf16_paged_mqa_logits","bf16_paged_mqa_logits"),("flag_gems.fused.cp_gather_indexer_k_quant_cache","cp_gather_indexer_k_quant_cache"),("flag_gems.fused.top_k_per_row_prefill","top_k_per_row_prefill"),("flag_gems.fused.top_k_per_row_decode","top_k_per_row_decode"),("flag_gems.fused.pack_seq","pack_seq_triton"),("flag_gems.fused.unpack_seq","unpack_seq_triton"),("flag_gems.fused.FLA.fused_recurrent","fused_recurrent_gated_delta_rule_fwd_kernel")]; out=[]; [(lambda o,m,n: out.append((m,n,True,(lambda: (inspect.signature(o) if callable(o) else type(o).__name__))()))(getattr(importlib.import_module(m),n),m,n) for m,n in specs]; [print(*x) for x in out]'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -e PYTHONPATH="$fg/src" -w "$fg" glm5.3-flash python3 -c '\''import importlib; specs=[("flag_gems.fused.mhc","mhc_pre"),("flag_gems.fused.mhc","mhc_post"),("flag_gems.fused.silu_and_mul_with_clamp","silu_and_mul_with_clamp_kernel"),("flag_gems.fused.indexer_k_quant_and_cache","indexer_k_quant_and_cache"),("flag_gems.ops.per_token_group_quant_fp8","per_token_group_quant_fp8"),("flag_gems.ops.hadamard_transform","hadamard_transform"),("flag_gems.fused.fp8_fp4_mqa_logits","fp8_fp4_mqa_logits"),("flag_gems.fused.bf16_paged_mqa_logits","bf16_paged_mqa_logits"),("flag_gems.fused.cp_gather_indexer_k_quant_cache","cp_gather_indexer_k_quant_cache"),("flag_gems.fused.top_k_per_row_prefill","top_k_per_row_prefill"),("flag_gems.fused.top_k_per_row_decode","top_k_per_row_decode"),("flag_gems.fused.pack_seq","pack_seq_triton"),("flag_gems.fused.unpack_seq","unpack_seq_triton"),("flag_gems.fused.FLA.fused_recurrent","fused_recurrent_gated_delta_rule_fwd_kernel")]; [(print(m,n,type(getattr(importlib.import_module(m),n)).__name__)) for m,n in specs]'\'''
```

首次 ABI signature 命令在 Triton `Heuristics` 对象上调用 `inspect.signature` 后中止，且把
`unpack_seq_triton` 错列在 `pack_seq` 模块；前面的 12 个符号已确认存在，但该输出不完整。
修正版区分 `unpack_seq` 模块，并对非 Python callable 输出对象类型。
第二版 one-liner 自身括号不匹配，在 import 前即 `SyntaxError`；没有写入。最终版只验证
每个模块/符号可解析并输出对象类型，签名使用第一次命令已成功打印的部分作为证据。

上游差异确认未改动这些算子，14 个依赖符号全部可解析后，才迁移四个薄 adapter 和
FlagGems backend 注册；不修改 FlagGems 源码：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; issue=$root/03-issues/020-hy4-latest-minimal-rebase; new=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; test ! -e "$issue/flaggems-register.patch"; for file in bounded_activation.py mhc.py recurrent_kda.py sparse_indexer.py; do test ! -e "$new/vllm_fl/dispatch/backends/flaggems/impl/$file"; done'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/workspace/vllm-plugin-FL-glm53-hy4-adaptation","glm5.3-flash","bash","-lc","git diff --no-ext-diff HEAD -- vllm_fl/dispatch/backends/flaggems/register_ops.py > /mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/flaggems-register.patch"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/flaggems-register.patch"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; patch=$root/03-issues/020-hy4-latest-minimal-rebase/flaggems-register.patch; cd "$root" && test "$(pwd -P)" = "$root"; test -s "$patch"; docker exec -w "$new" glm5.3-flash git apply --check --3way "$patch"'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","git","apply","--3way","/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/flaggems-register.patch"]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/workspace/vllm-plugin-FL-glm53-hy4-adaptation","glm5.3-flash","cp","--parents","vllm_fl/dispatch/backends/flaggems/impl/bounded_activation.py","vllm_fl/dispatch/backends/flaggems/impl/mhc.py","vllm_fl/dispatch/backends/flaggems/impl/recurrent_kda.py","vllm_fl/dispatch/backends/flaggems/impl/sparse_indexer.py","tests/unit_tests/test_glm5_support.py","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -e PYTHONPATH="$plugin:$fg/src" -w "$plugin" glm5.3-flash bash -lc '\''git diff --check; python3 -m compileall -q vllm_fl; pytest -q tests/unit_tests/dispatch/test_types.py tests/unit_tests/dispatch/test_manager.py tests/unit_tests/dispatch/test_call_op.py tests/unit_tests/dispatch/test_input_support.py tests/unit_tests/test_glm5_support.py'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; libs=/mnt/nfs/users/jinghao/lib; cd "$root" && test "$(pwd -P)" = "$root"; echo PROVIDED_LIBS; find "$libs" -maxdepth 1 -type f -name "*.so" -exec sha256sum {} + | sort; echo OLD_PLUGIN_LIBS; docker exec -w "$old" glm5.3-flash bash -lc '\''find vllm_fl/dispatch/backends/vendor/thead/lib -maxdepth 1 -type f -name "*.so" -exec sha256sum {} + 2>/dev/null | sort; sed -n "1,320p" vllm_fl/dispatch/backends/vendor/thead/bootstrap.py; sed -n "1,320p" vllm_fl/dispatch/backends/vendor/thead/impl/native_extensions.py'\''; echo NEW_PLUGIN_LIB_DIR; docker exec -w "$plugin" glm5.3-flash bash -lc '\''find vllm_fl/dispatch/backends/vendor/thead/lib -maxdepth 1 -type f -print 2>/dev/null | sort || true; sed -n "1,320p" vllm_fl/dispatch/backends/vendor/thead/bootstrap.py'\'''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/lib","glm5.3-flash","cp","_C_stable_libtorch.abi3.so","_C.abi3.so","_moe_C.abi3.so","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL/vllm_fl/dispatch/backends/vendor/thead/lib/"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; sha256sum /mnt/nfs/users/jinghao/lib/_C_stable_libtorch.abi3.so /mnt/nfs/users/jinghao/lib/_C.abi3.so /mnt/nfs/users/jinghao/lib/_moe_C.abi3.so; docker exec -e PYTHONPATH="$plugin:$fg/src" -w "$plugin" glm5.3-flash python3 -c '\''from vllm_fl.dispatch.backends.vendor.thead.impl.native_extensions import load_all_native_extensions,native_extension_is_available; load_all_native_extensions(); required=(("cache","_C_cache_ops::concat_and_cache_mla"),("core","_C::dynamic_scaled_int8_quant"),("moe","_moe_C::grouped_topk")); print([(c,o,native_extension_is_available(c,o)) for c,o in required])'\''; docker exec -w "$plugin" glm5.3-flash sha256sum vllm_fl/dispatch/backends/vendor/thead/lib/_C_stable_libtorch.abi3.so vllm_fl/dispatch/backends/vendor/thead/lib/_C.abi3.so vllm_fl/dispatch/backends/vendor/thead/lib/_moe_C.abi3.so'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash bash -lc '\''pidfile=/workspace/glm53-adaptation-runtime/graph-flaggems-db-timeout/service.pid; test -s "$pidfile"; pid=$(cat "$pidfile"); echo PID=$pid; ps -o pid,ppid,pgid,sid,stat,etime,comm,args -p "$pid"; pgrep -a -f "vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16|VLLM::Worker" || true; curl -fsS --max-time 5 http://127.0.0.1:8010/health; sed -n "1,260p" /mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph.sh; sed -n "1,260p" /mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph_host.sh'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash bash -lc '\''service_pid=$(pgrep -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16" | head -n 1); test -n "$service_pid"; echo SERVICE_PID=$service_pid; ps -o pid,ppid,pgid,sid,stat,etime,comm,args -p "$service_pid"; pstree -aps "$service_pid" || true; pgrep -a -f "resource_lock.py|graph-65k-40k-20260907-v2/supervisor.sh" || true; sed -n "1,320p" /mnt/nfs/users/jinghao/glm5.3-flash/runs/graph-65k-40k-20260907-v2/supervisor.sh'\'''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/020-hy4-latest-minimal-rebase","state":"directory","mode":"0755"}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/06-tmp/020-hy4-latest-minimal-rebase","state":"directory","mode":"0755"}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase","state":"directory","mode":"0755"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash bash -lc '\''service_pid=1339072; test "$(tr "\\0" " " </proc/$service_pid/cmdline)" = "/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16 --served-model-name GLM-5.3-Flash-BF16 --tensor-parallel-size 16 --host 127.0.0.1 --port 8010 --max-model-len 65536 --max-num-seqs 32 --gpu-memory-utilization 0.90 --reasoning-parser glm45 --compilation-config {\\"cudagraph_mode\\":\\"PIECEWISE\\"} "; ps -o pid,ppid,pgid,sid,stat,args -p "$service_pid"'\'''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","glm5.3-flash","kill","-TERM","1339072"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; for _ in $(seq 1 60); do if ! docker exec glm5.3-flash kill -0 1339072 2>/dev/null; then break; fi; sleep 1; done; ! docker exec glm5.3-flash kill -0 1339072 2>/dev/null; ! docker exec glm5.3-flash pgrep -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16"; ! curl -fsS --max-time 3 http://127.0.0.1:8010/health; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-e","PYTHONPATH=/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL:/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems/src","-e","CUDA_VISIBLE_DEVICES=0","-e","PYTHONDONTWRITEBYTECODE=1","-e","TRITON_CACHE_DIR=/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/triton","-e","TMPDIR=/mnt/nfs/users/jinghao/glm5.3-flash/06-tmp/020-hy4-latest-minimal-rebase","-e","FLAGGEMS_DB_URL=sqlite:////mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/TunedConfig_thead_triton_3_6.db?timeout=1800","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","bash","-lc","set -o pipefail; pytest -q -p no:cacheprovider /workspace/vllm-plugin-FL-glm53-hy4-adaptation/tests/unit_tests/test_glm5_precision_graph.py /workspace/vllm-plugin-FL-glm53-hy4-adaptation/tests/unit_tests/test_glm5_tail_graph.py 2>&1 | tee /mnt/nfs/users/jinghao/glm5.3-flash/05-runs/020-hy4-latest-minimal-rebase/precision-tail-graph.log"]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-e","PYTHONPATH=/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL:/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems/src","-e","CUDA_VISIBLE_DEVICES=0","-e","PYTHONDONTWRITEBYTECODE=1","-e","TRITON_CACHE_DIR=/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/triton","-e","TMPDIR=/mnt/nfs/users/jinghao/glm5.3-flash/06-tmp/020-hy4-latest-minimal-rebase","-e","FLAGGEMS_DB_URL=sqlite:////mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/TunedConfig_thead_triton_3_6.db?timeout=1800","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","bash","-lc","set -o pipefail; pytest -q -p no:cacheprovider /workspace/vllm-plugin-FL-glm53-hy4-adaptation/tests/unit_tests/test_flaggems_bindings_graph.py 2>&1 | tee /mnt/nfs/users/jinghao/glm5.3-flash/05-runs/020-hy4-latest-minimal-rebase/flaggems-bindings-graph.log"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash bash -lc '\''echo STATUS; git status --short; echo DIFF_STAT; git diff HEAD --stat; git diff HEAD --numstat; for file in vllm_fl/patches/_version.py vllm_fl/transformers_utils/__init__.py vllm_fl/transformers_utils/processors/__init__.py; do echo FILE=$file; sed -n "1,260p" "$file"; done; echo CALLERS; grep -RInE "patches\._version|is_vllm_024|transformers_utils\.processors|glm5_next_multimodal|Glm5NextProcessor" vllm_fl tests/unit_tests/test_glm5_support.py | head -n 500; echo HY4_REUSE_CANDIDATES; grep -nE "^class |Kpool|Tail|recurrent|Indexer|MHC|silu.*clamp" vllm_fl/models/hy_v4.py vllm_fl/model_loader/hy_v4_loader.py | head -n 500'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash bash -lc '\''grep -RInE "dispatch\.backends\.model_ops|vendor\.thead\.impl\.model_ops|backends/model_ops|impl/model_ops" vllm_fl tests/unit_tests/test_glm5_support.py || true; test ! -e vllm_fl/dispatch/backends/glm5_next.py; test ! -e vllm_fl/dispatch/backends/vendor/thead/impl/glm5_next.py'\'''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","mv","vllm_fl/dispatch/backends/model_ops.py","vllm_fl/dispatch/backends/glm5_next.py"]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","mv","vllm_fl/dispatch/backends/vendor/thead/impl/model_ops.py","vllm_fl/dispatch/backends/vendor/thead/impl/glm5_next.py"]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","perl","-pi","-e","s/vllm_fl\\.dispatch\\.backends\\.model_ops/vllm_fl.dispatch.backends.glm5_next/g; s/impl\\.model_ops/impl.glm5_next/g","vllm_fl/dispatch/backends/flaggems/register_ops.py","vllm_fl/dispatch/backends/reference/register_ops.py","vllm_fl/dispatch/backends/vendor/thead/register_ops.py","vllm_fl/dispatch/backends/glm5_next.py","tests/unit_tests/test_glm5_support.py"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash bash -lc '\''find tests/platforms -maxdepth 2 -type f -print | sort; grep -RInE "PPU_SDK|thead|vendor_name.*thead|mark\.gpu" tests | head -n 500'\'''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -e PYTHONPATH="$plugin:$fg/src" -w "$plugin" glm5.3-flash bash -lc '\''test -z "$(grep -RIlE "dispatch\.backends\.model_ops|vendor\.thead\.impl\.model_ops" vllm_fl tests/unit_tests/test_glm5_support.py || true)"; git diff --check; python3 -m compileall -q vllm_fl; pytest -q tests/unit_tests/dispatch/test_types.py tests/unit_tests/dispatch/test_manager.py tests/unit_tests/dispatch/test_call_op.py tests/unit_tests/dispatch/test_input_support.py tests/unit_tests/test_glm5_support.py'\'''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems","glm5.3-flash","pip","install","--no-build-isolation","--no-deps","-e","."]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","pip","install","--no-build-isolation","--no-deps","-e","."]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-e","TMPDIR=/mnt/nfs/users/jinghao/glm5.3-flash/06-tmp/020-hy4-latest-minimal-rebase","-e","PIP_CACHE_DIR=/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/pip","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems","glm5.3-flash","pip","install","--no-build-isolation","--no-deps","-e","."]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-e","TMPDIR=/mnt/nfs/users/jinghao/glm5.3-flash/06-tmp/020-hy4-latest-minimal-rebase","-e","PIP_CACHE_DIR=/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/pip","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","pip","install","--no-build-isolation","--no-deps","-e","."]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash python3 -c '\''import importlib.metadata as m,json,pathlib; [(print(name,m.version(name),json.loads((pathlib.Path(m.distribution(name)._path)/"direct_url.json").read_text())["url"])) for name in ("flag_gems","vllm-plugin-FL")]'\''; sha256sum start_glm53_graph.sh start_glm53_graph_host.sh'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["cp","--no-clobber","/mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph.sh","/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/start_glm53_graph.sh.before"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/start_glm53_graph.sh.before"}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["cp","--no-clobber","/mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph_host.sh","/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/start_glm53_graph_host.sh.before"],"creates":"/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/start_glm53_graph_host.sh.before"}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.copy -a 'src=/private/tmp/start_glm53_graph_020.sh dest=/mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph.sh mode=0755' --check --diff
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.copy -a 'src=/private/tmp/start_glm53_graph_host_020.sh dest=/mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph_host.sh mode=0755' --check --diff
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.copy -a 'src=/private/tmp/start_glm53_graph_020.sh dest=/mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph.sh mode=0755'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.copy -a 'src=/private/tmp/start_glm53_graph_host_020.sh dest=/mnt/nfs/users/jinghao/glm5.3-flash/start_glm53_graph_host.sh mode=0755'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/service/triton","state":"directory","mode":"0755"}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.file -a '{"path":"/mnt/nfs/users/jinghao/glm5.3-flash/06-tmp/service","state":"directory","mode":"0755"}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; bash -n start_glm53_graph.sh start_glm53_graph_host.sh; ! grep -E "VLLM_FL_CONFIG|runtime_dir|/workspace/vllm-plugin-FL-glm53-hy4-adaptation|/workspace/FlagGems" start_glm53_graph.sh start_glm53_graph_host.sh; sed -n "1,260p" start_glm53_graph.sh; sed -n "1,260p" start_glm53_graph_host.sh'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.shell -a 'cd /mnt/nfs/users/jinghao/glm5.3-flash && test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash && nohup bash ./start_glm53_graph_host.sh </dev/null >05-runs/020-hy4-latest-minimal-rebase/service.log 2>&1 & echo $! >05-runs/020-hy4-latest-minimal-rebase/service-host.pid'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; if curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null; then echo SERVICE_HEALTHY; else echo SERVICE_STARTING; tail -n 80 "$run/service.log"; fi; docker exec -w "$root" glm5.3-flash pgrep -a -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16|VLLM::Worker" || true; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; log=$root/05-runs/020-hy4-latest-minimal-rebase/service.log; cd "$root" && test "$(pwd -P)" = "$root"; date --iso-8601=seconds; stat -c "LOG mtime=%y size=%s" "$log"; docker exec -w "$root" glm5.3-flash ps -o pid,ppid,stat,etime,%cpu,%mem,comm -p 1872063,1872844,1872845,1872846,1872847,1872848,1872849,1872850,1872851,1872852,1872853,1872854,1872855,1872856,1872857,1872858,1872859; grep -aEn "Traceback|ERROR|Exception|No available|failed|illegal|OOM|out of memory" "$log" | tail -n 80 || true; ppu-smi'
```

首次 FlagGems editable install 未显式设置 `TMPDIR`，pip 在容器 `/tmp` 创建并清理了临时
wheel cache；没有持久产物，但不满足新工作区边界。随后用上方带 `TMPDIR/PIP_CACHE_DIR`
的命令重新安装并把后续 pip 隐式写入收敛到 `06-tmp/07-cache`。第一条未带环境变量的
plugin 安装命令不执行。

## 验证结果

2026-09-07 17:20 轮询显示 16 个 worker 均存活，PIECEWISE 图捕获 11/11 完成，
EngineCore 初始化耗时 277.62 秒，多模态预热完成；容器仍为 `running` 且重启次数为 0。
该次 health 探测发生在 API 监听前，返回 connection refused，不作为服务失败。日志明确
显示插件自动读取新 checkout 内的 `vllm_fl/dispatch/config/thead.yaml`，没有设置
`VLLM_FL_CONFIG`。启动命令的后台 shell 因 `&` 优先级在错误 cwd 写相对 pidfile 而返回
rc=1，但服务只启动了一份；先解析并核对现存 resource-lock/service PID，不重复启动。

端口就绪后只执行适配阶段的最小真实推理，不执行未选择的正式 acceptance。请求和响应
留在本轮 `05-runs`；先检查 HTTP 状态、JSON 结构、非空输出及服务日志，再修正 host pidfile：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; for _ in $(seq 1 12); do if curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null; then echo HEALTH=READY; exit 0; fi; sleep 5; done; echo HEALTH=NOT_READY; tail -n 100 "$run/service.log"; exit 1'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.shell -a 'cd /mnt/nfs/users/jinghao/glm5.3-flash && test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash && set -o pipefail && curl -fsS --max-time 1800 -H "Content-Type: application/json" -d '"'"'{"model":"GLM-5.3-Flash-BF16","messages":[{"role":"user","content":"请只回答：北京是中国的首都。"}],"temperature":0,"max_tokens":32}'"'"' http://127.0.0.1:8010/v1/chat/completions | tee 05-runs/020-hy4-latest-minimal-rebase/sanity.json'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash python3 -c '"'"'import json; p="05-runs/020-hy4-latest-minimal-rebase/sanity.json"; d=json.load(open(p)); c=d["choices"][0]["message"]["content"]; assert c.strip() and d.get("usage",{}).get("completion_tokens",0)>0; print({"finish_reason":d["choices"][0]["finish_reason"],"completion_tokens":d["usage"]["completion_tokens"],"content":c})'"'"'; grep -aEn "Traceback|ERROR|Exception|illegal|OOM|out of memory|EngineCore.*died" "$run/service.log" | tail -n 80 || true; curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; pgrep -af "resource_lock.py.*glm53-hy4-latest-20260907|start_glm53_graph_host.sh"; docker exec -w "$root" glm5.3-flash pgrep -a -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16"'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.shell -a 'cd /mnt/nfs/users/jinghao/glm5.3-flash && test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash && pid=$(pgrep -f "resource_lock.py.*glm53-hy4-latest-20260907" | head -n 1) && test -n "$pid" && ps -p "$pid" -o args= | grep -F "--resources ppu:0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 port:8010 vllm:/workspace/vllm plugin:/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL flaggems:/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems --run-id glm53-hy4-latest-20260907" >/dev/null && printf "%s\n" "$pid" > /mnt/nfs/users/jinghao/glm5.3-flash/05-runs/020-hy4-latest-minimal-rebase/service-host.pid'
```

首次真实请求返回 HTTP 500。最早异常在所有 TP worker 的 sparse MLA decode：
`FlagGems flash_mla_sparse_fwd -> AssertionError: Unsupported h_q`；不是 execute-model
超时，也没有生成乱码或重复文本。API/worker 随后由 vLLM 失败策略退出，容器保持
`running`、restart=0。当前假设是最新 Hy4 的普通 sparse MLA backend 对本模型 TP16
局部 query-head 数不适用，但注册缺少该输入能力守卫；先进行下列只读所有权/shape 对比，
再只修改真实拥有该选择逻辑的 backend/registration，并用失败 shape 建 focused regression：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; for file in vllm_fl/dispatch/backends/flaggems/impl/mla_sparse.py vllm_fl/dispatch/backends/flaggems/register_ops.py vllm_fl/dispatch/backends/reference/impl/mla_sparse.py vllm_fl/dispatch/backends/reference/register_ops.py vllm_fl/attention/mla_prefill.py; do echo NEW=$file; docker exec -w "$new" glm5.3-flash sed -n "1,420p" "$file"; echo OLD=$file; docker exec -w "$old" glm5.3-flash sed -n "1,420p" "$file"; done; echo FLAGGEMS_CONTRACT; docker exec -w "$fg" glm5.3-flash sed -n "1040,1140p" src/flag_gems/fused/flashmla_sparse.py; echo MODEL_HEADS; docker exec -w "$root" glm5.3-flash python3 -c '"'"'import json; c=json.load(open("/mnt/cpfs/models/GLM-5.3-Flash-BF16/config.json"))["text_config"]; print({k:c.get(k) for k in ("num_attention_heads","num_key_value_heads","head_dim","kv_lora_rank","qk_rope_head_dim","qk_nope_head_dim")}); print("tp16_local_heads",c.get("num_attention_heads")//16)'"'"''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$old" glm5.3-flash git diff --no-ext-diff HEAD -- vllm_fl/dispatch/backends/flaggems/impl/mla_sparse.py vllm_fl/dispatch/backends/flaggems/register_ops.py vllm_fl/attention/mla_prefill.py; docker exec -w "$new" glm5.3-flash grep -RInE "MlaSparse|mla_sparse|forward_mqa|supports=.*head|num_heads|Unsupported h_q" tests vllm_fl/dispatch | head -n 500'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; old=/workspace/vllm-plugin-FL-glm53-hy4-adaptation; cd "$root" && test "$(pwd -P)" = "$root"; echo NEW_TEST; docker exec -w "$new" glm5.3-flash sed -n "1,220p" tests/dispatch/test_flaggems_mla_sparse_no_padding.py; echo NEW_HISTORY; docker exec -w "$new" glm5.3-flash git log --oneline --follow -- vllm_fl/dispatch/backends/flaggems/impl/mla_sparse.py tests/dispatch/test_flaggems_mla_sparse_no_padding.py; echo OLD_BF16_METHOD; docker exec -w "$old" glm5.3-flash sed -n "245,340p" vllm_fl/dispatch/backends/flaggems/impl/mla_sparse.py; echo OLD_STATUS; docker exec -w "$old" glm5.3-flash git status --short -- vllm_fl/dispatch/backends/flaggems/impl/mla_sparse.py; echo VLLM_PARENT_INIT; docker exec -w /workspace/vllm glm5.3-flash grep -nE "prefill_padding|fp8_decode_padded_heads" vllm/v1/attention/backends/mla/flashmla_sparse.py'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; new=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; echo IMPL_HISTORY; docker exec -w "$new" glm5.3-flash git log --oneline --follow -- vllm_fl/dispatch/backends/flaggems/impl/mla_sparse.py; echo TEST_HISTORY; docker exec -w "$new" glm5.3-flash git log --oneline --follow -- tests/dispatch/test_flaggems_mla_sparse_no_padding.py; echo BLAME; docker exec -w "$new" glm5.3-flash git blame -L 255,285 -- vllm_fl/dispatch/backends/flaggems/impl/mla_sparse.py; echo DEPENDENCY_REFERENCES; docker exec -w "$new" glm5.3-flash grep -RInE "FlagGems|flag-gems|flag_gems|github.com/flagos-ai" pyproject.toml setup.py setup.cfg requirements* README.md docs 2>/dev/null | head -n 300; echo FLAGGEMS_HISTORY; docker exec -w "$fg" glm5.3-flash git log --all --oneline -- src/flag_gems/fused/flashmla_sparse.py | head -n 80'
```

其中 `git log --follow` 首次同时给了两个 pathspec，Git 按预期拒绝；没有远端写入，
用上方逐文件 history 命令纠正。

只读对比确认新基线提交 `795f7c9` 删除了 BF16 small-head padding，并把测试改成 4 heads
原样传入；当前安装的 FlagGems `dcd0cfe` 则在同一入口硬断言 `HQ == 64 or HQ == 128`。
这是直接可复现的依赖契约错配。修复不按模型名分支，也不修改 FlagGems：在插件拥有的
FlagGems adapter 内根据算子公开约束选择 64/128 kernel heads，零填充 query、用 `-inf`
填充 sink，并在返回时切回真实 head 数；超过 128 显式报错。同步修正已有 focused test，
先做 CPU contract test，再执行单 PPU eager/graph regression：

```bash
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","git","mv","tests/dispatch/test_flaggems_mla_sparse_no_padding.py","tests/dispatch/test_flaggems_mla_sparse_head_padding.py"]}'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.copy -a 'src=/private/tmp/glm53-mla-small-head-020.patch dest=/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/glm53-mla-small-head.patch mode=0644' --check --diff
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.copy -a 'src=/private/tmp/glm53-mla-small-head-020.patch dest=/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/glm53-mla-small-head.patch mode=0644'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; patch=$root/03-issues/020-hy4-latest-minimal-rebase/glm53-mla-small-head.patch; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash git apply --check "$patch"'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","git","apply","/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/020-hy4-latest-minimal-rebase/glm53-mla-small-head.patch"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -e PYTHONPATH="$plugin:$fg/src" -w "$plugin" glm5.3-flash bash -lc '"'"'git diff --check; pytest -q tests/dispatch/test_flaggems_mla_sparse_head_padding.py tests/dispatch/test_mla_backend_helpers.py tests/unit_tests/dispatch/test_types.py tests/unit_tests/dispatch/test_manager.py tests/unit_tests/dispatch/test_call_op.py tests/unit_tests/dispatch/test_input_support.py tests/unit_tests/test_glm5_support.py'"'"''
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.command -a '{"argv":["docker","exec","-e","PYTHONPATH=/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL:/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/FlagGems/src","-e","CUDA_VISIBLE_DEVICES=0","-e","PYTHONDONTWRITEBYTECODE=1","-e","TRITON_CACHE_DIR=/mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/triton","-e","TMPDIR=/mnt/nfs/users/jinghao/glm5.3-flash/06-tmp/020-hy4-latest-minimal-rebase","-e","FLAGGEMS_DB_URL=sqlite:////mnt/nfs/users/jinghao/glm5.3-flash/07-cache/020-hy4-latest-minimal-rebase/TunedConfig_thead_triton_3_6.db?timeout=1800","-w","/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL","glm5.3-flash","bash","-lc","set -o pipefail; pytest -q -p no:cacheprovider /workspace/vllm-plugin-FL-glm53-hy4-adaptation/tests/unit_tests/test_glm5_precision_graph.py /workspace/vllm-plugin-FL-glm53-hy4-adaptation/tests/unit_tests/test_glm5_tail_graph.py 2>&1 | tee /mnt/nfs/users/jinghao/glm5.3-flash/05-runs/020-hy4-latest-minimal-rebase/precision-tail-graph-after-head-padding.log"]}'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; ! curl -fsS --max-time 3 http://127.0.0.1:8010/health; ! pgrep -f "resource_lock.py.*port:8010.*plugin:/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL"; ! docker exec glm5.3-flash pgrep -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16"; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.shell -a '(cd /mnt/nfs/users/jinghao/glm5.3-flash && test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash && exec bash ./start_glm53_graph_host.sh </dev/null > /mnt/nfs/users/jinghao/glm5.3-flash/05-runs/020-hy4-latest-minimal-rebase/service-after-head-padding.log 2>&1) & pid=$!; test -n "$pid"; printf "%s\n" "$pid" > /mnt/nfs/users/jinghao/glm5.3-flash/05-runs/020-hy4-latest-minimal-rebase/service-after-head-padding-host.pid'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; pid=$(cat "$run/service-after-head-padding-host.pid"); ps -o pid,ppid,pgid,sid,stat,args -p "$pid"; tail -n 80 "$run/service-after-head-padding.log"; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; for _ in $(seq 1 12); do if curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null; then echo HEALTH=READY; exit 0; fi; sleep 5; done; echo HEALTH=NOT_READY; stat -c "mtime=%y size=%s" "$run/service-after-head-padding.log"; tail -n 100 "$run/service-after-head-padding.log"; docker exec -w "$root" glm5.3-flash pgrep -a -f "VLLM::EngineCore|VLLM::Worker" || true'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.shell -a 'cd /mnt/nfs/users/jinghao/glm5.3-flash && test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash && set -o pipefail && curl -fsS --max-time 1800 -H "Content-Type: application/json" -d '"'"'{"model":"GLM-5.3-Flash-BF16","messages":[{"role":"user","content":"请只回答：北京是中国的首都。"}],"temperature":0,"max_tokens":32}'"'"' http://127.0.0.1:8010/v1/chat/completions | tee 05-runs/020-hy4-latest-minimal-rebase/sanity-after-head-padding.json'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash python3 -c '"'"'import json; p="05-runs/020-hy4-latest-minimal-rebase/sanity-after-head-padding.json"; d=json.load(open(p)); c=d["choices"][0]["message"]["content"]; assert c.strip() and d.get("usage",{}).get("completion_tokens",0)>0; print({"finish_reason":d["choices"][0]["finish_reason"],"completion_tokens":d["usage"]["completion_tokens"],"content":c})'"'"'; grep -aEn "Traceback|AssertionError: Unsupported h_q|illegal|OOM|out of memory|EngineCore.*died" "$run/service-after-head-padding.log" | tail -n 80 || true; curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
.venv/bin/ansible PPU-13 -i inventory/hosts.yml -m ansible.builtin.shell -a 'cd /mnt/nfs/users/jinghao/glm5.3-flash && test "$(pwd -P)" = /mnt/nfs/users/jinghao/glm5.3-flash && set -o pipefail && curl -fsS --max-time 1800 -H "Content-Type: application/json" -d '"'"'{"model":"GLM-5.3-Flash-BF16","messages":[{"role":"user","content":"请只回答：北京是中国的首都。"}],"temperature":0,"max_tokens":128}'"'"' http://127.0.0.1:8010/v1/chat/completions | tee 05-runs/020-hy4-latest-minimal-rebase/sanity-after-head-padding-128.json'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$root" glm5.3-flash python3 -c '"'"'import json; p="05-runs/020-hy4-latest-minimal-rebase/sanity-after-head-padding-128.json"; d=json.load(open(p)); m=d["choices"][0]["message"]; c=m["content"]; assert c and c.strip() and d["choices"][0]["finish_reason"] == "stop"; print({"finish_reason":d["choices"][0]["finish_reason"],"completion_tokens":d["usage"]["completion_tokens"],"content":c,"reasoning_chars":len(m.get("reasoning") or "")})'"'"'; grep -aEn "Traceback|AssertionError: Unsupported h_q|illegal|OOM|out of memory|EngineCore.*died" "$run/service-after-head-padding.log" | tail -n 80 || true; curl -fsS --max-time 5 http://127.0.0.1:8010/health >/dev/null; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
```

重启 preflight 解析到 PID 3022818 的同 scope resource-lock，容器内已无 vLLM 服务。
先核对完整命令、父子关系和旧 run-id；若它确为本轮失败服务留下的 wrapper，只向该 PID
发送 TERM 并验证退出，不影响容器或其他 workload：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; pid=3022818; ps -o pid,ppid,pgid,sid,lstart,stat,args -p "$pid"; pstree -aps "$pid" || true; pgrep -P "$pid" -a || true; docker exec -w "$root" glm5.3-flash pgrep -a -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16" || true'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; pid=3022818; args=$(ps -p "$pid" -o args=); case "$args" in *"resource_lock.py"*"port:8010"*"plugin:/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL"*"--run-id glm53-hy4-latest-20260907"*) ;; *) echo "unexpected process: $args" >&2; exit 1;; esac; kill -TERM "$pid"'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; for _ in $(seq 1 30); do if ! kill -0 3022818 2>/dev/null; then exit 0; fi; sleep 1; done; echo RESOURCE_LOCK_STILL_ALIVE >&2; exit 1'
```

对 PID 3022818 的精确 `ps` 没有返回进程行；此前宽松 `pgrep -f` 实际匹配了包含该
pattern 的检查 shell 自身，`pstree` 因目标已不存在而退化为整棵系统树。没有执行 TERM。
改用锚定 Python argv 的模式复查，只有没有真实 resource-lock 和 vLLM service 才启动：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; if pgrep -af "^python(3|3\\.[0-9]+)? .*resource_lock.py .*port:8010"; then exit 1; fi; if docker exec glm5.3-flash pgrep -a -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16"; then exit 1; fi; docker inspect -f "{{.State.Status}} {{.RestartCount}}" glm5.3-flash'
```

首次生成的补丁首个 hunk 新行计数少 1，`git apply --check` 报 `corrupt patch at line 35`；
修正后发现 test hunk 原行计数也少 1，第二次 check 报 `corrupt patch at line 73`。两次均未
修改产品代码；修正全部 hunk count 后覆盖本 issue 中该补丁并重新执行相同 check/apply。
第三次 check 显示 source hunk 上下文未匹配；读取精确行后扩大为覆盖完整 method tail 的
单一 hunk，仍未发生产品写入。

- 新 checkout `git diff --check`、`python3 -m compileall -q vllm_fl` 通过。
- dispatch 最小回归：80 passed（types/manager/call/input-support），8.43 秒。
- 使用真实 `/mnt/cpfs/models/GLM-5.3-Flash-BF16/config.json` 的插件注册、CausalLM/VLM
  导入和配置解析通过，输出 `GLM5_NEXT_REGISTRATION_IMPORT_CONFIG_PASS`。
- 新 checkout 已安装 editable，Thead native 三个 `.so` 与用户提供目录逐文件 SHA-256
  一致，三个必需 native op 注册均为 true；FlagGems 也从最新 checkout editable 安装。
- 最终 CPU/contract 回归 103 passed；单 PPU precision/tail eager+graph 14 passed，修复前
  另有 FlagGems bindings graph 17 passed，总计 31 个 device case 全部通过。
- 第一轮新服务完成 120 分片加载、11/11 PIECEWISE graph capture 和多模态预热；真实请求
  精确暴露 `Unsupported h_q`，不是 timeout。按当前 FlagGems 64/128-head 契约修复 adapter 后
  第二轮服务健康，128-token sanity 返回 `finish_reason=stop` 和“北京是中国的首都。”。
- 32-token sanity 返回 HTTP 200，但 reasoning 用尽生成上限而 `content=null`；这是预期的
  length 截断证据，不计为功能失败。修复版服务保持 health，容器始终 `running`、restart=0。
- 正式准确率不属于本轮自动执行范围；旧正式成绩 83.84%，40K 定向诊断投影 86.36%。

最终代码审计只读命令如下；tracked 与 untracked 分开列出，并检查旧 checkout 路径、
`VLLM_FL_CONFIG`、`runtime_dir`、模型权重路径特判、examples/临时文件及外部 checkout 状态：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash bash -lc '"'"'echo BASE_HEAD; git rev-parse HEAD; git branch --show-current; echo STATUS; git status --short; echo TRACKED_DIFF; git diff HEAD --stat; git diff HEAD --numstat; echo UNTRACKED_PRODUCT; git ls-files --others --exclude-standard | grep -vE "(__pycache__|\\.pyc$)" | sort; echo FORBIDDEN_REFERENCES; grep -RInE "/workspace/vllm-plugin-FL-glm53-hy4-adaptation|/workspace/FlagGems|VLLM_FL_CONFIG|runtime_dir|/mnt/cpfs/models/GLM-5.3-Flash-BF16" vllm_fl tests || true; echo EXAMPLES; git status --short -- examples; echo DIFF_CHECK; git diff --check; echo EDITABLE; python3 -c "import importlib.metadata as m,json,pathlib; [(print(name,m.version(name),json.loads((pathlib.Path(m.distribution(name)._path)/'"'"'direct_url.json'"'"').read_text())['"'"'url'"'"'])) for name in ('"'"'flag_gems'"'"','"'"'vllm-plugin-FL'"'"')]"'"'"; echo FLAGGEMS_STATE; docker exec -w "$fg" glm5.3-flash bash -lc '"'"'git rev-parse HEAD; git status --short'"'"'; echo VLLM_STATE; docker exec -w /workspace/vllm glm5.3-flash bash -lc '"'"'git rev-parse HEAD; git status --short'"'"''
./scripts/adapt-model GLM-5.3-Flash-BF16 ppu --hosts PPU-13 --steps adaptation --check-only
./scripts/audit-workspace
```

首次最终审计命令在本地 zsh 解析 `direct_url.json` 嵌套引号时失败，未建立 SSH 连接、
无远端写入。editable URL 已在安装后单独验证，本次去掉该重复项后执行：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; fg=$root/01-repos/FlagGems; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash bash -lc '"'"'echo BASE_HEAD; git rev-parse HEAD; git branch --show-current; echo STATUS; git status --short; echo TRACKED_DIFF; git diff HEAD --stat; git diff HEAD --numstat; echo UNTRACKED_PRODUCT; git ls-files --others --exclude-standard | grep -vE "(__pycache__|\\.pyc$)" | sort; echo FORBIDDEN_REFERENCES; grep -RInE "/workspace/vllm-plugin-FL-glm53-hy4-adaptation|/workspace/FlagGems|VLLM_FL_CONFIG|runtime_dir|/mnt/cpfs/models/GLM-5.3-Flash-BF16" vllm_fl tests || true; echo EXAMPLES; git status --short -- examples; echo DIFF_CHECK; git diff --check'"'"'; echo FLAGGEMS_STATE; docker exec -w "$fg" glm5.3-flash bash -lc '"'"'git rev-parse HEAD; git status --short'"'"'; echo VLLM_STATE; docker exec -w /workspace/vllm glm5.3-flash bash -lc '"'"'git rev-parse HEAD; git status --short'"'"''
```

审计结果：基线/HEAD 为 `d56f7b2`；13 个 tracked path 共 115 insertions/16 deletions，
其余新增均为上方列出的 GLM5-Next 产品代码或两个 focused unit test。`examples/` 无改动，
没有旧 checkout、权重绝对路径、临时脚本或 `runtime_dir` 引用。grep 命中的
`VLLM_FL_CONFIG` 仅为上游已有的通用配置文档/实现，不是本适配新增启动依赖。
FlagGems `dcd0cfe` 和 vLLM `ee0da84` 均干净。

## Small-head padding 复核

用户指出此前已经有无需 padding 的优化版 sparse MLA。先核对当前实际安装来源、仓库
remote、包 metadata、容器内所有 FlagGems/FlagGems-vllm checkout，以及优化入口的
head 约束；本节只做只读诊断，不继续修改代码或重启服务：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; echo WORKSPACE_CANDIDATES; docker exec -w /workspace glm5.3-flash find /workspace "$root/01-repos" -maxdepth 2 -type d \( -iname "*flaggems*" -o -iname "*flag*gems*vllm*" \) -print; for repo in /workspace/FlagGems "$root/01-repos/FlagGems" /workspace/FlagGems-vllm "$root/01-repos/FlagGems-vllm"; do if docker exec glm5.3-flash test -d "$repo/.git"; then echo REPO=$repo; docker exec -w "$repo" glm5.3-flash git remote -v; docker exec -w "$repo" glm5.3-flash git branch --show-current; docker exec -w "$repo" glm5.3-flash git rev-parse HEAD; fi; done; echo PACKAGE; docker exec -w "$root" glm5.3-flash pip show flag-gems flaggems-vllm FlagGems-vllm 2>/dev/null || true; docker exec -w "$root" glm5.3-flash python3 -c '"'"'import flag_gems; print(flag_gems.__file__)'"'"''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; cd "$root" && test "$(pwd -P)" = "$root"; for repo in /workspace/FlagGems "$root/01-repos/FlagGems" /workspace/FlagGems-vllm "$root/01-repos/FlagGems-vllm; do if docker exec glm5.3-flash test -d "$repo"; then echo REPO=$repo; docker exec -w "$repo" glm5.3-flash grep -RInE "Unsupported h_q|HQ == 64|small.head|num_heads.*64|flash_mla_sparse_fwd" . --exclude-dir=.git --exclude="*.pyc" | head -n 300; fi; done'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; repo=/workspace/FlagGems-vllm; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$repo" glm5.3-flash bash -lc '"'"'echo STATUS; git status --short; echo BRANCHES; git branch -a; echo LOCAL_HISTORY; git log --all --oneline --decorate -- src/flaggems_vllm/ops/flashmla_sparse.py | head -n 120; echo ASSERT_HISTORY; git log --all -S "Unsupported h_q" --oneline -- src/flaggems_vllm/ops/flashmla_sparse.py; echo EXPORTS; sed -n "1,220p" src/flaggems_vllm/__init__.py; sed -n "1,220p" src/flaggems_vllm/ops/__init__.py'"'"'; docker exec -w "$repo" glm5.3-flash git ls-remote --heads origin'
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash sed -n "1,190p" vllm_fl/dispatch/backends/vendor/thead/impl/mla.py; docker exec -w "$root" glm5.3-flash python3 -c '"'"'import importlib.util; s=importlib.util.find_spec("flash_mla"); print(s); print(list(s.submodule_search_locations or []) if s else None)'"'"'; docker exec -w "$root" glm5.3-flash python3 -c '"'"'import flaggems_vllm,inspect; print(flaggems_vllm.__file__); print(inspect.signature(flaggems_vllm.flash_mla_sparse_fwd)); print(inspect.signature(flaggems_vllm.sparse_attn_triton))'"'"''
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; plugin=$root/01-repos/vllm-plugin-FL; cd "$root" && test "$(pwd -P)" = "$root"; docker exec -w "$plugin" glm5.3-flash bash -lc '"'"'echo THEAD_CONFIG; grep -nE "attention_backend|vendor.thead|default.flagos|mla" vllm_fl/dispatch/config/thead.yaml; echo THEAD_REGISTRATION; grep -nE "attention_backend|TheadMLASparse|mla" vllm_fl/dispatch/backends/vendor/thead/register_ops.py vllm_fl/dispatch/backends/vendor/thead/thead.py; echo FLAGGEMS_SELECTION; grep -nE "attention_backend|MLASparse" vllm_fl/dispatch/backends/flaggems/register_ops.py vllm_fl/dispatch/backends/flaggems/flaggems.py'"'"'; grep -aEn "attention_backend.*using|attention_backend.*switched|THEAD_FLASHMLA_SPARSE|FLAGGEMS_FLASHMLA_SPARSE" "$root/05-runs/020-hy4-latest-minimal-rebase/service-after-head-padding.log" | tail -n 100'
```

复核结论：此前把 padding 当最终修复不正确。容器同时安装了普通 `FlagGems`
（当前 editable 指向新建的 `01-repos/FlagGems@dcd0cfe`）和用户指定的
`FlagGems-vllm@255ab56`（editable 指向 `/workspace/FlagGems-vllm`）；本轮插件 adapter
实际导入 `flag_gems`，没有调用 `flaggems_vllm`。这两份 checkout 当前公开
`flash_mla_sparse_fwd` 都仍断言 64/128 heads，但插件已经提供 Thead 专属
`TheadMLASparseImpl`，它调用环境中的 `flash_mla.flash_mla_sparse_fwd` 并明确无需 padding。
服务日志证明实际路由错误地选择了 `default.flagos` / `FLAGGEMS_FLASHMLA_SPARSE`，没有选
`vendor.thead` / `THEAD_FLASHMLA_SPARSE`。因此 4→64 padding 只是掩盖路由错误的 mitigation，
会增加无意义计算；最终方案应删除它，并让 PPU sparse MLA 走已有无 padding vendor 路径，
随后重新做 graph、真实推理与性能对比。

2026-09-08 用户询问当前完成状态。`./scripts/health-check --limit PPU-13` 显示 Host 可达、
accelerator query 正常；进一步只读核对当前容器、服务端口和实际 attention backend：

```bash
ssh PPU-13 'root=/mnt/nfs/users/jinghao/glm5.3-flash; run=$root/05-runs/020-hy4-latest-minimal-rebase; cd "$root" && test "$(pwd -P)" = "$root"; curl -sS --max-time 5 -o /dev/null -w "health_http=%{http_code}\n" http://127.0.0.1:8010/health; docker inspect -f "container={{.State.Status}} restarts={{.RestartCount}}" glm5.3-flash; docker exec -w "$root" glm5.3-flash pgrep -a -f "^/usr/local/bin/python3.12 /usr/local/bin/vllm serve /mnt/cpfs/models/GLM-5.3-Flash-BF16|VLLM::EngineCore|VLLM::Worker_TP" | head -n 20; grep -aE "attention_backend.*using|Setting kv cache block size.*backend" "$run/service-after-head-padding.log" | tail -n 20'
```

本地 `adapt-model ... --steps adaptation --check-only` 通过，`audit-workspace` 为 0 errors；
80 条 warning 均为既有 legacy layout/state，其中当前模型仍提示
`deployment-identity.yml` 与 `runtime-config.yml` 哈希不一致。尝试生成本轮 adaptation
binding 时因此被 gate 拒绝；环境阶段未被本轮选择，故不静默刷新该 identity，也不把
`platform.yml` receipt 改成未通过 gate 的新值。README 已同步真实代码与服务状态。

## 限制与下一步

- 非 FlagGems 第一批已落地；`git apply --3way` 按 Git 行为把 10 个 tracked 修改置于
  staged，未创建 commit，也未 push。新增模型文件保持 untracked，便于用户直接审查。
- 下一步需要获准在 `01-repos/FlagGems` 创建同步 checkout，复核四个 adapter 的真实 ABI
  后再完成 FlagGems 注册、focused graph tests 和最终 diff 精简。
- 当前 diff 已按 `support-hy4-preview@d56f7b2` 复核；未复制旧 examples、一次性脚本或
  device 大测试，vLLM/FlagGems checkout 保持干净。未 commit、未 push。

## 经验沉淀

- 知识库处理状态：`local-only`
- 候选经验：适配基线大幅前移时应从干净最新 checkout 重建最小 diff，不在旧 dirty 树上
  继续堆叠兼容 patch。

## 2026-09-08 后续结论（取代本记录的 padding/路由建议）

[021](021-flaggems-sparse-small-head-no-padding-20260908.md) 已验证指定 FlagGems
`sparse-mla-opt-w8a8-moe-fix@bca444b8` 的 standalone `flash_mla_sparse_fwd` 原生支持
TP16 本地 `HQ=4`。因此无需把当前服务强制改路由到 Thead native backend，也无需保留
4→64 tensor padding；插件 BF16 workaround 已删除，算子 eager/graph、整模 11/11 graph
capture 和真实请求均通过。020 中“最终必须改 vendor 路由”的判断由这一新证据取代。
FP8 `flash_mla_with_kvcache` 仍有限制，不能套用该结论。
