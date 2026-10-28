# 003：max-num-seqs=64 的并发 OCR 功能回归

2026-10-20，用户明确要求将 max-num-seqs 调至64，显存比例保持0.55，更新两份启动脚本、重启本任务模型服务并检查并发 OCR。

## 变更与边界

H100-149 / minicpm-ocr-vllm-native，容器 ID `917cfd5ed14be7e4ee321d7c8db7810e93178cd4c46eadf8025457697bfdf8af` 未改变，始终保持运行。Host 和容器工作根均为 `/public/flagos/jinghao/MiniCPM-OCR`，设备号/inode `45:225185087240` 再次匹配。

两份启动脚本仅替换 `--max-num-seqs 8` 为 `--max-num-seqs 64`。GPU 0、TP1、BF16、gpu-memory-utilization=0.55、max-model-len=16384、FULL_AND_PIECEWISE、前缀缓存和8010端口保持原配置。仅停止旧 API PID 8618 的已核实进程组并启动新 API PID 10319；未停止容器或其他任务。产品源码九个改动文件的当前哈希与上轮 source review 完全一致，权重和依赖未改。

Host/容器根级 `start-model.sh` 与容器内部 `/opt/minicpm-ocr/start-model.sh` 的 SHA-256 均为 `8ce2e2fae3e703e71644f635e26428c5728e19343e7f22bf8212cc16c729f47a`，语法检查通过。两处交付配置和持久副本、manifest 已同步，旧内容保留在 `04-runs/seq64-restart-20261020/previous/`。新部署指纹为 `33822fe64f2ae6450faff4be25e54089a62baba65ff890a2e083c3cef9f47c74`，旧记录及回执保留为历史，不直接冒充新部署证明。

## 冻结与实测

操作选择为 service-sanity，使用仓库 `test/Accuracy_test/sanity.py`，先离线预检，再显式运行。Skill bundle SHA-256 `355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d`，完整 bundle/runner 身份保存在原始计划中。固定64路客户端并发、128个唯一请求ID、180秒超时；内容来自已验证的 OCR 请求，参考输出来自上一轮同构 Transformers 的冻结结果。

原生 observer 在宿主机核实容器、host network、API PID、boot ID、start ticks、命令行哈希及监听端口，报告 verified。原生结果为 passed：128/128参考文本一致，零请求错误、未丢弃或重试失败样本。覆盖图像、多图、4x/16x和小图选项。Prometheus 实际观测到同时运行64条请求，waiting峰值8；NVIDIA显存观测峰值45053 MiB，约44.0 GiB。服务健康接口为200、模型列表正确，当前新服务启动日志未见OOM、Traceback或EngineDeadError。

## 证据与限制

均在批准远端根：`03-acceptance/seq64-sanity-20261020/manifest.json`、`service-binding.json`；`04-runs/seq64-sanity-20261020/` 中的 test-plan、service-observation、sanity-result、summary 和 monitor；`04-runs/seq64-restart-20261020/` 中的 launch、previous-process、service-startup 和 verification。精度匹配结论来自原生 runner，设备并发与显存来自现场观察；不将显存采样峰值当作全时刻绝对上界。

本轮为容量配置与功能回归；不执行正式数据集精度或性能评测，不补造完整 execution-mode 回执，也不标记 optimized。历史 FULL 限制仍适用，本轮不改变图模式，下一次源码、容量或输入能力变化需重新验证相应范围。
