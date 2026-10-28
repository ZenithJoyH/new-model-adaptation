# 005：混合模型前缀缓存显式开启与align模式


读取首轮引擎完整配置确认 `enable_prefix_caching=False`；之前“保留默认开启”的假设不成立。
vLLM对当前模型的默认值关闭缓存，CacheConfig默认True不能代替最终引擎值。
模型源码明确拒绝mamba cache_mode=all、支持align。因此在clone重试尚处初始化阶段时，
按owner.json核对PID97193/start_ticks1107743078/命令SHA与PGID，记录组成员后仅向本任务组
发送SIGTERM，确认退出和GPU释放后启用新配置 `eager-prefix-align-20261023.json`：
显式追加`--enable-prefix-caching --mamba-cache-mode align`。保持50000上下文，不将前两轮作为
符合前缀缓存要求的推理证据；它们均未执行成功的模型请求。新run独立保留，后续核验最终生效值。

上述停止第一次等待25秒未完成，命令按守卫失败，未创建/启动prefix-align配置。
复核发现GPU worker已全部退出、GPU为空，但API97193仍poll，子engine为僵尸。
再次核对同一owner身份后，仅对该API发送SIGKILL；resource_tracker保留自行清理，不杀容器。
停止记录分别为旧run的stop-prefix-config.json与stop-stuck-api.json。

新实例PID116900，run `model-eager-prefix-align-20261023`；配置SHA256
`cc7f33c088738531861174d3c1f5737d9a8e6ca924833f21b7f4ff8d476bd25c`。
引擎启动日志已确认 `enable_prefix_caching=True`、enforce_eager=True、max_seq_len50000。
尚在warmup，不把配置生效当作推理或缓存正确性通过。后续需验证长公共前缀复用、
cache清理后的输出一致性及选定graph模式；原生环境绑定需覆盖新增运行语义。

## 首次真实复用验证边界

新实例eager已通过3条短请求。第一组前缀探针输入1370 tokens，5条答案全对，
重复相同问题token和logprob完全一致（delta0），但原生prefix_cache_hits_total仍为0。
起初推测公共对齐为1600，但此推测被后续2930-token探针证伪；不能将ratio4直接当作块膨胀倍数。
因此此组只证明长输入输出稳定，不作为prefix状态复制通过。
保留 `04-runs/model-eager-mamba-fixed-20261024/prefix-state.json`，
新探针 `02-issues/prefix-state-v2-probe.py` 用500条背景项、每条命中请求等待原生指标刷新，
命中delta必须大于0；新输出 `prefix-state-v2.json`，尚未判定。

2930-token第二组探针冷/重复请求输出均为56，但重复请求原生命中delta0，脚本因此明确失败
（rc2，`prefix-state-v2.json`），不是数值失败。已读vLLM `unify_kv_cache_spec_page_size`、
`resolve_kv_cache_block_sizes`、MambaManager和scheduler的align切分公式。原生页统一先按
最大物理页/当前页的整数比例增大block_size；text-only原始索引页102400B→409600B
将block400放大至1600，压缩页25600B→409600B则放大至6400，普通KV/GDN/PLE仍400。
公共scheduler对齐因此6400，hash粒度GCD400。先前记录的1600/hash推断撤销。
1370/2930两组输入均不足6400公共块；原4096预算会让普通中间chunk结束于4000而非6400。
不能据此声称4096预算下所有输入都无法命中（最后一段也可能恰好结束于6400）。
拟单独调整现有配置为6400，确保长输入第一chunk在公共边界保存状态，
保持其它开关不变，在>6400-token输入上验证真实命中。此为配置修正，不更改vLLM或新增
QSA缓存实现。通过已安装模型静态shape/dtype方法和原生unifier生成独立几何记录，
路径 `04-runs/heterogeneous-mamba-copy/cache-geometry.json`（按观测block400还原，不是worker内存快照）。

## 已验证真实命中

`model-eager-cache6400-20261024` 的8730-token探针5条全部通过：cold/hit/changed/isolated/hit-again，
原生命中增量分别0/6400/6400/0/6400；改尾部输出5，其余输出56。相同问题token完全相同，
logprob最大绝对差0。原生 `04-runs/model-eager-cache6400-20261024/prefix-state.json`
及server.log留存，证明GDN/PLE异构copy工厂在真实prefix命中下工作，而非只通过buffer单测。
单独开启FGV运行时接入将启动新实例，其结果另记007。
