# 012：A/B 在线服务 GPQA 精度差异

## 元数据

- 状态：`partially-verified`；`index_put_` 根因修复后的 full198 已完成，严重精度退化消失；剩余生成上限与跨实例确定性分叉仍待单变量定位
- 首次出现时间：2026-09-15
- 最后验证时间：2026-09-18
- 模型：Qwen3.8-Flash-Next，BF16
- 平台与 Host 别名：T-Head PPU，`PPU-01`
- 容器名称与镜像：A `qwen3.8-flash`，B `qwen3.8-flash-test`
- Plugin / FlagGems / vLLM revision：A Plugin `939600b323c02c21916f1f76bfb4cd8c2b02578d`，
  tracked diff SHA-256 `6a47295587033b3899e7cbd334f3a488d154aa346b0c267748169115aeb33be1`；
  FlagGems clean `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`；vLLM clean
  `ee0da84ab9e04ac7610e28580af62c365e898389`
- 执行模式与负载：TP8、async、`FULL_AND_PIECEWISE`；GPQA Diamond full198、c64、
  `temperature=1,top_p=0.95,top_k=20,max_gen_toks=60000`

## 问题现象

- A 在关闭全部实际使用的 FlagGems ATen 替换后 strict 173/198（87.37%），9 timeout；B strict
  181/198（91.41%），0 timeout。两轮提示与目标哈希逐题一致。
- 配对结果为：双方正确 172；双方错误 11；A timeout/B 错误 5；A timeout/B 正确 4；
  A 非 timeout 错/B 正确 5；A 正确/B 错误 1。B 的净优势 8 题由 4 题 timeout 恢复和净 4 题答案翻转组成。
- A 结果位于 `04-runs/Qwen3.8-Flash-Next-async-no-flaggems-aten-c64-maxgen60000/`，结果 SHA-256
  `bf7f031e7921448c7153bb33cdf29d6e350083af7953e98f9a2f408435d3bfd7`；B 结果位于
  `04-runs/Qwen3.8-Flash-Next-alt-test-c64-maxgen60000/`，结果 SHA-256
  `889ee7b406340b0d0d298ed65cd650885110525da45682cc7a86797abe42e548`。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 005 generation cap | 达到输出上限会损失 strict 分数 | 本轮 A 有 HTTP timeout，B 没有 | 高 | timeout 单独计入，不从分母删除 |
| 011 async rank 分叉 | A 曾发生长稳态服务挂起 | no-ATen 本轮服务稳定，只剩 9 个请求级 timeout | 中 | 先完成算子稳定性定位，再固定服务做精度单变量实验 |
| hy4 generic topk | 动态宽度算子会在 decode 中反复编译 | 当前全局 topk 已在 T-Head blacklist，且真实 TP 固定次序复现通过 | 低 | 不按关键词直接复用；继续检查其他动态/原地算子 |

## 诊断与假设

- 已验证：两轮 workload 除 endpoint/model name 外一致；单次 `temperature=1` 长生成含随机波动，不能把
  8 题差异全部归为数值错误。
- 已验证：对相同 198 个提示做 `temperature=0, seed=1234, max_tokens=64` 对照时，并发 32 有
  118/198 个序列分叉，单并发仍有 109/198 个序列分叉，首处分叉中位位置均为 token 17 左右。
  并发不是主因；A/B 的 logits 存在小差异并被长生成放大。
- 已验证：短样本前若干 token 一致，logprob 差异总体较小；没有证据表明存在大面积数值损坏。
- 高优先级假设：B 把 QSA main/raw/compressed cache 和 PLE conv-state cache 显式作为 custom-op
  Tensor 参数并声明 `mutates_args`，A 只声明 `output`；B 还用 non-owning graph output view，A 在
  native weak-ref 不可用时退为 identity。这些差异会改变 graph 对 cache 依赖及 graph storage 生命周期的建模。
- 次优先级假设：A/B 启动容量不同。A 为 max len 65536、max seqs 32、max batched tokens 4096、
  memory 0.90、capture 到 32，并启用 qwen3 reasoning parser；B 为 max len 100000、memory 0.85、
  capture 到 128，未显式限制 seqs/batched tokens，也未启用 parser。这些差异主要解释 timeout 和响应封装，
  需要与源码差异分开控制。

## 受控尝试

| 轮次 | 唯一变量 | 基线 | 本次设置 | 结果 | 结论 |
|---|---|---|---|---|---|
| 1 | 配对统计 | 仅比较总分 | 逐题按 prompt/target hash 对齐 | B 净高 8 题，其中 4 题来自 A timeout | 精度差异不是单一类型 |
| 2 | 采样随机性 | full198 temperature 1 | temperature 0、seed 1234、max 64 | c32 分叉 118/198；c1 分叉 109/198 | 随机性不是全部解释，并发不是主因 |
| 3 | source/graph ABI | A 隐式读取 module cache、graph output identity fallback | B 显式 cache Tensor 参数与 mutation、non-owning view | 静态 diff 已确认，尚未单变量回移 | 当前首要待验证源码假设 |
| 4 | FlagGems ATen 归因 | 关闭普通 ATen：173/198（87.37%），9 timeout | 仅 model 组约 89.90%，7 timeout；仅 runtime 组 58.59%，66 timeout；全部有效 ATen 118/198（59.60%），57 timeout | runtime 组单独复现主要退化，model 组没有 | 低分与 runtime 普通 ATen 组强相关，但尚未定位单算子 |
| 5 | runtime 组语义二分 | 36 个 runtime ATen 同开 | probability/sampling/index 20 个与 state/shape/reorder 16 个分别启用 | probability 179/198（90.40%），5 个 content-none；state 111/198（56.06%），65 个 content-none | state 组单独复现主要退化，进入该组 8+8 二分 |
| 6 | timeout 标记归类 | 评测器统一输出 `<TIMEOUT>` | 对照 API `finish_reason`、`content` 与 7200 秒配置 | probability 的 5 个均为 length/content-none；state 的 65 个中仅 25 个 length，另 40 个为 stop/content-none | 延长 HTTP timeout 不能解释 state 退化；长度上限与算子异常需分开处理 |
| 7 | state 组 8+8 二分 | state/shape/reorder 16 算子：111/198（56.06%） | tensor/norm 8 个与 index/mutation 8 个分别启用 | tensor/norm 174/198（87.88%），9 个 content-none；index/mutation 115/198（58.08%），63 个 content-none | 主要退化定位到 index/mutation 8 算子，进入 4+4 二分 |
| 8 | index/mutation 组 4+4 二分 | index/mutation 8 算子：115/198（58.08%） | A `unbind,repeat_interleave_self_int,index_put_,searchsorted`；B `lt,gather,vstack,scatter_` | A 109/198（55.05%），69 个 content-none；B 178/198（89.90%），7 个 content-none | 主要退化由 A 组单独复现，进入 A 组 2+2 二分 |
| 9 | A 组 2+2 二分 | A 4 算子：109/198（55.05%） | A1 `unbind,repeat_interleave_self_int`；A2 `index_put_,searchsorted` | A1 170/198（85.86%），10 个 content-none；A2 111/198（56.06%），70 个 content-none | 主要退化由 A2 单独复现，进入单算子对照 |
| 10 | A2 单算子对照 | A2 2 算子：111/198（56.06%） | 分别仅启用 `index_put_` 与 `searchsorted` | `index_put_` 119/198（60.10%）、59 个 content-none；`searchsorted` 173/198（87.37%）、12 个 content-none | 主要退化由 `index_put_` 单独复现；`searchsorted` 与无普通 ATen 基线同分 |
| 11 | `index_put_` 真实调用与大偏移 UT | 既有测试只覆盖小张量与 logits | 捕获 GDN state `shape=[80884,6,128,128]`、`stride=[102400,16384,128,1]`、int32 index；在首个 `row*stride0 >= 2^31` 的 row 20972 做原生/FlagGems 对照 | 原生 ATen 精确通过；FlagGems 在显式同步后仍有 98304/98304 元素未更新；低位 0..31 与 64 次 slot 复用通过 | 已排除异步 race；根因为生成的 Triton kernel 用 32 位中间量计算大 element offset |
| 12 | 64 位 offset 修复 | 生成 kernel 的 program offset 与加载后的 int32 index 参与 stride 乘法 | 在乘法前提升为 `tl.int64`，加入约 2.15 GiB 的通用回归测试 | 紧凑 UT 1/1、真实边界 UT 1/1、完整 GDN 3/3、既有扩展场景 16/16 均通过；diff/ruff 通过 | 算子级根因修复已验证，仍需整模 full198 回归 |
| 13 | 修复后双服务 full198 | `index_put_` 修复尚无整模正式回归 | 两个相同 graph 配置的 TP8 服务经本地轮询代理承载 c64、198 题、`max_gen_toks=60000` | 170/198（85.86%），覆盖 198/198；7 个生成达到 60000 token；所有请求 HTTP 200，无非 timeout 错误 | 59.60% 的严重退化已消失，但正式精度仍低于 88% |
| 14 | 生成上限归因 | 评测结果中的 `<TIMEOUT>` 可能是传输、RPC 或生成上限 | 联查代理耗时、vLLM `finish_reason`、token 计数和响应字段 | 7/7 均为 `finish_reason=length`、`completion_tokens=60000`、`content=None`；最长 HTTP 请求 5515.856 秒，低于 7200 秒客户端 timeout；两服务无 abort/error | 延长 HTTP timeout 无法恢复这 7 题；直接失分来自模型没有在 60000 token 内退出 reasoning |
| 15 | 双实例确定性探针 | 两服务源码、模型、参数一致，仅设备组、端口及独立图编译状态不同 | 对 28 个错误/上限样本用 `temperature=0,seed=1234` 做并发与严格串行短探针，再对 5 题各重复 3 次 | 并发 17/28、串行 20/28 跨端口分叉；每个端口内部 3 次输出完全一致，两个端口之间稳定不同，首个可见字符分叉在 47–214 字符 | 不是采样随机性或客户端并发 race；存在实例相关且可重复的 graph 数值/状态路径差异，具体源码点尚未由单变量实验确认 |
| 16 | graph/eager 首轮对照 | 8038 graph 与 8039 eager，表面启动参数一致 | 保持模型、容量、prompt、seed 不变，将 0–7 卡服务切换为 eager | 第 28 题附近 8039 返回 HTTP 500 并退出；TP5 首个异常为 FlagGems `index` 自动调优 SQLite `database is locked` | 环境核对发现诊断启动器漏带正式服务的 `VLLM_FL_FLAGOS_BLACKLIST_APPEND=_conv_depthwise2d,index,normal_`；该轮不是有效执行模式对照，保留为失败证据 |
| 17 | 修正后的 graph/eager 重复性对照 | 原 graph/graph 在选定 5 题上 5/5 跨端口分叉，各端内部稳定 | 8039 eager v2 补齐与 8038 相同 blacklist；同 5 题、每端 3 次、`temperature=0,seed=1234,max_tokens=32` | 两端内部仍均为 1 个唯一输出；跨端分叉降至 3/5。doc 71、168 转为一致；doc 160 保持旧 0–7 graph 轨迹；doc 30、89 成为第三条稳定轨迹 | graph/cudagraph 路径会影响部分 greedy 轨迹，但不是全部分叉的唯一原因；设备组或共用算子/编译数值路径仍未排除 |

## 根因

- 已验证根因：A 的 9 个 timeout 直接造成其中 4 题相对 B 的 strict 损失。
- 已验证：runtime ATen 低分由 state/shape/reorder 16 算子组单独复现；probability/sampling/index
  20 算子组达到 90.40%，高于 88% 阈值。
- 已验证：index/mutation 8 算子组的主要退化由
  `unbind,repeat_interleave_self_int,index_put_,searchsorted` 4 算子组单独复现；另一 4 算子组为
  89.90%，高于 88% 阈值。
- 已验证：单独启用 FlagGems `index_put_` 时 strict 降至 119/198（60.10%），而单独启用
  `searchsorted` 为 173/198（87.37%），与关闭普通 ATen 的基线完全相同。当前精度退化的 dispatch
  归因已收敛到 `index_put_`。
- 已验证：真实服务会执行 GDN state 原地写入，state 为 float32
  `[80884,6,128,128]`、stride `[102400,16384,128,1]`，逻辑大小约 31.8 GB，索引为 int32。
  FlagGems 生成内核直接计算 `cur_index * input_stride`，在 row 20972 首次越过有符号 int32 element
  offset。最小 UT 使用相同 stride、约 8.6 GiB backing storage；原生 ATen 对照通过，FlagGems 在显式
  `torch.cuda.synchronize()` 后仍有 98304/98304 元素未写入。因此这不是 H2D/stream 可见性问题，而是
  大偏移地址计算溢出。
- 已验证：评测器把 `content=None` 统一转换为 `<TIMEOUT>`。state 的 65 个标记中有 40 个请求已经
  `finish_reason=stop`，并非 HTTP 或 vLLM RPC timeout；只延长 7200 秒客户端 timeout 不会修复。
- 已验证：`index_put_` 修复后的正式轮次中 198 个请求全部 HTTP 200，服务无 RPC timeout、OOM、abort
  或 traceback。7 个 `<TIMEOUT>` 全部是 `finish_reason=length` 且精确达到 60000 completion tokens，
  不是异步调度挂死或传输超时。它们使 strict 从非上限样本的 170/191（89.01%）降到
  170/198（85.86%），是本轮未达到 88% 的直接原因；至少需要恢复其中 5 题才可达到 175/198。
- 已验证：错误高度集中在长 reasoning。170 个正确样本 completion token 中位数 3110.5；21 个非上限
  错误样本中位数 34342；7 个上限样本全部为 60000。7 个上限样本中 6 个为 Chemistry，整轮
  Organic Chemistry 为 56/72，是当前最明显的题型聚集。
- 已验证：两个独立 graph 服务在 greedy、固定 seed、严格串行条件下仍有 20/28 输出分叉；每个服务内部
  对选定样本重复 3 次完全一致。因此它不是采样随机性、请求并发 race 或代理路由错误，而是两套独立
  图编译/捕获、cache 状态或设备组产生的稳定数值路径差异。
- 尚未完全证实：跨实例分叉的具体源码归因。cache Tensor 未作为 custom-op 显式参数并声明 mutation、
  graph output identity fallback、独立编译/autotune 以及两服务 KV cache 容量差异仍是候选；在相同卡组上
  做 eager/graph 和两个 cache ABI 修改的逐项对照前，不能把它宣称为某一个 FlagGems 算子缺陷。
- 已验证：一次 graph/eager 诊断中的 HTTP 500 由诊断启动器漏带正式 blacklist 后启用 FlagGems
  `index` 引起。TP5 在 shape `[336,2560]` 的首次自动调优中与其他 rank 并发创建 SQLite 表，报
  `sqlite3.OperationalError: database is locked`，随后 8039 EngineCore 退出；8038 始终健康。补齐
  `_conv_depthwise2d,index,normal_` 后，修正的 eager v2 启动并完成重复性探针，无 500。该错误属于
  已知 autotune cache 并发问题，不是本次正式 170/198 的扣分原因。
- 已验证：修正后的 5 题 graph/eager 对照只消除 2 题分叉，另 3 题仍稳定不同。这个结果支持 graph
  路径是部分数值分叉的贡献因素，同时反证“两个独立 cudagraph capture 是所有分叉的唯一原因”。

## 解决方法或 Workaround

- 根因修复已在容器的 `/workspace/FlagGems` 工作树实现：生成 kernel 的 `pid/arange` program offset 和
  `tl.load` 得到的 tensor index 在任何 stride 乘法前提升为 `tl.int64`。同时在
  `tests/test_index_put.py` 加入 uint8、约 2.15 GiB backing storage 的通用大偏移测试，避免测试占用生产
  float32 用例所需的 8.6 GiB。
- 2026-09-17 红绿结果：紧凑用例修复前 1 failed、修复后 1 passed；真实 Qwen3.8 stride 边界用例由
  1 failed 变为 1 passed；完整 31.8 GB GDN shape 由 2 passed / 1 failed 变为 3 passed；原有 eager、
  non-blocking H2D、CUDA Graph、ATen dispatch、非连续布局与 `torch.compile` 16/16 通过。
- 先完成 011 的 FlagGems 单算子稳定性定位，固定不会挂起的 A dispatch。
- 依次做三个单变量：QSA/PLE cache 参数及 mutation 声明、graph non-owning output view、B 容量参数。
  每步先做 eager/graph cache replay 与 198 提示确定性短探针；只有差异显著收敛后再跑 full198。
- A/B Plugin 都是现存 editable 工作树；本记录只读取差异，尚未修改或提交源码。vLLM 保持 clean。

## FlagGems 证据

- A/B 在线有效 dispatch 在关闭普通 ATen 后都只显示 5 个非 ATen 自定义 MoE 算子；因此当前精度差异
  的下一层候选主要是模型 cache ABI、graph storage 和容量参数，而非普通 FlagGems ATen 数值实现。
- FlagGems 单算子稳定性由 011 独立记录，不能用本精度对照替代。
- 当前容器实际导入 `/workspace/FlagGems/src/flag_gems`，revision
  `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`（`support-qwen3.8-flash`）。36 个 runtime
  ATen 算子已无遗漏地分成两组：probability/sampling/index 20 个，state/shape/reorder 16 个。
- 两个并行 full198 运行分别位于
  `04-runs/gpqa-full-c64-maxgen60000-runtime-probability-half-20260916-v1-control/` 和
  `04-runs/gpqa-full-c64-maxgen60000-runtime-state-half-20260916-v1-control/`；服务目录分别为
  `04-runs/flaggems-aten-runtime-probability-half-20260916-v1/` 和
  `04-runs/flaggems-aten-runtime-state-half-20260916-v1/`。
- HY4 的 `56000bf` 处理的是 BF16 indexer 候选最终排序重新进入通用 `torch.topk` 后，随动态
  `N/k` 反复编译的问题。Qwen3.8 本轮实际 runtime ATen 列表不含 `topk`，固定启用的融合
  `topk_softmax` 在所有对照中保持不变；现有证据不支持直接复用该根因。
- state 组下一轮已拆为：tensor/norm 组
  `full_like,masked_fill_,expand,ne_scalar,pow_tensor_scalar,mean_dim,rsqrt,chunk`，以及 index/mutation 组
  `unbind,repeat_interleave_self_int,index_put_,searchsorted,lt,gather,vstack,scatter_`。服务证据目录分别为
  `04-runs/flaggems-aten-state-tensor-norm-half-20260916-v1/` 与
  `04-runs/flaggems-aten-state-index-mutation-half-20260916-v1/`。
- 2026-09-16 两组服务均完成 `FULL_AND_PIECEWISE` 图捕获并返回 HTTP 200，日志确认异步调度开启；
  随后已启动两组 full198、c64、`max_gen_toks=60000` 评测。客户端逐请求 timeout 为 7200 秒，
  控制目录分别为 `04-runs/gpqa-full-c64-maxgen60000-state-tensor-norm-half-20260916-v1-control/`
  与 `04-runs/gpqa-full-c64-maxgen60000-state-index-mutation-half-20260916-v1-control/`。
- 8+8 原生 lm-eval receipt 覆盖均为 198/198。tensor/norm 结果 SHA-256
  `b995043897fd9f820a8594a75d4c7f5ea67e3f7b8f5cf51dc5a5075e48ec84e1`；index/mutation 结果
  SHA-256 `02c3e5c3ff7fb7e81ed1733cf98a9e0431af50ba13aac596942100522337be82`。
- index/mutation 已继续拆成 A 组
  `unbind,repeat_interleave_self_int,index_put_,searchsorted` 与 B 组
  `lt,gather,vstack,scatter_`。2026-09-16 两组服务均完成图捕获、HTTP 200，并完成 full198、c64 评测；
  控制目录分别为 `04-runs/gpqa-full-c64-maxgen60000-state-index-mutation-a-20260916-v1-control/`
  与 `04-runs/gpqa-full-c64-maxgen60000-state-index-mutation-b-20260916-v1-control/`。
- 4+4 原生 lm-eval receipt 覆盖均为 198/198：A 为 109/198（55.05%）、69 个 content-none；B 为
  178/198（89.90%）、7 个 content-none。服务全程存活，未发现 RPC timeout、OOM、非法内存或 traceback。
- A 组已于 2026-09-17 继续拆为 A1 `unbind,repeat_interleave_self_int` 与 A2
  `index_put_,searchsorted`。两组服务完成图捕获并返回 HTTP 200；full198、c64、客户端 timeout 7200 秒、
  `max_gen_toks=60000` 的评测均完成。控制目录分别为
  `04-runs/gpqa-full-c64-maxgen60000-state-index-mutation-a1-20260917-v1-control/` 与
  `04-runs/gpqa-full-c64-maxgen60000-state-index-mutation-a2-20260917-v1-control/`。
- 2+2 原生 lm-eval receipt 覆盖均为 198/198：A1 为 170/198（85.86%）、10 个 content-none；A2 为
  111/198（56.06%）、70 个 content-none。两项服务全程存活，未发现 RPC timeout、OOM、非法内存或
  traceback。A2 已进一步拆为仅启用 `index_put_` 与仅启用 `searchsorted` 的单算子对照。
- 单算子原生 lm-eval receipt 覆盖均为 198/198：仅 `index_put_` 为 119/198（60.10%）、59 个
  content-none；仅 `searchsorted` 为 173/198（87.37%）、12 个 content-none。两项服务全程存活，
  未发现 RPC timeout、OOM、非法内存或 traceback。
- 可复现 UT 位于远端
  `07-bugs/flaggems-index-put-logits-forcing-20260917/test_index_put_gdn_large_offset_minimal.py`。在
  `qwen3.8-flash`、FlagGems `2aacb2ed7b116baee0acc147cdc770b4176a6cdd`、PPU 8 上运行约 8 秒稳定失败；
  日志为 `04-runs/index-put-gdn-minimal-ut-20260917-v1/pytest.log`。完整真实 shape 覆盖位于同目录
  `test_index_put_gdn_state.py`，结果为 2 passed / 1 failed，失败仅出现在越过大偏移边界的行。
- 修复验证目录为 `04-runs/flaggems-index-put-int64-fix-20260917-v1/`；修复后完整 GDN 与边界用例复用了
  原运行目录并已转绿，旧的失败输出由此前会话和本记录保留。面向 PR 的最新官方 `master`
  基线验证位于 `04-runs/flaggems-index-put-int64-pr-20260917-v1/`，focused source regression 为
  1 passed，`git diff --check` 与 Python 编译检查通过；该容器当前未提供 `ruff` 可执行文件。
- 2026-09-17 已从官方 `origin/master` `fd5a07bfca1cdd6bd9e61c8885d4dcd8e01c0a0c` 建立独立分支
  `fix/index-put-int64-offset`，仅包含 `src/flag_gems/ops/index_put.py` 与
  `tests/test_index_put.py`。提交为 `f75014b67aefc05a19c48bafff01e281e6987333`，作者与提交者均为
  `ZenithJoyH <1355922182@qq.com>`，容器工作树提交后 clean。上游 issue 为
  <https://github.com/flagos-ai/FlagGems/issues/6411>，PR 为
  <https://github.com/flagos-ai/FlagGems/pull/6413>；PR 正文使用 `Fixes #6411`，GitHub 已识别为关闭关联。
- 2026-09-18 当前 FlagGems 验证分支 HEAD 为
  `2b1e5cfdbd22d453933b2c6589a29daf31315ccd`，已包含上述 `f75014b67aefc05a19c48bafff01e281e6987333`
  修复。本次 full198 后不再出现启用全部 ATen 时 59.60%/大量 stop-content-none 的故障形态，说明该修复
  对整模路径生效。

## 验证结果

- 最小回归：相同提示的 greedy 短探针已完成并发、串行和单服务重复性三档。
- `graph`：两个相同配置的服务均完成 `FULL_AND_PIECEWISE` 自动 capture，正式轮次全程健康。
- 正式结果：run-id
  `gpqa-full-c64-maxgen60000-index-put-int64-auto-capture-dual-20260918-v1`，170/198（85.86%），
  198/198 覆盖，7 个最终生成上限，0 个非 timeout 错误，未通过 88% 阈值。receipt SHA-256
  `1846b8085e235326803b7a249f60fe2159657d96eaf8dbd8f5442a553c1f23a6`。
- 跨实例严格串行探针 SHA-256
  `918fa38f66b449e69f9ac24765da586d959a7b93044b68fb5e5b9356c4407d7f`；单服务三次重复探针 SHA-256
  `a8f6f72035cc6065b230bb666d26a648c9a776822560e4aac791d8c0a40f8891`。
- 修正后的 graph/eager 5 题重复性结果位于
  `04-runs/graph-eager-repeatability-corrected-20260918-v1/result.json`，SHA-256
  `73bc1e8004588cf6eee58533b2dd6fb81008e0045d026321d8f8a9f3756545b1`。失败的首轮对照没有生成部分
  result；服务日志保留在 `04-runs/secondary-eager-parity-20260918-v1/service.log`。

## 限制与下一步

- 正式轮次使用随机采样，单次答案翻转不能单独证明某个 kernel 精度缺陷；确定性短探针只能证明两实例
  数值路径不同，不能直接外推出哪一侧更准确。
- 下一步先在同一卡组上保持模型、容量、提示和 seed 不变，分别回移 cache mutation ABI 与
  non-owning graph view；每步先用 5 题和 28 题短探针判断分叉是否收敛。随后把 max model len 提至 100000，
  提高 max generation 对 7 个 length 样本做定向回归，最后再以单一已固定服务跑 full198。
- 在新的 198/198 receipt 达到 88% 前，整模精度子步骤保持失败；不能通过去掉 reasoning parser 或从分母
  删除生成上限样本获得通过。

## 经验沉淀

- 是否可跨模型或平台复用：custom op 若读写 cache，应把 cache 作为 Tensor 参数并完整声明 mutation；
  该设计原则可复用，但当前数值收益只在 Qwen3.8/T-Head 待验证。
- 知识库处理状态：`needs-validation`
- 候选知识库条目：opaque custom op 的 cache 依赖与 cudagraph replay 精度/状态一致性。
