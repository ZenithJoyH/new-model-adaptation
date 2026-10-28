# 003：MetaX shuffle 编译工具链不匹配

## 基线与现象

- 状态：`open`；2026-10-27；mx-102 / `glm5.3-flash`。
- 实际 FlagGems-vllm `/opt/FlagGems-vllm@ddce1d66`，FlagGems
  `/opt/FlagGems@3eab0949`，两者干净；Plugin `4e23ae8f`，vLLM `ee0da84a` 只读。
- FlagTree 源码来源 `2f1229e51c03b345a1c72207854828eed7282de9`，实际导入同一安装的
  Triton 3.6.0 / MetaX plugin v0.6.2；PyTorch `2.10.0+metax3.8.2.2`，C550。
- 库原生 `python -m pytest -q tests/test_glm5_numerics.py --quick`：6通过、2失败。
  卷积编译在 `metax.mlir_opt` 报 `custom op 'maca.shfl.sync' is unknown`。
  KDA 是独立的数值断言失败（最大绝对差0.000415742），此前只看日志尾部将两项都归为
  编译失败的判断已撤回；完整JUnit回溯才是该项依据。
- 原生结果：工作根 `04-runs/fgv-glm-numerics-baseline-20261027/mx-102/`。
  独立复现：同根 `07-bugs/001-metax-shuffle/repro.py`，无需整模或服务。

## 受控诊断

| 轮次 | 唯一变化 | 结果与证据 |
|---|---|---|
| baseline | SDK 默认 MLIR optimizer / translator | 6通过2失败：conv编译失败、KDA数值断言失败 |
| tiny-warps1 | 最小复现使用1 warp | conv 同样失败；KDA 复现输入不连续，被前置校验拒绝，不能作为编译结论；保留原记录 |
| bundled-opt | 仅进程内将 optimizer knob 选为已安装后端的工具 | 仍6通过2失败，错误推进到默认 SDK translator 不识别 shuffle；`04-runs/fgv-glm-numerics-bundled-opt-20261027/mx-102/` |
| matching-tools | 仅进程内选择 FlagTree 构建声明的同一官方 MLIR 工具对 | 仍6通过2失败，构建用translator未注册MACA dialect；`04-runs/fgv-glm-numerics-matching-tools-20261027/mx-102/` |
| corrected-input | 独立CPU参考、显式连续状态 | tiny KDA通过、conv仍编译失败；`04-runs/metax-shuffle-model-default-v2-20261027/mx-102/`，该轮未传shape，实际为tiny |
| model-shape | 显式 `--shape model` | 128维KDA通过、512通道/4宽conv仍编译失败；`04-runs/metax-shuffle-model-default-v3-20261027/mx-102/` |

`num_warps=1` 未解决 conv，停止盲目调参。已安装 backend optimizer 中存在 shuffle 操作，
默认 `/opt/maca/mxgpu_llvm/bin/mlir-opt` 中不存在；两个工具均非新下载或自制二进制。
仅换 optimizer 不足以解决 translator 的相同缺口，不据此添加产品 workaround。

## 来源和边界

FlagTree 的 `python/setup_tools/utils/metax.py` 声明官方构建工具包
`metax-llvm19-3.8.0.6-x86_64_v0.6.0.tar.gz`，MetaX plugin v0.6.2。
只读核实已有官方缓存位于
`/public-flash/jinghao/qwen3.8-flash/06-cache/path-correction-20261023/flagtree/metax/metax-llvm19/`。
诊断可读取该依赖，不修改它，也不将该挂载路径作为交付方案。

- optimizer：307547456 bytes，SHA256
  `5fbd9ca42bce6f1e287fc7c840bfc67a8e7a7f72cf6b6f2e96834f19d1c55a10`。
- translator：68394512 bytes，SHA256
  `43357af6ed02372d966be1373634788202d1e153c4a89242271e3c2384d10b98`。
- ldd 仅依赖当前系统标准运行库，无外部开发目录依赖。

以上诊断均没有产品源码修改。FlagTree/SDK 不在 profile 的默认可写组件清单；若对照证明必须
补齐匹配工具，先给出具体容器内安装路径、官方来源和回归方案，再请求该依赖安装例外。
不得覆盖 SDK、更新整个编译器、修改 vLLM 或借助 PYTHONPATH 选择另一份实现。

## 验证与限制

先完成相同8项原生数值对照，再验证模型实际 KDA128维、conv4宽的 eager、capture 和至少
两次变输入 replay。有状态 prefill/decode、cache 更新必须单独验证。
未完成上述工作前不扩大到整模，不宣称算子或适配通过。知识库状态：`needs-validation`。

卷积结果更新：mx-102 `04-runs/conv-metax-smoke-20261027/mx-102/` 为71通过、rc0；
`04-runs/conv-metax-graph-20261027/mx-102/` 为20通过、rc0，含选择守卫两侧和18项
真实设备eager/一次capture/两次变输入replay，覆盖FP32/FP16/BF16及D512/W4。
同一源码和测试已同步至mx-101：`04-runs/conv-and-basic-glm-20261027/mx-101/`
98项通过、rc0（70项既有卷积、20项新增图/选择回归、8项基础GLM数值）。
两个改动文件已用安装环境已有black格式化，
预览差异仅本任务新增行换行调整。最终source review和性能仍待完成，不据此标记适配完成。

原8项基线中的generic recurrent差异已做唯一参考精度变量对照：
`04-runs/fgv-glm-numerics-kda-reference-fp32-20261027/mx-102/` 1通过、rc0。
默认GPU参考allow_tf32=True；设False/highest后原始断言通过，没有修改该测试或生产KDA。
后续bounded-prefill的另一项差异见问题005，不能混用generic recurrent结论。

## 卷积局部修复计划（编码前）

已定位触发点为 `causal_conv1d.py:_conv_kernel` 的历史窗口 `tl.gather`。模型宽度4也复现。
优先在已授权的实际安装 FlagGems-vllm 中，使用现有vendor判定，为MetaX选择静态寄存器
历史元组移位，避免该shuffle操作；原有其他平台矩阵路径保留。不会重写公共compiler或SDK。

### 项目真相

| 字段 | 冻结内容 |
|---|---|
| API/来源 | 既有 `causal_conv1d_fn/update`，序列分段的depthwise `torch.nn.functional.conv1d`，CPU参考使用当前Torch2.10 |
| 可写文件 | FGV实际安装 `src/flaggems_vllm/ops/causal_conv1d.py` 的kernel分支和launch constexpr；`tests/test_causal_conv1d_metax.py` 新增针对性回归 |
| 只读 | 原有数值测试、参考和benchmark文件；vLLM、FlagTree、SDK、其他算子 |
| 构建 | 纯Python/Triton，实际editable解释器首次JIT；不重装、不改导入路径 |
| 功能命令 | 原有 `tests/test_causal_conv1d.py` 与 `tests/test_glm5_numerics.py --quick`，新增MetaX测试；CPU参考、状态及graph两次回放 |
| 性能 | 既有 `benchmark/test_causal_conv1d_fn.py`、`...update.py`，先collect核对active set与baseline；失败原路径不能提供可比延迟，不编造加速比 |
| active set | FP32/FP16/BF16，D=2/23/512，width=2/3/4/8，短序列/varlen含空段，initial/bias/activation、padding和非连续stride |
| 聚合 | 功能逐项通过；性能逐shape latency与SpeedUp，关键shape不得由平均值掩盖 |
| 超时/profiler | 每个诊断使用独立run并检查实际进展；无已验证profiler，不做盲调或性能优化声明 |
| autotune豁免 | 本次仅MetaX编译兼容性修复，沿用32通道/4warps；NVIDIA原路径和已有参数不变，未引入候选参数搜索 |
| fallback | 生产路径无torch计算回退；既有metadata/view/allocation保留 |

### 对齐契约

| 字段 | 冻结内容 |
|---|---|
| 输入 | prefill `[D,T]` / decode `[B,D,T]` 或varlen `[T,D]`；weight `[D,W]`；state `[slots,D,history]`；W2..8、history≥W-1；FP32/FP16/BF16同device |
| 输出/状态 | 输出shape/dtype与x一致，单独分配；按slot原位更新state前W-1项；无效slot输出0、不更新；空段保持state |
| dtype/累加 | 输入转换为state dtype后FP32累加，激活后转state dtype，再存输出dtype；不新增promotion或dtype支持 |
| layout | 保留现有显式stride；metadata须连续整型/布尔；不增加contiguous/copy |
| 语义 | 卷积权重顺序、初始状态、bias、silu、padding/null协议不变；NaN/Inf按运算传播，不承诺bitwise等价重排；数值容差不放宽 |
| autograd/unsupported | 推理forward-only；既有APC旋转/投机元数据拒绝分支保留，未声明backward或复数/整数支持 |
| 参考用途 | Torch计算只在测试/benchmark内，生产不导入参考 |

### 路径与验证

| 路径 | 条件/实现 | 验证与风险 |
|---|---|---|
| empty/error | 现有host metadata检查与空输出 | 空请求/非法metadata；不新增计算 |
| MetaX | `runtime.device.vendor_name == metax`；同kernel中constexpr静态历史元组 | 各dtype/宽度/stride、prefill/decode状态、至少两次变输入graph；FP32求和重排风险 |
| 其他vendor | 原矩阵窗口和gather分支 | host选择守卫验证；缺少其他设备，实际硬件回归不宣称通过 |
| unsupported | 既有明确异常 | 不删接口、注册或测试，不用Torch补洞 |

新增算子导出/注册/tune config不需要：公共API、注册和签名不变；只新增MetaX constexpr实现。
`optimization.md` 与 `deep_opt.md` 在当前主线不存在，记录缺失，不编造其内容。
KDA的GPU参考误差另做同输入CPU对照和精度配置诊断，不放宽断言或借卷积修复混改KDA。
