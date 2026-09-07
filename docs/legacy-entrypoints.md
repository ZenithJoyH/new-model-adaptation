# 历史执行入口与新运行边界

2026-09-07 的本地修复将不可安全重放的一次性入口改为明确拒绝执行。原文件路径仍在，
但正常调用仅给出停用原因并返回非零；不连接服务器、不改文件、不发模型请求、不启动或停止进程。
Python 入口可以安全导入；shell 被 source 时返回失败，不主动退出调用者 shell。
Ansible 入口仅含本机失败任务，原远端任务不再留在可执行 YAML 内，也没有绕过开关。
Ansible 自身的 `--skip-tags always` 或排除 localhost 的 `--limit` 可跳过唯一拒绝任务并
返回 0，但不会运行任何历史动作；这种退出码不表示入口已启用或新操作已获准。

## 保留范围

| 模型/平台 | 历史材料 | 处理与可用替代 |
|---|---|---|
| GLM / PPU | 固定目录的 `start_gpqa.sh` | [完整原文及 SHA256](../models/GLM-5.3-Flash-BF16/ppu/acceptance/historical-entrypoints/README.md)；新全量精度使用共享 runner |
| Qwen / PPU | 旧全量/22 题启动、22 题执行器和旧 graph sanity Playbook | [完整原文及 SHA256](../models/Qwen3.8-Flash-Next/ppu/acceptance/historical-entrypoints/README.md)；正式精度与诊断子集保持区分，前台 sanity 测试源码保留 |
| Hy4 / PPU | 三组旧 GPQA shell/Playbook、旧 stop/restart、固定路径的 sanity/check/score 部署入口 | [完整原文及 SHA256](../models/Hy4-preview/ppu/acceptance/historical-entrypoints/README.md)；保留前台测试源码及显式新目录的 fixed c32/c64 prepare/start |

快照位于各平台 `acceptance/historical-entrypoints/`，只有 Markdown，不再作为脚本/Playbook
发现和执行。原文用于理解旧试验和比对证据，不是复制粘贴后绕过新门禁的操作教程。
历史配置、日志摘要、分数和 `platform.yml` 未因此改成通过。

## 新任务怎么运行

1. 明确模型、平台、具体 Host 别名和所选阶段；按[工作流指南](workflow-guide.md)只检查/执行
   选中的步骤。核实当前模型 snapshot、软件及容器身份、服务实例和前置证据，不从旧 PID、
   日期目录或旧启动 JSON 推导当前身份，也不自动刷新历史收据。
2. 为本次运行准备独立输出目录，部署当前共享工具及其完整依赖。正式精度使用
   [llmrun.py](../test/Accuracy_test/llmrun.py) 与正式契约；诊断、阶段计分和历史 finalize
   结果不能替代 passing `acceptance-result.json`。
3. 前台测试先选择步骤并检查当前阶段、运行计划与服务身份，再执行明确 argv。现有模型
   专用 sanity 源码只是测试 payload，不会自动获得授权或准入；不要直接导入它来检查帮助
   或收集函数。
4. 后台任务必须由实际 worker/supervisor 管理完整生命周期。两个 Hy4 fixed 包装器的使用和完整 bundle
   见[部署边界](../test/Accuracy_test/README.md#阶段计分与部署边界)：需要全新 `run_dir`、
   已核实的 `run_plan_src`，不能原地升级活跃目录。它们的旧 proof 仍不替代当前服务
   实例的正式门禁。其他历史后台任务也不能以短命 SSH/launcher 冒充生命周期保护。
5. 服务停止或重启必须按当次授权、完整进程身份和已核实资源重新准备操作，不能从快照中
   取旧 PID 或进程名直接 kill。容器本身始终不因适配被停启。

上述操作会涉及实际环境时，应先按项目规则记录准确、可复现命令；本次仓库维护没有
执行这些远端步骤，也没有替换已部署的旧副本。强杀或脱离进程组的子进程仍不在普通
supervisor 的完整清理保证内，不因本地测试通过而扩大保证范围。

## 验证与恢复

回归检查每个停用入口的拒绝行为、历史原文摘要和没有遗留可执行远端任务。要调查原始
行为，按快照内记录的原路径与 SHA256 在独立临时目录审查，不覆盖原停用入口或活跃运行目录。
没有删除历史代码或历史结果；仓库外的已部署副本不受本次更改影响。
