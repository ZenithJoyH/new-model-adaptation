# MiniCPM-V-4.7-1B / PPU-13 / vllm-plugin-fl 环境分析

2026-10-08 FlagGems 安装组件的 split-KV 修复、影响面及上游 PR 审查见 [专项修改审查](flaggems-splitkv-pr-review.md)；以下为原始环境基线，不代表当前组件哈希或正式验收身份。

核对日期：2026-09-28。目标仅为 inventory 别名 `PPU-13` 上运行中的 `minicpmV4.7-1B` 容器；`./scripts/connectivity-check --limit PPU-13` 成功，主机名为 `bm-aliyun-wlcb-zonea3-c-810e-96g-10-13`。同机其他容器属于独立工作负载，本任务不操作。

## 身份与路径边界

| 项目 | 已核实值 |
|---|---|
| Host / 容器 | `PPU-13` / `minicpmV4.7-1B`，容器 ID `a8861de7fe732bf0e2e469976d0736a17f90bc7de96c65986b5e1e5745bcbf22`，运行中 |
| 镜像 | `sha256:f222f9a173b320d799ada39791979828f6abc5218063616b7efdf05873c52c1f` |
| 已批准工作根 | Host 与容器均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B`；容器 `/mnt` 来自 Host `/mnt` 的 bind mount；两侧目录 `stat` 均为 `41:12343819932`，开始时为空 |
| 外部权重 | Host 与容器均为 `/mnt/cpfs/models/MiniCPM-V-4.7/weights/1b`；`config.json` 的设备号:inode 均为 `40:1103894`，SHA-256 `0d2f763cf97a0a5beec8f52b13b4cbf7262680df6fd35e1f0e48c09288c4bb12`；`model.safetensors` SHA-256 `3b801e149bc6dab4bb8c4cf61bed4197cce810f6c2f523f60b266459f809251c`；外部权重只读 |
| 模型参考实现 | `modeling_minicpmv4_7.py` SHA-256 `398ec5cf6a8b31d136fbcaf3671c1be2bc25d3ffc77aa457feec185d26999bd2`；`mrope_minicpmv4_7.py` SHA-256 `cf6d70719e9e58bbab40612e56efeb6fb5cb7019b0aa780e1536aedb5023b1c3` |
| Plugin | editable 包 `vllm-plugin-fl 0.3.0rc2.post1+g3a27a6fb2`，实际导入 `/workspace/vllm-plugin-FL/vllm_fl/__init__.py`；Git `main@3a27a6fb2d514cdf55c00481bf813225dac63319`，`origin/main` 同 revision，工作树干净。该现有产品树是 profile 声明的可写范围 |
| vLLM | 安装包 `0.24.0+empty`，实际导入 `/usr/local/lib/python3.12/site-packages/vllm/__init__.py`；现有 `/workspace/vllm` Git `ee0da84ab9e04ac7610e28580af62c365e898389` 干净；安装包与源码 checkout 的文件对应关系尚未证明，均保持只读 |
| FlagGems | 安装包 `5.3.5`，实际导入 `/usr/local/lib/python3.12/site-packages/flag_gems/__init__.py`；现有 `/workspace/FlagGems` Git `master@1a38df24f72ca5a4a6a24650b5d66356709750ba`，跟踪 `origin/master`，工作树干净。安装包不是 editable，checkout 同步后不能自动视为运行时已更新 |

## 设备与软件

`./scripts/accelerator-check --limit PPU-13` 的 `ppu-smi` 查询成功。容器内 `ppu-smi -L` 可见 16 张 `PPU-ZW810E`，`torch.cuda.device_count()` 亦为 16。Host `PPU-SMI 1.28`，驱动 `2.1.1-rbd225`；容器内 PyTorch `2.10.0`、Transformers `5.8.1`、Triton `3.6.0`。当前未见本容器中的 vLLM 服务进程。目标先选单卡 TP1；实际占用、可用设备和内存须在启动前再次核实。

配置声明 `MiniCPMV4_7ForConditionalGeneration`、`model_type=minicpmv4_7`、`mrope_mode=canvas`、BF16；文本骨干为 `qwen3_5_text`，`max_position_embeddings=262144`。按 profile 初始服务规则计算的 `--max-model-len` 为 50000，后续如果真实运行受限，必须单独诊断并记录，不静默缩短。架构细节见模型级 `architecture-and-inference.md`；与 NVIDIA 检查的权重 SHA 相同，但 PPU 实现和执行结果需独立验证。

## 适配路径与当前差距

当前 Plugin 使用 `vllm_fl:register_model` 扩展 vLLM 模型注册，`vllm_fl/models/` 已有模型专用 shim；vLLM 0.24 的 `minicpmv4_6.py` 可参考视觉塔、merger、Qwen3.5 文本骨干及权重映射，但其 M-RoPE 将三个通道复制为顺序位置，不能满足 4.7 canvas 语义。当前 Plugin 没有 4.7 注册。模型专用语义应放 Plugin model adapter 和正式注册入口；PPU 算子差距只能在核实当前 FlagGems 与 Plugin dispatch 后选择实现，不先把 NVIDIA 的故障或 workaround 当作 PPU 事实。

现有 `docs/troubleshooting/` 与 MiniMax-M3/PPU-13、MiniCPM-V-4.7-1B/NVIDIA 记录已经检索。相关经验是候选假设：共享关键词无法证明完整失败签名相同；当前尚无 PPU 1B 实际模型运行失败签名。Plugin 的 `README.md` 提供版本、扩展与测试入口；checkout 内未发现 `AGENTS.md` 或 `CONTRIBUTING.md`。仓库级贡献规则见 `docs/plugin-contribution-policy.md`。

用户明确授权后，已核实干净的 `master`/`origin/master` 并通过 Ansible 在目标容器中执行 `git fetch origin master` 和 `git pull --ff-only origin master`，从 `1a38df24f72ca5a4a6a24650b5d66356709750ba` 快进到 `80d0000d93dad55320df06687eb088a5b6dad07d`，完成后工作树仍干净。本次上游差异仅为 `.github/workflows/backend-test.yaml`，运行中的非 editable FlagGems 安装包保持 5.3.5，未发生运行时代码变更。

工作根七个规定目录已经通过 Ansible `--check --diff` 后创建。下一步实施模型专用注册和 canvas 位置桥接，先做导入与 CPU 契约检查，再逐步做 PPU eager、full graph、必要时的 decode-full。每轮原始结果放本工作根的 `04-runs/`，不写入本地模型目录。

## 原生环境取证

基线部署身份保存于 `PPU-13:/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/01-environment/deployment-identity.json`，文件 SHA-256 为 `64208e4d8db34d9a420dee3e953ce7ee7757e94509a4e95cd8979ba5d3663e75`，规范化 JSON 的部署指纹为 `c18b01be07806a7326b1f7f9ebfec599af339c1c9c725ca167bb6ade85137daa`。它记录的是尚未启动模型服务的基线；产品源码或服务配置变化后必须重新取证并更新绑定，不把旧身份用于后续运行。

容器内原生只读探针由上述工作根的 `01-environment/environment-probe.py` 执行，结果为 `04-runs/env-ppu13-minicpm47-1b-20260928/environment-probe.json`，SHA-256 `a4e3f153258e33d8a9af22ff93f7be01082b46a91dab83130d25ed62e7bccfd0`。探针重新核对权重/config/tokenizer 哈希、工作根映射、实际包导入路径、三棵源码树 revision 和干净状态，14 项断言全部为 true；Host 侧重新读取保存文件也确认 `status=passed`。环境取证不声明模型推理通过。

本轮逐 Host `environment_identity` 原生回执为同一 run 目录下的 `framework-check.json`，SHA-256 `0420842a10ea280a6d895196ab544ccfba9a1f28cd31d4fee3e8df029c3a0d7d`。Host 与容器都重新读取了该文件，scope 为 `PPU-13`、结果为 `passed`，引用上述两份文件及真实 SHA-256。

## 2026-09-29 最终源码与服务身份复核

实施后重新核对同一个 Host、容器、权重和批准工作根，没有移动外部权重或更换容器。新部署身份为 `01-environment/deployment-identity-v2.json`（文件 SHA-256 `b211d534f97ac4225b07b3da738fe4e261ea2ed89ac9eea851f95f79d33c1a18`，规范化内容指纹 `64db21546a04caa0b6a4d3fb711bda02ceaa4487a94ee0ae929d4f3a8c2c61e3`）。它以原有权重、tokenizer、镜像、vLLM 和 FlagGems 身份为基础，增加实际 Plugin 四个产品文件的 SHA-256 与正常服务配置。此指纹不含服务 PID，因此随后仅为正式性能切换前缀缓存时仍可核对同一基础部署。

`01-environment/current-state-v2.py` 在目标容器内重新读取三份权重/配置哈希、工作根和权重的设备号与 inode、三棵源码树 HEAD/工作树、Plugin 四个文件哈希和导入路径、服务进程身份、端口健康、模型 ID、decode FULL 7/7 图捕获及前缀缓存状态。27 项断言全部通过；原始输出在 `04-runs/env-final-v2-20260929/probe.json`，SHA-256 `5ba0a0f4e590f70bf897b6529491f914ca29d89cf4fec52f37d01c231ef094cb`。当前 Plugin 工作树恰有本任务两处跟踪修改和四个未跟踪文件，`git diff --check` 通过；这不是“干净工作树”的声明。API PID `109945`、启动 tick `337210114`、命令 SHA-256 `de005c1cebe1acd8a90935259fddd9078fcf8e6e04e260c09ebe1d61c16abd59`；该实例仍在运行。

旧环境回执只证明 2026-09-28 未改动源码的基线，不应用作当前最终源码的环境回执。当前阶段的原生回执需以新部署指纹及本节证据重新绑定。
