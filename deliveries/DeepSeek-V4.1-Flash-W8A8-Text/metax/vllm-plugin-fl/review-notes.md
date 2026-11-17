# 源码与审查说明

这是候选交付材料；没有提交、推送或开PR。全部补丁来自两台机器实际安装树，未通过导入路径选择另一个副本。

| 组件 | 精确补丁基线HEAD | 文件/块 | 补丁SHA-256 |
| --- | --- | --- | --- |
| plugin | `37f2127367cfbc24349a1f28cb37c4c629b9ed6c` | 53/70 | `72d614f59d72731e8451a4b1d0b6742d4f94d62edf58f1419d2ba3a72b5e8b5a` |
| fgv | `f108ba81bf6799ccfe48c86f77cbb3ce117c4179` | 45/106 | `b7872796ce75b7b76387d2bb2e5bcfcb1f459c85f31b441f32f01cb28a5507eb` |
| fg | `e584bded1ddb0ea2a638653043ef0d48931119a3` | 3/4 | `a43ba6fc892ee91e428e36ef279f5f053881c134b325d637d06f75a8ade345c9` |

Plugin目前为detached HEAD，对应本地origin/0.4.0-dev；FGV为main/origin/main，FG为master/origin/master。此处HEAD是已验证工作基线，不是已确认的最终PR目标。未切换分支、重基或改写历史。vLLM保持只读、干净。

本轮修改仅5文件：图测试dtype与容差、provider docstring、FGV算子描述，以及两个外部资产测试路径；运行时可执行AST和数值kernel均未改变。相对上一轮逐块审查，Plugin仅4文件变化，FGV仅1文件变化，FG补丁不变。其余96文件的补丁块逐字一致，沿用已绑定审查；本轮5文件的每项新增/删除已重新审阅。

## 适用规范与尚未完成项

- plugin:A1/A3/A4/B1/B3/B4：框架metadata与数值实现分开，既有dispatch/public API，错误直接传播。
- plugin:F2/F3/F4/F5/F7/G1/G2：独立参考、真实新输入图测试、限定改动、英文源码、运行示例与长期支持边界；过程报告留在管理仓库/原生证据。
- operator:B1/B2/C1–C8/D1–D6/E1–E7/F1–F6按各编号审查适用，FlagGems仅ATen，vLLM计算归FGV；本轮FGV仅修改description。
- plugin:D3：所需新增算子API尚未有可验证的公开固定依赖；必须先交付算子，再固定Plugin依赖，不能凭旧公开提交或浮动分支宣称齐备。
- plugin:H9：同设置高精度模型质量比较未完成；GPQA达用户阈值、同量化参考或eager/FULL对照不能替代。
- 目标分支/最新上游集成、依赖固定后的clean build/install、相应CI和未测硬件验证仍待完成。当前材料不宣称PR已就绪或完整适配通过。

## 继承改动隔离

以下8项原有Plugin改动完整保留，不进入本任务补丁，也未复位或暂存：
- `vllm_fl/dispatch/backends/vendor/metax/patches/fix_standalone_compile.py`（` M`）
- `vllm_fl/dispatch/backends/vendor/metax/patches/pynccl_wrapper.py`（` M`）
- `vllm_fl/dispatch/backends/vendor/metax/shims/_kths_triton_unified_attention.py`（` M`）
- `vllm_fl/dispatch/config/metax.yaml`（` M`）
- `tests/functional_tests/compilation/test_metax_standalone_artifact.py`（`??`）
- `tests/functional_tests/distributed/test_metax_mccl_abort.py`（`??`）
- `tests/unit_tests/compilation/test_metax_standalone_artifact.py`（`??`）
- `tests/unit_tests/distributed/test_metax_mccl_abort.py`（`??`）

## 本轮验证

Plugin37的8项适用hooks及FGV44的7项适用hooks均通过，精确快照字节未被formatter改动。13项实际安装树回归在103 GPU0隔离条件下全部通过，日志SHA-256 `f6059fc0d1ac524f72ca53db025827493ee54309d7a753908407eaa83bba0e88`，原生退出0；包含真实FP16/BF16新输入图重放、6组attention/cache和冻结tokenizer哈希。原始证据在批准根 `04-runs/pr-cleanup-v4-20261105/`，不复制日志入本交付目录。

共享GPU的v1/v3曾在创建stream处阻塞，分别超时/主动结束，失败全部保留；v2仅为控制脚本收集项数预期错误，实际13项未减少或跳过。限制CPU线程未解决共享GPU问题，停止本任务模型、隔离GPU后通过；驱动内部原因未定，不把该现象记作已修复。102未重复此13项硬件运行，不冒充两机均补测。

恢复服务使用同一脚本SHA `364d18c989f8ce0e5e1406e714eb79cd8586af95487512b6c39aaf9845f9bce9`。两机实际argv、允许环境及原生生效配置与先前64配置一致，FULL捕获19尺寸完成，8项恢复文本请求与内容审阅正常。原生响应SHA `128ed43c97e15ea77ec4bbac63f897d2aebabde5ab8b91de4c1bbea569e8caf0`；新候选服务契约SHA `4e06dfc698829fe57792d7860805ac5021f800cbf8fe3edfb90d3dceb00e20a0`，当前精确部署身份 `c8e5374193de3c0a4641e64a579323b1f8a06cbcd0f9ff0fae5e8c3e7e23bf27`。此为恢复候选身份，不将历史16配置得分迁移为64完整精度通过。

## 完整文件/增删索引

下表用于定位全部180块，不是自动架构评审结论。已有模型/平台的未命中分支、默认值和相关回归限制见管理仓库016记录。

| 组件 | 文件 | 块 | 新增 | 删除 |
| --- | --- | ---: | ---: | ---: |
| plugin | `README.md` | 2 | 48 | 0 |
| plugin | `pyproject.toml` | 1 | 3 | 0 |
| plugin | `tests/functional_tests/conftest.py` | 2 | 1 | 1 |
| plugin | `tests/unit_tests/dispatch/test_flaggems_quantization.py` | 1 | 1 | 12 |
| plugin | `tests/unit_tests/quantization/test_w8a8_linear.py` | 6 | 115 | 10 |
| plugin | `tests/unit_tests/quantization/test_w8a8_moe_experts.py` | 2 | 11 | 0 |
| plugin | `vllm_fl/__init__.py` | 3 | 16 | 0 |
| plugin | `vllm_fl/dispatch/backends/flaggems/impl/quantization.py` | 1 | 3 | 3 |
| plugin | `vllm_fl/dispatch/backends/flaggems/impl/w8a8_moe.py` | 3 | 33 | 3 |
| plugin | `vllm_fl/dispatch/backends/flaggems/register_ops.py` | 1 | 118 | 0 |
| plugin | `vllm_fl/quantization/w8a8/linear.py` | 6 | 15 | 7 |
| plugin | `vllm_fl/quantization/w8a8/moe_experts.py` | 1 | 9 | 14 |
| plugin | `examples/deepseek_v41_client.py` | 1 | 63 | 0 |
| plugin | `tests/functional_tests/models/test_deepseek_v41_attention_chain.py` | 1 | 327 | 0 |
| plugin | `tests/functional_tests/models/test_deepseek_v41_cache_metadata.py` | 1 | 449 | 0 |
| plugin | `tests/functional_tests/models/test_deepseek_v41_compressor_state.py` | 1 | 362 | 0 |
| plugin | `tests/functional_tests/models/test_deepseek_v41_engram.py` | 1 | 375 | 0 |
| plugin | `tests/functional_tests/models/test_deepseek_v41_model_state.py` | 1 | 270 | 0 |
| plugin | `tests/functional_tests/models/test_deepseek_v41_projections.py` | 1 | 281 | 0 |
| plugin | `tests/functional_tests/ops/test_dynamic_w8a8_checkpoint.py` | 1 | 245 | 0 |
| plugin | `tests/functional_tests/ops/test_w8a8_moe_clamp.py` | 1 | 191 | 0 |
| plugin | `tests/unit_tests/dispatch/test_deepseek_v41_attention.py` | 1 | 116 | 0 |
| plugin | `tests/unit_tests/dispatch/test_deepseek_v41_compressor.py` | 1 | 103 | 0 |
| plugin | `tests/unit_tests/dispatch/test_engram.py` | 1 | 96 | 0 |
| plugin | `tests/unit_tests/dispatch/test_w8a8_moe_clamp.py` | 1 | 107 | 0 |
| plugin | `tests/unit_tests/models/deepseek_v41/test_config.py` | 1 | 131 | 0 |
| plugin | `tests/unit_tests/models/deepseek_v41/test_engram_metadata.py` | 1 | 112 | 0 |
| plugin | `tests/unit_tests/models/test_deepseek_v41_cache.py` | 1 | 92 | 0 |
| plugin | `tests/unit_tests/models/test_deepseek_v41_tokenizer.py` | 1 | 202 | 0 |
| plugin | `tests/unit_tests/models/test_deepseek_v41_weights.py` | 1 | 269 | 0 |
| plugin | `tests/unit_tests/quantization/test_w8a8_int8.py` | 1 | 172 | 0 |
| plugin | `vllm_fl/dispatch/backends/flaggems/impl/deepseek_v41_attention.py` | 1 | 181 | 0 |
| plugin | `vllm_fl/dispatch/backends/flaggems/impl/deepseek_v41_compressor.py` | 1 | 66 | 0 |
| plugin | `vllm_fl/dispatch/backends/flaggems/impl/deepseek_v41_linear.py` | 1 | 93 | 0 |
| plugin | `vllm_fl/dispatch/backends/flaggems/impl/engram.py` | 1 | 103 | 0 |
| plugin | `vllm_fl/dispatch/backends/flaggems/impl/w8a8_linear.py` | 1 | 64 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/__init__.py` | 1 | 40 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/attention.py` | 1 | 478 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/attention_metadata.py` | 1 | 383 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/cache.py` | 1 | 300 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/compressor.py` | 1 | 77 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/compressor_metadata.py` | 1 | 139 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/config.py` | 1 | 69 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/encoding.py` | 1 | 581 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/engram.py` | 1 | 196 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/engram_metadata.py` | 1 | 172 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/model.py` | 1 | 369 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/model_state.py` | 1 | 298 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/projections.py` | 1 | 199 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/rope.py` | 1 | 56 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/tokenizer.py` | 1 | 121 | 0 |
| plugin | `vllm_fl/models/deepseek_v41/weights.py` | 1 | 149 | 0 |
| plugin | `vllm_fl/quantization/w8a8_int8.py` | 1 | 167 | 0 |
| fgv | `benchmark/test_fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert.py` | 1 | 76 | 0 |
| fgv | `conf/operators.yaml` | 3 | 106 | 1 |
| fgv | `src/flaggems_vllm/ops/__init__.py` | 5 | 23 | 0 |
| fgv | `src/flaggems_vllm/ops/flash_mla_with_kvcache.py` | 22 | 190 | 54 |
| fgv | `src/flaggems_vllm/ops/fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert.py` | 6 | 17 | 13 |
| fgv | `src/flaggems_vllm/ops/fused_moe.py` | 1 | 6 | 2 |
| fgv | `src/flaggems_vllm/ops/indexer_k_quant_and_cache.py` | 3 | 27 | 22 |
| fgv | `src/flaggems_vllm/ops/mhc_with_norm.py` | 2 | 3 | 3 |
| fgv | `src/flaggems_vllm/ops/triton_scaled_mm.py` | 4 | 24 | 2 |
| fgv | `src/flaggems_vllm/runtime/backend/_metax/fused/fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert.py` | 6 | 32 | 21 |
| fgv | `src/flaggems_vllm/runtime/backend/_metax/ops/__init__.py` | 4 | 6 | 0 |
| fgv | `src/flaggems_vllm/runtime/backend/_metax/ops/fused_moe.py` | 12 | 103 | 12 |
| fgv | `src/flaggems_vllm/runtime/backend/_metax/ops/scaled_int8_quant.py` | 4 | 15 | 2 |
| fgv | `src/flaggems_vllm/runtime/backend/_metax/tune_configs.yaml` | 1 | 129 | 0 |
| fgv | `src/flaggems_vllm/runtime/backend/_nvidia/tune_configs.yaml` | 1 | 129 | 0 |
| fgv | `tests/test_fused_deepseek_v4_qnorm_rope_kv_rope_quant_insert.py` | 1 | 251 | 0 |
| fgv | `tests/test_triton_scaled_mm.py` | 1 | 102 | 0 |
| fgv | `tools/select_tests.py` | 2 | 8 | 0 |
| fgv | `benchmark/test_deepseek_v41_candidates.py` | 1 | 99 | 0 |
| fgv | `benchmark/test_deepseek_v41_compress_norm.py` | 1 | 93 | 0 |
| fgv | `benchmark/test_deepseek_v41_indexer_k_store.py` | 1 | 77 | 0 |
| fgv | `benchmark/test_dequantize_int8_weight.py` | 1 | 38 | 0 |
| fgv | `benchmark/test_engram.py` | 1 | 127 | 0 |
| fgv | `benchmark/test_flash_mla_with_kvcache_independent.py` | 1 | 162 | 0 |
| fgv | `benchmark/test_metax_w8a8_moe.py` | 1 | 117 | 0 |
| fgv | `benchmark/test_mhc_pre_delayed.py` | 1 | 134 | 0 |
| fgv | `benchmark/test_w8a8_boundaries.py` | 1 | 79 | 0 |
| fgv | `src/flaggems_vllm/ops/deepseek_v41_candidates.py` | 1 | 403 | 0 |
| fgv | `src/flaggems_vllm/ops/deepseek_v41_compress_norm.py` | 1 | 275 | 0 |
| fgv | `src/flaggems_vllm/ops/deepseek_v41_indexer_k_store.py` | 1 | 103 | 0 |
| fgv | `src/flaggems_vllm/ops/dequantize_int8_weight.py` | 1 | 79 | 0 |
| fgv | `src/flaggems_vllm/ops/engram.py` | 1 | 331 | 0 |
| fgv | `src/flaggems_vllm/ops/mhc_pre_delayed.py` | 1 | 241 | 0 |
| fgv | `src/flaggems_vllm/runtime/backend/_metax/ops/flash_mla_with_kvcache.py` | 1 | 60 | 0 |
| fgv | `src/flaggems_vllm/runtime/backend/_metax/ops/triton_scaled_mm.py` | 1 | 64 | 0 |
| fgv | `tests/test_deepseek_v41_candidates.py` | 1 | 330 | 0 |
| fgv | `tests/test_deepseek_v41_compress_norm.py` | 1 | 291 | 0 |
| fgv | `tests/test_deepseek_v41_indexer_k_store.py` | 1 | 171 | 0 |
| fgv | `tests/test_dequantize_int8_weight.py` | 1 | 123 | 0 |
| fgv | `tests/test_engram.py` | 1 | 444 | 0 |
| fgv | `tests/test_flash_mla_with_kvcache_independent.py` | 1 | 348 | 0 |
| fgv | `tests/test_metax_w8a8_moe.py` | 1 | 457 | 0 |
| fgv | `tests/test_mhc_collapse.py` | 1 | 164 | 0 |
| fgv | `tests/test_mhc_pre_delayed.py` | 1 | 207 | 0 |
| fgv | `tests/test_w8a8_boundaries.py` | 1 | 282 | 0 |
| fg | `conf/operators.yaml` | 1 | 11 | 0 |
| fg | `src/flag_gems/__init__.py` | 1 | 1 | 1 |
| fg | `tests/test_clone.py` | 2 | 100 | 0 |
