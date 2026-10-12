# FlagOS Plugin 环境核对（2026-09-23）

## 当前目标：H100-149

2026-09-24 复核：profile 已从 v3 更新到 v4，新增可选的
`FlagGems-vllm` 产品组件。`H100-149` 目标容器内安装元数据为
`flaggems_vllm==0.1.0`，`direct_url.json` 标记 editable；实际 import
文件为 `/vllm-workspace/FlagGems-vllm/src/flaggems_vllm/__init__.py`，
Git 根目录为 `/vllm-workspace/FlagGems-vllm`，HEAD
`3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`，工作树为空。
本次 V4.1 skip-QNorm 实现复用该库算子，未修改其源码。原环境回执绑定
profile v3 和旧 Plugin diff，不能直接沿用为本轮通过证据；下述新身份
将用于重新生成逐 Host 环境回执。

本轮产品改动稳定后已重新采集
`H100-149:/public/flagos/jinghao/deepseekV4.1/01-environment/h100149-plugin-20260924/deployment-identity.json`
（Host SHA-256 `4735a45242e9e7fa9d4da70717aaabb8fbc5faf90da8d920f824b59efb83db2e`）。
新身份含当前 Plugin 的 tracked diff 及 39 个 untracked 产品文件的逐文件哈希，
并重新核对四棵源码 HEAD/工作树、模型配置、索引和 tokenizer SHA、48 个
权重分片的总字节数 `962114250788`、18K eager 启动脚本 SHA 和 TP8 配置。
模型关键哈希与上一轮完全一致；vLLM 仍为既存 87 条修改，FlagGems 与
FlagGems-vllm 工作树为空。Host 与容器的工作根 device:inode 均为
`45:226864815887`，容器镜像 ID 与原记录一致。此采集只证明部署身份，
不把正在执行的 18K eager 请求视为已通过。

用户要求将 H100-145 当前适配容器保存后，转至 H100-149 继续。H100-145 的
`xingchen4-flagos` 已保存为镜像
`deepseek-v41-plugin-fl:h100145-20260923-r1`，镜像 ID
`sha256:956bf9360f00d835c0b054c50ffc7f455f72972ccb7302f7c952afb3274385b7`。
导出包在共享根的
`01-environment/h100145-flagos-20260923/container-snapshot/deepseek-v41-plugin-fl-h100145-20260923-r1.tar`，
大小 `31839528960` 字节，SHA-256
`6f7d2cdf1cb88585ef3f9fb5b65c05a552d2fef433b7d36be33087d942a36d35`；
H100-149 导入后的镜像 ID 与源端一致。

| 项目 | H100-149 实测 |
|---|---|
| SSH Host | `H100-149` → `p-jn-sz-dell-h1-su8-gpu11-401-11o-12u-208-149`；`./scripts/connectivity-check --limit H100-149` 通过 |
| GPU | 8 × H100 80GB；驱动 580.105.08、CUDA 13.0；2026-09-23 17:49 每卡 0 MiB；`./scripts/accelerator-check --limit H100-149` 通过 |
| 新容器 | `deepseek-v41-plugin-adapt-20260923`，ID `23b621c59652dee0f39725af0819ca491194e8f78b88676d26298475b2723339`，运行中，镜像为上述 ID；旧容器和服务未停启 |
| 工作根 | Host 与新容器均为 `/public/flagos/jinghao/deepseekV4.1`，`/public` RW bind；两侧 `stat` 均为 `45:226864815887` |
| 模型 | `/public/models/DeepSeek-V4.1-Flash-W8A8-BF16` 已在新容器核实；配置、索引、tokenizer 文件 SHA-256 分别与下文 H100-145 记录一致，共享文件本身未复制 |
| 产品源码 | Plugin editable `/vllm-workspace/vllm-plugin-FL`，HEAD `fd5c727fcdb607bc4354cd11384761bb5d5ecfba`，本次适配 diff 在容器可写层；vLLM HEAD `ee0da84ab9e04ac7610e28580af62c365e898389` 只读，原有 diff SHA-256 `2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`；FlagGems 与 FlagGems-vllm HEAD 分别为 `7cd137ccaf09f25ce3012ba86438682072a69bc9` 和 `3d73c8a4440749fe0e6aff1ffe1d6f40832e6741`，两者工作树干净 |

当前部署身份保存在
`H100-149:/public/flagos/jinghao/deepseekV4.1/01-environment/h100149-plugin-20260923/deployment-identity.json`，
宿主机与容器读取 SHA-256 均为
`d0b1ba4d085aea08a3cffe4e77fd2603f9191cf3ed16892845e6a17ca47ba1ee`。
该身份包含 Plugin 的 tracked diff SHA-256
`dc46cc66a69d72f228781e9c591397095e323c982b56e677d0bd8c790b096e79`
及 untracked 文件清单 SHA-256
`5442b335de98f5b3c7426a640b2267906ff8627439f7456281e71b17b104bf47`；
后续产品改动将使此身份失效，必须重新现场核验再绑定。用户另外授权新容器在本轮诊断
使用本地 `/tmp/deepseek-v41-plugin-h100149` 存放编译缓存和临时文件，日志仍在
工作根 `04-runs/`。此项仅适用于该容器，不改变挂载。

## 历史来源：H100-145

本记录针对 `H100-145` 的 `xingchen4-flagos`，仅用于分析
`/public/models/DeepSeek-V4.1-Flash-W8A8-BF16` 在现有 vLLM +
vllm-plugin-FL profile 下的接入条件。尚未运行该模型，不能据此判定服务可用。

## 身份与工作边界

| 项目 | 已核实值 |
|---|---|
| Host | `H100-145` → `p-jn-sz-dell-h1-su8-gpu15-401-13o-12u-208-145` |
| GPU | 8 × H100 80GB；核查时每卡使用 0 MiB；驱动 580.105.08、CUDA 13.0 |
| 容器 | `xingchen4-flagos`，ID `4a12a9db0515ae847205b0de38a225ec205641efff55e835171b4d5d71e89537`，镜像 `sha256:d0af16489bc171d5434fc225c7afd89d32da7946af53655b9ad6dc7b50c745ca`；保持运行 |
| 工作根 | Host `/public/flagos/jinghao/deepseekV4.1` = Container `/public/flagos/jinghao/deepseekV4.1`；`/public` RW bind，两个视图下根目录 inode 均为 `226864815887` |
| 权重 | `/public/models/DeepSeek-V4.1-Flash-W8A8-BF16`；`config.json` SHA-256 `319a455c36424ca5bceef21eadfed8572c316d80afc3f79259730fd2e1b4b4ba`；`architectures=DeepseekV41ForCausalLM`，`model_type=deepseek_v41`，compressed-tensors W8A8，`flagos_bf16_engram=true` |
| vLLM | `0.24.1.dev0+gee0da84ab.d20260922.empty`；安装路径 `/usr/local/lib/python3.12/dist-packages/vllm`，source `/vllm-workspace/vllm`，Git HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`；非 editable 安装，且原工作树有无关既存修改；本任务只读 |
| Plugin | `0.3.0rc2.post1+gfd5c727fc`；editable source `/vllm-workspace/vllm-plugin-FL`，`main@fd5c727fcdb607bc4354cd11384761bb5d5ecfba`，检查时干净；本 profile 唯一可写产品源码 |
| FlagGems | editable source `/vllm-workspace/FlagGems`；用户授权后仅快进同步 `master@0927d5a0854238f1e33967c3145c0c95a66e50e2` → `master@7cd137ccaf09f25ce3012ba86438682072a69bc9`；同步后工作树干净 |

冻结的部署身份为
`H100-145:/public/flagos/jinghao/deepseekV4.1/01-environment/h100145-flagos-20260923/deployment-identity.json`，
Host 与容器读取 SHA-256 均为
`36543ca1be4ab77b4d2cbd0b9b0a98cafcb94a15960088bde0eaee24634f1a23`。
它绑定 `model.safetensors.index.json` SHA-256
`b2f55a31758defcde309cb875fc20ea341a995aca6fa7ff6699a288311ae1f58`、
48 个权重分片总字节数 `962114250788`、`tokenizer.json` SHA-256
`c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b`、
`tokenizer_config.json` SHA-256
`6ac8c8dc065ed118161d02dd532749ae3f52c243deac27872134fae2f50d8547`、
V4.1 编码文件 SHA-256
`502bdaec8a3fd88ebc24c4721a7038fbe42f2063c664638127056107920035c1`。
vLLM 现有未提交差异的 `git diff --binary` SHA-256 为
`2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`；
其 Git HEAD 和 dirty 状态从本任务开始至今保持不变。
同时从容器实时采集了 8 卡状态、模型/分词器哈希、三棵源码 HEAD 与
`git status --porcelain`，原始 JSON 保存在
`H100-145:/public/flagos/jinghao/deepseekV4.1/01-environment/h100145-flagos-20260923/live-state.json`；
采集文件 SHA-256 为
`ecbfca0a4d40ee7e1e70b6ae0fdaf4a9d28242998ef6cb0260680d6f1a2fbc3a`。
此快照显示 vLLM 的 87 条既存修改均未被本任务处理，Plugin 和 FlagGems 干净。

`./scripts/connectivity-check --limit H100-145` 与
`./scripts/accelerator-check --limit H100-145 --show-processes` 到达上述 Host。
FlagGems 同步使用单 Host Ansible playbook、`git fetch --no-tags origin master` 和
`git merge --ff-only FETCH_HEAD`；首次尝试遇到代理 503、未发生合并，重试成功。
没有使用用户提供的带凭据备用代理，代理凭据未进入脚本或日志。

工作根通过共享 NFS 同时出现在 H100-149。现有根级 `start-model.sh`
（SHA-256 `c3836b6b3d3d6382c0cc2efcc48249241dea96332c73f2ac6f1cfba4842b2389`）
是另一现场已有文件，不能当作 H100-145 的启动证明，也不能覆盖。
新运行产物必须以 H100-145 唯一名称写入本 profile 指定的 `01-environment/` 至
`07-bugs/` 目录；当前没有新服务或运行产物。

## 接口与差距

现有 vLLM 只有 `vllm/models/deepseek_v4`，没有
`vllm/models/deepseek_v4_1`、`DeepseekV41ForCausalLM` registry entry 或 V4.1
tokenizer 实现；其本地 `origin/main@a6c47fbbf4187e8ae5396ebdcf93234db617a4ad`
也未含 V4.1 model tree。Plugin 现有模型目录仅有 `qwen3_5.py`，尚未注册
V4.1。vLLM 暴露 `ModelRegistry.register_model()` 和
`TokenizerRegistry.register()`，但这两个注册点只解决入口，不会实现 CED、CSA2、
mHC、Engram、V4.1 DSML 分词与 W8A8/BF16 权重协议。

[Plugin PR #427](https://github.com/flagos-ai/vllm-plugin-FL/pull/427) 的对象已在
现有 Plugin Git object store 中核实：head
`da62cddeb538f3d9d203e4e07cbc164e94f76869`，30 文件、约 4,637 行新增；
`vllm_fl/models/deepseek_v4.py` 继承 vLLM 的 `DeepseekV4ForCausalLM`，是 V4
W8A8 output projection/算子接入，不包含 V4.1 架构。其 30 文件均不在当前 Plugin
`main` 工作树中。把该 PR 直接应用到当前容器并不能加载本模型。

H100-149 已验证的 NV-native V4.1 参考安装包含
`vllm/models/deepseek_v4_1/` 下 26 个 Python 文件、约 12,235 行，且依赖
`deepseek_v4` 公共组件；另有 V4.1 tokenizer。该安装与本 Host 的 vLLM 版本和
内部 API 并不相同。用户已明确锁定当前 vLLM，要求所需功能在 Plugin 补齐；
因此必须设计选择性可维护移植，验证所有缺失的引擎接口能由既有 Plugin 扩展点承载，
避免直接复制整套上游模型和绕过 dispatch。然后再做量化、算子 backend、H100 graph
适配。参见
`../adaptation/001-v41-engine-baseline.md`。

## 当前界限

已验证 Host、容器映射、包路径、Git 所有权、模型配置和基础缺口；
环境原生回执为
`H100-145:/public/flagos/jinghao/deepseekV4.1/04-runs/env-h100145-flagos-20260923/framework-check.json`，
SHA-256 `1bf5cbd6ad05135df4d077aef2f3ddcc70fa0b713e37882ac6ac6273a2886518`。
这只证明环境身份；未执行模型加载、eager、graph、精度或性能测试。
当前 vLLM 按用户指令锁定，不得更改源码或安装。
