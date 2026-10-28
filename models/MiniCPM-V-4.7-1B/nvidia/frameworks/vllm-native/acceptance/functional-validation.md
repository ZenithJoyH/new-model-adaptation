# MiniCPM-V-4.7-1B 原生 vLLM 功能验证摘要

验证日期：2026-09-28；Host `H100-149`；容器
`MinicpmV4.7-1B-native`；模型
`/data/models/MiniCPM-V-4.7/weights/1b`；vLLM wheel
`0.24.0+cu129` / `_version.py` 短标记 `gee0da84ab`。
Host 与容器共享根均为
`/public/flagos/jinghao/MiniCPMV4.7-1B/native`，设备号:inode 相同。
部署身份文件 `01-environment/deployment-identity.json` SHA-256
`ac0c3db328583cfeac83ce7b0a508d7aa1383b4cb36be965686283b4193df0fe`。

## 执行模式和结果

| 模式/轮次 | 现场证据 | 结论 |
| --- | --- | --- |
| 4.6 别名加载基线 | `04-runs/baseline-46-alias-driver-20260928/service.log` | 加载真实 1B 权重，但 M-RoPE 语义不适合作为 4.7 通过证据 |
| 原生 eager | `04-runs/native-eager-20260928/` | 4.7 架构注册、权重加载、文本 42、单图 Red、短视频 red/blue 链路通过；初次视频回复触及 96 token 上限 |
| 请求 `FULL` | `04-runs/native-full-20260928/service.log` | GDN backend 只有 `UNIFORM_BATCH` 支持，引擎自动变成 `FULL_AND_PIECEWISE`；不通过 full 级别 |
| 显式 `FULL_DECODE_ONLY` | `04-runs/native-decode-full-20260928/service.log` | 捕获 51 个 decode FULL graph，无自动降级；API 就绪 |
| 变输入十并发 | `04-runs/native-decode-full-20260928/concurrent-summary.json`，SHA-256 `19600f0270008d923a19f02837177f4d588006bb0cf38f008f6b2610017c6578` | 10/10 HTTP 200、`stop`，文本、红/蓝单图、双图、视频的简单预期词均命中；该集合不是项目固定 GPQA sanity 或正式精度 |
| 根级最终启动脚本 | `start-model.sh`，SHA-256 `d21322e696819ea953c54f609fabf89c1494ee32e73fae9410419eec870a4926` | Host/容器同路径，可执行，`bash -n` 通过；占用端口时拒绝替换现有服务；从脚本启动后 graph 捕获、健康检查通过 |
| 最终实例请求 | `04-runs/final-launcher-smoke-20260928.json` SHA `47ad14bebd3a11ece71068ade8245f742238b50d0c04bb06fcbc8bb676cc7618`；`04-runs/final-launcher-smoke-256-20260928.json` SHA `922dbae922d8fdcbc265aecc7514b389ccc2cbe670e989c30aef172e41c9c6ca` | 首次 96-token 响应 `length`，保留为不通过；仅增至 256 token 重试后 `stop`、答案 42 |

最终脚本位于 Host 与容器的
`/public/flagos/jinghao/MiniCPMV4.7-1B/native/start-model.sh`，日志只写
`04-runs/`，缓存写 `06-cache/`，临时写 `05-tmp/`。GPU 0、TP1；
`CUDA_VISIBLE_DEVICES=0` 固定设备，`--gpu-memory-utilization 0.35` 限制占用，
`--max-model-len 2048` 是本轮已测上下文范围。`127.0.0.1:8307` 限制对外暴露并固定
已测接口；`--served-model-name` 固定 API 身份。`--trust-remote-code` 读取 checkpoint
配置/processor，`--model-impl vllm` 拒绝隐式走 Transformers，
`--enable-prefix-caching` 保持非性能配置要求，
`FULL_DECODE_ONLY` 是此 Host 已验证的最高允许图级别。
`HF_HOME`、`XDG_CACHE_HOME`、`TRITON_CACHE_DIR`、`VLLM_CACHE_ROOT`、
`PYTHONPYCACHEPREFIX`、`TMPDIR` 把隐式写入约束在批准工作根；
`TRITON_LIBCUDA_PATH` 解决该镜像 libcuda 查找失败。

## 代码审查与界限

registry 原文件备份 `02-issues/registry.before.minicpmv4_7.py`，
原/新 SHA-256 分别为
`ab52495073a046b79d00a314cbc96e719e3ed916ea8a8bf6f3202015062b5676` / 
`58ea925cd79c7771b35455d48c5d991928fd019539d8e0e61e100af541d55d43`。
实际 diff 仅新增四行 4.7 映射；新模型 adapter
`/usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/minicpmv4_7.py`
SHA `e1bddd8ee92576ff8260ef8e5362a8a7fb7d47c3f4f70584e63944695c2cf86d`。
4.6 adapter 哈希未变；registry 4.6/4.7 命中、未知 4.8 未命中。
该容器是 wheel 安装且没有 Git 树，完整 HEAD、PR base、原有 dirty/untracked
无法核实；用户明确授权本任务直接修改安装包，本轮未提交、推送或建 PR。

当前仅能标记 `functional`，不标记 `optimized` 或完整验收。缺少模型参考实现
逐 token 数值对照、项目固定 GPQA sanity manifest、冻结正式数据集/指标阈值和
相应原生准确率回执；性能须在准确率通过后另启显式
`--no-enable-prefix-caching` 的独立服务，并核实其生效状态。
本任务未运行性能测试，不把十并发的 2.081 秒视为正式 benchmark。
多卡、长上下文、高分辨率复杂切片与跨平台未验证。
