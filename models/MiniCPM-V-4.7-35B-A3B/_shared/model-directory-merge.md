# MiniCPM-V-4.7-35B / 35B-A3B 目录合并

合并日期：2026-10-12。用户明确确认两个名称指同一个模型，统一入口为 `MiniCPM-V-4.7-35B-A3B`；`model.yml aliases` 保存旧名称，工具调用使用统一名称。

两份原记录均指向 `/data/models/MiniCPM-V-4.7/weights/35b-a3b`，配置 SHA-256 均为 `3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646`。参数和索引校验沿用旧 35B 目录已有的本地检查，未确认上游 revision 或 PPU 权重与 NVIDIA 逐字节相同。

## 内容对应

| 合并前来源 | 合并后入口 | 处理 |
| --- | --- | --- |
| 35B / NVIDIA Plugin | [nvidia/frameworks/vllm-plugin-fl](../nvidia/frameworks/vllm-plugin-fl/README.md) | 整体迁移，问题编号与验收记录保留；framework 的 model 改为统一名称 |
| A3B / NVIDIA 原生 | [nvidia/frameworks/vllm-native](../nvidia/frameworks/vllm-native/README.md) | 原位保留 |
| A3B / PPU Plugin | [ppu/frameworks/vllm-plugin-fl](../ppu/frameworks/vllm-plugin-fl/README.md) | 原位保留，修复 NVIDIA 交叉引用 |
| A3B / PPU 原生 | [ppu/frameworks/vllm-ppu](../ppu/frameworks/vllm-ppu/README.md) | 原位保留 |
| 两份架构与模型元数据 | [架构与推理链路](../architecture-and-inference.md)、[model.yml](../model.yml) | 整合公共结构、参数统计及尚未验证项，框架特有结果回链各自记录 |
| NVIDIA 平台说明 | [平台入口](../nvidia/README.md) | 两份历史说明按框架保留；平台注册表增加 Plugin |
| 空平台与公共索引 | 各平台、模型及全局 README | 保留 A3B 骨架，合并导航，修复 1B 与 PPU 的引用 |

## 证据与人工接续

四套框架的 Host、容器、工作根、部署、验收计划、profile、人工交接历史与阶段状态保持原值。旧运行名、远端路径、哈希和回执仍属于原轮次，不因模型别名合并而转换成新证据。
现有 v2 阶段均为 `not_started`，本次不新增通过状态、不重算历史验证哈希。原生 vLLM 的 legacy 平台状态不代表 NVIDIA Plugin 通过。继续工作仍需选择准确框架、Host 和阶段，并遵守[人工协作流程](../../../docs/human-collaboration.md)。

## 完整快照与恢复

- [合并前 35B 全目录](../../../.local/adaptation-history/20261012-minicpm35b-merge-082214/snapshot/models/MiniCPM-V-4.7-35B)、[合并前 A3B 全目录](../../../.local/adaptation-history/20261012-minicpm35b-merge-082214/snapshot/models/MiniCPM-V-4.7-35B-A3B)。
- [逐文件 SHA-256 清单](../../../.local/adaptation-history/20261012-minicpm35b-merge-082214/before-manifest.json)、[恢复说明](../../../.local/adaptation-history/20261012-minicpm35b-merge-082214/README.md)。两份原始架构、metadata、README 和所有框架文件均可查回。
- [更早的 35B 契约升级前快照](../../../.local/adaptation-history/20261012-model-layout-080344/snapshot/models/MiniCPM-V-4.7-35B)。

完整快照位于 Git 忽略的本地归档，仅本机保存。旧目录剩余重复文件移入同一归档的 `retired/models/`；活动 models 目录只保留统一入口。本次没有远端执行或提交推送。

## 本地核对结果

合并前快照的 126 个文件均通过 SHA-256 与权限核对，包含两个模型全目录及三份外部索引/引用文件。四套框架的配置除迁入工作区的 `model` 名称外完全一致；286 个模型内本地 Markdown 链接可解析。审计前后问题清单完全相同，没有新增问题。全仓库既有两处 XingChen4 缺失目录链接错误和九项历史证据警告仍保留，不属于本次合并产生的问题。
