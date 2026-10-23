# 可执行验收契约 v2

新工作区由 new-framework 创建 v2 记录；旧数据保持原契约。基础字段及路径规则沿用
[框架证据契约](framework-evidence.md)，交接见[人工协作流程](human-collaboration.md)。

## 固定契约

profile_snapshot、profile_sha256 固定机器可执行要求；documents、display_name 不参与哈希。
新建或显式升级的工作区使用 `profile_hash_version: 2`，另将 `acceptance.steps` 的有序名称
序列纳入哈希和非架构阶段上下文，避免 JSON 键排序掩盖验收顺序变化。缺少该字段的旧 v2
工作区仍按原算法核验，不自动改写哈希/历史回执；通过 workspace-control 显式升级后复核。
架构绑定模型身份和证据，其余阶段绑定部署、对应计划及前置回执。performance_targets
变化不直接改变 accuracy 的上下文。审计按固定版本验证，另提示当前 profile 更新；
升级须显式执行。optimized 需要 v2、完整验收和性能目标通过。

## 公共回执

非架构 framework_check 保留 scope/run_id/context_sha256/checks/artifacts，另需
producer: {kind: human|agent|tool, name: 操作人或工具}。每个必需检查给出具体证据：

```json
{
  "producer": {"kind": "human", "name": "operator"},
  "check_results": {
    "source_review": {
      "status": "passed", "method": "review", "note": "核对实际 diff、调用方和未验证范围",
      "evidence": [{"path": "04-runs/run/source-review.json", "sha256": "<实际哈希>"}]
    }
  }
}
```

method 为 measurement 或 review。审查结论明确标为判断，哈希证明文件完整性，不是运行
真实性的签名。下面的客观步骤还须独立校验，不能只写 checks=true。

## 执行模式

先冻结 acceptance_plan.execution.max_abs_error。execution-mode 和 model-eager 的
native.execution 引用 JSON：

```json
{
  "kind": "execution_measurements", "run_id": "<本轮run>",
  "runs": [
    {"mode": "eager", "inference_count": 1, "max_abs_error": 0,
     "evidence": [{"path": "04-runs/run/eager-result.json", "sha256": "<实际哈希>"}]},
    {"mode": "graph", "inference_count": 2, "max_abs_error": 0,
     "effective_level": "full", "capture_count": 1, "replay_count": 2,
     "evidence": [{"path": "04-runs/run/graph-result.json", "sha256": "<实际哈希>"}]}
  ]
}
```

runs 精确覆盖 profile.required；Torch-FL 仅填 eager。数值来自实际框架测试，附输出和参考
对比。graph 核对实际档位、capture、至少两次 replay；逐级 fallback 要求继续生效。
通用工具尚不自动从所有厂商日志中推断图模式，专用测试需输出这些测量字段。

## 服务绑定

精度配置、sanity_result 和性能 runtime 保存 service_binding：

```json
{
  "service_instance_id": "<实例ID>", "deployment_fingerprint": "<部署SHA256>",
  "host_alias": "PPU-01", "endpoint": "http://127.0.0.1:8010/v1/chat/completions",
  "process_identity": {
    "container_id": "<完整容器ID>", "boot_id": "<Linux boot UUID>",
    "start_ticks": 12345, "cmdline_sha256": "<命令哈希>"
  },
  "observation": {"path": "/approved/root/04-runs/run/service-observation.json", "sha256": "<实际哈希>"}
}
```

observation 对应本轮 run、Host、实例、进程和监听端口。service_observation.py 支持
--manifest-file；前台人工运行可加 --standalone 创建新 challenge 后取证。后台 worker
由 worker 创建挑战，不用 standalone。当前采集器支持它已实现的 Linux /proc、Docker
host-network、IPv4 localhost 场景；其他环境需补齐采集器，不能凭填写 ID 声称现场验证。
所有路径须通过已核实映射在评测进程和 gate 中可读。

## 小集合与正式精度

sanity 使用 test/Accuracy_test/sanity.py。manifest 固定 model、concurrency、timeout 和
带唯一 id 的 cases；每项包含 request.messages（可含多模态输入）及参考实现的 reference_text。
当前比较器做去除首尾空白后的精确文本比较，适合固定短答案/确定性回归；自由生成或
浮点输出须提供对应比较器。小集合检验适配一致性，正式数据集检验模型能力阈值。

```bash
python3 test/Accuracy_test/sanity.py --manifest /approved/03-acceptance/sanity.json \
  --service-binding /approved/03-acceptance/service-binding.json --run-id sanity-001
```

默认离线检查；显式增加 --run 和新的绝对 --output 才发请求。框架回执 native.manifest、
native.sanity 引用 manifest 和报告，acceptance_plan.sanity_manifest_sha256 在执行前冻结。
gate 重验 case 覆盖、响应、错误和参考一致性；performance_sanity 等审查项仍须单独证据。

正式精度继续使用 llmrun.py。v2 配置添加 formal_contract_version: 2、service_binding 和
非空 concurrency_reason；num_concurrent 是按容量依据冻结的正整数。旧配置继续保持至少
32 并发。limit=0、完整样本、超时计失败、正式阈值和缓存要求保持生效。v2 原生报告复制
实际消费配置中的服务绑定，gate 核对配置、报告和现场 observation。
取证与评测使用同一个预先选定的 run_id；llmrun 的 `run_id` 使用此 ID，避免默认时间戳
生成另一个 run。性能 runner 同样显式传入 `--run-id`；重复使用已存在的运行目录会被拒绝。

## 性能目标

acceptance_plan.performance_targets 与 request 一起冻结，cases 与请求逐项同序：

```yaml
performance_targets:
  cases:
    - case: [1024, 128, 4, 16]
      limits:
        P99 TTFT (ms): {max: 200}
        Req/s: {min: 10}
```

支持 min/max 绝对目标；min_ratio/max_ratio 是当前值除以 baseline。相对目标必须提供
performance_targets.baseline 的完整 benchmark-result.json path/sha256，原始依赖也须可读。
工具核验 baseline 产物、模型、tokenizer、上下文和场景一致性；硬件拓扑、精度与缓存
可比性仍须现场证据和审查。指标名使用原生 summary 的准确列名。
原生 benchmark passed 表示测量有效；v2 framework performance passed 还要求目标达标。

## 可恢复交付

active profile 的 summary.native.delivery 引用 delivery_manifest，至少含 launcher、config、
source、lock、restore 五类不同文件及哈希：启动脚本、配置、源码提交引用或补丁、依赖锁定、
恢复步骤。scripts/delivery_manifest.py --root <批准根> --file <role=相对文件> ... --output <新清单>
只读取明确选择的文件，不复制源码、不打包镜像。launcher 内容与验收脚本一致。
image.validation 默认 pending；实际新容器验证完成后才填写 passed、完整镜像 digest 和证据。

脱敏小型恢复材料可版本化保存在 deliveries/<model>/<platform>/<framework>/；完整结果、
镜像和大文件用已有批准的持久存储，模型目录保留索引。临时远端目录不能作为唯一备份。
提交推送仍需用户请求；工具不自动发布交付包。
