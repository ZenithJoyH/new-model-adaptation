# W8A8 CPU / PPU 量化边界比较

验证时间：2026-09-04。PPU-07 / hy4，PPU-ZW810E capability 80，torch 2.10.0；
FlagGems 051f303（修复内核）与 842b19d（仅调整测试样本）生产源码相同。
完整镜像、软件环境及最初大 M 缺陷记录见 `/bug/hy4-w8a8-large-m-raHNmgWY/README.md`。

`original_test_fused_moe.py` 保留 051f303 的原始随机测试，不使用模型服务或插件。
固定 seed=20260904，M=4095/E=8/K=128/I=128/top-k=2，FP16 激活、INT8 权重、
F32 非单位逐通道 scale，连续张量，动态 per-token 量化。eager 的 CPU 全输出比较
曾出现 36/524160 元素超出 atol=0.003、rtol=0.04，最大差 0.0458984375。

```bash
python3 -B -m pytest -q -x original_test_fused_moe.py -k 'large_m_accuracy and eager and dtype0 and 4095'
python3 -B diagnose_reference.py
```

逐阶段定位：第一次 INT8 量化已有 3 个值相差 1，scale 差约 1.86e-9。
使用设备实际量化数据作为 GEMM2 输入时，GEMM2 与最终输出和 CPU 参考逐位一致。
这与原来的漏用 scale、大批次误差上亿不是同一问题；不能将这个随机全链路
跨设备逐元素比较当作稳定的漏 scale 回归。仅固定第一轮输入 scale 仍有
第二轮量化/激活舍入敏感性，该尝试的失败样本保留在
`/bug/hy4-w8a8-rounding-aa3bxdvb/test_fused_moe.py`。

`test_fused_moe.py` 是定向 scale 回归：gate=32，up=code/4，SiLU 后中间值可精确
表示为 8*code，第二轮 scale=8；保留非单位、逐通道权重 scale。原容差不变。
20 项 FP16/BF16、M=32/4095/4096/4097/8192、eager/graph 和改变输入 replay 通过。
将 dtype 分类仅在独立进程中恢复为原有错误逻辑，BF16/M4096 仍有
524180/524288 元素超差、最大误差 884736，证明定向样本仍能检出原缺陷。
这不宣称所有随机 FP16 量化舍入差异已经消失，也不替代整模型精度验收。
