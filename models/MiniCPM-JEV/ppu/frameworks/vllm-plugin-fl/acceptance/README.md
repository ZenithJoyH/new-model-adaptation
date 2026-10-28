# 适配验收索引

2026-10-23，推理功能实测通过，正式整体验收未完成。详见[执行模式与交付](execution-mode.md)。

| 项目 | 当前结论 |
| --- | --- |
| eager / PIECEWISE | 原生概率、固定参考、token、变输入 graph 通过 |
| 4/8 并发与图像消融 | 通过，原始结果留在批准工作根 |
| 最终启动器与镜像内客户端 | 实际启动、就绪、24 请求及原生进程/端口取证通过 |
| 源码审查 / vLLM 未变 | 新贡献规范逐块复审通过：Plugin 26 项、FlagGems 4 项；vLLM 未改，详见 [010](../adaptation/010-adaptation-consolidation.md) |
| 正式 sanity / 全量精度 / 性能 | 未完成；classify 浮点响应需匹配的比较器、配置与场景 |
| 镜像打包及新镜像运行 | pending，未执行 |

正式后续步骤不以自定义小集合结果替代原生比较器或完整报告。原始失败均保留，未放宽 0.005 概率容差。功能回执位于工作根 `04-runs/framework-functional-20261023/`；后续工作使用新 run 并绑定真实服务身份。

2026-10-23 新贡献规范复审已覆盖 Plugin、FlagGems、FlagGems-vllm 及只读 vLLM。Plugin 面向用户指定的上游 main `f41b7de8`，FlagGems 单独按 master `e510c6bb` 准备干净候选补丁，均通过固定基线 apply-check。逐文件/逐块必要性、增删统计、测试矩阵、PR 草案和限制见 [最新源码审查](../adaptation/010-adaptation-consolidation.md)；原始证据在 `04-runs/pr-review-20261023-1/`。本轮仅补强四个测试文件，产品代码保持与已验证服务一致，未提交或创建 PR。此结论为声明范围内 PR 候选，不代表目标分支完整 CI、其他硬件或正式整体验收通过。

原生 `adapt_model.py --check-only --verify-records` 的 execution-mode gate 已在目标容器中通过，直接读取真实远端 artifacts，并复核 architecture/environment/adaptation 前置回执。输出保存为 `04-runs/framework-functional-20261023/native-gate.log`。原生 delivery_manifest 工具生成的五类清单与交付清单一致。

本地 `audit-workspace` 对 MiniCPM-JEV 无发现；全仓库仍有两处既有的 XingChen4-29B-A4B 链接失效，未修改无关内容。审计仅检查本地结构，远端通过结论来自上述原生 gate 与实测产物。

收尾保护性检查发现，源 `minicpm-ocr` 容器内的 API/Engine PID 相对起始记录已有变化，当前有 8011/9999 服务；容器 StartedAt 仍为 2026-10-21。本任务仅对其作只读检查，未停止、重启或修改这些服务。最终事实保存在 `04-runs/framework-functional-20261023/final-host-state.json`；不宣称旧服务进程全程未变化。
