# 016：mx-59 sortopt 剩余差距与紧凑排序索引

## 范围与前置身份

2026-10-10，继续用户请求的 mx-59 / Qwen3.6-27B / vllm-plugin-fl 阶段3吞吐优化；不是正式验收，不扩展其它主机。容器 `qwen3.6-27B` ID `1f62bdcb818d7119ed6595133dc64c3f14c194ae565c95dba18ef89bbd4fe657` 保持运行。核实完整 `/public-flash` 同路径RW挂载、`/models/Qwen3.6-27B` 权重别名RO；批准工作根 `/public-flash/jinghao/qwen3.6-27B`。

实际Python `/opt/conda/bin/python3`，editable FlagGems `/workspace/FlagGems` HEAD `7599dd130046f84df099aa771e91d35d5991e69a`、Plugin `/workspace/vllm-plugin-FL`，vLLM `/workspace/vllm` 只读。实际导入分别指向上述安装树；元数据FG `5.4.0.dev588+gaf5291a06`、Plugin0.2.0、vLLM0.20.2+empty，元数据不替代源码身份。FG继承015的sort改动/测试；Plugin继承原attention/GDN/worker和015的ready-PID改动，不覆盖。vLLM完整diff SHA256仍为 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`。

上游核查 `git ls-remote origin refs/heads/master` 报HTTP2 framing错误；改为HTTP1.1加timeout45仍超时。用户明确同意本轮固定现有7599dd13，不同步、不丢弃本地优化。不宣称此次上游核查成功。

工作产物统一使用各批准目录下的 `throughput2-mx59-20261010`；不会复制源码树或使用PYTHONPATH。维护native runner第一次remote_src复制报EIO，改为从本地项目已维护的同名runner部署，源代码不变，保留失败。

## 输入数据与假设

用户提供 `test/perf_test/benchmark_results/qwen36-27b-somegems-noatten-nogdn-prefillopt-nommout-sortopt/`。目前4K/16K历史CSV完整SUMMARY：总吞吐2732.91/3479.65 tok/s；对历史 `qwen36-27b-base` 的2955.72/3545.30分别仍低7.54%/1.85%。历史base日期2026-09-22，不是本轮受控基线，不用其差值证明补丁收益。

当前实际服务已被用户重启为alias末尾 `-sortopt`，Host API1582795/container231746，GPU6/7、TP2 BF16、显存0.9、batched tokens8192（015为16384）、FULL_AND_PIECEWISE/max capture64、262144上下文预算。黑名单仍 `gdn_prefill,gdn_decode,index_select,mm,max,exponential_,attention_backend,mm_out`，连续单prefill开启，prefix cache显式关闭。实际进程未设置PYTHONPATH/FG/TRITON/INDUCTOR缓存覆盖；保持服务继承缓存以作同配置比较。独立诊断沿用015批准的06-cache。

检查到MetaX既有patch因原生Triton编译限制，将top-k/top-p过滤导向PyTorch排序路径；本轮不复制sampler、不改采样参数或其注册。4K剩余生成间隔71.44ms，对历史base66.23ms，排序仍是候选热点。Plugin检查表明已初始化路径、IO关闭路径和first-use诊断已有fast path，不为叠加改动未经测量调整策略/缓存/黑名单。

64K benchmark尚在运行、KV usage接近100%，没有完整SUMMARY。用户明确授权停止性能客户端1595882及子进程1629466；核验父子关系/cwd/模型/65536请求命令后仅发送SIGTERM，服务排队清空，容器未停止。已有4K/16K和残留64K文件均保留；64K不作为完成结果。

## 受控方案与验证

先以当前服务重新执行 `single-scenario` 4096输入/1024输出/并发64/128请求、runs3/skip-first1，先dry-run。Skill bundle SHA256 `3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff`；baseline在完成完整native校验前不应用产品补丁。

唯一产品候选：公共FG `src/flag_gems/ops/sort.py` 的radix中间索引从int64改int32；现有 `n < 2**30` 已限制合法长度，输出仍转回int64，稳定性、方向、排序key、输入不变性、返回协议及ATen入口不改。减少每一radix pass的索引载荷，而非近似排序、跳过top-p或改变随机采样。根据微基准最终仅在行数m≥8使用紧凑索引，小batch保留原int64及无额外复制路径。现有51项精确值/索引/strides/改变输入graph replay回归，加8项m=8、宽131073的FP32/FP64/int64/bool输入不变性及索引dtype契约，新增m=8新路径的两次变输入graph replay；不放宽容差。非MetaX硬件未测，不宣称通过。

前置安装sort SHA256 `be54de41003acd872334e0a095e7af7fc5361f2f4d261439e3053fd17f3ca3dd`，Plugin manager `59f5fa67d0d698206baa00d1486b59467e7895cb60a726a7414773f44f5ced50`。候选补丁通过 `git apply --check` 后已安装；无guard候选sort SHA256 `59a4002641dd9673e30e9b3518a22aff76b3aa878a1d4f7e7ecfac4bece79bfd`，59项回归91.61s通过。根据小batch测量加guard后SHA256 `e200fbf2287ebd4104e8e312fe0dab90e6a05326a8f56b25cccc604c7c46a199`，新增回归文件SHA256 `6264db09b5be334cf27cd141ddc812337128c320acbbe61ca7fc5eb4e2f4b202`；完整60项回归106.31s通过，日志 `04-runs/throughput2-mx59-20261010/sort-guard-regression.log`。仅增加既有 `benchmark/test_sort.py` 的(1/8/64,248320)场景；未运行整个默认benchmark套件，不宣称其通过。

定向公共sort微基准使用固定CPU生成数据、GPU6、同黑名单、batch1/8/64、词表248320、3预热/15次CUDA event中位数，同一模型空闲显存占有条件。无guard候选：B1 1.114624→1.149184ms（约3.1%退化），B8 2.689792→2.462208ms，B64 14.269952→12.672000ms（约11.2%下降）。因此小batch保留原路径，不能宣称所有batch都提速。证据 `04-runs/throughput2-mx59-20261010/{baseline,indices32}-operators.log`。

最终带guard版本在优化模型空闲且KV容量相同条件下复测，证据 `04-runs/throughput2-mx59-20261010/guarded-operators.log`：B1 1.112832ms（相对基线−0.16%，基本持平）、B8 2.456320ms（−8.68%）、B64 12.668416ms（−11.22%）；小batch不再承担额外输出cast。两次均保留模型显存占有、相同GPU/输入/缓存包装和计时方法，但服务进程经过重启；不以该微基准替代同配置native模型对照。

本轮基线原生报告 `04-runs/throughput2-mx59-20261010/baseline/qwen36-27b-somegems-noatten-nogdn-prefillopt-nommout-sortopt/20261010_132250_930021/benchmark-result.json`。三轮均128成功/0失败，计入均值的两轮2716.95/2718.06 tok/s，均值2717.51。应用前native完整性核验通过，保留baseline服务日志与身份；再次核对安装sort文件SHA256未变化才应用补丁。只向已核验的Host API1582795发送SIGTERM，其engine/worker全部退出后运行独立回归，以避免015观察到的首次stream创建等待。容器始终运行，源文件备份位于批准02-issues，不重写共享launcher。

## 端到端结果

优化服务沿用冻结参数重启，GPU6/7、TP2、黑名单和图模式均不变，不修改共享启动脚本。原生优化报告 `04-runs/throughput2-mx59-20261010/optimized/qwen36-27b-somegems-noatten-nogdn-prefillopt-nommout-sortopt/20261010_135258_227700/benchmark-result.json`，SHA256 `24ece8a8f10a03daeaf9764a3f8f31087b510c3f142fc00a123755f37f146247`；基线报告SHA256 `7b714e0649965ec640c7f50e973a931f5dcc557f9c3d78f8da32595bb6d962e0`。

优化三轮总吞吐2644.19/2758.16/2759.41 tok/s，首轮按预设不计入；基线三轮2712.38/2716.95/2718.06。所有六轮均128成功、0失败、524288输入token、131072输出token。两份native报告完整性、相同producer/request/逐轮命令均核验通过；KV容量都为888032，mixed PIECEWISE和decode FULL捕获均11/11。完整对照证据 `04-runs/throughput2-mx59-20261010/comparison-verification.json`，核验时间2026-10-10 14:07:49 +08。

| 指标（跳过首轮，后两轮均值） | 基线 | 优化 | 变化 |
| --- | ---: | ---: | ---: |
| 总吞吐 tok/s | 2717.51 | 2758.78 | +1.52% |
| 输出吞吐 tok/s | 543.50 | 551.75 | +1.52% |
| 测量耗时 s | 241.16 | 237.56 | −1.49% |
| 平均TTFT ms | 15002.92 | 14985.34 | −0.12% |
| 平均TPOT ms | 102.84 | 101.10 | −1.69% |
| 中位ITL ms | 72.10 | 70.38 | −2.39% |
| P99 ITL ms | 1508.92 | 1506.37 | −0.17% |

结论仅针对本轮固定7599dd13、当前8192批处理设置及4K/1K并发64；不将排序微基准收益等同模型收益，不拿旧base或015不同配置测量作为同配置对照。Plugin本轮只检查未改；公共sort的索引载荷优化贡献可测的约1.52%总吞吐提升。服务现为container API286148，日志 `04-runs/throughput2-mx59-20261010/optimized-service.log`。

最终核验通过：容器ID及running状态保持不变；实际module路径仍为上述安装树，FG HEAD固定、sort和测试SHA256匹配；FG `git diff --check`通过。Plugin manager SHA256及vLLM完整diff SHA256与基线相同。GPU/黑名单/8192/图模式/服务缓存环境保持冻结配置，没有PYTHONPATH。源码及进程身份见 `01-environment/throughput2-mx59-20261010/final-identity.json`。native测完运行/排队请求均0，独立微基准后服务健康HTTP200；模型服务保持运行。源码改动位于容器内部安装树，不依赖host源码挂载；本轮未保存新镜像。

正式精度、16K/64K重测、其它平台GPU、完整默认benchmark套件及镜像交付未选择或未完成；不更新framework正式状态。更新文档后 `audit-workspace` 仍为既有12个profile revision错误、78项待复核，非整体审计通过。未提交、推送或操作其它机器/服务。
