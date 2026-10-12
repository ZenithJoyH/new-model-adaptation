# Qwen3.6-27B / MetaX / vllm-plugin-fl

记录于 2026-10-12 显式升级为 evidence v2 / profile v7。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

最新进展（2026-10-10，mx-59）：已安装Plugin更新至官方兼容vLLM0.20.2的
release/0.2@8b059122，MetaX vendor FA恢复原生mcoplib KV写入，保留GDN/attention、
连续prefill和ready-PID适配。280项dispatch、8组cache eager/图重放及TP2
FULL_AND_PIECEWISE启动、4条短请求通过；临时服务已释放，容器仍运行。
FG/vLLM及共享launcher未改，未重测吞吐或打包镜像；详见[018](adaptation/018-mx59-plugin-compatible-release-upgrade.md)。
下面为mx-58历史记录，不作为当前mx-59服务状态或正式验收证明。

历史进展（2026-09-24）：按用户收窄范围，仅优化FlagGems-vLLM的MetaX Flash
Attention，取消GDN decode优化。为D256/GQA5–16的单query路径启用既有BM16/BN16
Split-KV，并修复partial输出stride；Plugin/GDN/公共FA计算均不改。GPU2上78项新增
回归与4项已有FA用例通过；B64/K4096算子耗时4437.171→921.830us（4.81x），
B64/K16384为5.17x，prefill控制基本不变。仅算子级验证，未重启模型服务、未测
端到端吞吐，也未更新正式验收状态。当前8001 health=200，8000在容器localhost不监听。
当前FGV源码和完整对照见[问题011](adaptation/011-flash-attention-splitkv.md)。
以下009启动与模型回归结果是历史证据，用户之后更改过profiling启动脚本/服务；旧PID、
启动脚本hash不能作为当前实例证明。

核实日期 2026-09-24；唯一目标 Host `mx-58`，容器 `qwen3.6-27B`。本轮
architecture 已完成，适配工作仍为 `in_progress`。当前源码在007公共patch/双路由
基础上修复了FlagOS GDN分页状态写回，详情见009。007环境身份是历史快照，未覆盖
当前source diff，不能作为本次部署的正式验收身份。`framework.yml`
保持适配中：正式第 4 阶段 acceptance 未选择，不能据冒烟标记
`functional` 或 `optimized`。

FA 保持现有 `attention_backend → default.flagos` 入口，由其 backend 内部选择
FlagGems-vLLM；未新增第二个 FA OpImpl。GDN 的两个高层调用点同时注册
`default.flagos` 和 MetaX `vendor.metax`：前者在 FlagOS backend 内适配并调用
FlagGems-vLLM，后者惰性委托原 vLLM/FLA prefill 与 decode；只有这两个高层算子
进入 GDN dispatch，低层 kernel 由 FlagOS backend 直接调用。公共 GDN hook
由 `WorkerFL.load_model()` 在模型构建前安装，与两套 `register_ops.py` 分离。
FlagOS 两个高层候选经过通用名单过滤；黑名单移除它们时，MetaX 选择 vendor，
纯非 speculative decode 保留原 packed 路径；没有 vendor 候选的平台仅在 registry
确实为空时回到捕获的原 vLLM 函数。默认 FlagOS 优先，不恢复
`VLLM_FL_USE_FLAGGEMS_GDN`。decode 对原位状态更新启用
局部 strict dispatch，不在失败后跨实现重试。vLLM、FlagGems、FlagGems-vLLM
源码未被009编辑；后续011仅修改FlagGems-vLLM中的MetaX FA。

此前007仅验证HTTP200/非空文本的结论不足；新发现非连续GDN状态写回会造成乱码，
现已在Plugin ABI适配处按真实stride转换，vLLM/FlagGems/FlagGems-vLLM源码不改。
TP2/BF16/GPU0/1、tokens16384、maxseqs默认256、prefix开启、gpuutil0.8，
不显式配置compilation mode（默认3），`FULL_AND_PIECEWISE`成功捕获mixed51/51
及decode FULL35/35。修复后8条文本与原vendor黑名单对照逐条一致。
GPU状态/图重放6/6、Plugin dispatch单测276/276通过。原8000服务和容器未中断。
eager也完成8条正常文本回归。最终用户脚本`/public-flash/jinghao/qwen3.6-27B/start-model-new.sh`
已在Host/容器同路径验证，SHA256 `5a54d34899a8a78935fd6c173b6c7e93676d5159ac4263574d3f5057055ac286`。
2026-09-24最后一轮PID754946/GPU0,1/8001保留运行；原8000及新8001 health均200。
原始日志/8条输出/验证JSON在`04-runs/start-model-new-20260924-113703-754937/`。
该最终运行前4条预期答案通过，7/8与vendor全文一致，第8条thinking续写有差异，
不宣称逐token全一致。原`start-model-new.sh`已备份，历史`start-model.sh`未改，
本次不是正式验收完成后的最终profile launcher交付。
这些是适配冒烟，不是正式 execution-mode、准确率或性能验收；其他模型/平台、
chunked/mixed batch 与直接数值回归仍未完整验证。若选择第 4 阶段，应按 profile
顺序完成 execution-mode、sanity、accuracy、performance、evidence、summary，
再重建根目录最终启动脚本，不能沿用历史 profiling 启动器。当前结果与设计审查见
[问题009](adaptation/009-gdn-paged-state-stride.md)，启动缓存诊断见
[问题008](adaptation/008-fa-full-piecewise-shape.md)；[环境分析](environment/README.md)
及001～007均为历史证据，当前源码hash记录在009。

本地仅保存精简 Markdown 与 `framework.yml`；可执行过程产物和原始日志在 Host/容器
同路径 `/public-flash/jinghao/qwen3.6-27B` 的批准编号目录内。
