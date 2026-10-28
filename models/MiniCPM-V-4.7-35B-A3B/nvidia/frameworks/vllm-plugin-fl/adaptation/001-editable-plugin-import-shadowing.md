# 001：editable Plugin 导入被镜像内旧 namespace 遮蔽

## 元数据

- 状态：`open`（定位已验证；运行配置未完成）
- 首次出现与最后验证：2026-09-28
- 模型：`/data/models/MiniCPM-V-4.7/weights/35b-a3b`
- 平台、Host、容器：NVIDIA H100 × 8；`H100-149`；`MinicpmV4.7-35B`
- Plugin / FlagGems / vLLM：Plugin `3a27a6fb2d514cdf55c00481bf813225dac63319`；
  FlagGems `da6727e38f6f8eedef6cba43695a87b4996f9eca`；vLLM wheel `0.24.0+cu129`
- 执行模式与负载：Python import 只读探针，尚未启动模型。

## 问题现象与证据

Plugin 的 pip `direct_url.json` 指向 editable 源码
`/vllm-workspace/vllm-plugin-FL`，但默认环境的 `find_spec('vllm_fl')`
返回 `/usr/local/lib/python3.12/dist-packages/vllm_fl` namespace，
`find_spec('vllm_fl.models')` 也指向旧 site-packages namespace；
仅 `vllm_fl.platform` 解析到 editable 源码。这意味着仅凭 editable 元数据不能证明
正式 `vllm_fl:register_model` 执行了目标源码中的 `__init__.py`。
受控地前置 `PYTHONPATH=/vllm-workspace/vllm-plugin-FL` 后，顶层、`platform`
和 `models` 的 `find_spec` 均指向该 Git checkout。命令通过
`./scripts/playbook /private/tmp/minicpm35-readonly.yml --limit H100-149`
在目标容器内执行；探针未写产品文件。

## 已有经验匹配

MiniCPM-V-4.7-1B 原生容器的源码不可编辑问题与本次不同：本次 Plugin 有干净的
editable checkout，但被镜像旧 namespace 遮蔽。未找到匹配的知识库失败签名。

## 诊断、根因与受控尝试

已验证的直接原因是 Python 模块搜索优先级和镜像内另一个 `vllm_fl` namespace
目录共存。尚未证明实际 vLLM 插件加载过程的最终模块来源，也尚未观察模型服务失败。

| 轮次 | 唯一变量 | 顶层与 models 结果 | platform 结果 | 结论 |
| --- | --- | --- | --- | --- |
| 1 | 容器默认环境 | site-packages namespace | editable 源码 | 入口来源不一致 |
| 2 | 仅前置 Plugin 源码 `PYTHONPATH` | editable 源码 `__init__.py` / `models/__init__.py` | editable 源码 | 搜索路径可受控；仍需实际入口验证 |

## 解决方向与边界

在本任务的运行配置中固定 Plugin 源码 `PYTHONPATH`，并在 fresh process 与 worker
spawn 中验证 `register_model` 和目标模型实际命中。此配置属于目标服务身份，不修改
site-packages、vLLM wheel 或无关容器。若后续证明 editable 安装本身有系统性错误，
可提交独立包装/安装修复设计；当前不以重装或删除镜像内旧目录作为捷径。
服务未启停；本问题没有 Plugin 产品 diff。vLLM `minicpmv4_6.py` 与 `_version.py`
起始 SHA-256 见环境分析，适配收尾需复核。

## FlagGems 与验证

FlagGems 已按授权快进到上述 revision，工作树干净；本问题不涉及算子选择或修改。
最小 import 对照已通过，`eager`、graph、数值与服务启动均未验证。

## 限制与下一步

下一步在批准工作根的 `01-environment/` 固定不含秘密的目标运行配置，
用正式 Plugin 注册入口和 worker 环境验证导入路径，然后继续 4.7 模型适配。
当前设计审查结论：这是运行环境问题；尚无可供 PR 审查的产品改动。
知识库状态为 `needs-validation`，不据此推广到其他镜像。
