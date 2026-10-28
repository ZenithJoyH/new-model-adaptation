# TORCH_SDPA 实际算子调用取证

2026-10-20，H100-149，容器 `minicpm-ocr-flagos-allgpu`。结论：当前视觉 `TORCH_SDPA` 使用 PyTorch 的接口和 dispatch，但 attention 计算实际进入 FlagGems，并执行其 Triton `_attn_fwd` kernel。此结论来自完整 OCR 请求的原生 profiler 调用链与 CPU/GPU 关联，不依赖注册表或手动 `use_gems()` 小算例。

## 取证范围

在当前容器、当前已安装源码中启动 GPU1/8012 独立诊断实例，正常执行 FL worker 的算子注册，没有手动启用或替换 dispatch。模型、最大长度262144、`FULL_AND_PIECEWISE`、`TORCH_SDPA` 与生产部署一致；诊断增加 torch profiler，并按仓库规定使用 `--no-enable-prefix-caching`。生产 GPU0/8011 服务没有重启或改配置。因此这是同一安装环境的实际端到端调用证据，不是对生产 PID 的在线插桩，也不是正式性能测试。

服务就绪后才启动 profiler，依次请求冻结的 `small-4x` 和 `invoice-16x`。两条请求均 HTTP200，文本和生成 token ID 均与冻结 HF 参考一致。trace 包含1,255,634个事件，其中1,173,281个 Python 调用事件；证据使用原生 `torch.profiler(with_stack=True, record_shapes=True)` 的 Python parent ID，以及 CUPTI 的 External id / CUDA correlation。

## 实际调用链

原始 trace 中的一条视觉调用按父子关系展开如下：

```text
MMEncoderAttention.forward_cuda
  → _forward_sdpa
  → vit_torch_sdpa_wrapper → torch.ops.vllm.torch_sdpa_wrapper
  → torch_sdpa_wrapper → apply_sdpa
  → torch.nn.functional.scaled_dot_product_attention
  → aten::scaled_dot_product_attention
  → aten::_scaled_dot_product_cudnn_attention
  → /opt/FlagGems/src/flag_gems/ops/_scaled_dot_product_cudnn_attention.py:25
  → /opt/FlagGems/src/flag_gems/ops/attention.py:880
      scaled_dot_product_attention_forward
  → cuLaunchKernelEx
  → GPU kernel: _attn_fwd
```

具体关联样例：Q/K/V均为BF16，形状 `[1,16,1012,72]`；CPU执行线程为5950。child aten事件的 `External id=747`，CUDA Driver API `cuLaunchKernelEx` 的 `External id=747, correlation=1613`，GPU `_attn_fwd` 的 `External id=747, correlation=1613`。launch时间落在 FlagGems forward 的 Python调用区间内。FlagGems wrapper的 Python id为68792，其子 forward id为68844。故这里的 `cudnn` 是 aten接口名，不能据此认定实际执行了原生 cuDNN attention kernel；当前实际 kernel 为 FlagGems `_attn_fwd`，其源码入口在 `attention.py:178`，launch在954行。

| 请求期间事件 | 次数 |
| --- | ---: |
| `aten::scaled_dot_product_attention` | 61 |
| `aten::_scaled_dot_product_cudnn_attention` | 61 |
| FlagGems `_scaled_dot_product_cudnn_attention` Python入口 | 61 |
| FlagGems `scaled_dot_product_attention_forward` | 61 |
| 与上述 child aten一一关联的 GPU `_attn_fwd` | 61 |

其中34次经过 vLLM 的 `vit_torch_sdpa_wrapper → apply_sdpa`，其余27次是视觉模型内部直接调用 SDPA。全部61次均验证到上述 FlagGems forward和对应GPU kernel；没有把解码器的 `kernel_unified_attention` 混入此计数。本次结论只覆盖所测请求中的 SDPA，不表示整个模型的所有算子均由 FlagGems执行。

## 原始证据与复核

以下路径均位于批准根 `/public/flagos/jinghao/MiniCPM-OCR/flagos`，在主机和当前容器内同路径可见。运行目录为 `04-runs/sdpa-calltrace-v2-20261020/`：

- `traces/rank0.1792478413970535362.pt.trace.json.gz`：原始 trace，SHA256 `2007a22f734f4df56981200ad9877315b20d52a73da23dcc838b5ec3b2d54f46`。
- `callchain-proof-all.json`：61条完整 Python父子链、CPU outer/child事件、Driver launch及GPU kernel的一一对应关系。
- `callchain-summary.json`：计数、代表性调用链、源文件哈希、生产服务前后身份、请求结果及诊断清理结果。
- `configuration.json`、`server.log`：实际诊断argv、环境与运行配置；仅诊断关闭prefix cache。
- `results.json`：两条冻结请求的响应、参考和逐token比较。
- `source-verification.json`：13个产品文件、vLLM2449文件、FlagGems3684文件、FlagGems-vllm398文件，均与原部署冻结清单一致。
- `production-before.json`、`production-after.json`、`cleanup.json`：生产API PID3699/start_ticks359670不变，前后health200；诊断PID5550及其两个子进程已清理，无剩余活跃诊断进程。容器保持运行。生产启动脚本SHA256仍为 `066993c36c83080e7d0aeb3fc6c01a1b1c03fcb3b5d10f9888ecdc9e051be5b7`。

解析器为 `02-issues/sdpa-callchain-v2.py`。首轮观察器在导入阶段逐事件检查共享文件系统标记，开销过高，已停止该独立实例并保留 `04-runs/sdpa-calltrace-20261020/`。第二轮自定义 `sys.setprofile` 侧录没有产生日志，不用作调用证据；原生profiler已提供完整Python事件。首次关联解析器仅检查CUDA Runtime事件而漏掉Triton的CUDA Driver事件，因此校验失败；保留 `02-issues/sdpa-callchain.py`，修正后的v2解析器同时检查两类事件，61条均通过关联校验。没有重跑或改写原始trace。

本次不改变部署fingerprint、原有验收回执或正式精度/性能状态。当前部署仍为 `27581af3bea2ad94f559dd65da49bd84420a65ce0dcf8e4412bc253964ef4940`。
