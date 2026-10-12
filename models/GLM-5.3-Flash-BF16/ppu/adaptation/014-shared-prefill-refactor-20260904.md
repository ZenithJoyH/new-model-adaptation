# 第一批精简：共享 MLA prefill 与 YAML 最小差异

## 已实施范围

2026-09-04 14:32–14:38（Asia/Shanghai），目标 PPU-13，运行中容器 `glm5.3-flash`。
镜像 `hy4-ppu07-snapshot:20260903`，完整镜像标识沿用 environment/迁移记录；本轮未重启或重建容器。
已安装 editable plugin `/workspace/vllm-plugin-FL-glm53-hy4-adaptation`，基线 `support-hy4-preview@5329cb1293f397fd194852496cfcc710c35f1bfc`。

- GLM config、worker、platform 入口统一使用 HY4 的 `configure_mla_prefill` 和 `MLAPrefillBackendFL`，不再覆盖 FLASH_ATTN。
- 保留 worker-local 初始化和 GLM cache runner adapter；显式配置的 backend 不被覆盖。
- 删除重复的 163 行 `dispatch/backends/flaggems/impl/glm5_mla_prefill.py`，恢复 `impl/mla_prefill.py` 为 HY4 基线，不再保留兼容别名。
- YAML 恢复 HY4 原有格式和注释，只展示实际增量。通过解析后的完整对象相等断言，确认所有 backend 顺序、blacklist 和 policy 值不变；**本轮未删除 blacklist 条目**。
- 未修改 KDA、KPool、mHC、MoE clamp、sparse backend 子类、dispatch 注册或测试断言；没有启动服务或评测。

相对 HY4 HEAD：从 62 文件、9958 新增/99 删除，变为 60 文件、9682 新增/11 删除。
默认 YAML diff 从 290 行变为 112 行。修改在 editable 安装路径内，干净进程已核实加载该目录，无需重复安装或添加启动环境变量。

## 备份与可复现操作

修改前备份目录：`/workspace/glm53-adaptation-runtime/refactor-shared-prefill-20260904`。
其中包含每个涉及文件的原内容、SHA256 清单、修改前完整 tracked diff 和状态；被删除 backend 可从这里恢复。
没有执行 git reset/checkout、提交或推送。

脚本按顺序执行：

1. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-prefill-refactor.yml`：检查精确代码、分支及保护仓库。首次因 git grep 无匹配返回 1 提前退出；修正为只接受搜索的正常无匹配状态后重跑成功，没有吞掉其他失败。
2. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-shared-prefill.yml`：先检查 FlagGems clean/master/origin/master，再 fetch + pull --ff-only；同步前后均为 `9553ae9c745bdf5fd4a25d50e0d67bf80d888030`。未修改算子源码。
3. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/refactor-ppu13-shared-prefill.yml`：运行 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/refactor_shared_prefill.py`。先验证 HEAD、vLLM clean、服务 8010 未监听及变换前提，再备份和修改。一次性脚本禁止不检查状态就重复执行。
4. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-shared-prefill.yml`：修改后补充 GLM worker 入口及新 token/context chunk 包装接口检查，再重跑数值/graph。
5. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/verify-ppu13-prefill-refactor-state.yml`：核实安装路径、全插件 Python AST、无旧 backend 名称引用、模型配置/端口和保护仓库。
6. `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/validate-ppu13-hy4-glm53-migration.yml`：原有 318 项测试，未改断言，失败照常返回非零。

执行格式：`./scripts/playbook models/GLM-5.3-Flash-BF16/ppu/adaptation/<playbook>`。

## 验证证据

- 专项脚本 `tests/test_shared_mla_prefill.py`，远端 `/mnt/nfs/users/jinghao/glm5.3-flash/test_shared_mla_prefill.py`。
- seed=53，单 PPU，Q/K `[17,4,256]`、V `[17,4,128或256]`、int32 cu_seqlens `[0,17]`；FP16/BF16 × V 两种维度 × causal 两种模式，共 8 组。
- 对照 FP32 PyTorch attention 和 logsumexp，atol/rtol=0.025；检查 out-buffer 地址/值、prefill/context 接口、每组 eager 及两次 graph replay。修改前后均通过；修改后 worker 注册与 runner adapter 保留断言也通过。
- 该测试是组件级数值验证，不是长上下文、多请求 TP16 整模或吞吐验证。
- 原回归 2026-09-04 14:37:29–14:37:45：318 collected，317 passed，1 failed。唯一失败仍为 `test_flaggems_quantization_registers_ordered_fallbacks`，Registry 缺少 register_impl。GLM support 27 项全过，未增加新失败。
- `./scripts/syntax-check` 通过；全插件 AST 和旧 backend 引用检查通过。
- vLLM `/workspace/vllm` 仍为 `ee0da84ab9e04ac7610e28580af62c365e898389`，工作树 clean；FlagGems 工作树 clean。
- 最终 YAML SHA256：`d19d2ca47daeec00bd2e477663abfe64c586931835e3be468ac0acc3d8895bab`。
- 最终 `git diff HEAD --binary` SHA256：`783b13c1d3575b6b6403541df59c15064b69948a31cbe352537face4b7f3c917`。

## 当前限制与后续

第一批修改完成，不代表整个重整或适配验收完成。注册接口失败仍未解决；未通过修改 mock、屏蔽异常或跳过断言消除失败。
14:37 再次验证原模型 `config.json` 不存在，8010 未监听；没有猜测模型路径或重建配置，因此未运行整模验证。
下一批仍需处理注册接口/策略依赖、逐条论证 blacklist、验证 sparse 子类等价性以及缩小 KPool hook 范围。
先解决这些窄范围验证及模型配置来源，再进入整模执行模式验证；历史 GPQA 未达 88 分的结论不变。
