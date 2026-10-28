# 004：省略前缀缓存开关后实际未启用

## 元数据

- 状态：已确认，根脚本保留显式启用参数
- 首次出现及复核：2026-09-30
- 模型、平台、Host：MiniCPM-V-4.7-1B、NVIDIA、`H100-149`
- 容器与引擎：`MinicpmV4.7-1B-native`，vLLM `0.24.0+cu129`
- 模式与负载：GPU 0 TP1 BF16、`FULL_AND_PIECEWISE`、正常前缀缓存配置，重复长文本前缀请求

## 现象与已有经验

vLLM `CacheConfig.enable_prefix_caching` 类字段默认是 `True`，但 CLI
`--enable-prefix-caching` 省略后，当前服务的相同长前缀请求没有产生
`vllm:prefix_cache_queries_total` 或 `vllm:prefix_cache_hits_total` 增量。
显式启用时日志有 Mamba align 前缀缓存启用提示；省略时没有。
已搜索现有 troubleshooting 与同模型记录，未发现同版本、同模式的完整签名；
不直接套用其他模型的缓存经验。

## 受控对照与根因边界

两轮根脚本仅相差 `--enable-prefix-caching`，均使用同一模型、vLLM wheel、
GPU 0、`XDG_CACHE_HOME=06-cache/`、图模式、容量和相同诊断脚本。

| 轮次 | 脚本 SHA-256 | 原始结果 | 缓存查询 / 命中增量 |
| --- | --- | --- | --- |
| 省略开关 | `664f7488c5a2c638f52fec6bf97b48c6fe961f61343fc66db99f372da8eac720` | `04-runs/minimal-launcher-20260930/prefix-cache-check.json`，SHA-256 `2f13bf28fab1f10324bf7cff46a5b8d2740d1e0d801456a314434910dd617572` | `0 / 0` |
| 显式启用 | `c5fce8aba2f93a66e9fc1a5a23a386900b05c2a5464d326750eabd723aaaa6df` | `04-runs/minimal-launcher-20260930/prefix-cache-check-explicit.json`，SHA-256 `9fece2ba9e67e01729ac5bde066be07139f6fd243d0d102aee13ab4a27315264` | `1484 / 576` |

这确认在当前模型与版本上省略开关不能满足“正常前缀缓存开启”的服务要求。
CLI 默认值在混合模型配置中如何解析尚未追溯到确切代码分支；不把
`CacheConfig` 的类字段默认值当作最终运行状态。

## 解决与验证

只在根级 `start-model.sh` 恢复 `--enable-prefix-caching`，没有修改
vLLM 产品代码。诊断脚本位于远端工作根 `02-issues/`，原始结果位于
`04-runs/`；失败的脚本版本备份在
`02-issues/start-model.minimal-cache-default-failed.20260930.sh`。
仅停止本任务已核对的 API PID `13222` 并从修正后的根脚本重启；容器未停启，
GPU 0 释放后再使用。对照时 API PID `14562` 的命令行含显式开关，日志显示
Mamba align 缓存启用，mixed PIECEWISE 与 decode FULL 各捕获 51 个图。
`04-runs/minimal-launcher-final-20260930/concurrent-summary.json` SHA-256
`f5f51ec8b27f79107bbdae0b75d38419bb04c5efbbc115536be71024bd09394e`：
十并发文本、单图、双图、视频请求全部 HTTP 200、`stop` 且命中简单预期；
`/health=200`，无服务 ERROR/Traceback/Exception。

## 限制与经验处理

重复前缀诊断只验证缓存生效，不是性能评测；两次请求的短生成触及
`max_tokens=16`，因此 `finish_reason=length` 不作为回答正确性证据。
未验证其他模型、vLLM 版本或平台。知识库状态：`needs-validation`；
适用范围限于本模型当前原生环境，正式准确率与性能验收仍待完成。
