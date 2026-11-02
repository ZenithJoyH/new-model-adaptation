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
升级须显式执行。optimized 需要 v2 和完整验收（含有效性能测量），不要求预设性能目标；
用户明确配置的优化目标仍须达成。v2 是证据记录/绑定规则的版本，不是另一套适配流程。

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

原生多机pipeline parallel允许一个协调Host提供API，其他Host使用`--headless`。
此时保留协调Host原有service_binding和本地API observation；绑定另加
`distributed: {kind: pipeline_parallel, participants: [...]}`，participants精确覆盖
全部target Host（含协调Host），每项提供host_alias、process_identity和observation引用。
一次评测仍只有一个run_id、服务实例和完整数据集，不为每个参与Host重复发送评测。

每项引用本轮`pipeline_process_observation`，必须由现场专用取证程序读取该Host实际容器
的/proc生成：schema_version1、status verified、run_id、host_alias、service_instance_id、
deployment_fingerprint、与API本轮challenge相同的coordinator_nonce、独立随机nonce、
pid/process_identity、argv、host_ip、processes及connections。processes逐项保存
pid/ppid/start_ticks/cmdline_sha256，connections仅记录进程树真正拥有的ESTABLISHED
IPv4 socket（pid/local/remote/state）。取证需前后检查进程身份，禁止取整个主机网络表后
将无关socket冒充本任务连接。协调Host根身份必须与API观察相同；headless角色、node rank、
nnodes、TP/PP、master和除node-rank/headless外全部推理参数须一致，参与Host与协调Host的
实际连接四元组必须互逆。所有引用仍按原契约校验哈希；缺失、旧run/nonce或单端连接不通过。
该扩展不把headless节点声明为本地API，也不代替实际16rank推理与图重放证据。

## 服务范围与共享启动绑定

新建或通过 `workspace-control upgrade` 显式升级的服务型 profile（含 sanity）会初始化
`acceptance_plan.service_contract: {schema_version: 1}`。这只是待填写计划，不是通过证据；
必须在小批量验证前完成冻结。纯 Python API 的 Torch-FL 不增加该计划。已有未使用此扩展
的 schema 1 小批量历史回执按原契约读取，不自动迁移或重新判分。启用本扩展时，schema 1
从实际请求识别模态并与模型能力比对；schema 2（所选 runner 支持时）还需核对声明的 modalities。
本扩展不改变 runner 原有响应判定方式。已有任务采用新检查前保留旧记录、明确升级，并重新验证受影响验收，不能只补哈希。

```yaml
acceptance_plan:
  service_contract:
    schema_version: 1
    architecture_sha256: <模型级 architecture-and-inference.md 的真实 SHA-256>
    required_modalities: [text, image]  # 按已核实结构分析；纯文本为 [text]
    hosts:
      <exact-host-alias>:
        launcher: {path: start-model.sh, sha256: <已测最小脚本 SHA-256>}
        argv: [<实际解释器>, -m, vllm, serve, <容器模型路径>, --served-model-name, <服务名>]
        environment: {}  # 必需且不含凭据的服务环境设置，默认不额外覆盖
        effective_config:
          served_model_names: [<服务名>]  # 实际服务名/别名，可与本地模型目录名不同
          prefix_caching_enabled: true
          settings:
            dtype: <实际值>
            graph: <实际值>
            max_model_len: <实际值>
            tensor_parallel_size: <实际值>
            # 填完整有效推理配置，包括影响推理的环境设置和框架默认值
```

能力结论必须来自结构分析并经核实。gate 将其文件哈希与计划绑定，并检查 sanity manifest
的 model 属于该 Host 的服务别名、modalities 覆盖实际必需模态。`sanity.py` 单独预检只检查
请求格式；正式框架 gate 才读取工作区能力计划，不能用清单自报能力代替模型分析。
当前原生小批量工具覆盖文本/图像；视频等其他能力仍须按 profile 单独验证，不能宣称覆盖。

sanity、accuracy、performance 和 active profile 的 summary 回执增加
`native.service_launch: {path: <本轮启动证据>, sha256: <真实哈希>}`。实际证据保存为 JSON；
下例用 YAML 展示其字段结构，填写真实值后转换为 JSON：

```yaml
kind: service_launch
schema_version: 1
run_id: <与本轮评测/总结一致>
service_binding: <与该轮原生结果一致的完整服务绑定>
launcher: {path: start-model.sh, sha256: <与冻结计划一致>}
effective_config:
  served_model_names: [<真实服务名>]
  prefix_caching_enabled: true  # 只有性能轮次为 false
  settings: <与冻结计划一致的完整有效推理配置>
configuration_review:
  reviewer: <实际审阅者>
  note: <如何从本轮服务的有效配置/启动输出核实默认值、模型身份及缓存状态>
  evidence:
    - {path: <本轮服务配置或输出的原始证据>, sha256: <真实哈希>}
```

现场 `service_observation.py` 读取实际进程 argv；取证 manifest 通过
`launch_environment_keys: [<必需环境变量名>]` 明确选择需比对的非秘密变量，与计划
environment 的键一致；为空时不采集环境。输出 `argv` 和 `launch_environment`，不导出
完整进程环境。进程身份仍需通过 PID、启动时间、容器、命令哈希与实际监听关系校验。
多机 pipeline 的专用取证程序应在每个 participant observation 中补充该 Host 的
`launch_environment`；按各 Host 的真实 argv/角色分别冻结，不能用协调节点代替 headless 节点。

gate 核对观察到的 argv 与进程哈希，比较冻结 argv、必要环境变量、脚本及有效配置。
命令只允许 `--enable-prefix-caching` 与 `--no-enable-prefix-caching` 这一处差别；性能必须
使用准确关闭参数，其他轮次必须开启缓存。有效配置只允许 `prefix_caching_enabled` 变化。
环境/命令相同也不能证明框架默认值未变化，因此仍必须审阅原始有效配置证据，不能凭填表通过。
新增字段只是取证与校验，不应添加到最终启动脚本；保持脚本最小且只使用必要容器内路径。

同一冻结计划与脚本哈希绑定后续阶段，summary 的交付脚本也须匹配。改变其他配置须重新
完成受影响验收（包括性能前的精度）。PID、run_id、服务实例可以随重启变化，每轮必须使用
新的现场取证，不能复用旧 observation。所有配置/脚本原件及大结果仍保留在批准远端目录。

## 小集合与正式精度

sanity 使用 `test/Accuracy_test/sanity.py`。manifest schema 是请求文件的格式版本，
与工作区 evidence_contract 版本分开管理。新 manifest 使用 schema 2，固定 model、
concurrency、timeout、modalities 及带唯一 id 的 cases。纯文本模型声明 `["text"]`；图像
模型声明 `["text", "image"]`，必须实际覆盖两类请求。模型能力来自已核实的结构分析，
不得把图像模型声明为纯文本来省略图像验证。每个 case 包含 `modality`、`request.messages`
及可审阅的 `expected_behavior`；图像 case 的 user 消息实际包含 `image_url` 和文本问题。
图片应可辨识且问题依赖图片内容，不能仅检查模型声称“看到了图片”。开放式回答不做逐字
比较；确定性问题可以在预期行为中写明正确答案。图像资产在远端保留可复核来源/版本。

```json
{
  "schema_version": 2, "kind": "sanity_manifest", "model": "<served-model>",
  "concurrency": 10, "timeout": 120, "modalities": ["text", "image"],
  "cases": [
    {"id": "text-1", "modality": "text",
     "request": {"messages": [{"role": "user", "content": "用一句话介绍太阳。"}]},
     "expected_behavior": "回答与太阳相关、语句完整，无乱码或异常重复"},
    {"id": "image-1", "modality": "image",
     "request": {"messages": [{"role": "user", "content": [
       {"type": "text", "text": "图片里有哪些物体？"},
       {"type": "image_url", "image_url": {"url": "<verified-image-url-or-data-uri>"}}
     ]}]}, "expected_behavior": "运行前根据实际图片填写可核验的物体及关键特征"}
  ]
}
```

示例只是字段说明；正式预检选几个代表性文本/图像请求并填写实际图片预期，不能保留占位符。
并发仍按实际容量固定，本次调整不改变现有并发选择政策。

```bash
python3 test/Accuracy_test/sanity.py --manifest /approved/03-acceptance/sanity.json \
  --service-binding /approved/03-acceptance/service-binding.json --run-id sanity-001
```

默认离线检查；显式增加 `--run` 和新的绝对 `--output` 才发请求。runner 保存原始响应、
错误和每请求 `elapsed_seconds`，检查非空输出及正常 `finish_reason=stop`；错误/超时、
截断/异常结束不能通过。正常完成返回 `needs_review`（退出码 0 只代表采集成功）。
Agent 或人工阅读实际请求、图片与响应后另存审阅，不改写原报告：

```json
{
  "schema_version": 1, "kind": "sanity_review", "reviewer": "<agent-or-human-name>",
  "run_id": "sanity-001", "manifest_sha256": "<manifest-sha256>",
  "report_sha256": "<original-sanity-result-sha256>",
  "cases": [
    {"id": "text-1", "output_health": true, "relevance": true,
     "note": "根据实际响应说明切题且无乱码、空输出或异常重复的依据"},
    {"id": "image-1", "output_health": true, "relevance": true, "image_understanding": true,
     "note": "逐项描述实际图片特征与回复的对应关系，不得照填模板结论"}
  ]
}
```

框架回执 `native.manifest`、`native.sanity`、`native.sanity_review` 分别引用文件和 SHA-256；
`acceptance_plan.sanity_manifest_sha256` 在执行前固定。gate 重验覆盖、原始响应、错误、时延、
审阅身份及报告绑定，全部检查通过才能将 sanity 标为完成。已有 profile 检查名
`reference_consistency` 对 schema 2 表示对预期行为的逐项审阅，属于有证据的判断；哈希不能
自动证明语义正确。`performance_sanity` 仍需独立观测吞吐、时延和资源，明显异常先修复。
历史 schema 1 保持精确参考文本比较，不改写历史结果；新请求应显式创建 schema 2 manifest。

正式精度继续使用 llmrun.py。v2 配置添加 formal_contract_version: 2、service_binding 和
非空 concurrency_reason；num_concurrent 是按容量依据冻结的正整数。旧配置继续保持至少
32 并发。limit=0、完整样本、超时计失败、正式阈值和缓存要求保持生效。v2 原生报告复制
实际消费配置中的服务绑定，gate 核对配置、报告和现场 observation。
取证与评测使用同一个预先选定的 run_id；llmrun 的 `run_id` 使用此 ID，避免默认时间戳
生成另一个 run。性能 runner 同样显式传入 `--run-id`；重复使用已存在的运行目录会被拒绝。

## 性能测量与可选目标

新模型适配没有强制的预期性能目标。必须固定场景、取得完整有效测量，保留原始产物、
服务绑定、吞吐/时延和资源观测并处理明显异常；正常退出不等于测量有效。没有另行要求
量化优化时省略 `acceptance_plan.performance_targets`，不填空目标或人为设置零阈值。
只有用户要求量化优化目标时，该字段才与 request 一起冻结，cases 与请求逐项同序：

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
原生 benchmark passed 表示测量有效；框架 performance 仍核对完整产物、服务身份、已通过
精度及关闭缓存等前置。若配置了目标则额外要求达标；缺少目标不会阻止适配验收或 optimized。
不得删除已冻结的目标以掩盖失败，改变优化任务范围须明确记录并重新验证受影响结果。
没有可比基线时只报告测量结果，不宣称优化幅度。

## 可恢复交付

active profile 的 summary.native.delivery 引用 delivery_manifest，至少含 launcher、config、
source、lock、restore 五类不同文件及哈希：启动脚本、配置、源码提交引用或补丁、依赖锁定、
恢复步骤。scripts/delivery_manifest.py --root <批准根> --file <role=相对文件> ... --output <新清单>
只读取明确选择的文件，不复制源码、不打包镜像。launcher 内容与验收脚本一致。
image.validation 默认 pending；实际新容器验证完成后才填写 passed、完整镜像 digest 和证据。

脱敏小型恢复材料可版本化保存在 deliveries/<model>/<platform>/<framework>/；完整结果、
镜像和大文件用已有批准的持久存储，模型目录保留索引。临时远端目录不能作为唯一备份。
提交推送仍需用户请求；工具不自动发布交付包。
