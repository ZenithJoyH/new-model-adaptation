# 100K验收前适配阶段复核

范围：mx-101 / qwen3.8-flash，BF16文本TP8；远端根 /public-flash/jinghao/qwen3.8-flash。

Plugin PR455、FlagGems-vllm PR959及本任务最小修复见001–009。贡献结论沿用009逐块审查：Plugin和FlagGems-vllm可作为声明范围内的PR候选；FlagGems没有本任务源码变更，vLLM保持只读。2026-10-24重新逐项比较真实安装的HEAD、完整diff、新增文件集合和SHA256，与85fbbd4d快照一致。未提交或推送。

100K上下文增加qwen3 reasoning parser，两种模式均保留clone,randn,normal_追加排除、FGV接入、内存SQL、prefill6400和prefix align。100K eager与显式FULL_AND_PIECEWISE三类整模请求通过，10例105token完全一致，最大生成token logprob差0.0029179352≤0.02。该对照覆盖短问、真实长前缀复用、混合流式请求；不等同全logits对照或GPQA验收。八客户端长前缀容量探针两种模式均通过，实际服务峰值4个运行请求，不能宣称8路同时活跃。

纯FULL更高优先级尝试的同源码GDN UNIFORM_BATCH能力限制及处置保留于008。该尝试使用50K上下文，100K没有重复纯FULL启动；当前明确选择混合图。正式全量精度、九场景性能、最终启动脚本和交付尚待完成；当前不标记optimized。镜像打包尚未执行。
