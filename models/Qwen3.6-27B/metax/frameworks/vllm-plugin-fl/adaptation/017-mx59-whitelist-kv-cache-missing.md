# 017：mx-59 白名单过滤 KV-cache 唯一实现导致启动失败

## 元数据与范围

- 状态：诊断时 `open`；后续[018](018-mx59-plugin-compatible-release-upgrade.md)已更新兼容Plugin分支，原生cache回归及同白名单TP2图模式启动通过。本页以下内容保留升级前只读诊断身份，不将其当作升级后状态。
- 检查日期：2026-10-10，仅按用户请求只读诊断 mx-59 / Qwen3.6-27B / vllm-plugin-fl。
- 容器：`qwen3.6-27B`，ID `1f62bdcb818d7119ed6595133dc64c3f14c194ae565c95dba18ef89bbd4fe657`，镜像标签 `flagos/qwen3.6-27b-metax:public-flash-20261008`。容器仍运行，完整 `/public-flash` RW挂载及权重RO别名未变化。
- Plugin HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，FG HEAD `7599dd130046f84df099aa771e91d35d5991e69a`，vLLM HEAD `bc150f50299199599673614f80d12a196f377655`；继承既有dirty改动，本轮未写远端。
- 最新脚本：`/public-flash/jinghao/qwen3.6-27B/start-model-flagos.sh`，SHA256 `1cc015c75db3a171244a663b9ae049813796826bd7020a9f1d6a93a4283f7de2`。
- 当前设置：GPU2/3、端口8001、alias `qwen36-27b-begin`，TP2/BF16、batched tokens8192、显存0.9、FULL_AND_PIECEWISE/max capture64。与016的GPU6/7、8002及黑名单配置不同，不沿用其服务状态或性能结论。

## 问题现象与证据

日志 `/public-flash/jinghao/qwen3.6-27B/service-qwen36-27b-begin.log`，读取时SHA256 `2d44ca8111c43472bcfaa60a4d4b62f4ce85e61fba277e2bd2e02b330e6825a1`。
两rank在2026-10-10 14:40:20图捕获预热中失败；首个Worker异常见日志342–413行：

```text
RuntimeError: No available implementation for op='reshape_and_cache_flash'. Registered: []
```

随后EngineCore/API退出；容器进程检查未发现仍运行的模型服务。本轮没有执行停止、重启、缓存清理或源码/脚本修改。

## 已有经验匹配与诊断

016成功服务日志 `04-runs/throughput2-mx59-20261010/optimized-service.log` 第307/340行明确：`reshape_and_cache_flash` 使用 `default.flagos`。此前黑名单没有禁用该算子。008的旧图缓存问题为FA形状断言，本次为注册列表为空，失败签名不匹配；虽然本次加载了编译缓存，不能据此归因缓存或降低图模式。

最新脚本启用了 `VLLM_FL_FLAGOS_WHITELIST=cat,cos,cumsum,fill,full,gather,gt,le,lt,max,mul,sin,softmax,to,where,zeros,zeros_like`，注释掉旧黑名单。该名单不包含 `reshape_and_cache_flash`。

已确认调用链及源码（均为容器安装树 `/workspace/vllm-plugin-FL`）：

1. 日志201/245行确认 `attention_backend` 选择 `vendor.metax`；334/335行确认 `gdn_prefill` 选择 `vendor.metax`。
2. `vllm_fl/dispatch/backends/vendor/metax/impl/attention/flash_attn.py:754` 写入KV cache时调用 `fa_utils.reshape_and_cache_flash`；后者在 `utils/fa_utils.py:33` 定义为 `CachedOp("reshape_and_cache_flash")`，并不是直接调用SDK或vLLM原C算子。
3. `vllm_fl/utils.py:216` 对白名单作精确成员过滤；`dispatch/backends/flaggems/register_ops.py` 最后用 `use_flaggems_op(impl.op_name)` 过滤后注册，因此唯一 `default.flagos` KV-cache候选被排除。
4. 当前MetaX/vendor、reference注册表均没有该算子的候选。`dispatch/manager.py:391` 对空候选报错，和日志 `Registered: []` 完全对应。

根因是白名单暴露了既有Plugin KV-cache回退缺口，而不是“白名单外一定自动走vendor”。该算子属于KV-cache写入，不等同Flash Attention计算；即使FA backend选vendor，cache写入仍需要单独可用的dispatch实现。首异常不是OOM、端口占用或FA shape断言，`Unknown vLLM environment variable` 只是原生vLLM不识别Plugin扩展变量的警告，Plugin源码仍会读取该变量。

## 解决建议与验证边界

- 最小配置workaround：在当前白名单追加 `reshape_and_cache_flash`，保留其FlagGems实现；白名单与黑名单不能同时非空，需注意继承的环境变量。此建议只针对本次缺失，未执行或声称启动通过。
- 如果要求名单外完全不用FlagGems，需要在既有dispatch中补齐真正可用的vendor/reference KV-cache实现，再验证名单过滤、eager/graph及原位cache写入。不能把FlagGems换个vendor标签或忽略白名单作为原生回退。
- `fa_utils.py` 的既有注释说明empty vLLM wheel缺少原C cache kernel；当前源码树顶层未检出 `_C*.so`。本轮未动态探测SDK/native kernel，不假定直接恢复 `vllm._custom_ops` 就能工作。
- 本轮没有运行GPU复现、服务启动或性能/精度测试；没有调整FULL_AND_PIECEWISE。源文件及日志只读分析能定位当前错误，配置修改后的全链路结果仍待验证。

## 源码边界与经验状态

Plugin manager SHA256仍 `59f5fa67d0d698206baa00d1486b59467e7895cb60a726a7414773f44f5ced50`；FG sort SHA256仍 `e200fbf2287ebd4104e8e312fe0dab90e6a05326a8f56b25cccc604c7c46a199`；vLLM完整diff SHA256与016一致。当前白名单也不包含sort，本次失败栈没有进入其调用；未将此问题归因016排序优化。

设计审查：本轮无产品变更，后续修复需保留既有dispatch控制语义并验证可选原生能力。知识状态 `local-only`，不推广到其它平台，不更新framework验收状态，不提交或推送。
