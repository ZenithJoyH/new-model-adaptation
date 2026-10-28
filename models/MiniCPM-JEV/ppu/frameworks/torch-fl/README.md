# MiniCPM-JEV / PPU / Torch-FL

2026-10-26，PPU-01 / `minicpm-jev` / 物理PPU3，Transformers 5.10.4、BF16、SDPA、bs=1。已验证12例的局部GDN融合优化。完整12例预热后测5轮，共60次单样例延迟：原路径中位148.21ms、p90 195.36ms；优化后中位56.31ms、p90 89.28ms。12例整轮中位总耗时1.887819→0.765616秒，约2.47倍。计时包含输入读图/预处理、传输、前向和输出回传，排除加载、预热和profiling。

优化接口位于容器实际安装的 `/workspace/PyTorch-Plugin-FL/torch_fl/compat/qwen3_5_gdn.py`，显式启用，默认不自动改变demo行为：

```python
from torch_fl.compat.qwen3_5_gdn import enable_qwen3_5_gdn

# 原demo加载到PPU厂商CUDA设备后，在torch.inference_mode()内打分。
assert enable_qwen3_5_gdn(model) == 18
```

2026-10-26已按用户要求启动[在线评分服务](adaptation/002-transformers-online-service.md)：同一`minicpm-jev`容器、PPU3，监听`0.0.0.0:8331`，POST `/score`接收原图/渲染图/OCR文本，GET `/health`和`/docs`可用。服务常驻模型并显式开启18层GDN优化，12例HTTP对照和4并发正确性验证通过。启动器为容器`/opt/minicpm-jev-transformers/start-model.sh`及既有工作根`start-model.sh`，SHA-256 `37c40e4fbcc243b8481f1122e4b18b943c044d5f7cbbc94b07034d236f88bbb2`。Host PID2185930/容器PID38442，服务代码与demo副本在镜像内路径，权重外置/mnt；新镜像验证未执行。

只替换18层GDN的既有chunk callable；保持HF原dtype L2定义和FP32中间计算，恢复BF16输出。现有矩阵乘、SDPA、模型forward和权重未改。未支持条件保留原实现，支持显式恢复。18项回归和Ruff检查通过。最大参考误差0.004621146 < 0.005；未验证其他模型/硬件、训练或长上下文精度。

详细根因、失败实验、精确证据和逐块源码审查见[001：算子路由性能优化](adaptation/001-operator-routing-performance.md)。工作根沿用既有Transformers区域 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt`；本轮证据在 `04-runs/torch-fl-op-routing-20261026-1/`。这是experimental profile下局部性能实验，未执行正式验收、不标记optimized，未commit/push或创建PR。框架正式阶段回执不由这些计时结果自动刷新。
