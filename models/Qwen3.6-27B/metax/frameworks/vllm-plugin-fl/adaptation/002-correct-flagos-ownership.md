# 002：纠正 FlagOS 所有权与 Flash Attention 重复分发

## 元数据

- 状态：`verified-root-cause / implementation-verified`；首次出现及最后核实：2026-09-23。
- Qwen3.6-27B / MetaX C550 / `mx-58` / 容器 `qwen3.6-27B`；镜像见[环境分析](../environment/README.md)。
- Plugin HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，FlagGems HEAD
  `c6f46cc970ea0bef8927ee657c021bd8621e3bb0`，FGV HEAD
  `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777`，vLLM HEAD
  `bc150f50299199599673614f80d12a196f377655`；仅 Plugin 属本 profile 可写产品树。
- 范围：本轮第 3 阶段接入设计纠正；TP2/GPU0,1、BF16、prefix cache enabled，
  eager 与请求 `FULL` 的 graph 模式；正式 acceptance 未选择。

## 现象与根因

首次实现虽把 FGV 算子注册成 `default.flagos`，却把 GDN hook 的安装入口放在
`vendor/metax/patches/gdn_linear_attn.py`，又修改
`vendor/metax/register_ops.py` 的 attention 可用性。更重要的是现有
`attention_backend` 已经把 FA 选进 FlagOS，自定义 backend 内还再次调用
`call_op("flash_attn_varlen_func")`，造成第二次不必要的 dispatch。用户指出这
违反 FlagGems/FlagOS 链路的所有权边界；旧问题 [001](001-flagos-flaggems-vllm-attention-gdn.md)
的源码位置、FA OpImpl 数量与部署身份结论因此被本记录取代。新问题并非 FGV
数值失败；历史 TP2 数值结果只作为算子 ABI 背景，不能直接证明新源码。

历史 Qwen3.6-35B 问题说明 GDN ABI 需单独验证，但不是本轮所有权设计的证据。
`docs/troubleshooting/` 无同一签名的已验证条目，本问题保留为本地设计纠正。

## 受控修改与职责

1. 撤销本轮对 `vendor/metax/register_ops.py` 与
   `vendor/metax/patches/gdn_linear_attn.py` 的增量；`git diff --` 这两个文件为空，
   原有 MetaX vendor 代码保留。
2. `vllm_fl/dispatch/config/metax.yaml` 仅定义 attention 顺序
   `flagos → vendor:metax`；FlagGems `register_ops.py` 决定 FlagOS attention
   的可用性。MetaX 上 `VLLM_FL_USE_FLAGGEMS_ATTN=0` 时仍为 MACA，设为 `1`
   且 FGV FA 导出存在时才选 `default.flagos`。其他平台原有 FlagOS 策略不变。
3. `vllm_fl/dispatch/backends/flaggems/impl/attention.py` 在已选中的
   `AttentionFLBackend` 内直接惰性调用 FGV `flash_attn_varlen_func`，仅按原
   BF16/FP16 契约去掉不适用的 FP8 descale。删除独立的 FA `OpImpl` 和 backend
   FA 方法；不再对每次 FA 执行第二次 `call_op`。
4. GDN prefill/recurrent 保留两个 `default.flagos` OpImpl，底层实现仍位于
   `flaggems.py`。vLLM 的七值 prefill、FP32 gate/beta、活跃状态 V×K/K×V
   适配和普通 decode 调用 hook 移至
   `vllm_fl/dispatch/backends/flaggems/impl/gdn_linear_attn.py`，从 FlagGems
   `register_ops.py` 在 MetaX 且 `VLLM_FL_USE_FLAGGEMS_GDN=1` 时安装。
   flag 关闭时不安装；KDA/spec 继续走原 vLLM 实现。未修改 vLLM/FlagGems/FGV。

替代方案是在 vendor 中安装 hook，或把完整 vLLM GDN core 复制到 Plugin；前者
违背用户指定边界，后者扩大维护和回归面，均未采用。公共调用方影响包括 MetaX
默认 attention、开启 FlagOS 的自定义 attention、Qwen3.5/Next GDN、其他平台
FlagOS attention；目前仅本模型/MetaX 得到模型级验证，不能外推支持其他平台。

## 验证与原生证据

- 新身份 `01-environment/deployment-identity-flagos-corrected-20260923.json`
  SHA-256 `8740a25ac400679af5791ac3fc7fd2469e879505391f6c3227f488582b3b9c71`。
  它绑定 Plugin tracked diff SHA-256
  `fb6a19258d953fb4dc9310c745918da72e10f4719f165ce02e662d2270807872`
  和新增 GDN 文件 SHA-256
  `2c2517ee46b48792c11bc00955d58e35dfd3dbc879e2fc41759196c7ac0c1b2c`。
- 开关路由原始 JSON：`04-runs/flagos-corrected-routing-20260923-off.json`
  SHA-256 `539bd4ca1de66cddbc578eeb3df909d7f12395af9c8f02b0c71015688f53998c`；
  `04-runs/flagos-corrected-routing-20260923-on.json`
  SHA-256 `6996bc2ac667bbfc28ada18482dd864d7433368e93fcfa6d675553306818ba2a`。
  关闭时 attention=`vendor.metax`、GDN hook=false；开启时
  attention=`default.flagos`、GDN hook=true；两个 GDN 算子均为
  `default.flagos`，且不存在第二个 FlagOS FA OpImpl。
- eager：`04-runs/flagos-corrected-eager-20260923/launch.sh` SHA-256
  `a03f46003c75a0bb42773c3615191c14f3945fbbac73766ad05c85b635e0a4a8`；
  `service.log` SHA-256
  `9d3d80cc55ee341b6868d9b58d46cf0e3dfaf3339ed36923b181c8fcddad59c2`；
  `completion-response.json` SHA-256
  `64c7e6820e9a05c0f41ddb0b1f6394af1628bb5e82adba5f3b3311ff80bff7a7`。
  两名 worker 均命中 FlagOS attention、GDN chunk/recurrent；实际请求 HTTP 200、
  16 token。
- graph：`04-runs/flagos-corrected-graph-20260923/launch.sh` SHA-256
  `029602820a423fc7cdc0f5d27db62017ffe7be0b9cf358992e75538d231ada91`；
  `service.log` SHA-256
  `3b839f6093bdf94b78c5f25af7667ea48e48ad66c5821d39ce6f223b254f41d5`；
  `completion-response.json` SHA-256
  `2d572197c56a27507382f27dc30f51afc9d2efd4ee375ba12b9299ee14221537`。
  精确请求 `cudagraph_mode=FULL`，stock vLLM GDN metadata 的
  `AttentionCGSupport.UNIFORM_BATCH` 使其自动转为 `FULL_DECODE_ONLY`；两名
  worker 在 capture 前命中 FlagOS GDN recurrent，decode graph 3/3 捕获，
  实际请求 HTTP 200、16 token。原 8000 服务全程未停，最后健康检查 200；
  两个本任务 8001 实例均按经核实的 PID 停止，容器保持运行。

`git diff --check` 和四个修改文件/一个新增文件的语法检查通过；
`vendor/metax` 两文件当前无 diff。未做新源码的独立数值对照、正式准确率或
稳态性能，因此模型冒烟不能作为第 4 阶段验收。原历史数值对照见 001，
但其 FA 测的是已删去的独立 OpImpl，需在正式验收前改为经 attention backend
触发的数值/准确率验证。

## 复核、限制和退出条件

PR base 未确认；Plugin HEAD 仍为上述 detached revision，五个本轮源文件
（四个 modified、一个 untracked），无提交/推送/PR。vLLM 只有继承的
`fused_recurrent.py` dirty diff SHA-256
`a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`；
FlagGems 与 FGV 保持 clean。MetaX GDN decode 的活跃 state
gather/transpose/scatter 仍可能有性能开销，未量化。FP8、FA3、DCP、KDA/spec、
其他模型/平台及 FGV 依赖缺失未验证；不得声称支持。解除 FULL prefill graph
限制需上游/Plugin 提供经实测的 GDN metadata/replay 支持，再重新尝试 FULL。
本问题知识库状态 `local-only`；正式 acceptance 尚未选择。
