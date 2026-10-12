# FlagGems W8A8 大批次错误复现

验证日期：2026-09-04。主机PPU-07，运行容器hy4，PPU-ZW810E capability80；torch2.10.0，vLLM0.24.0（直接复现不需要vLLM/plugin）。
镜像：`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`。
FlagGems：`8416e6dab471451cc437aac3896fdc382dce382e`，master/origin/master clean；与服务原版`60d04309`的`src/flag_gems/fused/fused_moe.py`字节相同，SHA256 `a780da6348ba611640b546b47c60b79baa1312094386ce8f49d99d0d8e4750af`。

## 直接复现

在本目录执行，`repro.py`无需加载模型权重。固定seed20260904；E256、M8192、K6144、I128、top8；x BF16 contiguous、w1[256,256,6144]/w2[256,6144,128] INT8 contiguous；F32 channel scales0.002/0.003、routing F32，dynamic per-token INT8。只比较前32行CPU参考以节省CPU工作量，eager/graph覆盖同一大batch。

```bash
TEST_BATCH=8192 PYTHONDONTWRITEBYTECODE=1 python3 -B repro.py
TEST_BATCH=8192 TEST_GRAPH_ONLY=1 PYTHONDONTWRITEBYTECODE=1 python3 -B repro.py
```

预期：与CPU INT8量化→整数点积/反量化→fused SiLU→动态量化→down GEMM→加权sum一致，atol0.003/rtol0.04。
实际：eager最大绝对误差139460608，196600/196608元素超阈值。脚本应以AssertionError退出（不是成功结果）。graph独立结果见同目录执行记录。

## 消融（仅修改测试进程内常量，不修改源码/模型服务）

```bash
TEST_BATCH=8192 TEST_DISABLE_MOE_OPT=1 python3 -B repro.py
TEST_BATCH=8192 TEST_DISABLE_MOE_OPT=gemm python3 -B repro.py
```

同时关闭large-M GEMM tuning与direct_sum：eager/graph最大误差均0.0009765625；仅关闭GEMM tuning保留direct_sum：均0.00390625，仍满足逐元素混合容差。
根因线索：`_get_config_dtype_str`没有W8A8分类，BF16输入使INT8权重路径被判为plain-half，4096以上进入half GEMM fast path。该优化不能漏用INT8 scale。不要将修复做成全局禁用BF16优化或切换vendor。

ATen拦截开/关都能复现大误差，故无需ATen上下文即可提交此问题。M32直接调用eager/graph通过。生产插件拟仅在W8A8适配器内按2048 token分块调用原FlagGems，避免进入错误优化；不改变模型上下文、调度器batch上限及vLLM源码。
