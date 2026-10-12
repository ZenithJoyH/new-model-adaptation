# 004：移除 FlagOS attention 注册门控和 GDN 环境变量

## 元数据与现象

- 2026-09-23；Qwen3.6-27B / MetaX C550 / `mx-58` / 容器 `qwen3.6-27B`，TP2、BF16、GPU0/1、prefix caching enabled。
- Plugin `/workspace/vllm-plugin-FL` HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，本次修改只涉及 FlagGems 注册文件和 MetaX policy 注释。最终 tracked diff SHA-256 `b681f19bd1de01745fc2f3c5cabccca8eef81f4fda2fbd13a82184664bcc19dc`；新增 GDN 适配文件 SHA-256 `2c2517ee46b48792c11bc00955d58e35dfd3dbc879e2fc41759196c7ac0c1b2c`。
- 用户要求删除 `_flagos_attention_available`、`_flagos_gdn_enabled` 和 `VLLM_FL_USE_FLAGGEMS_GDN` 控制。旧注册层在 MetaX 上将 attention 可用性额外绑定到 FA 环境变量，并仅在 GDN 环境变量开启时安装 vLLM GDN call-site hook。这与已有 `attention_backend` 内部 FA 选择和 FlagOS GDN dispatch 形成重复门控。
- 经验参照：[002](002-correct-flagos-ownership.md) 的所有权边界和 [003](003-remove-fgv-export-probes.md) 的导出探测移除；此前探针和模型请求均绑定旧源码，不能直接充当本次验证。`docs/troubleshooting/` 无相同完整签名的条目。

## 修改、行为与边界

`vllm_fl/dispatch/backends/flaggems/register_ops.py` 删除两个 helper 和仅供它们使用的 `os` 导入。`attention_backend` OpImpl 恢复使用 `backend.is_available`，不在注册阶段读取 FA 开关。MetaX GDN hook 在 FlagGems 注册路径安装，不再读取 `VLLM_FL_USE_FLAGGEMS_GDN`；其两个算子仍为 `default.flagos`，继续经过现有 `use_flaggems_op` 过滤与 dispatch。复核发现仅删除开关会在现有 FlagOS policy 排除 GDN 算子时仍安装 hook，造成缺失实现的调用路径；最终仅当两个 GDN OpImpl 都通过 policy 过滤且 backend 可用时安装 hook。这是沿用现有 dispatch 策略的能力守卫，并非新的环境变量或 FGV 导出探测。hook 自身幂等，KDA/spec 不支持的分支保持原 vLLM 路径。未修改 `vendor/metax`、vLLM、FlagGems 或 FlagGems-vLLM，也没有新增第二个 FA OpImpl。

`VLLM_FL_USE_FLAGGEMS_ATTN` 仍由 FlagGems `attention_backend` 方法读取：设为 `1` 返回 FlagGems-vLLM 的 `AttentionFLBackend`；关闭时返回 vLLM `TritonAttentionBackend`。由于注册门控已删除，MetaX policy 的首选 FlagOS 候选在这两种情况下均可用，关闭时**不再默认选 MACA**；MACA 仍是 policy 中的后备候选。同步修正 `vllm_fl/dispatch/config/metax.yaml` 注释。此默认变化是用户要求移除注册判断的直接影响，不能把旧的“开关关闭仍走 MACA”结论沿用到新源码。其他平台的 FlagOS attention 可用性仍取决于 backend；实际硬件路径未复测。

替代方案是保留 MetaX 专属注册门控或把 GDN 改至 vendor 路径；两者均与本次明确的用户要求及既有 FlagOS 所有权边界不符。当前不更改 FA backend 内部开关，也不声称环境变量关闭时 Triton 路径已经完成模型级验证。

## 验证与证据

- 最终部署身份：Host/容器同路径 `01-environment/deployment-identity-flagos-no-gates-policy-20260923.json`，SHA-256 `a25e369a2206da9226cc72e3fd742d5bfbc8b7dbca9859752a7955bcc4e89b40`；核实容器镜像 digest、模型配置/索引/tokenizer、四组件 revision 和 dirty 状态。测试配置不再包含 GDN 环境变量。前一身份 `01-environment/deployment-identity-flagos-no-gates-20260923.json` SHA-256 `6001d6fad19366aeddce3a9d388208e5fc41f28ac66ee88f5e93b5e5e2cd1b11` 仅对应策略守卫加入前的源码。
- `git diff --check`、Plugin 注册文件语法检查通过；全 Plugin `.py/.yaml` 中不再有两个 helper 或 `VLLM_FL_USE_FLAGGEMS_GDN`。`vendor/metax` 本轮无差异。路由探针位于 `05-tmp/flagos-no-gates-route-20260923.py`，SHA-256 `ce47260ffc3496660af9b0e4af1f635f2ded5fb0feb3e668cefb041faa755ff4`；最终 diff 下两个新进程均不设置 GDN 变量。FA 开关关/开时 attention 都先选 `default.flagos`，实际 backend 分别是 Triton/FlagGems-vLLM；两个 GDN 算子都先选 `default.flagos`，hook 安装且重复调用幂等，无第二个 FA `default.flagos` OpImpl。另用 `05-tmp/flagos-gdn-policy-miss-20260923.py`，SHA-256 `66d27da815034e732d1844580cd5b14508a29b6c4b73d72d46f03e568c0cee8f`，在仅放行 attention 和 GDN chunk 的新进程中验证 recurrent FlagOS 被排除、GDN hook=false。
- 策略守卫加入前的隔离 eager 模型实例启动器 `04-runs/flagos-no-gdn-gate-eager-20260923/launch.sh`，SHA-256 `4158a4f07ef27cc57fda59be7a87b03f650ffef0a45c1617ffc086373f371503`，显式 `unset VLLM_FL_USE_FLAGGEMS_GDN`，仅在 GPU0/1、127.0.0.1:8001 运行。最终 `service.log` SHA-256 `39697e305520897096f83981a766c1569eba9f0bfc428ef664167054a838500d`：两名 worker 的 attention、GDN chunk/recurrent 均命中 `default.flagos`；`--enable-prefix-caching` 生效。请求脚本 `05-tmp/flagos-no-gdn-gate-request-20260923.py` SHA-256 `e398c9a747dcb126e5055aea44f49e89581d7539cf961f43ce04a7e9fafdaf93`；响应 `04-runs/flagos-no-gdn-gate-eager-20260923/completion-response.json` SHA-256 `ae7cf45b7d7f70d4cb86e67d0ce6764906e65cc230723b1218a7e28b9d5b771d`，HTTP 200、非空文本、16 个 completion tokens。最终守卫在默认策略下计算为真，但尚未用最终 diff 重跑模型请求。
- 启动前 GPU0/1 空闲、8001 未被占用。核实 PID `411741` 的模型和端口后，仅向该测试进程发送 TERM；日志显示正常退出，8001 连接拒绝，PID 消失。原 8000 服务健康检查仍为 200，容器仍 running。没有停止或重启适配容器。此前 `py_compile` 产生一个忽略的 `.pyc` 缓存，不属于源码差异。

## 设计审查与后续

本次相对 003 的实际源代码差异仅是 FlagGems `register_ops.py` 的两个门控删除及现有 policy 守卫、`metax.yaml` 注释更新；四个 tracked 修改文件和一个未跟踪 GDN 适配文件是本轮累积工作。Plugin PR base 未确认，HEAD 未改，无提交、推送或 PR。公共影响面包括 MetaX 默认 attention 选择、GDN hook 初始化、其他平台 FlagOS 注册；最终 diff 的正/负路由已验证，模型 eager 请求仍绑定守卫加入前的相邻 diff。FA 关闭时只验证了实际 backend 选择，没有模型级数值或请求验证；最终 diff 的 eager/graph 和其他模型/平台仍需复测。此前 003 的 `FULL_AND_PIECEWISE` graph 请求绑定旧 diff 和 GDN 环境变量，不能冒充本次源码的 graph 回执。当前适配保持 `in_progress`，正式 acceptance 未选择；这仍是局部设计/冒烟证明，而非精度或性能结论。知识库状态 `local-only`。
