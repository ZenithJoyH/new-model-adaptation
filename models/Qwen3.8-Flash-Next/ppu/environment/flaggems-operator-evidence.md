# FlagGems 算子检查（2026-09-04 历史记录）

2026-09-04，master已fetch+pull --ff-only至8416e6dab471451cc437aac3896fdc382dce382e，clean且等于origin/master。同步记录sync-and-prepare-evidence.jsonl。
递归检索src/flag_gems全部Python文件，QSA/PLE/ngram/common_slot以及packed GDN ABI均无匹配；详见inspect_synced_operators.json。
存在chunk_gated_delta_rule与fused_recurrent_gated_delta_rule_fwd，但不是packed-QKV、索引原位SSM、FP32 beta且调用方提供输出buffer的decode接口，不能无适配直接替换。ARM的causal conv monkey patch不是PPU设备实现。
因此本次复用候选插件的10个DEFAULT/portable Triton dispatch：6个QSA、PLE gather/scatter、GDN packed decode、common slot mapping。源路径vllm_fl/dispatch/backends/triton/qwen38，注册在triton/register_ops.py。明确是插件自有算子，不冒称FlagGems已有。
安装后先跑注册与结构测试，再numerical/layout/dtype/eager/graph用例。当前仅完成代码搜索，尚未通过本容器设备测试。通用算子依旧走现有插件FlagGems/厂商分派；发现算子错误时，在工作根 `08-bugs/` 整理最小复现并通过容器对应路径原地执行，已有用例不再复制到 `/bug`。
运行时triton模块3.6.0由当前镜像提供，与历史分支测试3.5.0不同，必须重跑回归。
