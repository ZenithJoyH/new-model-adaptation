# H100-149 FlagOS 环境分析

2026-10-08 从最终共用容器创建 `minicpmV4.7-35B-new`，镜像内安装与设备检查通过；
见[新容器环境记录](model-containers-2026-10-08.md)。下文保留原独立容器历史分析。

## 目标与核实

2026-09-28 `./scripts/connectivity-check --limit H100-149` 通过，实际 hostname 为
`p-jn-sz-dell-h1-su8-gpu11-401-11o-12u-208-149`。目标容器是
`MinicpmV4.7-35B`（ID `c64f9dcf3b9cb8b775909d01cf549825cad663a14f7b7aa956ee46f88f39bd74`），
正在运行，未被本任务重启或停止。另有名为 `MinicpmV4.7-35B-native` 的独立容器，
不属于本工作区。本任务的唯一 Host 为 `H100-149`。

| 对象 | 只读核实结果 |
| --- | --- |
| 镜像 | `harbor.baai.ac.cn/flagos-inner-models-release/minicpm4.7-base-nvidia003-gems5.3.5-tree0.6.2-cxnone-plugin0.0.0-vllm0.24.0-cp312-pt211-cu129-x64-580.105.08`，image ID `sha256:36fe2dcc73d074f6a35e7111f5bc597d7830ae4ba44e0e436623cb71ad44ddeb` |
| 硬件 | 8 × NVIDIA H100 80GB HBM3，各 81,559 MiB；`nvidia-smi` 驱动 580.105.08、CUDA 13.0；检查时八卡均 0 MiB/0% |
| 工作根 | 宿主机和容器内均为 `/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`，`/public` bind mount；两边设备号:inode 都是 `45:213357695245`，无 symlink 改写 |
| 权重 | 容器内 `/data/models/MiniCPM-V-4.7/weights/35b-a3b`，`/data` bind mount；目录设备号:inode `64768:2147497685`，只读使用 |
| checkpoint | `config.json` SHA-256 `3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646`；索引 SHA-256 `9908f05c01616fdcce1a5f6b60e5cbfceb8f6bf908ca80552cb39954b6aa2a27`；1,152 个 BF16 tensor、35,212,875,824 参数；索引引用的 17 个 shard 均存在 |
| 软件 | Python 3.12、PyTorch `2.11.0+cu129`、Transformers `5.12.1`、vLLM `0.24.0+cu129`、Plugin `0.3.0rc2.post1+g3a27a6fb2` |

2026-09-28 在映射复核、`--check --diff` 通过后，已用 `serial: 1` 的 Ansible
在工作根创建 `01-environment/`、`02-issues/`、`03-acceptance/`、`04-runs/`、
`05-tmp/`、`06-cache/`、`07-bugs/`；容器内核对目录名通过。
当前容器内只有 `/bin/bash` 主进程，没有本任务推理服务。
候选部署身份清单保存在宿主机和容器同路径
`/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/01-environment/deployment-identity.json`，
文件 SHA-256 为 `11ef42ce0f9a39453829f792564c72881c80d58797ef72890a3c695ba19b7f69`。
其 UTF-8 JSON 按键排序、紧凑分隔符的 SHA-256 为
`9512802d2bbae8a972e02b1818019597b1417695f21db2e80d9c49b916bdb3f9`，
用于当前 `framework.yml` 的部署指纹。清单明确候选 TP8、BF16、50,000 token 和
Plugin 源码导入路径；这些尚非已通过的服务配置，实质变化必须重新核实并绑定证据。
同日重新执行的现场探针保存在
`H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos/04-runs/env-h100149-minicpm47-35b-20260928/environment-probe.json`，
SHA-256 `54192b6cccad5975f314133e2197218e0ab38d531097b93866b60a20c213c6d9`；
该探针在目标 Host 重测容器/挂载、八卡、权重哈希、两棵源码树状态与实际 import 来源，
所有身份断言通过。这是环境阶段的原始测量摘要，不是模型服务结果。
环境阶段的逐 Host 回执位于同一个 run 目录的 `framework-check.json`，
SHA-256 `00102385594c58185ee822f5872e5af4db5f49bcd29b1b1bc34f2e37d6b42e7b`；
回执引用上述探针和部署身份清单，未包含模型推理通过声明。

## 源码与安装边界

- vLLM 从 `/usr/local/lib/python3.12/dist-packages/vllm/__init__.py` 导入，
  pip `direct_url.json` 指向 wheel `file:///vllm-workspace/dist/vllm-0.24.0+cu129-cp38-abi3-linux_x86_64.whl`。
  这不是 editable vLLM checkout；vLLM 全程只读。当前 4.6 adapter
  `minicpmv4_6.py` SHA-256 为 `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`，
  `_version.py` SHA-256 为 `763ed234b0648da39d230104ca1afb879dd874d64a4fb6363a43a73649592804`。
- Plugin 的 pip 元数据为 editable 安装，源目录
  `/vllm-workspace/vllm-plugin-FL`，Git `main` HEAD
  `3a27a6fb2d514cdf55c00481bf813225dac63319`，起始工作树干净。
  `pyproject.toml` 将 `vllm_fl:register` / `vllm_fl:register_model` 分别注册为
  platform/general plugin；当前源码未包含 MiniCPM-V 4.7 实现或登记。
  默认 Python 导入受到镜像内残留 `site-packages/vllm_fl` namespace 目录影响：
  `vllm_fl` 顶层和 `vllm_fl.models` 解析到 site-packages，而
  `vllm_fl.platform` 解析到 editable 源码。只读对照证明将
  `PYTHONPATH=/vllm-workspace/vllm-plugin-FL` 前置后，三者均解析到源码。
  运行配置必须固定这一导入路径并再做实际入口验证；见[问题 001](../adaptation/001-editable-plugin-import-shadowing.md)。
- FlagGems 导入路径为 `/vllm-workspace/FlagGems/src/flag_gems/__init__.py`。
  用户明确授权同步后，在干净的 `master` / `origin/master` 上执行 `git fetch`、
  祖先关系检查和 `git pull --ff-only`，从
  `1478cefcf2ee304ebb72c2f51acade0d45c82f13` 快进到
  `da6727e38f6f8eedef6cba43695a87b4996f9eca`；完成后工作树干净。
  首次无代理 fetch 因容器无法解析 GitHub 而失败；随后仅对同步命令临时使用用户提供的
  代理，凭据没有写入本仓库或本记录。当前尚未判定任何具体算子是否可用。

## 组件差距与验证顺序

目标 checkpoint 的 `architectures` 为 `MiniCPMV4_7ForConditionalGeneration`，
文本骨干 `qwen3_5_moe_text`，`mrope_mode=canvas`，最大位置配置为 262,144。
初始服务按项目规则应选 50,000 token；尚未证实 TP8 混合 cache 和 graph 能承载。
参考实现与 processor 的路径、哈希见模型级[架构分析](../../../../architecture-and-inference.md)。

| 组件 | 现有扩展点或参照 | 待验证差距 |
| --- | --- | --- |
| 配置与模型注册 | Plugin `register_model()`、vLLM OOT registry；已安装 vLLM `minicpmv4_6.py` | 4.7 配置/架构尚未注册；不得只把 4.7 别名指向 4.6 |
| 文本骨干与权重 | vLLM Qwen3.5 路径、现有 MoE adapter、Plugin 模型专用 shim | 35B MoE packed 专家、共享专家与 TP8 权重映射需逐 tensor 核对；1B 稠密模型结果不可复用 |
| 视觉与占位符 | vLLM 4.6 多模态 processor/ViT/merger | 4.7 的 16x 下采样、image/video 占位符数量和动态网格需对照 |
| 位置与状态 | vLLM `SupportsMRoPE`、参考 `mrope_minicpmv4_7.py` | canvas prefill/decode、`rope_deltas`、批处理和 graph replay 需实现并验证 |
| 算子与 graph | 同步后的 FlagGems、Plugin dispatch/backend | 在确认上述接口后再按精确 dtype/shape 检索算子；full graph 优先，未有失败证据前不得降级 |

按仓库策略，先验证 Plugin import 与注册、权重映射和小范围算子，再运行最小
text/image/video 推理；之后尝试 full graph，并依次进行 execution-mode、十并发 sanity、
FlagEval 正式精度、前缀缓存关闭的性能、证据和最终启动脚本验收。当前尚未开始这些验证。

## 经验检索

检索了 `docs/troubleshooting/` 和 MiniCPM-V-4.7-1B NVIDIA 记录。
1B 的 4.7 注册与 canvas M-RoPE 差距具有结构相似性，但其文本骨干是稠密 24 层、
参数规模 1.55B，且运行容器和 profile 不同；不能将其环境发现当成 35B 成功证据。
已知 TP `sample_tokens` 超时条目没有本任务的实际失败签名，暂不套用。
