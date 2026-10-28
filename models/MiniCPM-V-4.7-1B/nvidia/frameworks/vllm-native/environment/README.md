# H100-149 原生 vLLM 环境分析

只读核实日期：2026-09-28。目标范围为 `H100-149`，容器
`MinicpmV4.7-1B-native`，权重
`/data/models/MiniCPM-V-4.7/weights/1b`。`./scripts/connectivity-check --limit H100-149`
通过，实际 hostname 为 `p-jn-sz-dell-h1-su8-gpu11-401-11o-12u-208-149`。

| 对象 | 核实结果 |
| --- | --- |
| 容器 | ID `66a0c79a982769313637ac15000e059cd280443cd7a22dea49f37b763a2c898e`，运行中，2026-09-28 01:55:21 UTC 启动，host network |
| 镜像 | `vllm/vllm-openai:v0.24.0-cu129-ubuntu2404`，image ID `sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4` |
| GPU | 8 × H100 80GB HBM3，驱动 580.105.08、CUDA 13.0；GPU 间 `NV18`。占用随时间变化；本任务只用 GPU 0，12:00 左右另有工作负载使用 GPU 2、3，未干预 |
| 运行栈 | Python 3.12、PyTorch `2.11.0+cu129`、Transformers `5.12.1`、Triton `3.6.0`、vLLM `0.24.0+cu129` |
| 权重 | 单个约 3.109 GB 的 `model.safetensors`；780 个 tensor、1,554,476,272 个参数；权重 SHA-256 `3b801e149bc6dab4bb8c4cf61bed4197cce810f6c2f523f60b266459f809251c`；配置 SHA-256 `0d2f763cf97a0a5beec8f52b13b4cbf7262680df6fd35e1f0e48c09288c4bb12`；tokenizer SHA-256 `33861e37bb955af1e3f3061182b820f347eba2b9c2c1011c82794bf0d6e77b54` |
| 工作根 | Host 和容器同路径 `/public/flagos/jinghao/MiniCPMV4.7-1B/native`；`/public` bind mount；两边设备号:inode 均 `45:242118752009`；初查为空，随后创建当前编号的七个过程目录 |
| 权重映射 | `/data` bind mount；Host 和容器中的配置文件设备号:inode 均 `64768:14475024`；路径没有 symlink 改写 |

本任务的一次性只读 `find / -maxdepth 4 -type d -name .git` 在 SSH 断开后仍运行。
核实 Host PID `2552019` 的命令及父进程后，执行 `kill 2552019` 清理该诊断进程；
随后 `ps -p 2552019` 无结果。未影响推理服务或适配容器。

## vLLM 源码身份与写入边界

`import vllm` 指向
`/usr/local/lib/python3.12/dist-packages/vllm/__init__.py`。pip 元数据的
`direct_url.json` 为本地 wheel 文件
`file:///vllm-workspace/dist/vllm-0.24.0+cu129-cp38-abi3-linux_x86_64.whl`，
并非 editable 安装。`_version.py` 记录短 commit `gee0da84ab`，但容器没有 Git 可执行文件，
`/vllm-workspace` 中也没有 vLLM checkout；在目标工作根和已检查的同用户目录中均未找到
对应源码树。这个短标记和 wheel 文件不能证明当前可编辑 Git HEAD、PR base、原有 diff
或导入路径与源码的关系。

本任务的 `vllm-native` profile 声明 vLLM 组件可写，模型文件、权重和平台 runtime
只读。其默认工作流要求 editable/source Git 树；用户在本任务中随后明确要求直接修改容器
安装的 vLLM，并说明没有相关源码。该明确指令构成本轮 wheel 路径的例外，不扩展到权重、
Transformers、其他容器或其他 Host。已核实 `site-packages` 是实际导入路径，修改前
`registry.py` SHA-256 为 `ab52495073a046b79d00a314cbc96e719e3ed916ea8a8bf6f3202015062b5676`，
4.6 adapter SHA-256 为 `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`，
且 4.7 adapter 路径不存在。原注册表备份在容器内
`02-issues/registry.before.minicpmv4_7.py`；哈希核对一致。因无 Git 树，完整 HEAD、
PR base、原有 dirty/untracked 不可得，后续以安装文件哈希与精确 diff 为审查边界。

## 适配差距与现有经验

vLLM registry 当前仅列 `MiniCPMV4_6ForConditionalGeneration`，没有目标
`MiniCPMV4_7ForConditionalGeneration`。4.6 adapter 具有 Qwen3.5 骨干、视觉塔、
图像/视频处理与权重前缀映射，可作为接口参照；其 `get_mrope_input_positions` 把顺序位置
复制到 3 个通道，而目标 checkpoint 的 `mrope_mode=canvas` 要求空间位置及 decode
偏移。因此必须按当前 checkpoint 和源代码核验语义，不能仅添加 registry 别名。

检索了 `docs/troubleshooting/` 和相近 NVIDIA 模型记录。已有 NV-native wheel 修改案例
说明该类镜像可能缺少 Git 元数据，但不是本次源码授权或成功证据；其模型结构及问题签名
与本 checkpoint 不同。知识库的 TP timeout 和 Plugin fullgraph 条目也没有当前失败签名，
暂不复用。

## 运行环境发现与受控基线

初始 4.6 架构别名诊断在 Triton 导入时失败：容器内有
`/usr/lib/x86_64-linux-gnu/libcuda.so.1`，但 `ldconfig -p` 未列出它，Triton 报
`libcuda.so cannot found!`。只改变环境变量
`TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu` 后，别名基线加载了真实权重并就绪。
保留两次启动日志于 `04-runs/baseline-46-alias-20260928/` 和
`04-runs/baseline-46-alias-driver-20260928/`。别名不代表 4.7 正确适配；它的 M-RoPE
仍是 4.6 的顺序位置。

应用模型专用注册和 canvas 位置实现后，原生 eager 服务在
`04-runs/native-eager-20260928/` 加载权重，生效参数包含
`--model-impl vllm --enable-prefix-caching --enforce-eager`；文本 `17+25` 返回 42、
单图主色返回 Red，两帧短视频能识别 red/blue。视频回复触及 96 token 上限，
仅证明链路及部分语义，不作为正式精度通过。API 与 EngineCore 进程
`3243/3838` 由本任务启动，在确认身份后为切换 graph 用
`docker exec ... kill -TERM 3243` 停止；两进程退出、GPU 0 释放，容器保持运行。

请求 `--compilation-config '{"cudagraph_mode":"FULL"}'` 的服务日志为
`04-runs/native-full-20260928/service.log`。引擎将其自动改为
`FULL_AND_PIECEWISE`，明确写出 GDN attention 的
`AttentionCGSupport.UNIFORM_BATCH` 限制；实际捕获的是 mixed
prefill/decode PIECEWISE 加 decode FULL，不能算 full 验收。该后端源码
`vllm/v1/attention/backends/gdn_attn.py` 也声明相同限制。API/EngineCore
`5177/5576` 在确认身份后由本任务停止，为显式 `FULL_DECODE_ONLY` 验证让出 GPU 0；
容器未停止。当前的 decode-full 独立运行证据在
`04-runs/native-decode-full-20260928/`。

## 后续验证

1. 完成显式 decode-full 的实际图捕获和变输入推理验证；保留 full 自动降级证据。
2. 检查多图、切片、视频、并发及 4.6 现有调用方，按项目原生入口冻结正式精度和性能配置。
3. 审查安装文件实际 diff 与可逆性；GPU 检查结果是时点状态，每次服务切换前核实占用。
