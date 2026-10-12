# 适配问题索引

- [001：mx-59 的 MoE 调用迁移至 FlagGems-vLLM](001-mx59-moe-flaggems-vllm.md)：
  完成现有容器的代码迁移与 20 项局部回归；完整模型验收未执行。
- [002：完整 MoE 与分阶段性能对照](002-full-vs-staged-moe.md)：10 种 token 数的
  eager/graph 数值与延迟比较通过；完整入口可用，性能随 shape/config 改变，不保证全部加速。
- [003：三个场景的端到端优化](003-e2e-optimization.md)：15文件已安装，196项回归及
  两个TP rank的实际路径采集通过；三场景吞吐提高21.3%/65.2%/49.0%，最终脚本和
  当轮正常prefix/align配置已验证并运行。4K/64K P99 ITL上升，正式精度与新镜像未验收。
- [004：Plugin 兼容分支更新](004-plugin-compatible-release-upgrade.md)：更新至
  release/0.2@8b059122，保留35B独立MoE/GDN补丁；471项局部检查与4个正确短响应通过。
  8010恢复用户现场prefix-disabled/黑名单配置，非003性能配置；新版本端到端性能未测。
