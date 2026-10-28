# 最终源码设计审查

2026-10-23，结论：三个独立修复可作为声明范围内的候选；仅验证 PPU-01、单卡 BF16 Qwen3.5 value head，未提交、推送或创建 PR。PR base 未由用户指定，本轮以容器任务开始时的真实 HEAD/dirty 基线区分新增改动。

## 身份与继承改动

Plugin HEAD `06014201f8ea8cd7092a56a945d8fc7998c5a46c`，继承 OCR 的 dirty diff 哈希 `52aee2ba258189339f395aa566c88b661c3b0d369defceeaae8f0272eb1aa0bc` 未变。FlagGems 按 profile 从干净 `367d19367880eaf8843449abe11db4cfb7d47e03` 同步至 `722854072a3329c6c33ea2850afe368c9b4f63bc`，再作 clone 注册修复。FlagGems-vllm `db220e684094896c0e4a038bb2a44ab6e8c95aea` 干净不变。

vLLM 源码 `ee0da84ab9e04ac7610e28580af62c365e898389` 保持干净，安装目录 1886 个 Python 文件与任务基线逐一哈希一致。完整 diff、未跟踪文件、任务专属 patch、实际导入路径和 checkpoint 全文件哈希保存在远端 `04-runs/source-review-final-20261023/manifest.json`，没有 PYTHONPATH。

## 逐文件职责

| 文件 | 必要性与影响 |
| --- | --- |
| FlagGems `src/flag_gems/__init__.py` | clone 注册使用正确嵌套 pair 和设备专用 Autograd fallthrough，保留 CPU 原生语义；见 002。 |
| FlagGems `tests/test_clone_registration.py` | CPU 梯度隔离、PPU FP32/BF16、布局、变输入 graph 回归。 |
| Plugin `vllm_fl/worker/worker.py` | 两处类型声明/判断接受既有 AsyncModelRunnerOutput，与只读 vLLM 当前接口一致；见 003。 |
| Plugin `tests/unit_tests/worker/test_pooling_output.py` | async pooling、同步结果、None、PP 中间张量发送选择；旧实现负例与真实请求错误一致。 |
| Plugin `vllm_fl/ops/vision_position.py` | FP32 双线性插值，经正常 PyTorch/FlagGems dispatch 使用已有 upsample 算子，保持 merge/多帧顺序；见 006。 |
| Plugin `vllm_fl/models/qwen3_5_vl.py` | 继承原生 dense VL，只替换视觉组件；原生无视觉工厂，适配约 30 行构造，复用全部 forward、语言主干及权重协议。 |
| Plugin `vllm_fl/__init__.py` | 正式 lazy ModelRegistry 注册 dense Qwen3.5 VL shim；不按路径或服务名分支。 |
| Plugin `tests/unit_tests/worker/test_vision_position.py` | 独立四角 oracle、CPU/PPU、FP32/BF16、非法网格和两次变输入重放。 |

没有吞异常、隐藏重试、复制完整上游模型或绕过 dispatch。编译 backend 选择在本模型启动配置中，不改公共平台默认。三个修复可分开提交；用户没有授权提交。

## 验证矩阵与限制

最终实际源码：Plugin 9 passed，FlagGems 3 passed，日志/XML 分别为 `04-runs/final-plugin-tests.*` 与 `final-flaggems-tests.*`。CPU 守卫与浮点 oracle、PPU eager/graph、完整双图模型、异步输出、4/8 并发均验证。Qwen3.5 文本模型、MoE 和其他 VL 模型的注册保持原状；generation 的完整 LM head、其他实际平台、量化及 TP/PP 多卡通信未执行，不能宣称已验证。PP 选择逻辑由单测覆盖，实际多卡通信保持原代码。

正式性能与完整数据集指标未执行。该限制不妨碍本次 value-head 推理功能结论，但不支持 optimized 或完整正式验收。各补丁退出条件分别在 002、003、006、007 中记录。审查绑定当前 source-review-final 的任务差异及部署指纹；后续产品源码变更需重验。
