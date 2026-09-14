# 新模型适配工作流操作指南

本指南说明如何按阶段调用工作流，以及本地记录与远端执行产物如何分离。完整技术要求见
[详细五阶段工作流程](model-adaptation-workflow.zh-CN.md)。

## 1. 调用一个或多个阶段

阶段编号和名称如下：

1. `architecture`：模型结构与推理链路分析
2. `environment`：推理环境分析
3. `adaptation`：进行适配
4. `acceptance`：适配验收
5. `retrospective`：适配复盘

可以使用编号、名称或自然语言调用。多个阶段始终按 1→5 顺序执行。

步骤 1 可以使用脚手架创建模型结构分析文档：

```bash
./scripts/adapt-model <模型目录名> --steps architecture
```

当前 `adapt-model` 的平台阶段仍包含旧版结构化文件门禁，与精简目录标准不一致，因此步骤
2～5 暂时不要用它的创建模式。直接在 Codex 中用自然语言提供模型、平台、准确 Host 和所选
阶段；本地布局用 `./scripts/audit-workspace` 检查。不得为通过旧门禁把 YAML 或过程文件放回
平台目录。

自然语言也可以直接调用，例如：“对 Hy4-preview 的 PPU-07 只执行第 2 步”和“执行步骤
3、4，但验收只做 execution-mode 与 sanity”。未选择的阶段只能检查前置证据，不能自动
补跑。

## 2. 本地记录目录

本地平台目录固定为：

```text
models/<model>/<platform>/
├── README.md
├── platform.yml
├── environment/
├── adaptation/
└── acceptance/
```

- `environment/`：只保存 Markdown 环境/平台分析。
- `adaptation/`：只保存 `README.md` 和 `NNN-title.md` 编号问题记录。
- `acceptance/`：只保存 Markdown 验收计划、结果报告、总结和复盘。

这三个目录不得保存脚本、Playbook、JSON/YAML 运行配置、原始日志、缓存、源码快照、测试
输出或临时子目录。平台根目录的 `platform.yml` 仅保存简洁状态和证据索引。

## 3. 远端执行目录

任何远端写入前，用户必须明确每台目标机器的 SSH Host 别名、绝对 `host_root`，以及目标
容器的名称、绝对 `container_root` 和二者映射。在核实前只允许只读检查。

远端批准工作根目录采用以下布局：

```text
<approved-root>/
├── start-model.sh     # 最终通过验收的 graph 模型启动入口
├── 01-environment/   # 环境采集、运行配置和启动参数
├── 02-issues/        # 一次性诊断脚本和过程代码
├── 03-acceptance/    # 验收配置与包装
├── 04-runs/          # 每轮日志和原始结果
├── 05-tmp/           # 临时文件
├── 06-cache/         # 显式缓存
└── 07-bugs/          # FlagGems 最小复现
```

远端工作根目录不存放源码，不创建源码仓库子目录或其他仓库副本。适配代码直接修改目标容器
中已经核实的 editable-install Plugin 源码；应记录包元数据、import 路径、Git 根目录、
revision 和工作区状态。vLLM 始终只读，FlagGems 使用容器内已核实且获准同步的现有 checkout。

当前编号对应精度后台运行计划 `schema_version=5`；旧版 schema 4 计划不会自动迁移或继续
执行。既有旧编号目录及本地引用保留为历史事实，只有实际完成远端迁移并重新核验后才能
更新记录。

本地 Markdown 记录准确的远端路径、命令、Host、容器、revision、镜像、参数、日期和结果，
不复制远端过程产物。Plugin 仓库只接收产品必需代码和可维护回归测试；一次性脚本不得放入
Plugin、vLLM 或 FlagGems 仓库。vLLM 源码全程不得修改，适配容器不得停止、重启或删除。
适配完成前必须验证根目录 `start-model.sh` 能从已核实的容器对应路径启动最终 graph 配置；
脚本只保留已验收配置必需的参数和设置，删除调试/诊断、临时路径、过期 workaround、重复
默认值、实验项和无关配置，并为每个保留的显式项记录依据。本地平台 README 和最终总结
只记录其准确路径、SHA-256、参数审查、revision、日期及就绪结果。

## 4. 阶段文档

- 步骤 1：更新模型根目录的 `architecture-and-inference.md`，并使用中文分析整体结构、
  推理链路和关键算子。
- 步骤 2：更新平台 `environment/environment-analysis.md`；其他专题环境分析可拆分为少量
  Markdown，但不得放采集脚本和结构化运行文件。
- 步骤 3：`adaptation/README.md` 作为索引，每个实质问题使用一个编号 Markdown。没有
  实质问题时不创建虚假问题记录。
- 步骤 4：在 `acceptance/` 记录计划、每轮验收结论和最终总结。原始结果及机器可执行配置
  留在远端 `03-acceptance/`、`04-runs/`。
- 步骤 5：在 `acceptance/adaptation-retrospective.md` 总结问题、有效经验、流程缺口和改进项。

## 5. 状态与证据

只有阶段真实完成且本地结论文档已经更新后，才能修改 `platform.yml` 的状态。通过状态必须
记录实际 `run_id`、验证日期、本地证据文档及其哈希；本地哈希只能证明记录未变化，不能
证明远端现场仍然有效。

先核对真实远端产物、服务身份和本地结论文档，再人工更新 `platform.yml` 中的运行标识、
验证日期、证据路径和摘要；不得仅为消除告警刷新哈希。旧版结构化证据门禁迁移前，历史
绑定只作为待复核记录，不得据此声称新一次验收通过。

## 6. 验收顺序

验收子步骤顺序固定：

1. `execution-mode`：分别跑通 `eager` 与 `graph`。
2. `sanity`：基于 `graph` 做 10 并发小批量正确性与性能预检。
3. `accuracy`：预检正常后，在规定 FlagEval 容器中用
   `test/Accuracy_test/llmrun.py` 进行至少 32 并发正式精度评测。有效完整结果中的各项
   冻结指标达到配置阈值即可完成该子步骤；指标无需为 `1.0`，个别题目答错不等于正式
   精度失败。逐题全部正确只用于前置 `sanity`。最终超时请求保留为错误样本并计入指标
   分母；只要样本完整且全部冻结指标达到阈值，允许存在少量超时。
4. `performance`：精度通过后，基于 `graph` 进行性能验收。非性能测试保持前缀缓存开启；
   性能测试开始前切换到专用服务启动配置，把 `--no-enable-prefix-caching` 加入准确服务实例
   的启动命令，但不得写入通用 graph 参数。核实该参数已生效且服务端前缀缓存已关闭，并
   把证据绑定到正式性能回执；状态开启或无法核实时不得执行。
5. `evidence`：核对运行身份、配置、日志和结果完整性。
6. `summary`：更新最终验收总结与平台状态。

正式精度的 `acceptance-result.json`、正式性能回执、完整样本、CSV、trace 和日志均保存在
对应远端 run 目录；本地 `acceptance/` 只记录其准确路径、SHA-256、关键指标和验收结论。

## 7. 本地维护检查

```bash
./scripts/audit-workspace
./scripts/syntax-check
```

`audit-workspace` 只检查本地结构、状态与链接，不连接远端。历史目录中违反新布局的过程文件
会标记为待迁移 warning；warning 不是成功证据。修改 inventory、组变量或 Playbook 后还需
按仓库规则运行 inventory 和语法检查。
