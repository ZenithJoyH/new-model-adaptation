# 006：GDN 仅以高层算子进入全平台 FlagOS dispatch

## 元数据与问题

- 2026-09-23；Qwen3.6-27B / MetaX C550 / `mx-58` / `qwen3.6-27B`；第 3 阶段适配继续 `in_progress`，正式验收未选择。
- 上一轮 [005](005-dual-route-metax-gdn.md) 的 Plugin HEAD 为 `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，tracked diff SHA-256 `3f22766bc58cb900e466e779e1432e0e70a6593e534c40c551fdfaa79dfab678`。容器、映射、editable Plugin 根和只读组件身份重新核对后才写入。
- 用户指出：GDN 的 FlagGems 链路不能依赖 MetaX vendor 才安装调用点 hook；同时低层 `chunk_gated_delta_rule_fwd`、`fused_recurrent_gated_delta_rule_fwd` 已由两个高层实现直接调用，不应各自再占一个 dispatch 算子。此前 FlagOS 注册仍经过 `use_flaggems_op` 过滤，hook 安装却在 MetaX vendor 注册完成时。

## 设计、修改与边界

当前公共调用点仍是 vLLM `GatedDeltaNetAttention` 的 prefill/普通 decode；对外保持 `gdn_prefill` / `gdn_decode` 的原参数、返回值和 paged state 语义。FlagGems `register_ops.py` 无平台判断地注册这两个 `default.flagos` 高层候选，并在自身注册末尾安装幂等 hook；这两个注册项不被通用 FlagOS 名单过滤，也不依赖 MetaX vendor 注册或 backend 可用性才注册。算子**执行选择**仍经过现有 dispatch 的可用性与 policy；这与注册阶段无门槛不同。非 GDN 算子的原名单过滤保持不变。

两个低层 `OpImpl` 已删除；`FlagGemsBackend.gdn_prefill/gdn_decode` 内部仍直接调用 `self.chunk_gated_delta_rule_fwd` / `self.fused_recurrent_gated_delta_rule_fwd`，再由这些 backend 方法惰性导入对应 FlagGems-vLLM kernel，不新增第二级 dispatch。packed decode 仅在实际选择 `default.flagos` 时改走普通 decode；选择其它候选时仍保留原 packed 路径。MetaX 的两个 `vendor.metax` 候选及其原 vLLM/FLA 委托保持不变，不增加其它平台 vendor/reference 实现。KDA/spec 保留原 vLLM 路径；decode 原位 state 更新保持 strict/no-retry。Flash Attention 仍只通过现有 `attention_backend` 接入。

替代的“为所有平台新增原 vLLM reference 候选”超出本次用户明确范围，未实施。FlagGems-vLLM 在本镜像已安装，调用处直接导入；其它平台只完成注册/隔离契约测试，不能据此声称硬件 kernel 已验证。受影响调用方包括共享 vLLM GDN 模型和现有 MetaX 双路由；非 GDN 算子的过滤行为及 vendor 实现均有回归/静态检查。

## 受控验证与证据

- Plugin `/workspace/vllm-plugin-FL` 最终 HEAD 未变，tracked diff SHA-256 `21fcbdf61a525f6ad3671187a9a47fb860caa5486296d4cd53a945ae3be50bf7`；未跟踪 GDN hook 与测试 SHA-256 分别为 `8328ee53d89e9551b4a497896c97bbac02507f5116da91a81ef849efe4a14a4c`、`de96f22cd7946132241149ceb00c5f564c945ba4b87308477cff89d1cac54cb5`。最终源码身份为 Host/容器同路径 `01-environment/deployment-identity-global-gdn-high-level-20260923.json`，SHA-256 `a4f7dbcffd77d6d9d8d7cd93ba81a41f9624dc6c8b73c19da8928479723460b0`，绑定镜像 digest、模型配置/索引/tokenizer、四组件 HEAD 和 dirty 状态。
- `tests/unit_tests/dispatch/test_metax_gdn.py` 新增负向门槛用例：将 `use_flaggems_op` 和 backend 可用性都设为 false，仍确认高层 GDN 注册与 hook 安装调用；两低层算子在 registry 中不存在。聚焦 6/6、全部 dispatch 273/273 通过，`git diff --check` 通过。独立新进程在仅放行 attention 的白名单下确认 GDN 高层 FlagOS/vendor 双候选与 hook；模拟无 vendor 注册时仅有两个 FlagOS 高层候选，选择和 hook 正常；另在 `VLLM_FL_PREFER=vendor` 新进程确认 MetaX 两个高层算子仍选 `vendor.metax`，hook 幂等。这是无 vendor 的逻辑隔离和 MetaX vendor 选路证明，不是另一平台硬件测试。
- 本轮隔离模型启动脚本在 `04-runs/global-gdn-flagos-{eager,graph}-20260923/launch.sh`，同一 SHA-256 `963152b25e85d5865fcc95e90369436bafe4d25b7570f813457719b48295e9b9`；TP2/BF16/GPU0/1、127.0.0.1:8001、prefix caching enabled。eager 的 `service.log` / `completion-response.json` SHA-256 为 `1180300354f65f1bd657204b97a9c5f83dbef21aeafff29ac1bb40f1dc49159d` / `d0978f7a447e72b649a57990094917fc50c7001628ec4ed24eb2515b2763369c`；两名 worker 的高层 `gdn_prefill/gdn_decode` 均命中 `default.flagos`，无低层 dispatch 命中，短请求 HTTP 200、16 completion tokens。
- graph 同样请求 `{"mode":0,"cudagraph_mode":"FULL"}`，stock GDN metadata 报 `UNIFORM_BATCH`，实际自动设为 `FULL_DECODE_ONLY`；decode 图 3/3 捕获，高层 GDN 两算子均命中 `default.flagos`，短请求 HTTP 200、16 tokens。graph log/response SHA-256 为 `66612ea662ae634d779966fc34ac8af84bca39350fe1fbf3743ca83fab1eddd6` / `0557e681ce5e111d40c1245d8e10572e6c53f6724b7da0d2826b540577124512`。
- 一次性编辑/请求代码只在批准的 `05-tmp/`，运行结果只在 `04-runs/`。每个测试服务启动前确认 8001 空闲、GPU0/1 可用，结束前核对 PID、模型名和端口，仅 TERM 本轮自启服务；验证后 8001 健康探测退出 4，原 8000 `/health` 退出 0。适配容器未停止。vLLM 继承 diff SHA-256 仍为 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`；FlagGems 与 FlagGems-vLLM 工作树 clean。

## 设计审查、限制与下一步

实际 Plugin diff 是 6 个 tracked 文件加 2 个 untracked 文件；本轮相对 005 只调整 FlagGems GDN 注册、移除 vendor 注册末尾的 hook 安装、将 hook 的 packed 判断从 MetaX ID 改为 FlagOS ID，并扩充聚焦测试。源代码没有新增 reference 或其它平台 vendor 候选，也没有改 vLLM/FlagGems。PR base 未确认，不能声称完整 PR diff 已审完或可合并；未提交、推送或创建 PR。当前 MetaX Qwen3.6-27B eager/decode-full 冒烟验证了本 Host 的高层选路；其它平台设备、其它 GDN 模型、直接数值对照、chunked/mixed batch、KDA/spec 与正式准确率/性能仍未完成。`FULL` prefill 图退出条件仍是上游 GDN metadata 支持并通过捕获/回放验证。经验状态 `local-only`，不得推广为全平台 kernel 已验收。
