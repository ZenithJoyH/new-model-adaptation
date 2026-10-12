# 推理环境分析

核实日期：2026-09-23；唯一目标 SSH alias 为 `mx-58`，连接到
`bm-jdyun-wx-zone1-d-mc550-64g-2-58`。`./scripts/connectivity-check --limit mx-58`
返回 ok=2、failed=0、unreachable=0；`./scripts/accelerator-check --limit mx-58`
通过，使用 MetaX 原生命令 `mx-smi`，显示 8 张 C550 64G、驱动 3.8.1、MACA 3.7.1.5。
没有用其他厂商查询工具替代。

目标容器 `qwen3.6-27B` 保持 running。镜像：
`harbor.baai.ac.cn/flagrelease-public/qwen3.6-27b-metax001-gems5.4.0-tree0.5.1-cxnone-plugin0.2.0-vllm0.20.2-cp312-pt28-maca37-x64-3.8.1:202607220155`。
用户指定并批准 Host 工作根 `/public-flash/jinghao/qwen3.6-27B`；容器内同路径。
`docker inspect` 已核实 `/public-flash:/public-flash` 读写 bind mount；两侧该目录
`stat` 的设备/inode 均为 `55:4137227`。历史根目录 `start-model.sh`、`service.log`、
`profile/` 保留原样；新运行产物只进入当前 01～07 编号目录。

组件身份与所有权：

- vLLM `/workspace/vllm@bc150f50299199599673614f80d12a196f377655`；源码只读。已有
  `M vllm/model_executor/layers/fla/ops/fused_recurrent.py` 是继承改动，不纳入本轮修改。
- editable-installed Plugin `/workspace/vllm-plugin-FL@675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，
  import 路径 `/workspace/vllm-plugin-FL/vllm_fl/__init__.py`，版本 0.2.0；开始时 detached HEAD、
  工作树 clean，是本 profile 唯一产品代码可写树。
- FlagGems `/workspace/FlagGems@c6f46cc970ea0bef8927ee657c021bd8621e3bb0`，
  master 跟踪 origin/master、开始时 clean；现有 KV cache 等算子依赖保留，不在本轮同步或编辑。
- FlagGems-vLLM `/workspace/FlagGems-vllm@05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777`，
  import 路径 `/workspace/FlagGems-vllm/src/flaggems_vllm/__init__.py`，版本 0.1.0，
  main 跟踪 origin/main、开始时 clean；本轮只调用其已安装导出，不修改源码。

权重只读目录 `/public-flash/models/Qwen3.6-27B`；配置和权重索引 SHA-256 见模型级
`architecture-and-inference.md`。现运行 OpenAI API 端口 8000，TP2、设备 6/7；
服务 PID 154980、engine 155256、worker 155524/155525 是检查时的快照，后续须重新核对。
现有服务通过旧根目录启动器启用 profiler 和 `--no-enable-prefix-caching`，属于性能/诊断轮次，
不能作为后续非性能适配验证的服务配置或最终启动脚本。

变更前 `metax.yaml` 把 `attention_backend` 只分发到 `vendor.metax`，实际为 MACA
Flash Attention 2.6.3。虽然 FlagOS backend 有 `VLLM_FL_USE_FLAGGEMS_ATTN` 分支，
该环境变量不在现服务环境中，而且当前 MetaX 路由不会进入它。GDN 的 prefill 走 vLLM
Triton/FLA，普通 decode 有 packed recurrent 快捷路径；Plugin 的 MetaX 层使用
`torch.ops.vllm.gdn_attention_core` 进入该路径。FlagGems-vLLM 导出
`flash_attn_varlen_func`、`chunk_gated_delta_rule_fwd`、
`fused_recurrent_gated_delta_rule_fwd`；后两者需分别保持变长 chunk metadata 和 FP32
gate/beta 语义。FlagOS `OpImpl` 注册及 policy 是本轮唯一新增算子选择入口。

本轮只选择 architecture、environment、adaptation 三阶段；没有选择正式 acceptance，
因此不得把算子验证或现服务就绪等同于模型 eager/graph、准确率、性能验收通过。

## 首次接入的历史身份（已被修正实现取代）

变更后的现场身份保存于 Host/容器同路径
`/public-flash/jinghao/qwen3.6-27B/01-environment/deployment-identity-flagos-20260923.json`，
SHA-256 `b760fe1f547ac022ea2dd360f7a64a845f2880db3545464befeb32e3d2ba505f`；
它同时是本轮 `deployment.fingerprint`。该身份绑定镜像 digest、模型配置/权重索引/
tokenizer 哈希、四个组件的 HEAD 与 dirty diff（Plugin 本轮 diff SHA-256
`196ee5aa9b6a82786c8e139c86a2c89ad06b2e341de469434c84b9b7e71d9fa4`）、
TP2 GPU0/1 和 prefix-cache-enabled 的共同测试配置。未声称对 15 个权重分片
逐字节完成哈希；按已检查的权重索引和原路径固定身份。原始基线指纹
`1e5c869632fc07d49d56e7a4bedd51cf2099f7912d733d2acc388b9462afab2d`
保留在历史 `identity-20260923.txt`，不再用它证明新代码。

隔离实例在 8001 端口、GPU0/1 上分别运行 eager 和请求 `cudagraph_mode=FULL` 的
graph 探针。二者都保持 `--enable-prefix-caching`；原 8000/设备 6,7 服务不变。
eager 完成模型请求；graph 启动时 stock vLLM 的
`GDNAttentionMetadataBuilder._cudagraph_support=UNIFORM_BATCH` 把 FULL 自动改成
`FULL_DECODE_ONLY`，随后 decode CUDA graph 3/3 捕获完成并通过模型请求。
两台隔离实例在验证后均按精确 PID 停止，8000 原服务仍返回 200。
过程证据和设计限制详见 `../adaptation/001-flagos-flaggems-vllm-attention-gdn.md`；
这些冒烟检查不替代第 4 阶段正式执行模式、准确率或性能验收。

## 修正后的历史部署身份

2026-09-23 按用户指出的所有权边界修正：FA 已由现有
`attention_backend → default.flagos` 选中，在该 backend 内直接调用
FlagGems-vLLM，不再把 `flash_attn_varlen_func` 另注册为 `OpImpl`；GDN 的
prefill/recurrent 注册和调用适配均位于 FlagGems/FlagOS 路径。本轮对
`vendor/metax/register_ops.py` 与 `vendor/metax/patches/gdn_linear_attn.py`
的新增改动已撤销；原有 MetaX 代码未改。`metax.yaml` 的 attention 顺序为
`flagos → vendor:metax`，FlagOS 注册可用性由 attention 开关控制，关闭时
仍选原 MACA 路径。

新现场身份为 Host/容器同路径
`/public-flash/jinghao/qwen3.6-27B/01-environment/deployment-identity-flagos-corrected-20260923.json`，
SHA-256 `8740a25ac400679af5791ac3fc7fd2469e879505391f6c3227f488582b3b9c71`。
已重新核实镜像 digest、模型配置/索引/tokenizer 哈希、四个组件 HEAD 与状态；
Plugin tracked diff SHA-256 为
`fb6a19258d953fb4dc9310c745918da72e10f4719f165ce02e662d2270807872`，
新增未跟踪产品文件 `vllm_fl/dispatch/backends/flaggems/impl/gdn_linear_attn.py`
SHA-256 为 `2c2517ee46b48792c11bc00955d58e35dfd3dbc879e2fc41759196c7ac0c1b2c`。
其余组件未修改。旧指纹不再证明当前源码。修正后的模型级 graph 冒烟见
`../adaptation/002-correct-flagos-ownership.md`；正式 acceptance 仍未选择。

## 历史源码身份更新：直接调用已安装的 FGV

2026-09-23 按用户确认，默认镜像的 `flaggems-vllm` 是必备依赖，故移除
FlagOS 注册阶段逐项检查其导出的 `_has_flaggems_vllm_op`。新身份为 Host/容器
同路径 `01-environment/deployment-identity-flagos-direct-fgv-20260923.json`，
SHA-256 `38f5790fe8edfa4593f9dab1a212dc1c2f17acc74baa4253f1e2abfd5bf5abcf`；
Plugin tracked diff SHA-256 为
`816532008cc0da8c1f8d7409a49b45920b37355de735b783546c1a7043659668`。
新进程已确认三个 FGV 导出可调用、开关前后 FlagOS 路由正确。
上节 002 身份及其 eager/graph 运行仍保留为历史证据；其原生回执不能直接绑定本次
新源码。详见 [问题 003](../adaptation/003-remove-fgv-export-probes.md)。

## 历史源码身份：移除注册层门控

2026-09-23 再按用户要求，移除 FlagGems 注册文件的 attention 附加判断和 GDN
环境变量门控。Host/容器同路径的新身份为
`01-environment/deployment-identity-flagos-no-gates-policy-20260923.json`，SHA-256
`a25e369a2206da9226cc72e3fd742d5bfbc8b7dbca9859752a7955bcc4e89b40`；
Plugin tracked diff SHA-256 `b681f19bd1de01745fc2f3c5cabccca8eef81f4fda2fbd13a82184664bcc19dc`，
GDN 未跟踪文件 SHA-256 `2c2517ee46b48792c11bc00955d58e35dfd3dbc879e2fc41759196c7ac0c1b2c`。
已重新核实容器镜像 digest、模型配置/权重索引/tokenizer 文件、四个组件 HEAD 和
dirty 状态；vLLM 仅保留原有继承 diff，FlagGems 与 FlagGems-vLLM 仍 clean。
测试配置保持 TP2/BF16/GPU0/1 和前缀缓存开启，去掉 `VLLM_FL_USE_FLAGGEMS_GDN`。

当前 MetaX attention policy 仍为 `flagos → vendor:metax`，但 FlagOS 注册不再由
`VLLM_FL_USE_FLAGGEMS_ATTN` 门控；关闭该变量时首选 FlagOS 实际返回 vLLM Triton
attention，而非旧记录中的 MACA，开启时返回 FlagGems-vLLM attention。
GDN hook 在 MetaX 的 FlagGems 注册路径、且两个 GDN OpImpl 通过现有 policy
并且 backend 可用时安装，不再需要单独环境变量。最终 diff 的正/负路由已通过；
FA 开启的隔离 eager 模型请求绑定加入 policy 守卫前的相邻 diff。关闭 FA
变量时只核实 backend 路径，最终 diff 的模型 eager/graph 尚未复测。见
[问题 004](../adaptation/004-remove-flagos-registration-gates.md)。
003 及更早的环境回执和服务日志是历史证据，不能证明当前源码。

## 历史源码身份：MetaX GDN 双路由

2026-09-23 按用户的新要求，在 MetaX vendor dispatch 链注册 `gdn_prefill` / `gdn_decode`，
直接委托原 vLLM/FLA prefill 与 fused-sigmoid decode；FlagOS 同名候选仍调用
FlagGems-vLLM，Flash Attention 仍只经已有 `attention_backend` 选择。默认策略下
两种 GDN 候选同时注册且 FlagOS 优先；现有 per-op policy 可只选择 vendor。
没有恢复 `VLLM_FL_USE_FLAGGEMS_GDN` 控制。decode 原位更新 cache，选定候选失败时
使用局部 strict dispatch，避免对可能已修改的状态跨后端重试。非 speculative vendor
decode 保留原 packed 快捷路径，KDA/spec 保留原 vLLM 路径。

Host/容器同路径的最终身份为
`01-environment/deployment-identity-dual-gdn-tested-20260923.json`，SHA-256
`07453f51fd424007e3909499b4787fb7d2acc833a8d0267a6e419d8ef0f79991`。
Plugin HEAD 不变，tracked diff SHA-256
`3f22766bc58cb900e466e779e1432e0e70a6593e534c40c551fdfaa79dfab678`，
未跟踪 GDN adapter 与聚焦测试 SHA-256 分别为
`52f53620eee92c012ba56127c40cc589d9a2c2d14503a47681b14c114b185eaf` 和
`207d86ce631968155bfc61fd73ba51a4b58308e268ed3e72dc865721087a1c66`。
此前各身份和回执仅作历史证据，不能绑定当前源码。真实 eager/graph 路由、
原 8000 服务保护及未覆盖的数值/性能范围见 [问题 005](../adaptation/005-dual-route-metax-gdn.md)。

## 当前源码身份：GDN 全平台 FlagOS 高层注册

2026-09-23 根据用户进一步明确的范围，FlagOS GDN hook 由 FlagGems 注册末尾无条件安装，
不再依赖 MetaX vendor 注册；`gdn_prefill/gdn_decode` 两个高层候选不经过通用名单过滤。
低层 `chunk_gated_delta_rule_fwd` / `fused_recurrent_gated_delta_rule_fwd` 仅由
FlagOS backend 内部直接调用 FlagGems-vLLM，不再单独注册 OpImpl。MetaX vendor
原 vLLM/FLA 候选保持不变，未新增其它平台 vendor/reference 算子。

Host/容器同路径新身份 `01-environment/deployment-identity-global-gdn-high-level-20260923.json`
的 SHA-256 为 `a4f7dbcffd77d6d9d8d7cd93ba81a41f9624dc6c8b73c19da8928479723460b0`；
Plugin HEAD 未变，tracked diff SHA-256 `21fcbdf61a525f6ad3671187a9a47fb860caa5486296d4cd53a945ae3be50bf7`，
未跟踪 GDN hook 和测试 SHA-256 分别为
`8328ee53d89e9551b4a497896c97bbac02507f5116da91a81ef849efe4a14a4c`、
`de96f22cd7946132241149ceb00c5f564c945ba4b87308477cff89d1cac54cb5`。
已核对当前容器 digest、`/public-flash` 映射、模型配置/索引/tokenizer 和四组件源码身份；
旧 005 身份及回执不再绑定当前源码。MetaX eager/decode-full 新轮次和无 vendor 注册
逻辑测试见 [问题 006](../adaptation/006-global-flagos-gdn-high-level.md)；非 MetaX 硬件
算子尚未验证。

## 当前源码身份：GDN 黑名单与公共 patch 入口

2026-09-24 将 FlagOS 的 `gdn_prefill/gdn_decode` 恢复为通用
`use_flaggems_op(op_name)` 过滤，`VLLM_FL_FLAGOS_BLACKLIST=gdn_prefill,gdn_decode`
可以关闭 FlagGems-vLLM GDN。hook 从 FlagGems 注册目录移到公共
`vllm_fl/patches/gdn_linear_attn.py`，由 `WorkerFL.load_model()` 在模型构建前
安装，两套 `register_ops.py` 不再安装它。MetaX vendor 的原 vLLM/FLA 候选
不变；没有 vendor 候选时仅对 registry 空缺回到原 vLLM 函数。低层 GDN kernel
仍由 FlagOS backend 内部调用；FA 接入未改变。

Host/容器同路径身份
`01-environment/deployment-identity-gdn-blacklist-shared-patch-20260924.json`
SHA-256 `8f24b75565c1ec521581fcc31d181365ef515eb372036dcd886983410fbd5e37`；
Plugin HEAD 未变，tracked diff SHA-256
`8871947198ded21d3c3c8446193007fd667a2ebde655037ffacc1ca125d7a899`，
未跟踪公共 hook / 聚焦测试 SHA-256 分别为
`023834bea19381b171d787138c5bbd953df5a792629040d35d4231a86507b5b9` /
`c203ba20087fbf556a457e032ee8b57082484dcfb28e35c4bf50bc9944040246`。
已重新核对容器 digest、模型配置/索引/tokenizer 和四组件 HEAD、dirty 状态。
默认/黑名单 × eager/graph 的现场结果、原始路径和限制见
[问题 007](../adaptation/007-gdn-blacklist-shared-patch.md)；非 MetaX 硬件未验证。
