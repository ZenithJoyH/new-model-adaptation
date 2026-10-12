# 013：GPQA 续跑直调缺少 API key 占位值及异常伪装超时

## 元数据

- 状态：`open`；首次出现及最后验证：2026-09-24。
- 模型/平台/Host：DeepSeek-V4-Flash W8A8，MetaX C550 x8，`mx-59`。
- 评测镜像：`harbor.baai.ac.cn/flageval/flageval-llmeval:v1`，image ID `sha256:62dac3397d7285a3ee6b30d196f951b677fc1e9ad9727e655200b92123f71a2c`；服务容器 `deepseek` ID `25df046a24ee4f823c650a5a34a4e4e29ac7aa4cdd361472435b3ab3f63ff149`。
- 任务：GPQA Diamond Think Max 198 题单次诊断，原作业 61 题后由用户中止；相同 compile 服务、任务与生成参数下补齐剩余 137 题。产品代码未改动。

## 问题现象与证据

- 原生 Runner `test/Accuracy_test/llmrun.py` 为每轮生成 nonce，拒绝跨进程恢复旧结果/缓存身份。续跑使用旧缓存的独立 SQLite 快照，原生 `--cached_only` 证实 `61/198 cached`，两个 filter 共 122 行；旧缓存和原中止容器不改动。
- 首次直接 `lm_eval` 调用的缓存计数为 61 命中、137 剩余，但容器 `deepseek-gpqa-diamond-max-resume-20260924-01` 在约 14 秒内以退出码 0 结束。attempt-1 表面有 198 唯一题、396 行，却把 137 个新请求全记为 `<TIMEOUT>`；缓存仍与启动前 SHA 相同。137 条异步异常都是同一条“API key 未找到”指纹，不是 86400 秒请求真实超时。结果和样本的精确路径、SHA 见 [运行记录](../acceptance/gpqa-diamond-max-diagnostic-20260923.md)；不展示受保护 GPQA 内容。
- 相同服务容器 `/health=200`，无 GPQA 内容的短请求返回 HTTP 200；从相同评测镜像、host network、增加 `OPENAI_API_KEY=EMPTY` 的短请求也返回 HTTP 200。旧与新评测容器的代理/API 环境变量名称已对比，缺失不是用户秘密，而是 Runner 运行时设置的占位值。

## 已有经验匹配

| 既有记录 | 相同点 | 差异及决定 |
|---|---|---|
| [012：GPQA 阶段评分口径](012-gpqa-max-partial-score-drift.md) | 相同任务和指标 | 012 是 strict 提取口径；本问题发生在 API 请求前，不能解释为模型答错或评分规则差异。 |
| [011：GPQA 模式差距](011-gpqa-reasoning-mode-score-gap.md) | 相同模型/服务目标 | 本问题是恢复入口环境缺失，与 Think Max 语义及 W8A8 数值尚无因果证据。 |

## 诊断、根因与受控修正

1. 只读查看 pinned `lm_eval` 源码：`CachingLM` 将旧 pickle `None` 视为未命中、正常缓存 61 条；异步 API 调用失败后通用异常处理会把异常转换为 `<TIMEOUT>`，而不是只对实际超时这样做。因此仅凭 lm-eval 退出码 0、198 行或低分都不能接受本 attempt。
2. 本项目 Runner 的 `configure_environment` 会执行 `os.environ.setdefault("OPENAI_API_KEY", "EMPTY")`；直调 `lm_eval` 时未执行 Runner，且新容器没有该环境变量。缺失占位值与 137 条同类 API-key 异常、零新增缓存吻合。只增加非秘密 `OPENAI_API_KEY=EMPTY` 的同镜像短请求返回 HTTP 200，服务未重启。
3. 原 attempt-1 原样保留并标为无效；缓存快照 SHA 保持 `3ffb8ab10fc00cb71a05d301b23ca6d31f1b2c5ae577c2d5a2c26f75c6096aa9`。用新 attempt-2 目录与容器、相同缓存和命令，仅补齐 `OPENAI_API_KEY=EMPTY`；启动日志已确认 61 命中、137 剩余，初始容器运行、错误计数 0、服务健康 200。最终成功仍待 198 唯一题/396 行、无非超时错误与 SHA/评分验证。

## 处理边界与下一步

- 本轮不改 FlagGems、Plugin、vLLM、模型服务或冻结评分指标；不能把伪 `<TIMEOUT>` 归因于硬件/模型精度。正式评测的通用异常应区别真实请求超时和配置/连接错误，但这是评测工具层候选修复，未在本次续跑中改源码。若要固化跨进程恢复功能，应单独设计缓存身份、快照和失败语义的回归测试，不绕过正式验收前置。
- 所有新配置在批准根 `03-acceptance/`、结果在 `04-runs/`、临时过程代码在 `05-tmp/`、缓存快照在 `06-cache/`。原作业与适配容器未重启/移除；监控只读。知识库处理：`needs-validation`，等待 attempt-2 完整结果后再评估是否可跨模型复用。
