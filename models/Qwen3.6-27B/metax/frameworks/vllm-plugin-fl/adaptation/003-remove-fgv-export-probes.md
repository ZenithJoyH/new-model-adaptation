# 003：移除 FlagGems-vLLM 导出探测

## 元数据与范围

- 2026-09-23；Qwen3.6-27B / MetaX C550 / `mx-58` / 容器 `qwen3.6-27B`。
- Plugin HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`；本轮只修改已核实的 editable Plugin `vllm_fl/dispatch/backends/flaggems/register_ops.py`。
- 状态：源码、新环境原生回执、新进程 dispatch 路由和默认编译模式的 graph 模型请求已验证；本轮修改后未重新运行 eager 模式，也未选择正式执行模式验收，因此先前的适配原生回执不绑定当前源码。

## 原因、修改与边界

默认镜像已安装 `flaggems-vllm`。原 `_has_flaggems_vllm_op` 在注册时逐项导入并探测导出，
与本环境的必备依赖契约重复。该可用性检查也会在缺失依赖时静默跳过 FlagOS 候选，
不利于暴露镜像配置错误；它并非算子运行时的能力判断。

删除 `_has_flaggems_vllm_op`；MetaX 的 FlagOS attention 候选仅由现有
`VLLM_FL_USE_FLAGGEMS_ATTN` 开关和 FlagGems backend 可用性决定。
GDN 两个 `default.flagos` 注册项改用同一 backend 可用性；最终仍受既有
`use_flaggems_op` 策略过滤。FA 仍只从原有 `attention_backend` 接入，
GDN 仍由 FlagGems/FlagOS 注册和 hook 接入；各实际实现直接导入
`flaggems_vllm` 算子。未新增 FA OpImpl，未改 vendor/MetaX、vLLM、FlagGems 或
FlagGems-vLLM。缺失必备依赖时，新进程会在实际调用处报错，不再静默回退。

## 验证与复核

- 新部署身份：Host/容器同路径 `01-environment/deployment-identity-flagos-direct-fgv-20260923.json`，SHA-256 `38f5790fe8edfa4593f9dab1a212dc1c2f17acc74baa4253f1e2abfd5bf5abcf`；Plugin tracked diff SHA-256 `816532008cc0da8c1f8d7409a49b45920b37355de735b783546c1a7043659668`，未跟踪 GDN 文件 SHA-256 `2c2517ee46b48792c11bc00955d58e35dfd3dbc879e2fc41759196c7ac0c1b2c`。
- 当前环境原生回执：`01-environment/framework-check-flagos-direct-fgv-20260923.json`，SHA-256 `7da00f6370f79c7c79956e6d4a60fd32c81d33533373b9380b817f930195107d`。
- 容器内 Python AST 解析和 `git diff --check` 通过；现场导入 `flaggems_vllm`，`flash_attn_varlen_func`、`chunk_gated_delta_rule_fwd`、`fused_recurrent_gated_delta_rule_fwd` 均为 callable。
- 现有路由探针 `05-tmp/flagos-route-correction-20260923.py` 在新 Python 进程中分别用两个开关全关/全开验证：关闭时 attention=`vendor.metax`、GDN hook=false；开启时 attention=`default.flagos`、GDN hook=true；两个 GDN 算子均为 `default.flagos`，没有第二个 FlagOS FA OpImpl。脚本断言全部通过。
- 复核 `git status --short`：四个本轮 modified 文件、一个未跟踪 GDN 文件；本次相对 002 仅变更 FlagGems `register_ops.py`。`vendor/metax` 无本轮 diff。PR base 未确认；未提交、推送或创建 PR。

## 默认编译模式的 FULL_AND_PIECEWISE 实测

2026-09-23 在同一镜像、Plugin diff 和 TP2/BF16、GPU0/1 上，启动独立
127.0.0.1:8001 服务；启动脚本为 Host/容器同路径
`05-tmp/flagos-default-mode-full-piecewise-launch-20260923.sh`，SHA-256
`bf7cada818bcc909291459ab950eb0372e0eaa509c622d592fe787eed3e36231`。
服务启用 `VLLM_FL_USE_FLAGGEMS_ATTN=1`、`VLLM_FL_USE_FLAGGEMS_GDN=1`、
`--enable-prefix-caching`；`--compilation-config` 仅含
`{"cudagraph_mode":"FULL_AND_PIECEWISE"}`，没有传 `mode`。其他 TP、显存、
上下文与此前 002 的隔离服务配置相同；因此本测试只针对编译/图模式变化，
不宣称为同条件性能对照。

- 原始服务日志：`04-runs/flagos-default-mode-full-piecewise-20260923/service.log`，
  SHA-256 `d591e22ccb163b324935ba301faed8a5ed3cb074745745677a6097073c9f5021`。
  Engine 初始化后的有效配置为 `CompilationMode.VLLM_COMPILE: 3`、
  `CUDAGraphMode.FULL_AND_PIECEWISE`，`splitting_ops` 包括 attention 和
  `vllm::gdn_attention_core`。两名 worker 的 FlagOS attention、GDN chunk/recurrent
  均选 `default.flagos`；首次 torch.compile 完成，混合 prefill/decode
  PIECEWISE 图 4/4 和 decode FULL 图 3/3 捕获完成。未见模式降级或致命运行异常。
- 真实请求脚本 `05-tmp/flagos-default-mode-full-piecewise-probe-20260923.py`，
  SHA-256 `063cdabfb462e80d81cc5503b0a85f16db8e02eb84767766c1f3b734a3b3f4f5`。
  两条不同长度 prompt 分别返回 HTTP 200、非空文本、32 completion tokens；
  `04-runs/flagos-default-mode-full-piecewise-20260923/completion-response-1.json`
  SHA-256 `a63e829514212fc6a0775814be10889454e3c551c3e67fbde033f235c57b42c0`，
  `completion-response-2.json` SHA-256
  `7c3f6a0c1e89f482b2a8f13be2116234cbceeb1c836598f58f8958c53ea9e1fe`。
- 启动前确认 GPU0/1 无其他进程、容器 8001 端口空闲；测试后核实 PID
  `386991` 的命令行确属本次模型、端口和模式，使用
  `docker exec ... kill -TERM 386991` 只停止该任务实例。随后验证 8001 关闭、
  GPU0/1 恢复空闲、原 8000 服务返回 HTTP 200，容器仍运行。未修改 vLLM 或
  Plugin 源码，Plugin tracked diff SHA-256 仍为
  `816532008cc0da8c1f8d7409a49b45920b37355de735b783546c1a7043659668`。

这证明当前栈可以实际运行默认 `mode=3` 与 `FULL_AND_PIECEWISE`，但 prefill
使用的是 PIECEWISE 图，并不是要求的 FULL prefill 图；按 profile 该探针仅属
适配诊断，不能替代 `full → decode-full` 的正式图级别验收。启动首次编译和图捕获
增加了时间/显存开销；本次两条请求不能形成稳态性能或正式准确率结论。

002 的 eager/graph 原生适配回执仍绑定旧 Plugin diff；不能直接重标为新源码通过。
当前 8000 服务未停止或重启，不声称其已加载新源码。下一步需重新核实本源码的
eager 模式并重建适配回执后，才恢复本 profile 的适配完成声明；正式
accuracy/performance 仍未选择。
