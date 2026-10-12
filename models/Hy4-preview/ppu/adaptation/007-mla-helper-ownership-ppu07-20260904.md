# MLA 辅助操作归属调整

2026-09-04，目标为 PPU-07 / `hy4` 的 `/workspace/vllm-plugin-FL-hy4-preview`。
插件基线 `11848598449f6d650df64170db4187c387361ce5`，分支 `support-hy4-preview`，保留原有 dirty 修改。
模型仍为 `/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`，本轮不更换模型、镜像或启动参数。
环境和镜像身份沿用 [vendor bootstrap 记录](011-vendor-bootstrap-refactor-ppu07-20260904.md)。

## 原因与改动

全插件 Python/YAML 调用检查确认：两个独立 dispatch 的实际调用者只有 T-Head sparse MLA。
FlagGems sparse MLA 原本就在 backend 内使用自己的拼接和缓存写入实现，不依赖这两个注册。

- T-Head `impl/mla.py` 移除 `CachedOp`，直接使用同 vendor 的 `native_extensions` 封装。
- 原生调用仍为 `_C_cache_ops.concat_mla_q` 和 `_C_cache_ops.concat_and_cache_mla`，没有替换内核。
- 删除 T-Head、FlagGems、reference 中两个冗余代理方法和六个注册项，以及 `thead.yaml` 的两个独立配置。
- 保留 `attention_backend` 调度、FlagGems attention 实现、原生封装和上游 Torch schema；不将 decode 操作塞进 `mla_prefill`。
- 这是职责收敛，不宣称吞吐提升；现有用户自定义配置若显式选择这两个已删除的 op，需要移除对应配置。

## 验证

执行 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-mla-helper-ownership.yml` 和 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-mla-helper-ownership.yml`。
源码哈希门禁、原文件备份及最小 diff 检查通过。备份保留在容器
`/tmp/hy4-mla-ownership-PNP36lKK/before`，可恢复本轮移除的代码。

插件新增 `tests/dispatch/test_mla_backend_helpers.py`，对应管理仓库的
`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_thead_native_sparse_mla_integration.py`。固定 seed，BF16、8 tokens、4 heads、Q=576、cache block=64：

- `STRUCTURE_OK`：不存在 helper CachedOp 和三套冗余注册。
- `BACKEND_HELPERS_EAGER_OK vendor.thead`：实际 backend hook 使用原生拼接和缓存写入；与 Torch reference 比较通过；禁用二次 resolve 后仍可调用，tensor query 和空 cache 分支通过。
- `BACKEND_HELPERS_GRAPH_CHANGED_INPUT_OK`：捕获后改变 query/cache 输入，replay 结果与新输入一致。
- `NATIVE_EAGER_OK (1, 4, 512)`、`NATIVE_GRAPH_OK`：原生 sparse MLA attention 的 sink/有效长度数值回归通过。
- 六项 bootstrap 单元测试与 fresh-process 原生 schema/幂等检查通过；移除 PPU 标识的模拟导入隔离通过，不代表其他硬件实测。
- `git diff --check`、管理仓库 syntax-check 和本次 playbook syntax-check 通过。

`/workspace/vllm` 保持 `ee0da84ab9e04ac7610e28580af62c365e898389`、clean；
FlagGems 保持 `60d043094d0217cad75528cb0e47a606c87ab1e4`、clean。
本轮未选择/新增 FlagGems 算子，仅移除冗余代理，不更新 FlagGems。
服务 PID/starttime 保持 `2084145/114318578` 和 `2084625/114319949`。
当前服务未重启，尚未加载本轮源码；独立测试进程完成验证。没有做全模型重新验收、性能测试、镜像更新、PPU-13 同步或 Git 提交。

本轮传输曾出现 SFTP/SCP 回退提示，随后传输成功，最终 Ansible `failed=0`、`unreachable=0`。
