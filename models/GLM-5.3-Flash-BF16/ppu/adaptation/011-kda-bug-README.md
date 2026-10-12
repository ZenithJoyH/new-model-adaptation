# FlagGems-vllm KDA / PPU 自动选择不支持的 TLE

核实日期：2026-09-04。主机 PPU-13，容器 glm5.3-flash。
镜像 hy4-ppu07-snapshot:20260903，sha256:29a6712e24ca8e758ac8b33d3412892f0541bff108e2c057445fa671578237f6。
设备 T-Head PPU-ZW810E96GiB；CUDA_VISIBLE_DEVICES=0。
Python3.12.3（GCC13.3.0），Torch2.10.0（PPU版），Triton3.6.0（PPU backend），vLLM0.24.0（复现无需导入vLLM）。
FlagGems-vllm main@5865ed53b183e6d3aff69ad1823622a11679d257；
FlagGems master@71d3736797ed2cefc23cddc075179156343a785f。

## 复现

```bash
cd /bug/flaggems-vllm-kda-ppu-5865ed5
CUDA_VISIBLE_DEVICES=0 python3 repro.py
```

随机种子5304。q/k/v/raw gate: contiguous BF16 [1,33,4,128]，stride [16896,512,128,1]；
beta: contiguous BF16 [1,33,4]，stride [132,4,1]；
initial_state: contiguous FP32 [1,4,128,128]；A_log FP32 [4]，dt_bias FP32 [4,128]。
scale=None，output_final_state=True，lower_bound=-5，cu_seqlens=None；其余为公共接口默认参数。

预期：支持 PPU 的 eager 推理，与脚本 CPU FP32 逐 token reference 接近。
实际：HAS_TLE_KDA=True，auto 选择 generic TLE，首次 eager 调用编译失败：
`NotImplementedError: unsupported TLE feature on the 'ppu' backend: tle.gpu.copy.tensor_descriptor, tle.warp_specialize`。
根因：仅检测 TLE 可导入/版本，没有过滤 PPU 编译器不支持的 TLE 能力。
已在上述 /bug 路径重新运行并确认同一错误。不是模型服务、插件或权重问题。

graph 独立模式：`CUDA_VISIBLE_DEVICES=0 python3 repro.py --graph`，当前默认路径在 eager warmup 即失败，尚未到 capture。
库提供 plain-Triton 选择：`FLAGGEMS_CHUNK_KDA_BACKEND=triton CUDA_VISIBLE_DEVICES=0 python3 repro.py --graph`。
此选择仅用于分离 backend 问题，不能用其测试替代默认 auto 缺陷证据。

数值检查固定门限 rel RMS < 0.01，atol=.004、rtol=.03，包含 output 和 FP32 final state；
`--varlen` 使用 [17,16] 分段和 int64 cu_seqlens [0,17,33]，graph replay 更新分段和输入。

## 第二个已复现问题：变长 graph 的陈旧 metadata

```bash
cd /bug/flaggems-vllm-kda-ppu-5865ed5
CUDA_VISIBLE_DEVICES=0 FLAGGEMS_CHUNK_KDA_BACKEND=triton python3 repro.py --graph --varlen
```

上述命令已在 /bug 路径执行。初始 [17,16] eager 通过，output rel RMS=.0035998，state=.0030002。
capture 后将原地址 cu_seqlens 更新为 [0,16,33] 并改变 q/state，首次 replay 输出 rel RMS=.170867，max_abs=.0214372，断言失败。
源码 `ops/FLA/index.py` 的 `prepare_chunk_indices`/`prepare_chunk_offsets` 使用 tensor_cache；
warmup 的 chunk table 不随同地址 tensor 的内容变化而重建，导致新分段最后一个 chunk 缺失。
固定输入的 warmup/capture 成功不能证明动态 replay 正确。
同一脚本不加 --varlen 的 plain-Triton eager 和两次 graph replay 均通过：输出 rel RMS 约.0037，state约.0032。
