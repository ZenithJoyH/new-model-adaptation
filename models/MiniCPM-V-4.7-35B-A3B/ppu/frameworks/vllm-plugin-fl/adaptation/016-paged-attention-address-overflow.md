# 长生成触发 paged attention 地址溢出

## 范围与现象

2026-10-10，在 PPU-13 的 `minicpmV4.7-35B` 容器、8010 服务上运行
32 并发全量 GPQA。模型为 `/mnt/cpfs/models/MiniCPM-V-4.7-35B-A3B`，
TP2、BF16、`FULL_AND_PIECEWISE`，上下文 262144，前缀缓存开启。
末尾长请求已生成 80342 tokens、计算上下文 83232 时，设备报告
`_paged_attn_fwd` 非法内存访问，随后 Worker、Engine 与 API 退出；容器保持运行。

失败轮 `accuracy-opt-20261010-1623` 的原生 GPQA 严格结果为 160/198，
包含 1 个失败占位；后续 MATH-500 的 500 个请求全部连接失败，不能将其
原生 0 分解释为模型精度。ERQA 尚未发出请求。原始失败证据保留。

## 定位与修复

当前 BF16/head_dim=256 的实际链路为 Plugin → FlagGems-vllm 的
平头哥 paged Flash 包装 → 公共 `_paged_attn_fwd`。混合 GDN/attention
缓存的 K/V 页面元素步长为 278528。block table 提供 int32 物理页号；
旧内核在指针提升之前以 int32 计算页面偏移：

`7948 × 278528 = 2213740544 > 2147483647`，有符号回绕为 `-2081226752`。

直接修改实际安装文件
`/workspace/FlagGems-vllm/src/flaggems_vllm/ops/triton_unified_attention.py`，
将加载后的物理页号转换为 `tl.int64`，再参与 K/V 地址乘法。保留既有
tile、算子注册和 Plugin 调度；生产路径未加入 Torch 计算回退。

| 内容 | SHA256 |
| --- | --- |
| 修复前内核文件 | `29068646a592cb1db5bb96c04f696597649201d574824b76c83f1c3852b39eae` |
| 修复后内核文件 | `bc51583dc58e4ca5b35f83a548fb7adaa5977526520b8a687500b743065981cc` |

## 已完成验证

- 同一实际安装算子的低页号测试通过；高页号测试在旧内核上复现非法内存访问，
  修改后两者均通过，常量数据参考误差为 0。
- 新回归位于安装仓库的 `tests/test_triton_unified_attention_large_cache.py`。
  1/4 个 query token × 交错/连续缓存布局共 4 项，通过随机数据与 FP32
  Math SDPA 参考对拍，以及 CUDA graph 捕获和重放。
- 修复后短序列微测约 70–71 μs，Math SDPA 参考约 169–171 μs；
  该微测不包含修复前延迟，也不能证明整模性能变化。

完整证据位于批准的远端根目录
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B` 下：

- 失败轮：`04-runs/accuracy-opt-20261010-1623/accuracy-service.log`。
- 新轮：`04-runs/accuracy-opt-recovery-20261010-1733/`，含
  `paged-address-fix.json`、`paged-address-fix.diff`、前后复现日志、
  `offset-regression-tests.json`、`paged-fix-microbenchmark.json`、`fixed-source.json`。
- 复现脚本：`07-bugs/accuracy-opt-recovery-20261010-1733/paged-offset-repro.py`。

修复后的全量精度结论须绑定新轮原生结果及完成核验；上述算子验证本身
不构成正式精度验收，也不证明此前其他轮次乱码具有同一根因。

## 上游提交

2026-10-12，用户的 `ZenithJoyH/FlagGems-vllm:main` 原落后上游 79 个提交、
无独有提交，已快进同步至 `46a81d39732af0e1b0ef6c474e500591dfb2d124`。
修复单独提交至 fork 的 `fix/paged-attention-int64-offset` 分支，提交
`45bdac9a31892e4b879407a3b406b6a4f66004ac`，上游 PR 为
[flagos-ai/FlagGems-vllm #908](https://github.com/flagos-ai/FlagGems-vllm/pull/908)。

PR 相对上游仅有一个提交、两个文件：公共内核中的 int64 提升，以及既有
`tests/test_triton_unified_attention.py` 内新增的四个公共入口回归用例。
生产文件与本轮已验证版本哈希完全一致。新测试增加不同页面/输入的两次图重放和
末槽 NaN 掩码检查；源码分支不包含此前其他 MoE、attention 优化或启动脚本。

Black/isort/flake8、语法和 diff 检查通过，当前实际安装的 PPU 环境收集 18 项测试成功。
由于 GPU 0、1 正在执行其他满负载任务，这次 PR 准备未重新执行 GPU 功能测试；
保留此前相同内核的四项实机回归证据，新公共入口用例及 NVIDIA 执行待上游 CI 验证。
收集回执为远端 `04-runs/pr-paged-offset-20261012/collection.json`，
测试文件 SHA256 为 `090e901ef1ad101f79544092c6d6ac2afc2b3c81e9401c3367817575249841f2`。

同日创建上游 [issue #910](https://github.com/flagos-ai/FlagGems-vllm/issues/910)，
内容限于公开代码中的页偏移溢出问题与修复说明。PR #908 已添加 `Fixes #910`；
GitHub 返回的 `closingIssuesReferences` 已确认此关联，合并后自动关闭该 issue。
