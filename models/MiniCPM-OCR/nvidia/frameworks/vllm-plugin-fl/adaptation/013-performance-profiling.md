# 013：FlagOS 性能差距的调用与耗时证据

## 范围与结论

2026-10-26，H100-149。初次 profiling 只做诊断；后续按用户要求验证了部署级 slice 黑名单及已知形状调优缓存复用，结果见末节。没有修改产品代码、`.so`、依赖或人工 `start-model.sh`，没有提交或推送。状态为 `open`：已有缓解措施，公共调优策略等根因尚未修改；不改变 `framework.yml` 或正式验收状态。

证据支持两个优先方向：**解码过程中的 FlagGems Python 包装及 DEBUG 日志开销**，以及**视觉动态形状未命中调优缓存时的在线 autotuning**。LM head、softmax 和 GDN 的 GPU 计算没有表现出足以解释整体差距的退化。不能将本轮 profiler 下的占比直接解释为此前整套基准约三倍差距的归因百分比。

## 固定身份与实验

- 权重：`/public/flagos/jinghao/MiniCPM-OCR/models/merge_rl_mergedp1_7140_hf5_4x`；沿用[原生对比](../acceptance/native-vs-flagos-performance-20261026.md)的权重身份。
- GPU4：H100 80GB，UUID `GPU-37abecc9-c318-840a-1e8b-3e389dd55035`；两个后端顺序使用同一卡、8013。8012 在 GPU3 保留，未对其开启 profiler。
- FlagOS：`minicpm-ocr-flagos-public`，vLLM `0.24.0+empty`，FlagTree `0.7.0`；原生：`minicpm-ocr-vllm-native-allgpu`，vLLM `0.24.0+cu129`；Torch 均为 `2.11.0+cu129`。
- 实际安装源：Plugin `/opt/vllm-plugin-FL`，HEAD `25eddf9a0616b08363e5c1553fc537e44ed4c81d` 加既有 OCR 修改；FlagGems `/opt/FlagGems`，HEAD `8200f71f51d784d54a5a51019cb955acb74d64c1` 加既有修改；FlagGems-vllm `/opt/FlagGems-vllm`，HEAD `fa78ddee4c3e78ce5047213ff0ef02acff34b2d5`。身份以逐文件哈希为准，元数据版本不能代替源码身份。
- 公共参数：BF16、上下文 262144、max-num-seqs 64、显存比例 0.55、`FULL_AND_PIECEWISE`、`TORCH_SDPA`、关闭前缀及多模态处理缓存；采用冻结 v1.1 包原请求参数、自然 EOS，不缩短输出。
- `single`：固定文本区域，213 个输出 token，并发 1；`mixed64`：原包 64 个区域，并发 16，35 文本、21 短内容、6 公式、2 表格，参考共 2764 个输出 token。single 是这 64 个区域之一。
- 每后端先各两次预热、两次无 profiler 对照，再各一次采样。另有 FlagOS 五次短栈场景请求。共 **655 次成功请求**，HTTP 200、非空、自然结束；不属于新一轮全量精度评测。
- 各诊断实例使用独立 FlagGems 调优缓存，复用既有 Triton/Inductor 编译缓存。四轮相同混合请求仍不能保证覆盖后续动态组批的所有形状。恢复后的 8012 也使用独立恢复缓存；本轮不能证明其与外部停止前缓存热度相同。

原始输出统一位于 H100-149：

`/public/flagos/jinghao/MiniCPM-OCR/flagos/04-runs/ocr-profiling-20261026-r2/`，以下记为 **O**。

诊断入口位于同根 `02-issues/ocr-profiling-20261026/`，以下记为 **A**。完整配置、实际环境、解释器、源码前后身份和请求响应分别保存在 `O/{flagos,native-r3,flagos-stack}/`。没有通过 `PYTHONPATH` 切换实现。

## 无 profiler 对照与采样边界

| 场景 | FlagOS 两轮，秒 | 原生两轮，秒 | 中位数比值 |
|---|---|---|---|
| single | 1.0563 / 1.0590 | 0.4880 / 0.4862 | 2.17 倍 |
| mixed64 | 17.1359 / 20.3777 | 3.4121 / 3.3562 | 5.54 倍 |

这是诊断子集，不能替代整套跨平台基准。single 两端均为 213 token；mixed64 两端采样轮次均为 2763 token，FlagOS 一轮无 profiler 对照为 2766，其余对照为 2764，响应全部保留。

无栈 profiler 下 single 为 FlagOS 1.5045 秒、原生 0.8618 秒；mixed64 为 30.4334 / 3.3988 秒。采样显著增加了部分开销并影响组批，不能直接把这些耗时当正常服务性能。短栈轮次只用于证明函数调用，不用于报告正常耗时。

## 1. 解码 CPU 路径：Python 视图及每次调用的日志构造

相同 single 采样中，两端 GPU kernel 累计时间接近：FlagOS **329.73 ms**，原生 **341.76 ms**；首个到最后一个 kernel 跨度却为 **1454.91 / 809.56 ms**。FlagOS kernel 区间并集占该跨度 **22.66%**，原生 **42.14%**。这里的 busy 只覆盖 kernel，不含 memcpy，不能等同整机 GPU 利用率。

| CPU 操作 | FlagOS 调用数 / self ms | 原生调用数 / self ms |
|---|---|---|
| `aten::slice` | 16697 / **298.91** | 19869 / **45.38** |
| `aten::fill_` | 2141 / **87.48** | 4075 / **8.48** |
| `aten::add` | 647 / **67.94** | 647 / **3.96** |
| `aten::mm` | 328 / **53.99** | 328 / **11.82** |
| `aten::div_` | 214 / **36.96** | 214 / **1.64** |

FlagOS slice 次数更少，但主机开销更大。实际服务短栈显示：

`WorkerFL.execute_model → ModelRunnerFL._update_states → InputBatch.refresh_metadata → _make_sampling_metadata → vllm.v1.utils.copy_slice → aten::slice → flag_gems/ops/slice.py:194 slice → logger.debug → logging._log → makeRecord → LogRecord.__init__`。

调用栈中也能看到 attention metadata 和 GDN metadata builder 的 slice。CPU tensor 的原生 slice 与 CUDA tensor 的 FlagGems slice 都存在，不能将所有 slice 直接归为 FlagGems；证据文件保留了上述具体 FlagGems 子调用。短栈窗口记录到 658 次 FlagGems slice、1751 次 LogRecord 构造和1750次 once filter 调用。

安装源码中，`vllm_fl/worker/worker.py` 在 rank0 调用 `flag_gems.enable(record=True, once=True, ...)`；`flag_gems/logging_utils.py:59` 将 logger 设置为 DEBUG，`:34` 的 once filter 挂在 handler 上。因此，后续调用仍先构造 LogRecord，再由 filter 丢弃已见位置。`flag_gems/ops/slice.py:194` 本身还包含 Python 形状、步长与边界计算，最终返回 `torch.as_strided` 视图。

独立进程使用同形状 CUDA int32 `[65]`、相同 `aten.slice.Tensor(x,0,0,2,1)`，**不启用 profiler**，每轮 20000 次、5 轮：

| 唯一变化 | 每次 CPU 耗时中位数 |
|---|---|
| 原生 | **3.00 µs** |
| FlagGems，record=False | **8.04 µs** |
| FlagGems，record=True / once=True | **14.52 µs** |
| 保持实现，独立进程仅禁用 slice logger | **7.59 µs** |

四组均验证值和 storage alias 正确。once 日志文件仅 **46 字节**，重复成本来自日志记录构造/过滤及 Python 包装。该实验只改变独立进程的日志状态，未修改 8012 或产品文件；它证明算子级开销，不等于已测得关闭服务日志后的整模型加速。

证据：`O/logging-call-proof.json`、`O/logging-check/result.json`、`O/logging-check/ops.log`、`O/flagos-stack/analysis/`；复现入口 `A/logging_check.py`。

## 2. 视觉路径：动态形状触发在线 autotuning

FlagOS mixed64 的 GPU kernel 累计 **19.394 秒**：

| Kernel | 次数 | 累计 GPU 时间 | 占 kernel 总时间 |
|---|---|---|---|
| `_attn_fwd` | 48647 | **11.737 秒** | **60.52%** |
| `zeros_kernel` | 54811 | **4.426 秒** | **22.82%** |
| `addmm_kernel` | 19537 | **2.361 秒** | **12.17%** |

CPU 还记录到 **1135 次 `cudaDeviceSynchronize`，累计 12.047 秒**。这些 CPU 等待与 GPU 时间重叠，不能相加。

702 次视觉 SDPA 中，四次慢调用如下；相同形状其他调用的 CPU 中位数约 0.20–0.21 ms：

| Q/K/V 形状 | 单次 CPU inclusive | 该调用内 device synchronize 次数 |
|---|---|---|
| `[1,16,1044,72]` | **4.885 秒** | 99 |
| `[7,16,1072,72]` | **4.467 秒** | 99 |
| `[1,16,996,72]` | **3.858 秒** | 99 |
| `[1,16,952,72]` | **3.854 秒** | 99 |

实际服务调用链：

`MiniCPMOcrForConditionalGeneration._process_vision_input → Idefics2VisionAttention.forward → scaled_dot_product_attention → aten::_scaled_dot_product_cudnn_attention → FlagGems _scaled_dot_product_cudnn_attention → scaled_dot_product_attention_forward → _attn_fwd`。

独立同形状采样进一步捕获到：

`FlagGems attention → LibTuner.run / default_policy → bench → Triton Autotuner._bench → libentry.do_bench → triton.testing.do_bench → kernel_call → cuLaunchKernelEx → _attn_fwd`。

`zeros_kernel` 的实际调用链为 `triton.testing.do_bench → NVIDIA driver.clear_cache → Tensor.zero_ → FlagGems zero_ → zeros_kernel`。服务中一个代表性清零 tensor 形状为 `[67108864]`，correlation 将它关联到视觉 addmm 内部；这是调优 benchmark 的 cache flush，不能当作模型业务需要的清零量。

独立算子 `[1,16,996,72]`、实际 interleaved QKV strides `[3442176,72,3456,1]`、BF16，在无 profiler 下首次调用 **4966.38 ms**，缓存命中后中位数 **0.1022 ms/次**。首次时间包含新形状调优及可能的 JIT，不能全部标为纯 autotune；另一个 1044 形状的实际短栈已直接证明 benchmark 路径。

稳态 CUDA event + graph replay：该 996 形状 FlagGems **0.0639 ms**，原生 Torch 默认 SDPA **0.0329 ms**；这里是独立默认 SDPA 对照，不声称 native 服务所有 masked/unmasked 形状均选择相同 kernel。BF16 输出最大绝对差 **0.0009765625**。安装源码 `attention.py:172` 的 forward 调优 key 为 `KV_CTX, HEAD_DIM`，动态视觉序列长度会改变 key。

证据：`O/mixed-attention-call-proof.json`、`O/flagos/analysis/`、`O/operator-check/result.json`、`O/operator-check/cold-attention.analysis.json`；复现入口 `A/micro.py`。

**边界：** 调优缓存为实例隔离，profiler 也会影响动态组批；四次慢 SDPA 的占比不能外推到缓存已经完全覆盖的长期服务，更不能直接当作上一轮整套基准差距的精确百分比。两次预热后仍可能出现新的序列长度，是本轮已验证的实际风险。

## 排除与优先顺序

- LM head 的实际 `aten::mm` 是 `[1,1024] × [1024,248128]`，FlagGems `mm_kernel_general_host_tma` 在 single 中 214 次、GPU 共 **35.13 ms**；原生对应 GEMM 为 **37.89 ms**。无 profiler CUDA event + graph replay 再测为 **0.1645 / 0.1784 ms/次**，合成 BF16 输入输出最大绝对差 0。它不是本轮主要 GPU 退化来源。
- single softmax：FlagGems 214 次 **11.17 ms**，原生 **21.20 ms**。GDN packed decode：两端各 3834 次，**13.92 / 13.90 ms**。不能据调用次数多就将这些算子列为主要慢点。
- 优先验证日志记录机制与 Python metadata/view 路径的主机成本；再处理视觉动态形状的缓存覆盖、调优策略及持久化，必要时评估语义等价的分桶策略。对稳态视觉 attention 再做选型。以上均为后续建议，本轮没有实施修复或测量修复后的整模型收益。

## 生命周期、失败与可复核证据

本轮开始前，两个原容器先后收到外部 Docker stop，8012 已拒绝连接，当时 profiling 尚未启动。用户明确授权“将这两个容器全部启动起来”后，启动原容器，并执行**未修改的原脚本**恢复 GPU3/8012；恢复时归档旧日志，健康检查和原 OCR 请求通过。新 PID 为容器内 **16**，argv 与外部停止前记录完全一致。未自动恢复外部停止的其他端口服务。

原生首次隔离实例因重启后 `ldconfig` 未列出实际存在的 `libcuda.so.1` 而失败，未发送请求；失败保留在 `O/native/`。重试 `native-r3` 仅显式设置 `TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu`，未修改驱动库、链接缓存或产品源码。

最终 `O/final-state.json` 验证：两个原容器运行且 `/public:/public` RW，8012 health 200；其恢复后的 PID/start ticks/argv 与脚本保持，GPU4 显存 0 MiB，临时 8013 已退出。FlagOS 安装源码与 vLLM Python/so 哈希和本轮开始前相同；原生开始/结束身份也一致。

- 启动脚本：`/public/flagos/jinghao/MiniCPM-OCR/flagos/start-model.sh`，SHA-256 `ab1239fa7729e8d532916b8c6feb4574cc0dccc78f3aa0cc8dceccbaf2a65d32`。
- 全部 trace、配置、分析、请求完整性与源码身份的冻结清单：`O/evidence-index.json`，SHA-256 **`e68870f042a462ab9e44d313d8bcad017f2f68d63da9c6d46621fd0e8fd0bae4`**。
- 调优短栈：`O/operator-check/cold-attention.pt.trace.json.gz`，SHA-256 `34e91b880e20bd468c86443f38d48af5ad34f706c7ea9e5c54994bec2701214d`。
- 原生/FlagOS 无栈 trace 的 CUDA correlation、CPU self、shape/stride、kernel 次数及区间并集分别在 `O/{flagos,native-r3}/analysis/*.analysis.json`。CPU self 按同 PID/TID 子区间并集扣除，GPU busy 按 kernel 区间并集计算；嵌套 inclusive 不能相加。
- 本地仅新增本诊断记录及索引。结构审计仍存在仓库原有 XingChen4 失效链接和其他模型历史告警；不涉及本模型，没有修改无关文件。

经验匹配参考[009](009-torch-sdpa-runtime-evidence.md)的 Python→CUDA correlation 方法，但权重和调用路径不同，没有复用其旧耗时。知识库状态 `local-only`：根因尚未通过产品代码修复，未验证其他模型或平台。

## 后续：slice 黑名单与持久化调优缓存

用户要求先把 slice 加入黑名单，再处理 autotuning。本次采用既有 `VLLM_FL_FLAGOS_BLACKLIST_APPEND=slice` 做模型部署级 workaround，保留平台默认黑名单，没有修改共享 NVIDIA 默认值或安装组件。只在 GPU4/8013 的新进程验证；8012 原进程保持，配置供后续启动继承，不声称当前8012已热切换。

新产物根为 `/public/flagos/jinghao/MiniCPM-OCR/flagos/04-runs/ocr-slice-blacklist-20261026/`（下记 **S**），诊断脚本在同根 `02-issues/ocr-slice-blacklist-20261026/`。以下为已完成结果。

### 黑名单的受控对照

基线、slice graph、slice eager 三个实例分别从同一个调优数据库种子建立独立快照，种子 SHA-256 均为 `4422bcf9029fcc81341a66b72cd52a4da6e1ef23b3c3cc905f67762d50bc978f`。权重、GPU4、模型参数、日志记录策略相同；graph 性能轮次均关闭前缀与多模态处理缓存。

固定213输出token的单请求，两次预热后、无 profiler 的三轮对照：

| 设置 | 三轮耗时，秒 | 中位数，秒 |
|---|---|---|
| 原配置 | 1.0201 / 1.0192 / 1.0221 | **1.0201** |
| 仅追加 slice | 0.8109 / 0.8194 / 0.8139 | **0.8139** |

该请求延迟降低 **20.22%**，速度为原配置 **1.253倍**。没有重跑完整32页v1.1基准，此收益不能外推为三个完整应用场景的收益。

实际算子记录中，基线含 `flag_gems.ops.slice.slice`，处理组 graph/eager 均不含该项；独立注册表检查确认 CUDA slice 保持原生实现。无 profiler 的原生 slice 实测中位数 **2.513µs**。24组 eager 算子契约覆盖 float32/BF16/int32/bool、连续/非连续、负索引/步长/空结果，值、stride、offset、storage alias 全部一致；另有3种dtype各两次变输入 CUDA graph 重放通过。

补充单请求 profiler 中，slice 仍为 **16697次**，CPU self 从初次采样的 **298.91ms** 降到 **39.63ms**，GPU kernel累计 **328.87ms**（初次329.73ms），与主机路径改善相符。该 profiler 轮次仅作调用/耗时归因。

六类固定请求包括文本、4x小图、4x/16x票据、双图、视频：处理组 **graph 12/12、eager 12/12** 内容及token ID均与原参考完全一致。连同基线12个回归请求、两组长文本性能请求，本轮共 **47个成功响应**，无失败或截断。eager 首轮存在较大冷开销，例如前两个请求66.70/84.71秒；这些耗时保留，不混入graph稳态性能收益。

首轮 guard 错误地要求一条 INFO 日志必须输出，在实际请求前提前停止了临时实例。核对真实函数解析和算子记录后确认黑名单有效，改为实际派发证据并重试；初次失败保留在 `S/flagos-slice/`，成功结果在 `S/flagos-slice-r2/`、`S/flagos-slice-r2-eager/`，没有覆盖失败记录。

### Autotuning 的缓存缓解及边界

复用初次 profiling 已产生的 ConfigCache 数据库，并在独立持久化目录预热检查四个真实 attention 形状，再由第二个全新进程验证。两个进程PID分别为11435、11604；四形状首次调用后的 `benchmark_success_count` 均为 **0**。

| Q/K/V形状 | 新进程首次调用，ms，无profiler | 随后稳态中位数，ms |
|---|---|---|
| `[1,16,952,72]` | 724.578 | 0.1590 |
| `[1,16,996,72]` | 5.663 | 0.1564 |
| `[1,16,1044,72]` | 5.169 | 0.1635 |
| `[7,16,1072,72]`，BF16 mask | 15.730 | 0.7317 |

保留真实 interleaved stride；输出对原生参考最大绝对差不超过 **0.001953125**。缓存重放短栈恰有 **4次 `_attn_fwd`**、**0次 `do_bench` Python事件**，未关闭FlagGems attention。首个调用仍有约0.725秒的进程首次调用开销，未进一步拆分；没有将它描述为亚毫秒冷调用。

这验证了**已覆盖形状的调优结果可跨进程复用**。本次沿用已有 Triton 编译缓存；清空编译缓存仍可能JIT，未知形状仍可能首次调优。没有修改公共调优策略、强制固定config或完成所有模型形状的离线覆盖，也不宣称完全解决autotuning。

### 可复用配置及收尾

容器内配置文件如下，均位于批准根，后续启动时导出即可继承，**不需要修改原启动脚本**：

- `01-environment/slice-blacklist.env`：`VLLM_FL_FLAGOS_BLACKLIST_APPEND=slice`；SHA-256 `f9314f58d78d3e854d421a34e718b42de5c9f153244eb2e4b069c77de325f7e9`。
- `01-environment/ocr-tuning-cache.env`：`FLAGGEMS_CACHE_DIR=/public/flagos/jinghao/MiniCPM-OCR/flagos/06-cache/ocr-slice-blacklist-20261026/persistent`；SHA-256 `e0bdadd3a63d5944299ef0907fc2583b05215fefcad7879ee123a13ba67cfee3`。

该缓存绑定当前H100及已验证的软件版本，不作为跨硬件通用缓存。就绪数据库快照在 `S/cache-check/ready-database/TunedConfig_nvidia_triton_3_6.db`，SHA-256 `7f1fb1f4cfc9268d842cd5cb681d46d379fab0ef3f04272751ebd2517d407a12`。配置与缓存目前是 `/public` 外部挂载产物，尚未打包镜像。

`S/final-verification.json` 再次核实：两个原容器运行，8012 health200且PID/start ticks/argv未变，启动脚本校验值仍为上文值，GPU4显存0MiB，临时8013已停止；Plugin/FlagGems/FlagGems-vllm及vLLM Python/so均与本轮前一致。没有产品源码新增/修改/删除，没有提交推送，`framework.yml`未变。

- 请求、trace、配置、源码身份等冻结清单：`S/evidence-index.json`，SHA-256 `f2b83be213869bad1ee9b031a6a9d2b8883242104bcdb450b3dbe02efe2e5a85`。
- 最终服务/源码/配置/就绪数据库校验：`S/final-verification.json`，SHA-256 `2e6cbafffa3d674fb7a0800c3f68fb68cfa4d0c06255e4dcab3bd9987494fdf2`。
- 缓存短栈：`S/cache-check/cached-replay.pt.trace.json.gz`，SHA-256 `023055e857d68b76fa1e9ec856bdb3207fec0226cd5200d982ace81d5d6ce898`。
- `./scripts/syntax-check --offline` 通过：295项workflow测试（19跳过）、7项operations测试及脚本语法检查通过，保留9条其他模型历史告警。未修改无关记录。

随后完成[完整v1.1应用复测](../acceptance/slice-blacklist-performance-20261026.md)：交互吞吐提高15.57%，批量不稳定且未证明提升，较高负载未见提升；4644请求无失败/截断，32页质量接近原值。完整负载仍新增attention benchmark缓存记录，不能将本节四形状命中或单请求20.22%改善外推为全场景优化完成。
