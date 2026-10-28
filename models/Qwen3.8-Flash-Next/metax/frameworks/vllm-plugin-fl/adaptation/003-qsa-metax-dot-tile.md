# 003：QSA MetaX MMA tile 编译约束

## 现象与基线

2026-10-23，mx-101 / qwen3.8-flash，实际安装 `/opt/FlagGems-vllm@c9003571`。
已包含PR959和问题002的3行fusion同步修复；本问题尚无产品改动。
组合回归 `04-runs/qwen-kernels-final/pytest.log`：291 passed、34 skipped、1 failed，428.87s。
首个失败 `test_qsa_split8_matches_single_with_invalid_pages_and_strides` 在single路径编译，
BF16 q[8,3,256]、非连续paged cache、topk513；并未执行到split数值对照。
34项跳过是当前vLLM没有Qwen4参考模块，保留原因，不作数值通过。

官方MetaX编译器报 `MACAMmaEncodingAttr::composeSharedLayoutForOperand`，
`shape_judge && "tn and tk not meet conditon"`；失败pass为ReduceDataDuplication。
实际IR的dot tile M8/N16。已读对应FlagTree源码Dialect.cpp:2665起：矩阵operand的M/K
必须达到并整除MMA thread shape；尚不能仅凭报错确定需提高M还是N。

## 改前项目真相与候选清单

| 字段 | 内容 |
| --- | --- |
| 算子/契约 | paged sparse GQA attention + optional sigmoid gate；BF16/FP16，FP32 softmax/accumulation，再按原边界round |
| 当前dispatch | MetaX目前加载generic入口；已有PPU薄wrapper通过私有入口min_block_m提高floor，不复制kernel |
| 拟修改 | 若受控对照证实M16足够，只新增MetaX薄wrapper、ops/__init__.py导出及既有QSA测试中的针对性回归 |
| 条件扩大 | 若N16也不兼容，再界定共享launch helper的MetaX条件；在证实前不改 |
| 只读 | vLLM、FlagTree、Plugin、通用kernel算法、原数值参考与容差、benchmark原文件 |
| Build | Python实际editable树直接生效；正常导入，不用PYTHONPATH |
| 验证 | 07-bugs/qsa-metax-dot-tile独立BF16数值和2次变输入graph replay；原QSA single/split、stride、invalid、graph测试；组合回归 |
| 性能 | 既有benchmark/test_qsa_attention.py；无正确旧实现则不编造修复前加速比，分别说明绝对结果及参考比 |
| 调优 | 这是合法tile约束修正，不新增调优参数；保留已有N/warps/stages及SM90调优，不扩展自动split选取 |
| 时间 | 受控probe每组180秒；功能600秒；长编译保留日志与失败，不自动当通过 |
| profiler | 本问题先用compiler IR、dispatch与launch元数据定位；尚未使用MetaX profiler |
| fallback | NO_TORCH_COMPUTE_FALLBACK；只复用已有Triton kernel，不另走Torch计算 |

## 语义及实现路径

输入q[rows,query_heads,D]、K/V[blocks,page,kv_heads,D]，独立strides；query_heads必须整除
kv_heads。indices/request/page非法值沿原mask处理，空输入沿原早返，output/workspace alias
和检查保持原协议。数值/rounding/gate保持原实现；修改只在厂商入口选择合法tile。
forward-only，无新增autograd、dtype、量化或平台能力承诺。Torch只用于测试参考。

| 路径 | 候选与边界 | 回归 |
| --- | --- | --- |
| MetaX single/split | 厂商wrapper同一min_block_m传至两路径，候选M16；不复制计算 | 当前原失败、独立reference、workspace/strides/graph |
| generic/NVIDIA/PPU | 无改变，原M8或PPU M16及SM90 launch参数保留 | 原floor测试、签名与export检查；其它硬件实测未授权 |
| 空/unsupported | 仍由通用host gate验证，原异常不吞掉 | 原CPU/空值与非法参数测试 |

独立受控probe尚在执行：M16/N16、M8/N32、M16/N32；未提前认定根因或应用产品补丁。

受控probe完成：M16/N16通过（最大绝对差0.005859375，1 capture/2变输入replay）；
M8/N32仍同一MLIR错误；M16/N32因共享内存74752>65536失败。故只提高MetaX的M floor到16，
保留原N16、warps4、stages2；不引入N32候选或全局编译器开关。证据
`04-runs/qsa-metax-dot-tile/probe-m{8,16}-n{16,32}.{log,json}`（失败试验无成功JSON）。
新增MetaX `ops/qsa_attention.py`薄wrapper与`ops/__init__.py`导出，调用既有私有扩展点
min_block_m=16；不修改通用算法或launch helper。测试仅追加至tests/test_qsa_attention.py，
检查公共export、ABI及floor参数；现有真实设备数值/graph测试继续不放宽执行。

公共07-bugs复现改前失败(rc1)、接入后通过：最大绝对差0.005859375，1capture/2变输入replay。
`pytest-after.log`：**37 passed、8 skipped in 26.42s**。8项为显式PPU厂商floor测试，
当前非PPU按原守卫跳过；MetaX实际single/split、invalid、非连续mapping/独立stat stride、
graph数值均执行通过。新增的两个ABI/floor分派测试通过，通用原测试内容未修改。
Black24.8.0、isort5.12.0、flake8 7.1.0按组件hook同版本检查所有7个本任务修改文件均rc0；
Black退出时NFS multiprocessing临时目录清理报Errno16，保留告警，未影响检查或修改原文件。

## 性能门禁与范围扩大（改前冻结）

更新后的组合回归 `qwen-kernels-verified/pytest.log` 为340通过/42跳过（235.19s）。
QSA既有强制single/split组件benchmark36项测量有效，但最小参考速度比仅0.1943，
不能把pytest的2 passed当作性能达标。服务启动前的审查因此停止，未创建模型进程。
PLE对照18项最大耗时比1.0211、其余接近1，未见明显回归。

Deep Opt Board：指标/参考口径沿用原benchmark；MetaX当前selector返回1，Plugin已有
`qsa_sparse_split_count`与caller-owned workspace扩展点；split8已在同条件benchmark与数值/graph
覆盖中验证。现有optimization.md/deep_opt.md缺失，沿workflow.md规定的受控单假设循环继续，
不宣称使用了不存在的profiler或协议文件。

唯一新假设：已测小row/大topk形状的single CTA串行key循环占主导，复用split8提高并行度。
新增范围仅在MetaX薄wrapper模块增加同名selector并导出，BF16/FP16、q[1..64,3,256]、
kv_heads1；rows<=8且topk512..2051，或rows9..64且topk2048..2051命中8，其他场景保留1。
逐形状审查发现rows64/topk513的BF16 split8比single慢约8.6%，因此在实施前收窄该分界，
不为split名称强制所有大batch切换；中间rows的分界是有边界的候选插值，不声称逐row最优。
不改generic/SM90 selector，不自动分配workspace。
原tests/test_qsa_attention.py仅追加selector守卫测试；另新增
`benchmark/test_qsa_attention_auto.py`复用原SparseBenchmark、input和Torch reference，测量实际
selector组合。原benchmark/test_qsa_attention.py与参考文件完全只读，原数值阈值不变。
没有新kernel、block参数或候选调参空间；候选仅既有single与split8，由实测范围限定。
验证新增selector边界、相同公共入口数值/graph、18项auto benchmark逐项speedup>=0.9；
保留36项强制路径结果及其single低效限制，不以auto均值隐藏该事实。

新增selector后：QSA回归 **51 passed/8 PPU skip（2.90s）**，Plugin QSA/runtime policy/
operator binding **18 passed（22.04s）**；原QSA数值与graph断言保持。
auto18项最小/最大参考速度比 **1.3265/6.5846**，全部>=0.9；
原强制single路径在部分形状低效仍如实保留，不宣称所有显式single调用已加速。
Black（workers1）、isort与flake8再次检查8个修改文件通过，无新增告警。
选择器只决定caller-owned workspace桶，不新增Torch计算/复制fallback，也不改capture期间分配协议。
源码身份及设计审查需按新增selector后的diff重新绑定，上一份after-qsa-m16身份不覆盖此版本。
