# 009：204800 上下文的多模态预热与 FlagGems 3D 卷积

**2026-10-01 14:58 后续状态：**本记录中 `c03db886...` 的根脚本验证是修改前证据。用户原位修改 `start-model.sh` 为 SHA-256 `5bd834658772572f5ebc39ff56be5bb168ca9cf255d8cd299e56fb7120aca124`，改成 `nohup` 并输出工作根 `service.log`；该日志位置不满足 `04-runs/` 约束，不能沿用旧脚本的最终验收结论。用户要求自行启动，代理启动的 TP16 进程已在 14:58 停止并确认 8025 空闲，容器继续运行。此前 TP8 单变量探索脚本 `01-environment/start-graph-decode-full-204800-s64-tp8-20261001.sh` SHA-256 `f4b87aee4139e49b1504600c9b0b402763b545e725b82024dbecb868e0aff325`，日志 `04-runs/service-204800-s64-tp8-20261001.log`：48/48 分片、完整多模态预热、6/6 decode 图捕获与健康接口通过；KV cache 411520 tokens、204800-token 请求最大同时驻留约 2.01 条。用户停止试验，TP8 请求验证未执行，TP8 服务退出；这些探索结果不改变下文 TP16 故障归因。

## 元数据

- 状态：`mitigated`；首次及最后验证：2026-10-01。
- 模型：`/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；`text_config.max_position_embeddings=1048576`。
- 平台：`PPU-07`，16 张 PPU-ZW810E；容器 `minimaxM3.1`，ID `1ac783da3c60aea237f5f64a0721c3f33c71b0218a317f0677e54619ec2634d1`，镜像 `sha256:66aba903fec3373d3518183f77227a713fb20e0fbf48038e6c813329cbd53172`；Host/容器工作根同为 `/mnt/nfs/users/jinghao/minimaxM3.1`，同 inode 映射已验证。
- Plugin `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加任务内既有 diff；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`；FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`。本轮仅改批准工作根下的运行脚本/证据，未改产品源码。
- 固定服务条件：BF16、TP16、`max_model_len=204800`、`max_num_seqs=64`、block128、batched8192、显存利用率 0.90、prefix caching enabled、`FULL_DECODE_ONLY` 捕获 1/2/4/8/16/32。除记录的单一算子策略外，诊断服务参数相同。

## 故障签名与调用链

默认 FlagGems 策略、不带 `--skip-mm-profiling` 的 204800/64 服务在初始化内存分析阶段失败，首报 TP4，硬件转储明确指出设备异常函数 `conv3d_forward_kernel`，错误为 PPU `illegal memory access`；API 未开放。脚本 `01-environment/start-graph-decode-full-204800-s64-defaults-20261001.sh` SHA-256 `029ffebde9206bc12553406d34d6c3cb836a13f6c1764addb526d0d1c1a7cb88`，日志 `04-runs/service-204800-s64-defaults-20261001.log` SHA-256 `9aa8d3e8288d1d2c582d40c67fa89e0476293e2b04c8bb6cb6af3d46058285b6`。

vLLM `MiniMaxVLVisionPatchEmbeddings` 在 `common/vision_tower.py:48-77` 用 kernel/stride `(2,14,14)` 的 `nn.Conv3d` 处理视觉 patch。Plugin `worker.py:258-292` 默认 `flag_gems.enable`，使普通 ATen 算子进入 FlagGems，并非一个单独的“MM 算子”开关。失败栈沿 `profile_run → embed_multimodal → video vision_tower → F.conv3d → FlagGems conv3d`。模型视频处理器的 `max_pixels=451584`，源码的 `get_num_frames_with_most_features` 在单视频条件下最多使用 500 帧；204800 的大上下文允许远大于日常 8 帧请求的启动 dummy 视频。**500 帧、672×672 与约 57.6 万个未合并 patch 是按配置计算的上限，不是现场采集的实际 tensor shape**。小视频请求通过不能证明此最大预热负载安全。

[问题 007](007-context-100k-capacity.md)有更早但首报路径不同的容量失败，仅作假设线索；[TP sample_tokens 超时](../../../../../../docs/troubleshooting/distributed-sample-tokens-timeout.md)发生在推理阶段，签名不同，不提高 RPC 超时。

## 单变量对照

| 轮次 | 相对前一轮唯一实质变量 | 脚本及日志 | 结果 |
|---|---|---|---|
| A | 从已通过的 65536/64 默认缓存配置仅提高上下文至 204800 | 上述 `204800-s64-defaults` | TP4 `conv3d_forward_kernel` 非法内存访问；API 未就绪 |
| B | A 增加 vLLM 原生 `--skip-mm-profiling` | `01-environment/start-graph-decode-full-204800-s64-skip-mm-20261001.sh` SHA-256 `2fa9e48a8b475841ad0984f57f843c59aa545a4e705d47f154f2fa04adaa553d`；日志 `04-runs/service-204800-s64-skip-mm-20261001.log` | 文本与小型多模态请求可用；跳过的最大多模态内存测量仍是容量风险 |
| C | 回到 A，仅用 `VLLM_FL_FLAGOS_BLACKLIST_APPEND=conv3d` 排除一个 FlagGems 注册项 | `01-environment/start-graph-decode-full-204800-s64-exclude-conv3d-20261001.sh` SHA-256 `2a7e792d231ca4a4c17b01b5b603d8af08274fa0c0df31fd99eb975d36b142f0`；日志 `04-runs/service-204800-s64-exclude-conv3d-20261001.log` SHA-256 `b58fefc36f80593d7b6d021050922988184858f9ef161908cd38b72a57ed6b30` | TP6 首报同一设备函数非法访问；栈多出 `_thead/ops/cudnn_convolution.py:351`，没有避开 FlagGems kernel |
| D | C 中只追加排除 `cudnn_convolution` | `01-environment/start-graph-decode-full-204800-s64-exclude-conv3d-cudnn-20261001.sh` SHA-256 `e62ad53ccdcd4ecc5761e65bb665e4963f6cd18c5ad174c0e80f740f8b9c96fd`；日志 `04-runs/service-204800-s64-exclude-conv3d-cudnn-20261001.log` SHA-256 `1189ff89325e99c4896fe7189d8b08fd32e341128c6ce7837062320a1e8f024c` | **不跳过**多模态预热，API 健康 200、6/6 decode-full 捕获、短题与长文本成功 |

C 轮为何仍命中：排除 `aten::conv3d` 后，PyTorch 转入 `aten::cudnn_convolution`；当前 T-Head FlagGems 实现的 `cudnn_convolution.py:313-363` 对 5D 输入又直接调用 `flag_gems.ops.conv3d`。D 轮同时排除这两条注册路径后，完整预热成功。因而本次启动故障可以归因于**当前 FlagGems 3D 卷积实现/调用链在该最大视频预热负载上的非法内存访问**，而不是 `--skip-mm-profiling` 开启了某个专门的多模态算子。尚未证明具体越界索引、Triton autotune 配置或触发 tensor shape；不把路径级归因写成已修复内核缺陷。

专用算子脚本在 Host/容器同路径 `07-bugs/009-mm-profile-conv3d/repro.py`，SHA-256 `076093963345e81ba8c10b3f29d289dfc700ecd20aeeb316dd03d3e8152ac3d6`。按视觉层 BF16、输入通道 3、输出 1280、kernel/stride `(2,14,14)`，N=1 与 1024 均通过；报告分别是 `04-runs/mm-profile-conv3d-repro-n1-20261001.json` SHA-256 `94bad334c6a2bb51ac3141c251a4ead439d1d13addbda9c5459f3b295f407e24` 和 `04-runs/mm-profile-conv3d-repro-n1024-20261001.json` SHA-256 `21cb5ccedc3eaa1a7c2d423eef715e057699adf90dbe044296846aa43da36ad7`。N=1024 运行时 Ansible SSH 连接曾中断，但完整报告写出、主机恢复且服务健康；不能据此称算子错误已在独立小 shape 复现。

## 实际请求验证

`03-acceptance/mm-requests-20261001.py` SHA-256 `496d32b6e08b93f18e68f96d4c6881ccb6f0e4be55b24b7b6dd1d40789729b26` 构造确定性的 PNG 和八帧 MP4，按 `temperature=0,max_tokens=512` 请求 OpenAI Chat API，分别记录 HTTP 成功与答案正确。204800/skip-mm 服务的 `04-runs/mm-requests-204800-20261001.json` SHA-256 `b64e721a649f76a4e15247d8491f2178f21cc1d016dfb6c71c6f8348558642e8`，与 D 轮完整预热服务的 `04-runs/mm-requests-204800-no-skip-20261001.json` SHA-256 `857e162a4d8733895d4f2d226a0e425f1ebad2796062b9fbefc8a76c40517e2e`，对同字节输入均得到 **5/5 请求 HTTP 200、4/5 答案正确**：蓝图、四位数字 OCR、双图第二张和视频末帧数字正确；纯红图稳定误答“绿色”。颜色问题独立记于[问题 010](010-red-image-color-error.md)，不能把 5/5 HTTP 成功写成多模态精度通过。

D 轮 `04-runs/context-natural-202k-no-skip-20261001.json` SHA-256 `86219f91df759748b6665cb9f751a3c511b9c7d5ddb9cb1dd746b4f5457abcb1`，约 201652 prompt tokens、HTTP 200 且回答末尾算术题 `2`。早先 5k/40k/100k/202k 的变化背景文本诊断均成功；重复 `a` 的病理输入在 40k 即失真，不能归因于上下文上限。

## 当前处理、验证与限制

- 根脚本 Host/容器同路径 `/mnt/nfs/users/jinghao/minimaxM3.1/start-model.sh`，2026-10-01 验证同 inode `29236341840`、mode `0755`、SHA-256 `c03db886fc93600b0ab1202bc70629ec3d66476f4382cdccb2996cbe264d3bdc`。其与 D 轮仅日志位置不同：`VLLM_FL_FLAGOS_BLACKLIST_APPEND=conv3d,cudnn_convolution`、无 `--skip-mm-profiling`；prefix cache enabled、decode-full、204800/64 保持。旧 skip-mm 根脚本保存在 `01-environment/start-model-skip-mm-root-20261001.sh`，SHA-256 `e660a47895f18235b363b364f3942d065f5d5a57e6a98b2fc433120ea8ffad08`。
- 根脚本独立启动的服务 host PID `3848319`，容器仍运行；实际进程具有双算子排除环境且无 `VLLM_PLUGINS`、`TMPDIR`、XDG、FlagGems、Triton 或 Torch 显式缓存环境。`04-runs/model-service.log` 当前启动段 14:18:01 记多模态预热完成、6/6 decode-full 图捕获；API `/health` 200、`/v1/models.max_model_len=204800`。容器 `bash -n`、端口占用拒绝退出码 1 通过。
- 根服务短题 `04-runs/service-smoke-204800-full-mm-root-20261001.json` SHA-256 `2dc9bb269817475c90e2b7ac9c59512e811050fcf525ba2732b936af179efbdc`，2/2 正确；5 个多模态请求 `04-runs/mm-requests-204800-full-mm-root-20261001.json` SHA-256 `e3951305365ca93bee3ac1770c6d12255b1c9df2d232198e3135dcec2d70a2a7`，5/5 HTTP 200、4/5 答案正确；长文本 `04-runs/context-natural-202k-full-mm-root-20261001.json` SHA-256 `64333785c9348705e26ba74cc117c64185279bc18d52f1e58ca8c04d650cbbe6`，201652 prompt tokens、正确。测试后服务保持健康。
- 处理分类：双算子排除是当前 PPU/模型/软件版本的运行配置 workaround，不是 FlagGems 根因修复。它让 3D 卷积走原生后端；其他图像形状、500 帧实际视频推理、原生后端性能/数值及 64 条满长请求并发仍未覆盖。64 是调度上限，图捕获尺寸止于 32。没有扩大 Plugin 公共代码例外，也不主张其他模型或平台支持。
- 服务切换仅在核实本任务准确 PID、命令与容器 cgroup 后进行：旧 root API `2958460` 为对照发送 TERM 后退出；单算子排除的 `3297756` 在初始化错误后自行退出；双算子诊断 `3470891` 在证据保留后发送 TERM 退出；根服务 `3848319` 启动且健康。**适配容器始终运行，未停止、重启或删除。**
- 正式 GPQA 最好 167/198＜0.88，`framework.yml` 的原生环境/执行模式/预检/全量精度回执来自此前 65k 配置；本轮 204800 验证不能替代正式全量精度或性能，不提升整项适配状态。后续需采集最大视频预热的实际 `Conv3d` shape 与 Triton autotune 配置，在 `07-bugs/` 构成失败的最小复现，再经单变量修复、数值/性能及正式精度回归后撤销双算子排除。知识库处理状态 `needs-validation`，当前不推广为跨模型经验；PR base 未在本轮确认，也未创建 PR。
