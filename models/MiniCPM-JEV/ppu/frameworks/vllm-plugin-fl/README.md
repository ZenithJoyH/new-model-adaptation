# MiniCPM-JEV / PPU / vLLM + vllm-plugin-FL

2026-10-23，value-head 推理功能已验证。PPU-01 的 `minicpm-jev-vllm` 基于运行中的 `minicpm-ocr` 非暂停快照创建，使用物理 PPU 1；原 OCR 服务保留在 PPU 0。

**当前运行配置**：Plugin 已从 `/opt/vllm-plugin-FL` 源码 editable 安装，无 `PYTHONPATH`。发现并修复 pooling 满上下文预留生成 token 的调度停滞，17 项回归通过，vLLM 未改。当前 API PID165227，保留用户脚本 `max-num-seqs=64`、默认上下文 262144；两次 262144-token 双图请求完整消费、概率一致，262145 正确拒绝，长请求后 12 短样例回归通过，health 200，采样显存峰值约 88.5 GiB。视觉插值已合并到模型子类，产品改动收敛为 5 个文件、测试 3 个文件；收敛后重新通过 17 项测试、两次满长度及短样例回归，见 [010 适配代码收敛](adaptation/010-adaptation-consolidation.md)。见[/opt 源码安装与长上下文验证](environment/003-opt-source-installation.md)和[009 调度边界修复](adaptation/009-pooling-context-boundary.md)。此为单请求容量/稳定性验证，不是长文业务精度或 64 路满上下文测试。此前结果保留在[上一轮环境复核](environment/002-user-script-installation.md)。按新贡献规范完成逐块 PR 审查，Plugin 26 项、FlagGems 4 项测试通过，面向上游的干净补丁已通过 apply-check，见 [最新 PR 审查](adaptation/010-adaptation-consolidation.md)。以下启动器哈希、PID 和正式回执描述保留首轮验证身份，不作为新安装和新参数的正式验收回执。

远端工作根（Host/容器同路径）：`/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt/vllm-plugin-fl`。新容器身份、映射及组件基线见 [环境分析](environment/environment-analysis.md)。

服务为 `http://127.0.0.1:8330/classify`，模型名 `minicpm-jev`。原生 pooling/classify、LAST pooling、BF16 主体、FP32 视觉位置插值与分类头，最终显式 PIECEWISE CUDA Graph + 原生 EagerAdaptor。12 样例两轮最大概率误差 **0.004417300 < 0.005**，token 数及阈值侧全部一致；4/8 并发各 24 请求与图像消融均通过。

最终启动器为工作根 `start-model.sh`，镜像内副本 `/opt/minicpm-jev-vllm/start-model.sh`，SHA-256 `4ba5cd978618c66d15ce52fcbe20060ea34f4c6dec9745b8cfbd6338c6deb616`。2026-10-23 实际启动、就绪和 24 请求对照通过。客户端 `/opt/minicpm-jev-vllm/jev-client.py` 支持原图、OCR 文件和渲染图；同目录 `RESTORE.md` 保存恢复说明。

按用户要求，2026-10-23 将 Host/容器同路径 `/mnt/nfs/users/jinghao/MiniCPM-JEV/start-model.sh` 精简为 978 字节，SHA-256 `7495c988c6d93c25c78cddfa709a9bbad22bc49a605fe692c4de0bd3666f27bf`，权限 0755。去掉 HOME/TMPDIR/字节码设置、重复的 HF/vLLM 缓存覆盖及模型配置已有的 BF16 参数，日志改为工作根 `04-runs/service.log`；保留 PPU/插件/RPC、缓存落盘、分类语义、资源限制和已验证图参数。容器内内容、映射与 Bash 语法核验通过，当前服务 health 200；未重启服务，精简版本尚未实际启动验证。原工作根和镜像内启动器及其历史证据保持原样。

最终 PID108830、实例 `jev-691fe8280a691510fdd32c5e`，原生 observer 核验容器 ID、启动 tick、命令和 8330 端口为 verified。原始证据在 `04-runs/final-launcher-20261023/`，样例结果在 `04-runs/final-launcher-native-20261023/`。

最终源码审查：`04-runs/source-review-final-20261023/manifest.json`。vLLM 1886 个安装文件未变，源码干净；Plugin 继承 diff 哈希仍为 `52aee2ba258189339f395aa566c88b661c3b0d369defceeaae8f0272eb1aa0bc`。三个修复为 clone 注册、异步池化输出和视觉位置插值，详见编号问题；最终 12 项针对性测试通过。未提交、推送或创建 PR。

范围上限为 functional：正式完整数据集、性能与新打包镜像验证未执行。现有 reference_text sanity 比较器尚未匹配 classify 浮点输出。图捕获覆盖至 1024 batch token，更大 batch 使用原生 fallback；context 配置 50000，未验证所有最大长度输入。其他硬件、generation、量化和 TP/PP 多卡未验证。

- [环境记录](environment/README.md)
- [适配问题及已验证结论](adaptation/README.md)
- [最终源码设计审查](adaptation/008-source-review.md)
- [执行模式与交付](acceptance/execution-mode.md)
- [验收记录](acceptance/README.md)

完整日志、脚本、diff、JSON 和缓存保留在远端批准工作根；本地只保存简明记录。
