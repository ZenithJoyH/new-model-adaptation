# 014：mx-59 补齐 MetaX 连续 KV 单请求 prefill 优化

## 范围与现场身份

- 日期：2026-10-09；模型 Qwen3.6-27B / MetaX C550 / vllm-plugin-fl。仅实施用户选择的局部适配，不执行正式验收。
- 修改目标：`mx-59` 的 `qwen3.6-27B`，容器 ID `1f62bdcb818d7119ed6595133dc64c3f14c194ae565c95dba18ef89bbd4fe657`，镜像标签 `flagos/qwen3.6-27b-metax:public-flash-20261008`。
- 批准工作根：Host/container 均为 `/public-flash/jinghao/qwen3.6-27B`；现场确认完整 `/public-flash` 同路径读写 bind，另有只读权重别名 `/models/Qwen3.6-27B`。`/workspace`、`/opt/conda` 不在挂载中。
- 实际安装的 Plugin 为 editable `/workspace/vllm-plugin-FL`，import 为该树的 `vllm_fl/__init__.py`，HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`。继承7个 tracked 修改、GDN patch/state-layout 及相关测试，不覆盖它们。
- vLLM HEAD `bc150f50299199599673614f80d12a196f377655`，继承 `fla/ops/fused_recurrent.py` 修改，本轮只读。前后完整 vLLM diff SHA256 均为 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`，并经 `cmp` 一致。
- 现场 FlagGems HEAD `c778fea4ab7825e5461d44fd5131eab2d3df9811`，FlagGems-vllm HEAD `4ea1b95b80efa2012fc5d82365f38a03ed691f09`。它们已不同于012镜像初始身份；本轮不更新、不选型、不修改这两个组件，保留 FGV 已有 untracked 基准与测试。
- 对照仅只读访问同机 `qwen3.6-27B-base`，其 Plugin HEAD `d1653d9ff0450ce0366686bfcde5d8aecab44755`，已有 vendor FA prefill 补丁。

## 现象、假设与经验匹配

用户指定的历史 CSV 中，共同的4K/16K/64K输入、1024输出、并发64、128请求场景，目标输出吞吐比 base 分别低37.4%/40.9%/44.1%。长输入的 TTFT 与长尾 ITL 明显恶化；不能把端到端指标直接当作 kernel 耗时，也不能据此量化单项优化贡献。

已确认 base 有 `VLLM020_CONTIGUOUS_SINGLE_PREFILL=1` 对应实现，目标缺失该分支。两组显存预算、其他算子名单、测量日期亦不一致；历史 base 服务日志已被覆盖，因此“此分支解释全部性能 gap”仍为假设。

检索 `docs/troubleshooting/` 和 MetaX 模型问题记录未找到此开关的现成条目；复用 base 的现场实现，不扩展成公共调度或新算子分发。008的旧编译缓存问题是后续模型重启时需注意的独立风险，本轮没有重启服务或复用模型图做验证。

## 修改、所有权与接口

仅修改已安装 Plugin 的 `vllm_fl/dispatch/backends/vendor/metax/impl/attention/flash_attn.py`，并新增可维护测试 `tests/functional_tests/ops/test_metax_contiguous_prefill.py`。

- 默认关闭；开关按 `strip().lower()` 接受 `1/true/yes/on`。
- 仅在一个 prefill、非 FP8、现有非 cascade / DCP world size 1 分支内，按 block table 收集分页 KV 并裁掉末页 padding，以连续 K/V 调用 vendor `flash_attn_varlen_func`，不传 `block_table`。
- 开关未开启或多个 prefill 时保留原分页调用；混合批次的 decode 部分、纯 decode、KV 写入、输出 buffer、scale/window/alibi/softcap/sinks 参数不变。
- 不改 `attention_backend` dispatch、FlagOS attention、GDN 注册/调用或 vLLM；这是已有 MetaX backend 内的 layout 特化，不增加重复分发。
- 迁移后整个 `flash_attn.py` 与 base 文件 SHA256 一致：`9a1e87cb97b9ec3283351e3e75d8a25f81c9800fc140661e094eb0da7c2c2bae`；修改前为 `f81fa552667b3ed98d1cf141d2dee33ba10476cda9a997744495bdbc36289ef2`。
- 新测试 SHA256 `1263bbb8f21de1b0a7b39d404a69f995a4f1bd6a5528514535e0a8ab53f014e4`，本轮 attention diff SHA256 `565e67bac78b6097c50158834a99d236950c1cabfd510949bc14a57d53f1b1b7`。

## 受控验证与失败保留

原生证据根：`/public-flash/jinghao/qwen3.6-27B/04-runs/metax-contiguous-prefill-mx59-20261009/`。修改前单文件备份在同工作根 `02-issues/metax-contiguous-prefill-mx59-20261009/flash_attn.before.py`；这是回滚备份，不是第二份 checkout。

1. 初次通用 Ansible 调用受本地沙箱 RPC 限制失败，尚未远程执行；经审批使用原 `./scripts/ansible` 入口后成功。最终取证首次因 Docker Go-template 被 Ansible 当作 Jinja 解析失败，改用 JSON 只提取容器 ID/运行状态后通过；未修改权限规则。
2. `baseline.log`：测试框架的 functional `pytest_sessionfinish` 调用 `os._exit`，截断失败详情。后续以 `--confcutdir=tests/functional_tests/ops` 隔离退出钩子，测试本地提供 device fixture，不替换真实 kernel。
3. `baseline-isolated.log`：测试夹具的16-token页仅提供两页、却要求33 tokens，参考计算维度失败；修正为足够的非单调页索引，未改数值容差。中间测试备份移到上述 `02-issues/`，不留 `.orig` 在产品树。
4. `baseline-valid.log`：原分页 SDK 在784页上报 `Paged KV cache block size must be a power of 2!`，两项16页数值测试已通过。后续将原分页能力测试限制在16/32页，784页单独覆盖新增连续 KV 分支；不修改旧路径能力或伪称分页784通过。
5. `baseline-optin.log`：有效16页单请求用例、开关为1，旧实现真实调用参数仍为4维 K 加 block table，而预期是3维连续 K；该负对照在产品变更前失败。
6. 应用唯一产品变更后，`regression.log`：**23 passed in 30.22s**。BF16/FP16、GQA12/2、D256、strided Q、非单调页、partial final page；开关未设/关闭/开启/带空白大小写、多 prefill 回原路径、混合 decode、784页连续 KV 均与浮点参考对照。调用观察器原样委托真实 vendor FA，不 mock 计算。
7. 纯 decode 使用真实 `FlashAttentionImpl.forward`，完成 eager、CUDA graph capture、两次改变 Q/K/V 的 replay 数值检查；prefill 保持原来 PIECEWISE 图外执行，不宣称新增 FULL prefill 图支持。

回归运行于当时唯一空闲的物理 GPU0，`CUDA_VISIBLE_DEVICES=0`，使用 `/opt/conda/bin/python3 -B -m pytest`，无 `PYTHONPATH`。pytest/temp/VLLM/Triton/Inductor cache 留在本工作根 `05-tmp/`、`06-cache/`；最终回归另隔离 Torch extension cache。早期基线继承了默认 Torch extension cache，未清理它。主要命令参数为：

```text
tests/functional_tests/ops/test_metax_contiguous_prefill.py -q
--confcutdir=tests/functional_tests/ops --maxfail=3
-o cache_dir=<工作根>/06-cache/metax-contiguous-prefill-mx59-20261009/pytest
--basetemp=<工作根>/05-tmp/metax-contiguous-prefill-mx59-20261009/pytest-regression
```

`target-source.json`、`base-source.json` 证明源文件及 forward AST 一致；`import-isolation.json` 证明隐藏 GPU 时 Plugin 顶层导入成功且未 eager 导入 MetaX attention（FlagGems 有无设备告警，未隐藏）。`container-after.json` 确认容器 running/unpaused；原服务 PID4098895/30990 保持不变，未停止任何服务或容器。

## 使用、设计审查与限制

- 下次启动对应 vendor attention 服务前设置 `VLLM020_CONTIGUOUS_SINGLE_PREFILL=1`。当前共享启动脚本未修改，现有进程没有热更新；未替换 `VLLM_CACHE_ROOT`、图模式、黑名单或显存预算。
- 测试覆盖 MetaX 本地 adapter；非 MetaX 无真实硬件验证，未对其他模型执行端到端验证。FP8 本来不受该 vendor backend 支持，未执行 FP8 数值测试。
- 限定设计审查：职责与原 dispatch 一致、标准库开关无新增厂商依赖、guard miss 保留原行为、不吞异常；可作为局部补丁候选。PR base branch 未确认，不提交、不推送、不创建 PR。
- 状态：**实现及限定算子回归已验证，性能改善待验证**。未做全模型启动、TP2集成、正式精度/性能或重新打包镜像；不更新 `framework.yml` 的验收状态，不标记整体适配完成。
- 本地 `./scripts/audit-workspace` 返回1：既有12个 profile revision 错误、78项历史材料待复核，包含本模型旧 profile 绑定；本轮不刷新旧证据或修复无关记录，不能表述为整体审计通过。
- 下一步在独立服务/缓存下保持同条件测量该开关贡献，再分别对齐显存预算及其他 FlagOS 算子；需用户选择对应运行范围后执行。
- 知识库处理状态：`local-only`。
