# 011：MetaX Flash Attention GQA decode Split-KV

2026-09-24；状态：本Host算子级优化已验证并保留；模型端到端与正式验收未执行。

## 范围与身份

用户最新指令取消010的GDN优化，只优化Flash Attention。允许修改已验证editable的 `/workspace/FlagGems-vllm` 内FA源码和维护性测试；Plugin、GDN、vLLM、FlagGems、启动脚本及现有服务均不改。属于本次用户授权的组件例外，不改变全局profile、不宣称正式验收。Host `mx-58`，容器 `qwen3.6-27B`，host/container root均 `/public-flash/jinghao/qwen3.6-27B`，已验证 `/public-flash` 同路径RW映射。FGV HEAD `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777` clean；其它继承修改见010/009。GPU2独立算子实验，不停止GPU0/1、6/7服务；容器保持运行。

已读选定vllm-plugin-fl profile/workflow/acceptance、详细适配流程、贡献与证据规则，搜索troubleshooting及同模型记录。FGV AGENTS/workflow/README与FA API、MetaX scheduler/launcher/splitkv/common、现有测试/benchmark已读。其引用optimization.md/deep_opt.md未提供。PR base未确认，不提交/推送。

## 假设

两份既有profile的rank0主decode FA：原生splitkv+merge约455.209us，FGV direct约5600.514us，共16144次，旧/new使用不同GPU，只用于定位。当前Qwen TP2 qheads12/kvheads2、D256；service.log确认page size784。单query的GQA swap使scheduler看到max_q=6，超过split capable当前上限4；因此没有走既有Split-KV。先只扩展swapped GQA调度，不新增kernel或改变公共数值实现。prefill路径本轮先保持不变。是否有收益必须用同GPU基准证明。

## 编码前三表：项目真相

| 字段 | 冻结内容 |
| --- | --- |
| Current op | FGV `flash_attn_varlen_func`，MetaX `mha_varlan_fwd`→scheduler→Split-KV/direct；既有attention backend唯一入口 |
| Editable | MetaX FA scheduling及对应维护性tests；需要时既有splitkv，公共修改必须另有独立证据 |
| Baseline | 先测未修改HEAD；种子41，独立FP32 attention参考，不以torch参考耗时计算加速比 |
| Active benchmark | BF16 D256 Hq12/Hkv2，page784；B1/16/64，KV1024/4096/16384；加B64/K4096但maxK262144图上界；保护prefill及旧GQA4 |
| Metric | 相同GPU2，3次warmup、CUDA graph每10调用、7次event样本中位us；逐case报告，主case不得被平均掩盖 |
| Correctness | Output atol0.002 rtol0.02；LSE atol0.0001 rtol0.0001；独立FP32参考、返回out别名、非连续Q/out/page stride、ragged/空KV/边界、变输入graph replay |
| Tuning | 首轮只改swapped query可调度上限（≤16），既有BM4/BN16及split成本模型不变；非MetaX无改动，不新增NVIDIA调优路径 |
| Artifacts | `02-issues/fa-splitkv-20260924/`脚本，`04-runs/fa-splitkv-20260924/`证据，`06-cache/fa-splitkv-20260924/`缓存；单轮超时600s |

## 编码前三表：契约

| 字段 | 内容 |
| --- | --- |
| Inputs | 原有FP16/BF16接口不变；本轮新命中仅BF16 paged swapped单query GQA，D256自动split；真实strides和seqused_k为准 |
| Outputs | 原shape/dtype，out原对象，LSE FP32；FP32分块累积与merge已有实现；不改KV |
| Masks/features | 原causal/窗口/alibi/softcap/dropout资格检查保留；未支持组合保持旧路径/既有异常 |
| Graph | scheduler仅host元数据，不从GPU读长度；capture后的seq长度和内容变化正确；num_splits=1显式禁用保持 |
| Scope | 推理forward；不改变backward、非MetaX、GDN、缓存布局或框架图模式 |
| Production | 不增加torch compute/copy/cast或外部fallback；仅复用现有Triton kernel与empty工作区 |

## 编码前三表：路径

| 路径 | 选择 | 验证 |
| --- | --- | --- |
| Existing | GQA≤4、非swapped prefill、非BF16、features | 路由未变、代表性数值与性能回归 |
| New swapped | 合并后GQA5–16，其它条件保持，split成本模型获益且工作区≤32MiB | Hq12/Hkv2及5/8/16边界、显式split/auto、图重放 |
| Guard miss | >16、num_splits1、成本模型不获益、features等 | 不强制split，原路径保持 |
| Empty | 原有empty语义 | 测试零KV与padding，不扩大未验证能力 |

## 验证记录

010的基准参考实现shape错误并已退出，非FA证据，不修复或继续该GDN实验。

未修改产品源码时，初始baseline的11个GQA6/prefill case均通过参考与graph检查；末尾GQA4 auto保护case在已有BM4 Split-KV编译失败，报 `MACAMmaEncodingAttr::composeSharedLayoutForOperand` / `tn and tk not meet conditon`。完整失败保留 `04-runs/fa-splitkv-20260924/baseline.log`。不能把该失败当成优化收益，也不扩大范围去修其它旧路径。

在产品编辑前冻结bench-v2：只将最后的GQA4保护case改为显式num_splits=1（direct guard miss），其余输入、参考、计时完全不变；重新运行baseline-v2全部12个case通过。新命中的GQA5–16改用既有BM16/BN16配置以避开BM4编译限制；其余路径保持原配置。前表BM4第一轮假设据此更新为BM16，不新增kernel。维护性测试先在旧源码上复现路由失败，再应用调度改动。

第一候选：路由16 fail/10 pass复现后，50项新测试通过，但冻结benchmark的B1数值失败（max abs约0.253），没有性能交付。诊断：B1的GQA transpose可保持no-copy view，原split launcher把最终out的转置stride用于连续FP32 partial buffer；merge按连续layout读，故错位。根因修复：partial使用自身row/head/batch stride，退出准备阶段恢复原输出stride，merge仍写最终输出原layout。仅MetaX helper修改，公共API/kernel计算和GDN不改。

加入B1后74项参考/eager/变输入graph测试通过。BM16/BN16候选冻结12case全部通过，B64/K4096=4437.171→921.651us（4.814x），B64/K16384=17655.527→3417.088us（5.167x）；prefill控制781.926→784.794us。证据stride-tests.log、stride-candidate.json。baseline-v2与candidate的脚本SHA均 `e084962b8239dc25bf970c9bda201d04aaad10f94a8a77a2b85f5159e99c26e7`。

第二轮受控候选：只在新D256/GQA5–16路径maxK≥4096时将BN16改为BN64（既有split成本模型随tile派生）；短KV及旧路径保持。新路径显式限定D256；其余head dimension不扩大支持。必须再次过相同74项测试与冻结基准；失败回退上述已验证版本。远端未安装black/isort/flake8，不安装依赖，格式工具检查暂缺，须如实报告。

## 最终结果与取舍

BN64在数值测试启动时即报OutOfResources：shared memory需73728B、C550上限65536B，未测速。后续BN32通过78项数值测试，但B64/K4096（maxK262144）达4978.329us，B64/K16384达21164.339us，明显回退；不保留。相关bn64-tests.log、bn32-tests.log、bn32.json保留，不隐藏失败。最终回到BM16/BN16，保留D256范围约束与partial stride根因修复，没有继续扩大调参范围。

最终源码回归 `final-tests.log`：78/78通过，覆盖GQA5/6/8/16、page16/32/784、B1/4、auto/explicit splits、非连续Q/out/KV/page table、空KV、输出保护区、变化输入的两次graph replay、范围与feature guard。现有测试另选4例验证FP16、BF16、ALiBi、softcap，`legacy-regression.log`：4/4通过。原生benchmark及既有FA测试collect共437项成功；不等同437项执行通过。新增维护性benchmark已收集，本次收益取自冻结独立A/B程序，不是原生benchmark或正式性能回执。

同GPU2 / BF16 / D256 / Hq12-Hkv2 / page784 / 单步Q，CUDA graph每10调用、7样本中位数；前后同一bench-v2 SHA。最终12case数值、LSE、graph检查全部通过，结果如下（单位us）。

| Batch | KV长度 | 修改前FGV | 最终FGV | 加速比 |
| --- | --- | --- | --- | --- |
| 1 | 4096 | 1676.800 | 88.858 | 18.87x |
| 16 | 4096 | 1822.874 | 280.627 | 6.50x |
| 64 | 1024 | 1128.986 | 284.083 | 3.97x |
| 64 | 4096 | 4437.171 | 921.830 | 4.81x |
| 64 | 16384 | 17655.527 | 3415.270 | 5.17x |

B64/K4096且maxK262144：4434.176→921.907us（4.81x）。prefill保护例B1/Q128/K1024为781.926→780.851us；GQA4显式禁split保护为1819.136→1813.453us，无明显退化。首个已修复BN16候选与最终复跑主B64/K4096分别921.651、921.830us，收益稳定。这是相对修改前FGV的算子级收益，不代表相对MetaX原生FA的加速或模型端到端吞吐。prefill热点尚未优化。

远端结果均在 `/public-flash/jinghao/qwen3.6-27B/04-runs/fa-splitkv-20260924/`：baseline-v2.json、stride-candidate.json、final.json、final-review.json及上述日志。执行入口为同Host/container root下 `02-issues/fa-splitkv-20260924/bench-v2.py`，参数 `final <04-runs/.../final.json>`，已存在结果拒绝覆盖。使用 `/opt/conda/bin/python3 -B`、CUDA_VISIBLE_DEVICES=2、FLAGGEMS_VENDOR=metax、PYTHONDONTWRITEBYTECODE=1，TMPDIR在05-tmp，XDG/TRITON cache在06-cache/fa-splitkv-20260924。没有服务性能测试，未改变任何服务prefix-cache或graph设置。

## 最终设计审查与影响面

2026-09-24审查actual diff：FGV基于HEAD `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777`，仅2 tracked源码修改+2 untracked维护性文件；没有新增/重复FA dispatch，不改export接口、公共FA计算、GDN或vLLM。无torch compute/copy/cast fallback新增，仅在既有MetaX分发层选择已有Triton kernel并修复empty临时缓冲区的元信息。未提交/推送，PR base仍未确认。

| 文件（FGV根下） | 最终SHA256 |
| --- | --- |
| src/flaggems_vllm/runtime/backend/_metax/ops/flash_attention/scheduling.py | 4802a4dfe3fe60bf0c4bbe592c147a2b414adb8565522cd4fb81314a8965963a |
| src/flaggems_vllm/runtime/backend/_metax/ops/flash_attention/splitkv.py | 489d526b7c58597c0d31e60fd8570d42826c2bbc9401c86ec6ca6c78bdc791e2 |
| tests/test_metax_flash_attention_scheduler.py | f55e64b2664ab255f13f598da03aded81d281f723371b1798c436624f94a608f |
| benchmark/test_flash_attn_varlen_gqa_decode.py | 35ad9941d306074fc0ebfa6272531a2e3e683c83f4fa10e0e295c0710dc2b126 |

FGV tracked diff SHA `e78a14bdb426f8a3f7599188682132e5ceda91d6b70e980187e2abb47dcd28e8`。Plugin仍7 tracked+4 untracked，最终tracked diff SHA `b54a2c62756f951cf92847e6e587adc48a02712a4073fb7022eb2590bf329087`；本轮未写入Plugin，不能用009旧身份替代当前身份。vLLM继承fused_recurrent.py修改及SHA `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`；FlagGems clean。详细四组件HEAD/status在final-review.json。

影响：MetaX BF16 paged D256 swapped GQA5–16新增Split-KV资格；成本模型与32MiB工作区上限继续决定是否启用。旧GQA≤4、非swapped prefill、其它head dimension、FP16、optional features、num_splits=1及非MetaX不扩大路由；只有partial stride修复影响已有MetaX split输出布局，恢复最终out stride后merge写回。其他模型/硬件未实测。旧GQA4/BM4在当前编译器的失败仍是已知未处理限制，不宣称全套FA支持或正式optimized。

AST与git diff --check通过；black/isort/flake8不可用，未安装。回退了失败/回退候选；自动patch生成的调度备份经SHA核对后移动至02-issues/.../scheduling-original.py，源码树未保留过程备份。局部数值与性能验证充分支持本改动，但全模型回归与端到端profile仍是后续工作，当前运行服务不会自动加载Python改动。

只读收尾核实：容器running；8001 health=200，8000在该容器localhost连接拒绝，未修复或重启它；本轮未停止任何模型服务/容器。mx-smi查询成功，GPU2/3在实验间隙均859MiB/0% util。不能把009的旧服务PID或health当当前证明。仓库audit返回1 error/78 review，error属于其它模型DeepSeek-V4-Flash的profile revision，未擅自修改；Qwen3.6-27B本次未新增布局问题。
