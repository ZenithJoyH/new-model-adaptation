# Qwen3.8-Flash-Next：本地记录整理

整理日期：2026-10-12。范围为目录、索引和已有 framework 契约；没有远端执行或新的适配/验收。

PPU-01 的功能与算子归属整理已有记录；最新双实例正式精度为 171/198（86.36%），低于 88% 阈值。跨实例数值差异和生成上限问题保持未关闭。

## 记录来源与适用范围

| 平台 | 来源 | 已记录 Host | 原记录状态 / 当前契约 |
| --- | --- | --- | --- |
| ppu | [legacy 平台记录](../ppu/README.md) | PPU-01 | functional |

## 现有契约与人工协作

本模型尚无显式 framework 工作区；保留原 legacy 布局和状态，不为整理而创建新适配、推断 framework/Host 或批量迁移历史阶段。后续用户选定新工作时使用 `new-framework`。

[人工接管与交回](../../../docs/human-collaboration.md)；[v2 证据契约](../../../docs/evidence-contract-v2.md)。只有用户选定实际阶段和 Host 后才推进适配。

## 文件归档与恢复

[整理前完整快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/Qwen3.8-Flash-Next)；[逐文件哈希清单](../../../.local/adaptation-history/20261012-model-layout-080344/before-manifest.json)；[归档与恢复说明](../../../.local/adaptation-history/20261012-model-layout-080344/README.md)。
归档位于 Git 忽略的 `.local/adaptation-history/`，仅本机可用，不等于已部署到远端或已持久交付。

本模型归档 54 个过程文件。保留全部原文和权限，没有删除试验数据；以下材料只用于历史查询，不作为当前运行入口。

| 原模型内路径 | 归档文件 | SHA-256 |
| --- | --- | --- |
| `_shared/config.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/_shared/config.json) | `c77cfd62621660b25e4c811bf44bf2ad4f63af98f23a874952a99e4e85f189f2` |
| `_shared/generation_config.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/_shared/generation_config.json) | `2a9c067fc2d6a652e174ffee36afede3a6c66261a88e4ac9baba476cee1d377e` |
| `ppu/acceptance/accuracy-index-launch.txt` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-index-launch.txt) | `f95d2ca5c67d68c0a8aabde9afdd33cfa669a874564bb6f4d7f39d7881ff18d9` |
| `ppu/acceptance/accuracy-index-progress.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-index-progress.json) | `4d3625138b329240c182156a50ba04cf8b0855a5db27a936c87d8f119daeee02` |
| `ppu/acceptance/accuracy-launch.txt` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-launch.txt) | `71a68529516617e4d44a5d48164320646dbca08778929f54e6a84457ca19010a` |
| `ppu/acceptance/accuracy-monitor-launch.txt` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-monitor-launch.txt) | `6b1362f6e007e61fb2894f8d26ce49ceabc885c3a9d3a98d33440575e67752e3` |
| `ppu/acceptance/accuracy-progress.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-progress.json) | `878e092bddf056706dc0b6c234c334feb9a37c9759c189ae6b10a1b8ab4bfaf5` |
| `ppu/acceptance/accuracy-timeout1800-launch.txt` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-timeout1800-launch.txt) | `2e00eca011c8d74a50f9a0f4b2cd24dd442b88a7c4375db5a0592ff5351b8127` |
| `ppu/acceptance/accuracy-timeout1800-progress.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/accuracy-timeout1800-progress.json) | `18d86385f8b489189d3e1c4227e775772673190a67c19ff8949fc2f7d3a50d0b` |
| `ppu/acceptance/capped22-launch.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/capped22-launch.json) | `4fb464a0bdbaf41f5b5bf69f8d02d9e38c4a0e6884e6bbe16110e41ba9373862` |
| `ppu/acceptance/capped22-manifest.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/capped22-manifest.json) | `edf565e5ac79bf0df8f2c724b2315f1b5ef4067b1c466369999f0eaa2038a5e2` |
| `ppu/acceptance/capped22-progress.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/capped22-progress.json) | `b2df562aae512b593abc856d6659168add84616bb9c7dfc4c1fa9a1d07960f4b` |
| `ppu/acceptance/communication_graph.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/communication_graph.py) | `4c11f6e218db33dbbb1f87ae93f29490e86f4901741119eed5b82295cd5b4a96` |
| `ppu/acceptance/evaluator-environment.txt` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/evaluator-environment.txt) | `0730fdde1066ce5123b9fe92cb5f2bffce9bcb48967e66d58b905e61d779aa55` |
| `ppu/acceptance/finalize_accuracy.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/finalize_accuracy.py) | `55aa41bafbdd85da1e0eb231dce61e75249f473064dbe4e44618d3d5bcf2520c` |
| `ppu/acceptance/finalize_accuracy_index.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/finalize_accuracy_index.py) | `d8ce5797d7077e2ffc8e82195a0c90a5787dec088634734a16124971223d5001` |
| `ppu/acceptance/finalize_performance.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/finalize_performance.py) | `abb62a7f23252f8ac9e5b04f92bc103e44e959f1a0fac70aef15efa1e14e170b` |
| `ppu/acceptance/graph-sanity-result.txt` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/graph-sanity-result.txt) | `4a8a315d94c6d7622bedf2b4eebc55eb25bb02d0f4bd1d2c434041b865d3e99a` |
| `ppu/acceptance/graph-sanity-reviewed.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/graph-sanity-reviewed.json) | `31fe4056358a598ed1468e2f6acf62515e7127269f494d4d12cbc6b16e8316cb` |
| `ppu/acceptance/graph_sanity.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/graph_sanity.py) | `0ade2073453c8764c5e2ed0edd07d41af6313c1fc7d4d47b2c58364b22f48cb9` |
| `ppu/acceptance/graph_sanity.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/graph_sanity.yml) | `1b28f09c218dc2a041cfb985faa81305e0ce9bc4ba323505b80f2c3a0d10dfb6` |
| `ppu/acceptance/historical-entrypoints/README.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/historical-entrypoints/README.md) | `e30c962d8bb5b59de58835af51c60a63cc7611d6d740dbf2714c6e8c57e9783f` |
| `ppu/acceptance/historical-entrypoints/graph_sanity.yml.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/historical-entrypoints/graph_sanity.yml.md) | `1ce707921cce759ef47fdaaadd9c4caa43ad086b40a4b33ef568459b31bd27af` |
| `ppu/acceptance/historical-entrypoints/rerun_capped22.py.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/historical-entrypoints/rerun_capped22.py.md) | `22a20bea7da08131c65780669d070b01c85cb055d46eabecf7c189ed6bdf0614` |
| `ppu/acceptance/historical-entrypoints/start_accuracy.py.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/historical-entrypoints/start_accuracy.py.md) | `66778896f6eb4c3749267c680b471573b11a9f7b82ab8d67bf4efa56264ae7fb` |
| `ppu/acceptance/historical-entrypoints/start_capped22.py.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/historical-entrypoints/start_capped22.py.md) | `fd7157af04d512ef7819275d2d567d6920a0aca12df6ca6a7287d160ab3d72c8` |
| `ppu/acceptance/inspect-capped-samples.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect-capped-samples.yml) | `0fbe04e5491190eebf5e36a6e77a442838c15d5c376f61e122f5b6973cb7ce3f` |
| `ppu/acceptance/inspect-capped22.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect-capped22.yml) | `9bef06d0a9691f8736c005b3e122aabe44e93a9d686215a9bcdc9fe207117a2b` |
| `ppu/acceptance/inspect_accuracy.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy.py) | `ac571320f9e7786c370b5d45943c8768fd92e45de28af4d0fbb93e1cb448a1f3` |
| `ppu/acceptance/inspect_accuracy_index.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy_index.py) | `b62b184fa7bc927aa365e86da2a36dec6d42f32e488728c290b0d435ac041211` |
| `ppu/acceptance/inspect_accuracy_index.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy_index.yml) | `f0ca47e2b0290b489aa00ad58215a74cab44c847e1e06f86d7199af45c607f2d` |
| `ppu/acceptance/inspect_accuracy_timeout1800.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_accuracy_timeout1800.py) | `dfc295eeef39d8c0604f4f3216044d8d72546f9064477b0a169615f467b1e658` |
| `ppu/acceptance/inspect_capped22.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_capped22.py) | `c0bc9e572901327a71b1c3e8048bba6c0834aa7ba8efbdb97551d68fc373204d` |
| `ppu/acceptance/inspect_capped_samples.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/inspect_capped_samples.py) | `3847e26944ad273168923aa342f6edb9fce58f924a2489ca492b1015ab47cc9c` |
| `ppu/acceptance/legacy-common-llm_config.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/legacy-common-llm_config.json) | `9c5cbbf6cdbaf7021190ae1fe83d83e7ebabeffe0f8f722d5aebf8f6a4a62c74` |
| `ppu/acceptance/legacy-common-llm_parallel_config.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/legacy-common-llm_parallel_config.json) | `56f5a922e39e33807fb61ddc8c62ea4b8b2e1b0f980adc4427b461f197067099` |
| `ppu/acceptance/llm_config.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/llm_config.json) | `cd0115fc68e63d44a4a39261012944f6325af79c68acacf84aa5317dca940a5c` |
| `ppu/acceptance/llm_config.timeout1800-index.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/llm_config.timeout1800-index.json) | `10afa45791f41b36e20f4d77df879843bcc7d2ca6bd3ab0e0b3ded7c15cbdf8d` |
| `ppu/acceptance/llm_config.timeout1800.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/llm_config.timeout1800.json) | `d6d9cdb5ed06ae4f61e94d34d0f1737db02a83ed7488e714ccb60321d0e2f482` |
| `ppu/acceptance/monitor_accuracy.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/monitor_accuracy.py) | `753154523d65a3a41b77cfec64c4833efb4be8cba86514d0fb5524ca823449ea` |
| `ppu/acceptance/rerun_capped22.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/rerun_capped22.py) | `2e9070274cf600fc7a1e3dd878798d3b0a17b76407fe19656f93cfb0ff48f6d8` |
| `ppu/acceptance/review_graph_sanity.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/review_graph_sanity.py) | `69e46406c7cc493c76312a5afcd49dd45a153e158486f6ab4231fa39840b2c54` |
| `ppu/acceptance/start_accuracy.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/start_accuracy.py) | `85746d1efc4f79b5f86c27b5036c18da48aafc6a3adbab336a2c4c1e3d348210` |
| `ppu/acceptance/start_capped22.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/start_capped22.py) | `1b2e89b938f400d083b588e7abc214dae0f9d91f4aded01bdae6a5dda8780d6c` |
| `ppu/acceptance/vllm_perf_qwen38.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/acceptance/vllm_perf_qwen38.py) | `3ab611366791c160a91084b3c8b9d720c19f282ec77bfe879f9b3057a817c290` |
| `ppu/environment/collect-ppu01.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/collect-ppu01.yml) | `cfb59c19d18768ff538f42fba634eee9d0a6b211c8405191ec84c50a05ecd416` |
| `ppu/environment/collect_container.py` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/collect_container.py) | `a0e3fa210ccf9db5bd3c54c2d023fa671070bafa7f05f3d2413b95d2b3365ab9` |
| `ppu/environment/container-baseline.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/container-baseline.json) | `180827db28da598e8c84419900f35ea8c37432662006d18ce9d7dd2f6216a2e1` |
| `ppu/environment/current-state-revalidation.json` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/current-state-revalidation.json) | `ede1b21fab1764bcccbcbe313fcd6b66a8932b1fb4145288ba22ba36aaa2b15a` |
| `ppu/environment/history/commands.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/commands.md) | `02f107479816bbff61f23ab0d3e1de95e7497fc243af4d2f1de01b38bc9ae7e6` |
| `ppu/environment/history/progress.md` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/history/progress.md) | `385dc4f0f4ff99bb57f1de50296aeb95bee6c846fb04fe0ab4cb7c0794249dd8` |
| `ppu/environment/revalidate-current-state.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/revalidate-current-state.yml) | `4e118f0c07ff809419a84ba823e3496182f2dcb178b2fc441f11fe260ebab6db` |
| `ppu/environment/runtime-config.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/runtime-config.yml) | `5abd73d2824c89e6c83b19533b3ae25fc0e0de8e1c718ac20257cdc4da24c833` |
| `ppu/environment/service-state.yml` | [历史原文](../../../.local/adaptation-history/20261012-model-layout-080344/relocated/models/Qwen3.8-Flash-Next/ppu/environment/service-state.yml) | `29681697a0406d236cb76e8361723d8101a5cc6e426ae3bd516f3e549fc0578a` |

## 保留的验证边界

legacy `platform.yml` 仍保留历史状态及绑定；本次不把人工接受结果或旧 Markdown 总结改写为原生通过。未选择的阶段不补跑。
结构审计只能证明目录和链接一致；profile 升级不能证明当前服务身份、权重、已安装代码、图模式、精度、性能或镜像交付已验证。
