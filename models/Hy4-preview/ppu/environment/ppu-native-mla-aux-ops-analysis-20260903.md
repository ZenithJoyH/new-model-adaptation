# PPU 原生 MLA 辅助算子可行性分析

日期：2026-09-03  
目标：评估是否可让 HY4 sparse MLA 的 query concat、KV-cache write 和 sparse attention 全部走平头哥原生编译算子。

## 参考镜像

- 镜像：`egslingjun-registry.cn-wulanchabu.cr.aliyuncs.com/egslingjun/inference-xpu-pytorch:26.04-v2.1.0-vllm0.23.0-torch2.10-cu130-20260710`
- digest：`sha256:fb48fe779ca7b91741b0248cf6cda4ab3785c69dd91dfe88890c7cafdc2996ac`
- vLLM：`0.23.0+v0.2.0.ppu2.1.0`
- Torch：`2.10.0`
- PPU SDK：`2.1.0`，CUDA compatibility SDK 13.0
- `flash_mla`：`2.0.0+v0.1.0.ppu2.1.0`

该镜像不是通过 `flash_mla` 提供 cache write。`concat_mla_q` 与 `concat_and_cache_mla` 位于 vLLM stable-libtorch 扩展 `_C_stable_libtorch.abi3.so`，加载后注册到 `_C_cache_ops`：

```text
_C_cache_ops::concat_mla_q(
  Tensor ql_nope, Tensor q_pe, Tensor! q_out) -> ()

_C_cache_ops::concat_and_cache_mla(
  Tensor kv_c, Tensor k_pe, Tensor! kv_cache,
  Tensor slot_mapping, str kv_cache_dtype, Tensor scale) -> ()
```

对应源码位于 vLLM `ee0da84ab9e04ac7610e28580af62c365e898389` 的：

- `csrc/libtorch_stable/cache_kernels.cu`
- `csrc/libtorch_stable/ops.h`
- `csrc/libtorch_stable/torch_bindings.cpp`
- Python wrapper：`vllm/_custom_ops.py`

## 实测结果

在正确参考镜像、16 张可见 PPU 上运行：

```text
NATIVE_CONCAT_EAGER_OK
NATIVE_CACHE_EAGER_OK
NATIVE_CONCAT_GRAPH_OK
NATIVE_CACHE_GRAPH_OK
```

初次核查时，当前 `hy4` 容器没有 `_C_stable_libtorch*.so`。为验证 ABI，先从固定 digest 临时提取该扩展，不替换 vLLM，仅在 `hy4` 的独立 Python 进程使用 `torch.ops.load_library()` 加载。结果：

```text
HY4_LOADED_EXTENSION_EAGER_OK
HY4_LOADED_EXTENSION_GRAPH_OK
```

该临时扩展和测试文件随后已删除。该结果证明参考镜像的 stable ABI 扩展可在当前 `hy4` 的 Python 3.12、Torch 2.10、PPU SDK 2.1.0、vLLM 0.24 环境加载，并正确执行 BF16 eager/graph。

## 当前落地状态

根据用户随后提出的交付要求，已将固定 digest 中的 `_C.abi3.so`、`_C_stable_libtorch.abi3.so` 和 `_moe_C.abi3.so` 放入当前插件源码的：

`/workspace/vllm-plugin-FL-hy4-preview/vllm_fl/dispatch/backends/vendor/thead/lib/`

来源、版本、digest、大小和 SHA-256 保存在同目录 `PROVENANCE.md`。插件在 `vllm_fl.register()` 的 PPU 平台初始化早期加载三个扩展，并在 fallback schema 注册前完成原生 op 注册；非 PPU 平台不加载。一次晚加载实验曾因 fallback schema 已存在而触发重复 `def()`，该方案已撤回并改成早加载。

当前 `concat_mla_q`、`mla_kv_cache_update`、BF16 Indexer cache write/decode top-k 和 dynamic per-token INT8 quant 均解析到 `vendor.thead`，已通过数值、eager 和 graph 聚焦测试。`bf16_paged_mqa_logits` 仍走 FlagGems；MoE 原生 SO 仅完成符号和 schema 收集，尚未接入正式 dispatch。完整边界和哈希见 [原生算子完整清单](native-operator-inventory-ppu07-20260903.md)。

## 可行性结论

HY4 sparse MLA 子链可以全部使用 PPU 原生编译路径：

1. `concat_mla_q` → `_C_cache_ops.concat_mla_q`
2. `concat_and_cache_mla` → `_C_cache_ops.concat_and_cache_mla`
3. sparse attention → `flash_mla.flash_mla_sparse_fwd`

但“整个模型的所有算子均为平头哥原生算子”尚不能成立。full Indexer 的 cache write 和 decode top-k 已原生化，BF16 paged logits 仍使用 FlagGems；dense W8A8 仅 activation quant 已原生化，scaled-MM 与 routed MoE expert 主链仍需逐项验证。

## 长期交付建议

当前把参考镜像二进制放入插件源码是用户指定的交付形式；仍需保留来源和校验信息，并在长期版本中优先收敛 ABI 和发布方式：

1. 使用平头哥提供的、与当前 vLLM 0.24 对齐的 PPU vLLM wheel/stable extension。
2. 若暂时没有匹配 wheel，在不修改 `/workspace/vllm` 源码的前提下，用当前 clean vLLM 0.24 revision 和 PPU SDK 构建 `_C_stable_libtorch.abi3.so`，作为镜像依赖安装。
3. 当前跨 vLLM 0.23/0.24 复用必须继续固定 digest、校验和与兼容矩阵，不能把一次 ABI 测试视为长期兼容承诺。
4. 保持平台注册早期显式加载；T-Head backend 的 `concat_mla_q` 和 `mla_kv_cache_update` 只调用 `_C_cache_ops`。
5. 保持 vendor-first policy 和明确 fallback；正式“全原生 MLA”验收时应增加严格模式，避免原生失败后静默回退。

## 可复现实验

- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-pytorch-native-concat-cache-mla.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-lingjun-vllm-cache-source.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/run-ppu07-reference-image-native-cache-test.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test-ppu07-hy4-reference-stable-extension-abi.yml`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_ppu_native_concat_and_cache_mla.py`
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_loaded_ppu_stable_cache_extension.py`
