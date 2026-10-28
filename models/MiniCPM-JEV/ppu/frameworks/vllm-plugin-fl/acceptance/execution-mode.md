# 执行模式与功能验证

2026-10-23，PPU-01 / minicpm-jev-vllm / 物理 PPU 1，部署指纹 `8ce80f553f0ab4dfbfe91bfb097c68c0bb995b3594fa60ce2930c4da73c8ed10`。固定 value-head checkpoint，BF16 主体、FP32 位置插值和分类头，LAST pooling，双图原生预算，prefix caching 开启，严格概率容差 0.005。

批准工作根为 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt/vllm-plugin-fl`。下表路径均相对此根。

| 实测 | 原始产物 | 结果 |
| --- | --- | --- |
| eager 原生 classify，12 样例两轮 | `04-runs/eager-fp32-head-native-20261023/` | 24 请求，max Δ 0.004417300，token/阈值侧全一致 |
| 显式 PIECEWISE / EagerAdaptor，两轮 | `04-runs/graph-eager-adaptor-native-20261023/` | 24 请求，同一 max Δ，真实运行日志命中 PIECEWISE |
| 4 并发，两轮 | `04-runs/graph-eager-adaptor-concurrency4-20261023/` | 24 请求全部对应、数值通过 |
| 8 并发，两轮 | `04-runs/graph-eager-adaptor-concurrency8-20261023/` | 24 请求全部对应、数值通过 |
| 双图均值色消融 / 恢复 | 上述 4 并发目录 `image-ablation.json` | s02 0.995437920 → 0.374200732 → 完全恢复 |
| 最终最小脚本、无调试配置 | `04-runs/final-launcher-native-20261023/` | 24 请求，同一 max Δ，原生 API 通过 |
| 镜像内客户端 | `04-runs/final-launcher-20261023/client-smoke.json` | s02 prob_1 0.995437944，237 token，调用成功 |

FULL → FULL_AND_PIECEWISE → FULL_DECODE_ONLY 均命中当前 vLLM pooling 能力守卫，详见 005；最终显式 PIECEWISE。Inductor 概率误差 0.005077541 超容差，使用 vLLM 原生 EagerAdaptor 保留 CUDA Graph 后通过，详见 007。7 个捕获尺寸为 1/2/4/8/256/512/1024；DEBUG 日志记录实际请求图分派，不以配置或就绪代替重放。更大的 batch 原生 fallback 是声明的覆盖边界。

最终服务 PID108830、start tick545358949、实例 `jev-691fe8280a691510fdd32c5e`，原生 `service_observation.py` 独立核验完整容器 ID、boot ID、命令哈希和监听 8330 端口，状态 verified；原始 observation 在 `04-runs/final-launcher-20261023/service-observation.json`。服务只监听 Host localhost。

最终启动器 Host/容器同路径 `<工作根>/start-model.sh`；镜像内交付副本 `/opt/minicpm-jev-vllm/start-model.sh`。SHA-256 均为 `4ba5cd978618c66d15ce52fcbe20060ea34f4c6dec9745b8cfbd6338c6deb616`，2026-10-23 语法、实际启动、就绪和样例实测通过。脚本不安装依赖、应用补丁、评测、清理或自动终止进程；必要参数用于任务语义、PPU 1/8330 资源选择、原生图模式、上下文与缓存目录。抽象 RPC 地址处理已复现的 Unix socket 路径上限，见 001。镜像内 source/lock/config/restore 材料和哈希见 `01-environment/delivery-manifest.json`；当前为 image validation pending。

此处为执行模式和功能验证，不代替完整数据集精度或正式性能。项目当前 sanity 比较器面向 reference_text，尚未为 `/classify` 的浮点响应提供匹配原生比较器；保持正式后续步骤未完成，状态上限为 functional。
