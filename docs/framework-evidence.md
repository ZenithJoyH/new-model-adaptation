# 框架流程与证据契约

通用工具校验身份、依赖和证据；框架 profile 定义具体实施方法与验收步骤。工具只读，不会
启动服务、执行测试或自动把阶段改为完成。

| Profile | 修改目标 | 验收顺序 | 当前能力 |
| --- | --- | --- | --- |
| vllm-plugin-fl | editable Plugin；vLLM 只读 | execution-mode → sanity → accuracy → performance → evidence → summary | active；eager/graph；graph 优先 full，最低 decode-full，后续绑定已验收最高级别 |
| torch-fl | 已核实 Torch-FL 源码 | device → operators → model-eager → 可选 wheel → summary | experimental；PPU Python API、eager 与可选 wheel 验证 |

`experimental` 允许创建工作区、实施和执行声明的基础验证，避免“必须先验证才能开始验证”
的循环。基础推理通过可标 `functional`；正式整体验收、精度/性能和 `optimized` 尚不可用。
其复盘只依赖已选实验步骤，不要求把完整正式 acceptance 标记完成。

## 入口

```bash
./scripts/new-framework <model> ppu torch-fl
./scripts/adapt-model <model> --platform ppu --framework torch-fl --hosts PPU-01 \
  --steps adaptation --check-only --artifact-root PPU-01=/verified/readable/work-root
./scripts/adapt-model <model> --platform ppu --framework torch-fl --hosts PPU-01 \
  --steps acceptance --acceptance-substeps model-eager --check-only \
  --artifact-root PPU-01=/verified/readable/work-root
```

`--check-only` 检查执行前置；增加 `--verify-records` 则同时验证所选步骤的完成证据。
完整选择 acceptance 时也核验该阶段的汇总回执，而不只是逐项子步骤。
所选子步骤必须来自该框架 profile，按 profile 顺序处理；选择多个步骤不会跳过尚未完成的
前置。每个步骤执行后重新核验，再进入下一步。

`--artifact-root HOST=/path` 表示当前进程可只读访问的、已核实对应那个 Host 的批准工作根。
它可以是已存在的只读挂载；也可在目标容器内运行校验工具时指向容器工作根。不得为校验
擅自挂载、复制完整原始产物到本地模型目录或建立源码镜像。工具可随验收工具部署到批准
的远端 `03-acceptance/`，保留 scripts/test 与精简元数据的相对结构；这不是产品源码 checkout。
不可读取准确远端文件时检查失败，不以 Markdown 或历史状态替代。

多 Host 重复传入参数。`workspace.roots` 的 host/container_root 表示同一存储根；若评测容器
映射路径不同，在对应行增加 `evaluator_roots: [/verified/evaluator/root]`，须事先核实。
原生回执中的绝对路径只允许落在这些根内；相对路径均以批准工作根为基准。

## 本地记录

`framework.yml` 保存 target、workspace、deployment、冻结 acceptance_plan 和每阶段状态。
`deployment.fingerprint` 是现场核实的模型/权重/tokenizer、组件 revision/diff、镜像、拓扑与
基准运行配置的 SHA-256 身份；变化后必须重新绑定和验证，不能只刷新本地哈希。
每个完成阶段及子步骤的 verification 包含：

```yaml
run_id: actual-run-id
last_verified: '2026-09-21'
evidence: acceptance/model-eager.md
evidence_sha256: <真实本地文档SHA-256>
context_sha256: <工具计算的上下文SHA-256>
receipts:
  - host_alias: PPU-01
    path: 04-runs/actual-run-id/framework-check.json
    sha256: <真实远端回执SHA-256>
```

架构阶段只要求模型级中文证据与本地绑定；其他阶段要求逐 Host 远端回执。五阶段的
verification 位于 `workflow.<phase>.verification`；子步骤位于
`workflow.acceptance.records.<step>`。本地审计检查声明、依赖、哈希和路径；没有读取远端
的审计结果永远不代表远端验证通过。

可用现有 `--evidence-info <stage> --evidence <md> --run-id <id> --check-only` 配合
`--framework` 输出本地绑定数据。该命令不生成测试结果、不补齐远端回执、不更新状态。

## 远端框架回执

在原生测试完成且真实结果已核实后，将本轮验证摘要保存到远端 run 目录：

```json
{
  "schema_version": 1,
  "kind": "framework_check",
  "status": "passed",
  "stage": "model-eager",
  "run_id": "actual-run-id",
  "context_sha256": "<对应本地记录的上下文SHA-256>",
  "scope": {
    "model": "<model>", "platform": "ppu", "framework": "torch-fl",
    "profile_version": 2, "host_alias": "PPU-01",
    "deployment_fingerprint": "<已核实部署SHA-256>"
  },
  "mode": "eager",
  "checks": {"model_inference": true, "reference_numerics": true},
  "artifacts": [{"path": "04-runs/actual-run-id/result.json", "sha256": "<真实SHA-256>"}]
}
```

必需 checks 来自 profile 对应步骤；环境阶段为 `environment_identity`，适配、整体验收与
复盘阶段为 `source_review`。每个 true 都必须由引用的实测产物支持；填写回执本身不是测试。
需要 mode 的验收使用 profile 主模式。vLLM 非性能步骤还必须记录
`prefix_caching_enabled: true`；原生精度/性能回执额外按下述适配器验证。

## vllm-plugin-fl 原生验收

- execution-mode 回执必须增加 `graph_level`，取值按 profile 当前顺序为 `full` 或
  `decode-full`。选择 `full` 时 checks 增加 `full_graph: true`。选择 `decode-full` 时 checks
  增加 `full_graph_attempted`、`full_graph_blocker_verified`、`decode_full_graph`，且均为 true；
  同时增加 `graph_fallback`，包含 `attempted_levels: [full]`、
  `selected_level: decode-full`、非空的 `attempted_configuration`、`failure_signature`、
  `reason`、`limitations`、`exit_conditions`，以及可读取且有 SHA-256 的 `evidence` 列表。
  这组字段证明降级，不得用一句“不支持全量图”代替。后续 sanity、accuracy、performance、
  evidence 与 summary 回执均记录 `graph_level`，并与同一 Host 的 execution-mode 回执一致。
- accuracy 的 `native` 包含 `report`、`config` 两个 `{path, sha256}` 引用，分别指向
  `llmrun.py` 的 `acceptance-result.json` 和实际冻结配置。`acceptance_plan.accuracy_config_sha256`
  在执行模式验收前冻结。重建并逐字段核对 runner 生效配置，包括模型名、endpoint、
  生成参数、数据集、并发和容器映射后的路径身份。同时验证运行身份、每 task 指标阈值、
  进程完成、样本完整性、
  超时策略及结果/样本哈希；低于 1 的达标得分可以通过。回执须记录 `service_instance_id`。
- performance 的 `native` 包含 `report`、`runtime` 引用，指向 `perf_acceptance.py` 原生
  回执及其运行配置。正式回执要求独立的无 profiler 测量；诊断轮次不代替正式结果。
  完整 benchmark 产物会再次验证。把完整 benchmark `request` 的规范化
  JSON SHA-256 固定到 `acceptance_plan.performance_request_sha256`；计算方式为 Python
  `json.dumps(request, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()` 的 SHA-256。
  回执还须记录性能 `service_instance_id` 和该 Host 的 `accuracy_receipt_sha256`。
- 性能关闭前缀缓存常需重启服务。冻结基准部署身份不变，只允许经过核实的缓存专用配置
  切换；记录 `accuracy_to_performance_transition` 检查及其准确前后启动/实例证据。
  其他源码、模型、拓扑、推理设置变化须重新执行精度，不能靠这项检查豁免。
- summary 回执中 `launcher` 为根目录 `start-model.sh` 的 `{path, sha256}`，必须存在且可执行；
  它必须启动该 Host 已验收最高 `graph_level`；其 syntax/readiness/minimal/cache checks 由
  现场实测支持。工具不能代替服务就绪探测。

## 旧入口与历史记录

`accuracy_admission.py` 的旧 `--run-plan` 快照入口只供原有 structured 布局使用。新工作区使用
`--framework ... --hosts ... --check-only --artifact-root ...` 做 accuracy 前置检查，或直接
使用 `adapt-model --framework`；它不导出旧快照，也不能直接传给旧 background worker。
通过前置检查后，仍按 profile 的准确容器/runner执行，完成后加 `--verify-records` 验证结果。

旧 compact Markdown 正式回执现在明确拒绝；保留历史结论与证据，重新核实后通过显式框架
工作区绑定原生远端产物。迁移不等于重新评测成功，也不得擅自搬迁远端目录。
