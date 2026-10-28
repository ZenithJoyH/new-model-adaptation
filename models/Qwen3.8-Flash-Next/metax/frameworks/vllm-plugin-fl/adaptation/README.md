# 适配问题索引

目标：mx-101 / qwen3.8-flash；批准远端根 `/public-flash/jinghao/qwen3.8-flash`。
当前在做组件验证与整模bring-up，尚未通过完整验收。

| 问题 | 当前结果 |
| --- | --- |
| [001 PR455与FlagTree源码安装](001-pr455-flagtree-metax-bringup.md) | PR已应用；FlagTree main源码安装、ABI修正后Plugin回归111通过/4跳过 |
| [002 PLE状态原位更新](002-ple-prefill-state-read-write-race.md) | 用户PR959通用路径211通过；独立fusion修复与37项回归通过 |
| [003 MetaX QSA tile约束](003-qsa-metax-dot-tile.md) | 组合340通过/42跳过；新增selector后QSA51通过/8跳过；auto性能18项达标 |
| [004 CPU RNG clone兼容](004-clone-cpu-rng-profile.md) | clone排除后eager三类通过；graph追加randn/normal_原生入口后通过，底层随机缺陷仍未独立修复 |
| [005 前缀缓存align配置](005-prefix-cache-align.md) | 8730-token五请求通过，三次各真实命中6400；冷/热logprob差0 |
| [006 异构Mamba前缀状态复制](006-heterogeneous-mamba-prefix-copy.md) | Plugin工厂兼容与108项回归通过；eager真实3问全对，真实长前缀复用通过；graph状态/混合请求也通过 |
| [007 FlagGems-vllm现有运行时开关](007-flaggems-vllm-runtime-binding.md) | 开启FGV接入；21项Plugin/72项clamp通过，内存SQL配置下整模三类回归通过 |
| [008 graph逐级验证](008-graph-execution.md) | RoPE38/共享216通过；FULL受GDN限制，显式混合图及10例105token对照通过 |
| [009 真实安装差异审查](009-source-review.md) | 清洁graph后身份复核无变化；Plugin/FGV为声明范围内PR候选，未提交 |

[011 长推理容量与精度并发](011-gpqa-long-reasoning-capacity.md)：C8全量尝试因KV压力中断，24条部分响应完整保留；C2双61038token容量通过，独立full198正在运行。
