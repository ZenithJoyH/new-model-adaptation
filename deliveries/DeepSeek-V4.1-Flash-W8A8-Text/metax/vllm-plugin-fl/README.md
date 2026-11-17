# DeepSeek V4.1 / MetaX PR候选材料

本目录是可审阅的源码补丁与PR正文草稿，尚未提交、推送或创建PR；不包含权重、密钥、日志或评测缓存。代码已在实际安装树整理，运行时可执行逻辑未改变；为隔离GPU短暂停止过本任务服务，现已按原64脚本恢复，8项代表性输出及独立审阅正常。最终检查与未完成门禁见[审查说明](review-notes.md)。

| 顺序 | 仓库 / 建议主题 | 草稿 | 补丁 |
| --- | --- | --- | --- |
| 1 | FlagGems：限定clone Autograd注册并保留CPU路径 | [正文](flaggems-pr.md) | [3文件补丁](patches/flaggems-clone.patch) |
| 2 | FlagGems-vllm：V4.1所需数值API、注册、独立测试及受控调优 | [正文](flaggems-vllm-pr.md) | [45文件补丁](patches/flaggems-vllm.patch) |
| 3 | vllm-plugin-FL：V4.1文本模型、加载/metadata、dispatch、量化接线及示例 | [正文](plugin-pr.md) | [53文件补丁](patches/plugin.patch) |

先交付算子公开API及测试，再将Plugin依赖固定到公开可获取版本/提交。当前补丁按精确安装HEAD生成；Plugin候选目标为0.4.0-dev（vLLM0.28），FGV候选为main，FG候选为master，均不冒充用户确认的最终PR目标或已完成最新上游重基。原有8项MetaX standalone/MCCL修改已单独保留，未混入上述补丁。

完整适配仍未通过。公开固定依赖、同设置高精度质量比较、相应构建/CI和未测硬件范围不得以当前GPQA分数代替。13项实际安装树硬件回归已在103隔离GPU上全部通过（6项dtype图、6项注意力/缓存、1项词表集成），静态检查也已通过。共享GPU下新stream创建曾阻塞，前次失败证据保留，不能声称已修复驱动内部原因。

详细管理记录见[016源码审查](../../../../models/DeepSeek-V4.1-Flash-W8A8-Text/metax/frameworks/vllm-plugin-fl/adaptation/016-final-source-review.md)。本目录不修改安装源版本选择，也不是新镜像或可直接宣称验收通过的发行包。
