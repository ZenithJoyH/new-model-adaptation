# 006：MetaX sparse MLA 共享内存配置适配

## 授权与编码前约束（2026-09-21）

用户明确要求调整 sparse MLA，授权本次修改现有 `/workspace/FlagGems-vllm` 的相关算子配置与聚焦测试；不扩展至 vLLM、其他算子或设备。mx-59/deepseek 的映射、editable 安装、clean 工作树与 HEAD `c0ffa628e945dc6b51af466d4f1a9b81df9ac4b8` 再次核实。基线见 005，最小形状也报 163840 B > 65536 B。仓库 workflow.md 已读，所指 optimization.md/deep_opt.md 在 checkout 中不存在；本轮为资源兼容修复，不是性能优化验收。

### 项目真相表

| 字段 | 冻结内容 |
| --- | --- |
| API / source | `flaggems_vllm.flash_mla_sparse_fwd`；没有一对一 torch API，以当前源码及已有测试契约为准 |
| Editable | `ops/flashmla_sparse.py` 的平台配置选择及聚焦测试；仅本次用户授权 |
| Read-only | 原有测试、benchmark、vLLM、权重和通用计算 kernel；旧失败证据不覆盖 |
| Build / validation | editable Python，无 wheel 重建；Triton 首次 JIT；最小复现后跑当前仓库相关测试 |
| Active set | BF16；SQ 2/17，HQ 64/128，DQK 512/576；KV 129；TOPK 64/128；sink、动态 length、无效索引；eager/graph |
| Benchmark / aggregation | 本次不运行正式性能验收、不声明 SpeedUp；逐个用例通过，不平均隐藏失败 |
| Timeout / profiler | 单次设备诊断最多 600 秒；不做 profiling，无性能结论 |
| Autotune | 保留通用 Triton autotune key；先诊断 BH=16、BK=16、warps=4、stages=1 是否足够；再冻结 MetaX 专用候选 |
| Exemption / fallback | 不重构 NVIDIA autotune 为 libtuner，防止扩大改动；非 MetaX 的原候选与路径不变；无 torch compute fallback |

### 数值契约表

| 字段 | 当前契约 |
| --- | --- |
| Input | 连续 BF16 q[SQ,HQ,DQK]、kv[SKV,1,DQK]；int32 indices[SQ,1,TOPK]；HQ 64/128、DQK 512/576 |
| Output | 新分配 BF16 [SQ,HQ,512]；FP32 max_logits/lse [SQ,HQ]；不改输入、无 out 参数 |
| Accumulate / dtype | FP32 累加；测试参考 FP32 softmax/matmul；不扩展 FP16/FP32/int/complex 输入支持 |
| Semantics | indices<0 或>=SKV 无效；topk_length 限定前缀；sink 只影响输出分母、不影响 max/lse；无有效 key 时 out=0、max=-inf、lse=+inf |
| Scope | forward inference only；不承诺 autograd/任意 NaN 输入；既有 shape/dtype/contiguity 校验不改 |
| Reference | torch 计算仅在测试；既有计算 kernel 不改；图重放覆盖两次变化输入 |

### 实现路径表

| 路径 | 触发 | 实现 / config | 验证与风险 |
| --- | --- | --- | --- |
| MetaX | runtime vendor=metax | 相同 Triton kernel、小块低共享内存配置 | 实机 eager/graph、动态长度与统计量；性能未知 |
| General | 非 MetaX | 保留 BK=64/BH=64、8 warps、stages 2/4 和 TLE 选择 | 配置守卫测试；无其他硬件实测 |
| Unsupported / empty | 原有输入校验及零 query 行为 | 不新增 fallback 或计算路径 | 测试确认既有失败语义；不扩大支持范围 |

## 状态

状态 `limited`：共享内存适配和空块数值修复已通过 eager 聚焦回归；graph 被独立原生 Stream 阻塞，不能声明完整算子/整模验收。

- 参数负对照见 005；独立进程小配置 `BH=16/BK=16/warps=4/stages=1` 成功，输出最大绝对误差 0.00048828125，max/lse 同时通过。证据 `04-runs/mla-config-small-16-16/output.txt`。
- 已在原 generic 算子增加 MetaX 配置选择，保持其他厂商两个原候选；MetaX 明确不走 NVIDIA TLE 路径。
- 新增聚焦测试在 eager 16 个数值组合和两个配置分支通过后，进入 graph 首例停止推进；同时运行的既有测试也等待。`04-runs/mla-metax-regression-20260921-02/interruption.txt` 保存精确 task-owned PIDs 的终止原因和命令，旧测试状态是中断，不是通过。容器未操作。
- 缩小 tile 专项负对照 `04-runs/mla-prefix-invalid-20260921/`：前 16 个 index=-1、后面有效时，输出 100% NaN。定位在线 softmax 的 `-inf - -inf`；仅调参数不满足原合法索引契约。
- 必要追加修复：相同 kernel 对 all-invalid tile 使用有限 rescale_max=0，而保留真实 max=-inf，使 exp 权重和旧累加贡献为 0；有效 tile 的数学运算保持不变。此保护影响 generic kernel，非 MetaX 硬件未实测；将单独跑既有数值参考和负对照，不把配置隔离当成数值全平台验收。
- 编译缓存元数据的小块内核 shared 分别为 40960/43008 B（512/576 维），原配置为 163840 B。实例：`06-cache/triton/AMDOSXWXFMWV5V2COP2IUAHICEIYGX2DUDGWVURY5R7LYWLEBWUQ/triton_flash_mla_sparse_fwd.json`、`06-cache/triton/TQSPVMU5GZQE3I4AMMTCYZ6ACR4OS74A2RWA64T6LSU3IKTDDVHQ/triton_flash_mla_sparse_fwd.json`；资源降幅不是吞吐提升证明。
- 串行复测 `04-runs/mla-metax-regression-20260921-03/output.txt` 在 19 个用例通过后，通过 faulthandler 定位等待点为 `torch/cuda/streams.py:37` 的 `Stream.__new__`，尚未进入 graph capture 或调用该算子。核对并终止 task-owned PID 357504，记录 `interruption.txt`；不能标记 graph 通过。
- 仓库 `black` 未安装，未擅自安装格式工具；`git diff --check` 通过。管理仓库 `./scripts/syntax-check` 的 245+4 个本地测试通过（1 skipped），最后因已有本工作区部署指纹缺项而返回失败，另有 70 条历史布局 warning。未伪造部署指纹消除审计错误。

## 最终验证与交付

- **21 passed、2 deselected**，30.55 秒：`04-runs/mla-metax-eager-final-20260921/{output.txt,junit.xml,identity.txt}`。命令：容器 cwd `/workspace/FlagGems-vllm`，`python -m pytest -p no:cacheprovider -q tests/test_flashmla_sparse.py -k 'not graph' --record none -o faulthandler_timeout=45 --junitxml=<上述结果目录>/junit.xml`。环境、缓存和超时与 `05-tmp` 中保留的任务补丁及测试计划对应，所有运行产物都在批准工作根。
- 覆盖：BF16 DQK=512/576、HQ=64/128、SQ=2/17、TOPK=64/128；sink 含 ±inf、动态 topk 长度、空 query、全无效索引、无效首 tile 后有效 key、dtype/layout 拒绝；配置守卫和 MetaX 禁用 NVIDIA TLE 守卫。图用例明确 deselected，不计入通过数。
- 原生 PyTorch（不导入 FlagGems）对照：`07-bugs/sparse-mla-adapter/native-graph-probe.py`，CUDA_VISIBLE_DEVICES=0，`timeout -k 5 90 python -u native-graph-probe.py`；结果 `04-runs/mla-metax-regression-20260921-03/native-graph-probe.txt`，张量创建成功，`torch.cuda.Stream(device=x.device)` 在 `streams.py:40` 等待，90 秒超时 rc=124。只能确认 graph 验证受原生 runtime Stream 创建阻塞，尚未确定驱动/运行时内部根因。
- 原有 `test_flash_mla_sparse_fwd.py::test_flash_mla_sparse_flashmla` 尝试未完成，保留中断日志，不宣称通过。未运行性能 benchmark，因此没有 SpeedUp/吞吐或非 MetaX 实测结论；本轮不触发性能 deep_opt。
- 没有新增生产 torch compute/copy/cast fallback；使用原 Triton kernel 数学路径，输出分配仍为原有 torch.empty，shape/dtype 检查不变。
- 最终两个产品路径：修改 `src/flaggems_vllm/ops/flashmla_sparse.py`，新增 `tests/test_flashmla_sparse.py`；未提交/推送，原 HEAD 不变。MetaX 单个安全 autotune 候选为兼容性基线，不是性能最优承诺；通用 BK/BH=64、8 warps、stages=2/4 不变。generic 在线 softmax 空块保护在有效 tile 上与原公式等价，但其他平台仍需实机回归。
- Diff 设计审查：保留现有公共导出/注册，无第二套算子实现、无厂商 SDK 导入、无静默 fallback；唯一新增共享数学行为是保护合法无效索引块。真实 diff/测试 SHA 保存在 `identity.txt`。判定为有限验证修复，不标记 adaptation complete。
- 下一步：解决独立 native Stream 阻塞后完成 graph 两次变输入 replay；再继续 decode MLA/元数据桥接及整模验证。不修改或重启容器来绕过该问题。
