# GPQA c64 服务故障只读诊断

核实时间：2026-09-04 12:03（Asia/Shanghai）。目标 PPU-13 / glm5.3-flash，
GLM-5.3-Flash-BF16、vLLM 0.24.0、TP16、graph、50K、seq32，客户端并发64。
镜像与插件基线沿用 `../environment/runtime-config.yml`；本次没有修改远端配置/源码或重启进程。

## 已证实的故障链

- 服务日志 `/workspace/glm53-adaptation-runtime/graph/service.log`，1211112字节。
- 11:45:05：32 running +32 waiting，生成607.9 tokens/s，KV cache36.3%。
- 11:45:20：16个worker出现 `sparse_indexer_gather_cache`（vendor.thead）和
  `sparse_indexer_mqa_logits`（default.flagos）分派日志（6627–6658行）。
- 11:45:35：生成吞吐降至0，32 running +31 waiting，KV cache34.3%。
- 11:46:18起，每分钟报告shared-memory broadcast无可用结果，持续至11:50:16。
- 11:50:16：`TimeoutError: RPC call to sample_tokens timed out.`（6712行），
  EngineCore fatal，随后API返回500并于11:50:17结束，评测连接失败。
- installed vLLM `multiproc_executor.py:327` 使用
  `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS`；`envs.py:1593`默认300秒，与停顿时间吻合。
  这是worker执行/响应超时，不是客户端7200秒请求超时；RPC名字不证明采样算子本身出错。

## 缩小到的可疑路径（尚未独立复现）

错误时scheduler dump含新请求prompt长度2901，模型config中 `index_topk=2048`、
`index_kpool=4`、`index_head_dim=128`、`index_n_heads=32`。
插件 `kernels/glm5_next/sparse_attn_indexer_kpool.py:350` 判断prefill最大位置+1
是否<=2048；短输入跳过MQA logits，超过阈值则进入gather/cache、MQA logits和topk路径。
这解释了简单短输入sanity为什么不能覆盖这次触发的稀疏prefill分支。

插件 `dispatch/backends/flaggems/impl/sparse_indexer.py:94` 的MQA包装转发到
`flag_gems.fused.fp8_fp4_mqa_logits.fp8_fp4_mqa_logits`。名称带FP8不表示本次输入
是FP8；当前服务使用BF16。最后分派日志与停顿强相关，但不足以证明具体算子错误，
也不能区分首次编译耗时、设备kernel停滞、此前异步操作故障或后续通信等待。
尚未判定为FlagGems算子缺陷，因此未制作声称可复现的 `/bug` 包。

## 不支持的归因与边界

- 容器running、RestartCount=0、OOMKilled=false；cgroup oom/oom_kill均0。
- 11:44:00–11:50:16内核日志无事件；11:50:17后为退出清理事件，晚于RPC异常。
- `accelerator-check`成功；截取的前4卡为1MiB、0%利用率、不可纠正ECC=0。
  这是退出后快照，不证明故障时所有卡健康。
- 没有OOM证据，也没有证据证明“并发64过大”是根因。实际活动序列仍32，剩余排队。
- vLLM源码仍为 `ee0da84ab9e04ac7610e28580af62c365e898389`、worktree clean。
- 进程已退出，无故障现场worker栈，无法仅凭现有日志定责具体kernel。

## 后续建议（本次未执行）

对>2048 token prefill分支做独立、带时间上限的诊断复现，并在调用前后采集
worker栈、编译状态及设备状态，区分编译慢与执行停滞；确认具体FlagGems缺陷后
再按规则在工作根 `08-bugs/` 打包并通过容器对应路径原地执行；已有用例不再复制到 `/bug`。
不要先放宽RPC超时、降低并发或重跑全量来替代定位。
算子检查/集成前遵守FlagGems同步规则，保留故障版本证据。

复现只读查询：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/diagnose-ppu13-glm53-gpqa-crash.yml`；连通性、设备检查使用公共脚本。
诊断脚本初次搜索不存在的 `VLLM_RPC_TIMEOUT` 返回1，后纠正为实际变量；一次输出
register缩进错误导致Ansible记为changed，但执行内容仅只读命令，已修正并复跑：
ok=6、changed=0、failed=0。`./scripts/syntax-check`通过。未提交或推送。
