# 004：当前 GDN demo 的实际 FlagGems / ATen 调用

2026-10-27，应用户要求核查开启 GDN 后是否还有其他 FlagGems ATen 替代实现实际执行。范围：PPU-01 / minicpm-jev / 物理 PPU3 / Torch-FL，当前 value checkpoint、BF16、SDPA、eager；control.mode=agent。未更改产品源码、模型或服务。

现场核对当前容器 ID `0ee63bbcec91264acfef52636b7a2983d53bf31ccb976c808fe827646673e069`，运行中，`/mnt:/mnt` RW；工作根为 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt`。PPU3 显存 15193/98304MiB，既有服务 PID2185930 保持运行。当前 demo SHA-256 见 003。实际导入 `/workspace/PyTorch-Plugin-FL/torch_fl/__init__.py`；cuda_alias_active=False。

方法：复用交付目录中的原 demo load/score 与已安装 GDN helper，加载后启用 18 层，s01 预热一次。在仅打分阶段通过 cProfile 跟踪 12 例顺序 bs=1 调用，通过 TorchDispatchMode 记录实际 ATen 入口及输入张量 dispatch keys；另保存这些 ATen 入口的 CUDA 注册信息。模型加载、导入和预热不在 trace 中。本轮为调用归属诊断，不报告性能或正式验收结论；Torch-FL eager 无跨请求前缀缓存，未操作 vLLM 服务。

结果：

- FlagGems 公共融合算子 `fused.chunk_gated_delta_rule.chunk_gated_delta_rule` 共 216 次，即 12×18。
- `flag_gems/ops/` 以及平台后端 `ops/` 下实际进入的函数为空；全部 FlagGems 来源文件仅为 `fused/chunk_gated_delta_rule.py`、`fused/FLA/` 六个相关文件及 `utils/libentry.py`。未发现其他通用 FlagGems ATen 替代实现。
- 融合算子内部每阶段均调用 216 次：`chunk_gated_delta_rule_fused_cumsum_kkt_solve_tril`、`recompute_w_u_fwd`、`chunk_gated_delta_rule_fwd_h`、`chunk_fwd_o`；另有调度、形状检查及 grid/libentry 辅助函数。这些不计为额外 ATen 算子。
- 跟踪期间张量分发键只有 CPU 和 CUDA 家族，无 PrivateUse1。例：`aten.embedding.default` 24 次，CUDA 注册为 ATen composite 实现；`aten.silu.default` 720 次，CUDA 注册为 ATen RegisterCUDA 实现；`aten.scaled_dot_product_attention.default` 648 次，为 ATen composite math 入口。不能仅凭入口统计判断其内部设备 kernel 数量。
- 服务 `/health` 仍为 ok、gdn_layers=18。

证据在上述工作根 `04-runs/gdn-aten-routing-20261027-1/score.pstats` 和 `routing.json`；后者 SHA-256 `7dbfbed17c5b0affc99f1e7279c8dacd4863c218d35161f0ed7c4ca76d1aceea`。原始执行日志为 `05-tmp/gdn-aten-routing-20261027-1.log`。首次调用因 Docker Go-template 与 Ansible 模板解析冲突，在远程执行前失败；改为读取 docker inspect JSON 后执行成功。

结论仅覆盖当前环境和这 12 例：除 GDN 融合算子及其内部实现外，没有实际观测到其他 FlagGems ATen 算子。PPU 配置中的 592 个 FlagGems、1445 个 CUDA 路由条目是 PrivateUse1 路由配置条目数，不能作为当前 CUDA demo 的实际调用统计。TorchDispatchMode/cProfile 为诊断工具；此次结果不代表其他设备路径、输入形状或未来版本。
