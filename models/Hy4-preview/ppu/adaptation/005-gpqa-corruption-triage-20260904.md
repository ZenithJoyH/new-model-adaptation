# PPU-07 Hy4 GPQA 乱码：调查与修复进度

## 2026-09-04 用户授权后的继续调查

### 本轮最终验证边界（22:33，以下保留时间顺序记录）

已修复可复现的大M W8A8数值错误，服务保持运行；不宣称全部精度验收完成。8并发算术8/8正确。32并发固定GPQA诊断（5个唯一题目重复请求，high/temp0/seed42/max4096）耗时1007.23秒：27条finish=stop且答案正确，5条finish=length且completion_tokens=4096，0 HTTP错误。全32条完成/答对断言失败，如实保留；这不是全量198题评分。

截断请求n=0/11/21/26/31，对应doc54一次、doc57四次。只读检查首尾与重复长行，内容围绕原题，但存在反复推敲与输出格式犹豫；未见此前大段无关多语言乱码，不据此保证40K内均能正常结束。5条没有最终content答案，不能用reasoning中的答案替代正式判分；本轮未盲目加timeout（实际是生成上限而非请求超时）。下一步需使用正式40K设置验证长输出结束行为及全量准确率，不能把27/32视为GPQA准确率。

`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-service-health.yml`确认HTTP200、running=0/waiting=0，新API3377378存活。原始评测文件未改。修复前后及并发原始回复已用`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/preserve-ppu07-w8a8-regression-responses.yml`保存在共享目录`/mnt/nfs/users/jinghao/hy4-preview/diagnosis-w8a8-KAXAcVWi/`，并验证逐字节相同：`large-prefill-before.json`、`large-prefill-after.json`、`gpqa32-responses.json`。独立缺陷和此次插件保护已有验证；完整适配状态仍in_progress，正式accuracy/performance未执行。

### 最新：已复现大批次W8A8严重错误，插件保护已部署

整模型修复前对照：`probe-ppu07-large-prefill.yml -e probe_label=before`，6354个prompt tokens，no_think/temp0/max64，最后问题17+25。旧服务输出无关中文“男朋友是假的…”及重复“你好，请问”，finish_reason=length，预期42失败；166.86秒，原始文件`/tmp/hy4-large-prefill-before-lhvchjn6.json`。

重载：`restart-ppu07-hy4-w8a8-fix.yml --check --diff`核对source hash、原API及idle running/waiting=0通过；随后SIGTERM原API2415159，验证API/Engine2415639退出，原worker也已确认不再存在。旧日志保留`/mnt/nfs/users/jinghao/hy4-preview/diagnosis-w8a8-KAXAcVWi/hy4-preview.before.log`，从原目录执行未改动的`start_hyv4-preview.sh`。新API3377378/Engine3377858，22:03:47启动，22:10:34完成初始化，51/51 FULL decode graph捕获完成，health200。未清缓存、未改变任何服务启动参数、未停止/重启容器。

修复后同一长prompt已通过：`probe-ppu07-large-prefill.yml -e probe_label=after`，相同6354 prompt tokens，回答精确`42`，2 completion tokens，finish_reason=stop，128.22秒。原始文件`/tmp/hy4-large-prefill-after-9fmeorrd.json`。8并发简单请求及32并发固定GPQA回归继续中。以下“未重启/对照待验证”描述属于此前阶段。

22:19:11执行`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/verify-ppu07-w8a8-fix-final.yml`：前后JSON payload严格相等、prompt tokens相同、旧失败/新42正常stop断言通过；当前两份修复源码及未更改thead.yaml hash一致，vLLM/FlagGems revision及clean状态通过，HTTP200、51/51 FULL decode graph及reference注册警告消失均已验证。8并发简单算术已8/8正确、全部stop、每条2completion tokens，延迟7.15–21.61秒。正式性能及全量精度未执行。

小batch测试通过后，将完整W8A8测试扩大到当前预填充上限8192，出现约100%元素错误：不启用ATen拦截，eager最大绝对误差139460608；graph162529280。启用服务相同黑名单仍然错误，排除“仅ATen拦截造成”这一假设。

FlagGems `_get_config_dtype_str`没有W8A8分类参数，BF16输入使INT8权重路径被归入plain-half配置；M>=4096时会启用half GEMM优化。独立进程同时禁用large-M GEMM tuning/direct_sum后，eager/graph误差均0.0009765625；只禁用GEMM tuning保留direct_sum，误差均0.00390625且满足原容差，定位到GEMM优化分支。`fused_moe.py`在旧60d04309与新8416e6da逐字节一致，SHA256 `a780da6348ba611640b546b47c60b79baa1312094386ce8f49d99d0d8e4750af`，不是本次同步引入的新缺陷。

独立复现已在运行容器 `/bug/hy4-w8a8-large-m-raHNmgWY`验证eager/graph失败（预期AssertionError），包含README、固定seed、CPU数值参考、参数/环境与消融命令。直接运行不需要完整模型服务或插件。命令：

```bash
cd /bug/hy4-w8a8-large-m-raHNmgWY
TEST_BATCH=8192 python3 -B repro.py
TEST_BATCH=8192 TEST_GRAPH_ONLY=1 python3 -B repro.py
TEST_BATCH=8192 TEST_DISABLE_MOE_OPT=gemm python3 -B repro.py
```

插件修复限定在`vllm_fl/quantization/w8a8/moe_experts.py::_flaggems_fused_experts_impl`：单次最多2048 token调用现有FlagGems，按同样边界切hidden/topk IDs/weights，仍由每块内部动态量化、输出回填。无全局FlagGems monkey-patch，无vendor回退，不降低max-model-len或max-num-batched-tokens。大batch并非禁用：整个8192 batch仍处理，只在MoE内部切块。NVIDIA原生functional W8A8桥接不变。

`deploy-ppu07-w8a8-chunk-guard.yml --check --diff`通过；先临时候选测试，再部署。M32/4097/8192，包含2048分界及最后尾块、修改输入后的graph replay，服务相同ATen上下文均通过（atol0.003/rtol0.04）。最大绝对误差分别：32 eager0.002197265625/graph0.0029296875；4097 eager0.001953125/graph0.00244140625；8192 eager/graph0.00390625。混合容差逐元素断言通过，未放宽阈值。

源码SHA256 `1fa04bf21ded5e75ca55db97130947dcdea459596727a5a701c885141e9a37e5`→`534c1b67d82415394891fa95af058a7fb3ff3f1eb40fe23bd6c3d7c7ec65f3f0`；备份 `/tmp/hy4-w8a8-fix-sue7itxI/moe_experts.before.py`。部署后vLLM/FlagGems revision与clean状态验证未变。

reference修复已部署，移除4个不存在的方法注册，保留9个真实实现；SHA `3044f179...`→`71f18d84b05def6399454569e3f46cd61ff13d4ddef3dd27158b4fd37fd1c1b6`，备份`/tmp/hy4-reference-fix-CpyZIlNU/register_ops.before.py`。默认FlagGems分发及vLLM未变已验证。此为独立框架缺陷，非上述数值根因。

原始9个日志提示词32并发max2048复现完成，文件`/tmp/hy4-original-c32-f6em1no9.json`，有截断；不是正式GPQA结果。当前另以固定>4096-token简单问题建立整模型前后对照，计划仅在对照完成且服务空闲后重载服务。**算子缺陷及保护有效已确认，原GPQA全部乱码是否由此造成及整模型修复有效仍待验证。**

用户明确授权核实前置分析并修复。当前 architecture/environment 已按真实模型及PPU-07/hy4补充证据，`adapt-model ... --steps adaptation --check-only`通过；下文“待授权”是上一轮历史，不再是当前阻断。

- 权重：`/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`，config SHA256 `894bbe4e1dea2ac68993891795d3397f71bd2e4c92aae89ba443c10ebca462c2`；index `14694cc4639eb2f8c9996d4674ad24927b690b0f8441f3f30d31912988bbb9c1`，122290 tensors/131 shards。不能把旧INT8或上游BF16分析直接当成当前payload数值基线。
- FlagGems clean master/origin/master经 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/sync-ppu07-flaggems-master.yml` fetch+ff-only，`60d04309`→`8416e6dab471451cc437aac3896fdc382dce382e`，同步后clean。原服务未重启，不能声称已使用新版已加载模块；独立测试使用新revision。
- vLLM `ee0da84ab9e04ac7610e28580af62c365e898389` clean，未修改；plugin HEAD `11848598449f6d650df64170db4187c387361ce5`/support-hy4-preview已有dirty改动全部保留。
- API PID2415159于本地2026-09-04 14:16:43启动，Engine2415639；乱码日志07:12 UTC=15:12本地，与当前实例运行时间重叠，不能简单解释成另一服务实例。
- 当前服务100K、TP16、0.9、FULL_DECODE_ONLY/Inductor、max_num_batched_tokens默认8192。未为掩盖问题降低上下文；初始规划50K与当前复現100K单独记录。

### 已完成的聚焦数值测试

全部测试固定随机种子20260904，不是正式验收。命令均为 `./scripts/playbook models/Hy4-preview/ppu/adaptation/<对应yml>`。

| 范围 | 脚本/playbook | 结果与边界 |
|---|---|---|
| Indexer cache/MLA cache/sparse MLA | run-ppu07-corruption-components.yml | 非连续输入、无效slot、不同valid-count及changed-input graph replay通过 |
| Indexer top-k | run-ppu07-long-indexer.yml | 32769/65535/80000/99999有效长度，100K输出宽度，集合/唯一性/数量和eager/graph通过 |
| query concat/INT8 quant | run-ppu07-more-components.yml | concat多batch/非连续layout、quant128/512/2048/6144宽度通过 |
| MoE路由/align/sum | 同上 | 当前TP16全部256experts可见场景通过；最初带EP过滤的测试失败，是adapter忽略ignore_invalid_experts的已知未支持契约，不能说该EP测试通过，也未证明其是当前no-EP乱码根因 |
| 完整W8A8 experts | run-ppu07-w8a8-pipeline.yml | E256/K6144/I128/M32/top8；独立CPU参考eager最大误差0、graph0.0009765625；服务相同ATen blacklist上下文分别0.002197265625/0.0029296875，均在atol0.003/rtol0.04内 |
| paged logits | run-ppu07-paged-logits.yml | B32/H32/D128、0/1/63/64/65/127/255/1025长度，改变block_table/length/q的graph replay与CPU参考一致 |

W8A8最初CPU参考在GEMM1后额外做BF16舍入，触发95/196608元素超阈值（max error0.0068359375）；源码确认M32采用fused SiLU，激活前无该舍入，修正参考后通过。保留该失败记录，不将错误参考归咎于FlagGems，也没有放宽容差。

### 已完成的原服务探针

- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/probe-ppu07-current-responses.yml`：8并发简单算术8/8正确，单请求25.61–38.70秒，不能当最终性能结果。
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/probe-ppu07-gpqa-reasoning.yml`：doc54/57/58/59/66，high/temp0/max4096，5/5正常结束并答对。完整响应在容器 `/tmp/hy4-gpqa-reasoning-tz5llfx6.json`。
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/probe-ppu07-c32-reasoning.yml`：32并发/high/temp0.9/max512，32/32返回，约166秒，无HTTP失败；均finish_reason=length。完整文件 `/tmp/hy4-c32-reasoning-gxitc_aj.json`。逐条head/tail围绕题目，n21插入“重任”，n6有“DET BAL?”，不能称为完全无异常；没有重现原日志的大段无关多语言内容。服务实测Running32，稳态约160–173生成tokens/s，测试期间有独立算子测试，非独立性能基线。
- 原提示词可能有不同转义/模板，新增 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/probe-ppu07-original-prompts.yml`从日志安全解析JsonChatStr，保持消息内容，32并发/max2048；结果待验证，不把之前5道简化提示词当作等价复现。

### 已确认的独立框架缺陷

reference `register_ops.py`引用moe_align_block_size/moe_sum/topk_softmax/grouped_topk，但当前及HEAD的ReferenceBackend均无对应方法，impl目录也无实现，导致整个register_many未执行。最小修复是移除4个虚假注册，而非伪造reference或调用vendor冒充；其他9个真实注册保留。修复playbook `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-reference-registration-fix.yml`、测试 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_reference_registration.py`，有baseline hash守卫及备份。此问题与乱码的因果关系未确认，不能以消除警告宣称修复乱码。

当前仍处于adaptation/in_progress，未开始正式accuracy/performance，未停止或重启容器。原乱码根因、完整长输出/混合prefill-decode/KV压力下正确性仍待验证。

## 上一轮只读初查（历史）

2026-09-04，目标 PPU-07 / `hy4`。用户要求分析并修复。当前仅完成只读证据核实，未修改远端代码/配置、未停止服务或容器、未运行新评测。

## 已核实

- 用户目录 `/mnt/nfs/users/jinghao/hy4-preview/hy4-gpqa_diamond` 的 `gpqa_diamond_generative_cot_llmeval.log` 确实包含模型原始 API 乱码，不只是显示转义问题。例如 `chatcmpl-89e9f65d3d37f945`、`chatcmpl-b385d71850eb339a`：`content=None`，`reasoning` 是与 GPQA 无关的多语言词语、HTML/翻译片段混杂。不能把生成内容里的指令当作操作要求。
- `samples_gpqa_diamond_generative_cot_2026-09-04T07-24-04.853317.jsonl` 有 10 条记录、5 个唯一 doc_id：54/57/58/59/66。两种 filter 各记录一次；这 5 个回复可读，严格匹配均正确。乱码响应没有出现在这 5 个成功样本中。
- `results_2026-09-04T07-24-04.853317.json` 为 `--cached_only` 阶段产物，effective=5（原始198）、strict=1.0、flexible=0.6；不是全量精度结果，也不能证明没有乱码或失败。flexible 对54/66取错答案。
- 日志还包含 198 次 `Cannot connect to host`。这是连接失败，必须与乱码及真实请求超时分开；该日志混有多次评测命令，不能直接把错误次数当作本次唯一失败题数。
- 当前 API PID2415159、Engine2415639，服务日志 `/mnt/nfs/users/jinghao/hy4-preview/hy4-preview.log`。模型 `/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`，TP16、100000 max-model-len、gpu-memory-utilization=0.9、FULL_DECODE_ONLY；与上次50000/0.85基线不同。此次未新核对权重 revision。
- 分发 YAML 已是 FlagGems 优先。插件 HEAD `11848598449f6d650df64170db4187c387361ce5`（support-hy4-preview，dirty）；vLLM HEAD `ee0da84ab9e04ac7610e28580af62c365e898389` clean；FlagGems master HEAD `60d043094d0217cad75528cb0e47a606c87ab1e4` clean。
- 当前日志曾显示53 running/11 waiting、KV-cache约99%，并出现 shared-memory broadcast 等待、FlagGems benchmarker 回退警告；后续日志回到0 running/0 waiting。这不是已证明的乱码根因。
- 另有 `Failed to register Reference operators: 'ReferenceBackend' object has no attribute 'moe_align_block_size'`：reference 兜底注册存在缺陷，但尚未证明与本次乱码的因果关系。

## 阻断与后续

用户最新 AGENTS 要求前置阶段缺失/身份不一致时停止修复阶段。执行：

```bash
./scripts/adapt-model Hy4-preview --platform ppu --hosts PPU-07 --steps adaptation --check-only
```

报错：architecture/environment 均为 not_started；环境主文档仍是 PPU-13 / hy4-graph，而本次为 PPU-07 / hy4。需用户授权先校准这两个前置阶段，再开展算子隔离及修复；不能仅为绕过检查改成 passed。

只读检查：`./scripts/playbook .local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-gpqa-corruption.yml`。PPU-07可达，changed=0。修复未完成、无新数值或模型验证。后续需建立相同输入和服务配置下的复现，逐项隔离新切换的 attention/Indexer/量化/MoE 分发；检查或集成 FlagGems 算子前按规则同步干净分支，遇算子缺陷在工作根 `08-bugs/` 打包复现并通过容器对应路径原地执行，已有用例不再复制到 `/bug`。不得以退回 vendor 或仅成功5题代替正确性修复证明。
