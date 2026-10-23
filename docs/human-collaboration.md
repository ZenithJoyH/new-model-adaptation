# 人工介入与 Agent 接续

人工可参与环境准备、代码修复、服务调整和验证。用同一个 framework 工作区记录交接，
使用同一套验收契约；人工已完成且证据有效的工作可以直接接续。

## 日常操作

可以直接对 Agent 说：“我要接管 Example / PPU / vllm-plugin-fl，检查安装环境，先记录
交接和当前运行任务。”Agent 查看工作区和已有执行记录后登记接管。直接操作时使用：

```bash
./scripts/workspace-control status Example --platform ppu --framework vllm-plugin-fl
./scripts/workspace-control handoff Example --platform ppu --framework vllm-plugin-fl \
  --actor operator --note '人工检查安装环境；记录当前服务和评测是否仍在运行'
```

status 显示已记录的 Host、容器、工作根、阶段状态和最近交接。接管期间，执行前置门禁和
journal 后续操作拒绝 Agent 继续。已启动的服务和评测继续保持原状：工具是协作控制，
不是进程暂停器。操作现场前确认已有任务是否仍在使用目标资源。人工的只读
`--verify-records` 校验仍可使用。交接保持既有 Host、工作根与操作授权边界。

只查看了环境：

```bash
./scripts/workspace-control resume Example --platform ppu --framework vllm-plugin-fl \
  --actor agent --change none --note '人工只读检查完成，可继续原任务'
```

实际修改了组件：

```bash
./scripts/workspace-control resume Example --platform ppu --framework vllm-plugin-fl \
  --actor agent --change code --note '人工修复组件，见变更说明' \
  --evidence /approved/readable-root/02-issues/change-summary.md
```

evidence 是当前进程能读取的绝对文件路径，可以是简要变更说明、测试结果或已验证的
patch/日志摘要。大型原始结果继续保留在批准工作根；note 不写密钥或完整命令历史。
人工也可以用自然语言说明修改内容，由 Agent 读取真实文件、整理证据并执行交回操作。

## 变更与复核范围

| `--change` | 默认复核起点 |
| --- | --- |
| none | 保留已有结果；发现配置、文档或阶段记录变化时拒绝此声明 |
| documentation | 按修改的证据文件定位；普通说明文案不影响固定契约 |
| service | execution-mode；Python API profile 从 model-eager 开始 |
| code / environment | environment，重新确认安装/部署身份，再验证下游 |
| model | architecture 及全部下游 |
| plan | 根据实际计划字段定位；仅改性能场景/目标时从 performance 开始 |
| evidence | 尝试接纳人工新回执，必须提供 artifact-root |

可重复 --change。工具同时对比接管时的配置和本地证据，采用能覆盖变化的范围。外部容器
或产品源码变化无法靠本地文件自行发现，操作人须说明；Agent 接续时核实实际组件和进程身份。
添加或移除可选验收步骤也属于计划变更，不能声明 `none`。交回时核对 profile 要求和顺序，
从第一处受影响的步骤起复核；移除步骤的旧回执进入历史，不能静默沿用依赖它的旧总结。
必需步骤不能删除，重排步骤也不能绕过 profile 顺序。

旧 verification 保存在 control.history 对应事件中，当前受影响阶段转为 not_started。
历史记录不再充当新部署的前置。无需删除旧结果、回滚人工修复或把失败记录改成通过。

## 人工已完成测试

人工运行维护的 runner 或 profile 专用测试，保存真实原生产物，按
[v2 回执](evidence-contract-v2.md) 标明 producer.kind=human 和操作人。
将新回执引用及本地说明写入 framework.yml 后交回：

```bash
./scripts/workspace-control resume Example --platform ppu --framework vllm-plugin-fl \
  --actor agent --change code --change evidence --note '人工修复并完成部分验证' \
  --evidence /approved/readable-root/02-issues/change-summary.md \
  --artifact-root PPU-01=/approved/readable-root
```

工具逐阶段校验新 run 的本地绑定、原生产物和前置依赖，通过的结果保留 passed；其余阶段
待复核，返回未接纳原因。旧 run 改标签不能作为新验证。接纳操作不执行测试、不启动服务。
缺少可读产物时，保留说明后恢复证据访问或执行必要验证。

## 旧工作区和契约升级

new-framework 默认创建 evidence_contract=2，在 framework.yml 固定 profile 快照和哈希，
新建/显式升级时使用 `profile_hash_version: 2` 固定验收顺序；旧算法不自动迁移。
普通工作流文案更新不改变既有证据。profile 更新后审计提示可升级，原固定版本仍可核验；
当时通过与满足最新契约是两个独立结论。旧工作区不自动迁移。

```bash
./scripts/workspace-control handoff Example --platform ppu --framework vllm-plugin-fl \
  --actor operator --note '准备显式升级证据契约'
./scripts/workspace-control upgrade Example --platform ppu --framework vllm-plugin-fl \
  --actor operator --note '采用当前 profile，保留旧记录，重新绑定实际证据'
```

upgrade 保留旧契约和记录，仍由人工持有控制权。v1→v2 从架构重新绑定；v2 profile 升级
从环境起复核。之后按实际变更交回。工具不自动刷新旧哈希或重跑阶段。
受影响 journal 不原地改写冻结输入；先检查已有进程，再以新 spec/run 接续，避免重复启动。

命令通过目录锁及原子写入更新 framework.yml。合作方使用同一入口；工具不能阻止绕过它
的终端命令。人工编辑 YAML 时先接管，避免与另一写入方同时修改。
