"""Version 2 objective evidence checks, shared by human and agent producers."""
import math
import re
from urllib.parse import urlsplit


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def producer(report):
    value = report.get("producer", {})
    require(value.get("kind") in {"human", "agent", "tool"} and
            isinstance(value.get("name"), str) and value["name"].strip(),
            "v2 回执需要 producer.kind/name；人工与 Agent 使用相同验证条件")


def service_binding(reader, binding, report, cfg, host):
    from service_observation import validate_identity
    require(isinstance(binding, dict), "缺少原生 service_binding")
    for key, expected in (("service_instance_id", report.get("service_instance_id")),
                          ("deployment_fingerprint", cfg["deployment"]["fingerprint"]),
                          ("host_alias", host)):
        require(isinstance(expected, str) and bool(expected) and binding.get(key) == expected,
                "原生服务绑定不匹配: " + key)
    observed = reader.json(binding["observation"])
    require(observed.get("run_id") == report["run_id"] and observed.get("host_alias") == host,
            "服务 observation 不属于本轮 run/Host")
    require(observed.get("status") == "verified" and
            observed.get("service_instance_id") == binding["service_instance_id"],
            "服务 observation 与原生运行不一致")
    validate_identity(observed.get("process_identity"))
    require(binding.get("process_identity") == observed["process_identity"], "进程身份与冻结 service_binding 不一致")
    require(type(observed.get("pid")) is int and observed["pid"] > 0, "服务 PID 缺失")
    require(isinstance(observed.get("nonce"), str) and re.fullmatch(r"[a-f0-9]{64}", observed["nonce"]),
            "服务 observation 缺少本轮 challenge")
    endpoint = urlsplit(binding.get("endpoint", ""))
    require(endpoint.scheme in {"http", "https"} and endpoint.hostname and
            not endpoint.username and not endpoint.password and not endpoint.fragment and not endpoint.query,
            "service_binding.endpoint 必须是无凭据 API URL")
    require(endpoint.hostname in {"127.0.0.1", "localhost"},
            "当前 observation 仅证明共享 host-network 的 IPv4 localhost 服务，不能绑定其他主机")
    require(observed.get("listening_port") == (endpoint.port or (443 if endpoint.scheme == "https" else 80)),
            "服务 observation 监听端口与请求不匹配")


def checks_evidence(reader, report, required):
    """Every assertion has its own evidence and named reviewer; no anonymous booleans."""
    results = report.get("check_results", {})
    for name in required:
        item = results.get(name, {})
        require(item.get("status") == "passed" and item.get("method") in {"measurement", "review"},
                f"{name}: 缺少有类型的 check_results")
        require(isinstance(item.get("note"), str) and item["note"].strip(), f"{name}: 缺少判断依据")
        refs = item.get("evidence")
        require(isinstance(refs, list) and refs, f"{name}: 缺少对应证据")
        for ref in refs:
            reader.file(ref)


def execution(reader, report, cfg, profile):
    raw = reader.json(report["native"]["execution"])
    require(raw.get("kind") == "execution_measurements" and raw.get("run_id") == report["run_id"],
            "缺少本轮 execution_measurements")
    tolerance = cfg.get("acceptance_plan", {}).get("execution", {}).get("max_abs_error")
    require(number(tolerance) and tolerance >= 0, "先冻结 execution.max_abs_error")
    runs = raw.get("runs", [])
    require(isinstance(runs, list) and all(isinstance(r, dict) for r in runs), "execution.runs 无效")
    require([r.get("mode") for r in runs] == profile["execution_modes"]["required"],
            "实测 runs 必须按 profile 覆盖全部执行模式")
    for run in runs:
        require(type(run.get("inference_count")) is int and run["inference_count"] > 0, "缺少实际推理次数")
        require(number(run.get("max_abs_error")) and 0 <= run["max_abs_error"] <= tolerance,
                "推理结果超出冻结的参考误差")
        require(isinstance(run.get("evidence"), list) and run["evidence"], "每个模式需引用原始输出/对比证据")
        for ref in run["evidence"]:
            reader.file(ref)
        if run["mode"] == "graph":
            require(run.get("effective_level") == report.get("graph_level"), "实际 graph 模式不一致")
            require(type(run.get("capture_count")) is int and run["capture_count"] >= 1 and
                    type(run.get("replay_count")) is int and run["replay_count"] >= 2,
                    "graph 必须实测 capture 及至少两次 replay")


def validate_performance_plan(plan, cases=None):
    targets = plan.get("performance_targets")
    require(isinstance(targets, dict) and isinstance(targets.get("cases"), list) and targets["cases"],
            "先冻结 performance_targets，测量有效不能代替性能达标")
    metrics = {"Req/s", "Output tok/s", "Peak Output tok/s", "Total tok/s", "Benchmark Duration (s)"}
    metrics.update(f"{stat} {metric} (ms)" for stat in ("Mean", "Median", "P99")
                   for metric in ("TTFT", "TPOT", "ITL"))
    seen = set()
    for target in targets["cases"]:
        require(isinstance(target, dict), "性能场景目标必须是映射")
        case = target.get("case")
        require(isinstance(case, list) and len(case) == 4 and
                all(type(v) is int and v > 0 for v in case), "性能场景需要四个正整数")
        require(tuple(case) not in seen, "性能目标场景不得重复")
        seen.add(tuple(case))
        limits = target.get("limits")
        require(isinstance(limits, dict) and limits, "每个场景至少需要一个性能目标")
        for metric, bounds in limits.items():
            require(metric in metrics, "目标必须是原生延迟/吞吐/耗时指标: " + str(metric))
            require(isinstance(bounds, dict) and bounds and set(bounds) <= {"min", "max", "min_ratio", "max_ratio"},
                    "目标仅支持 min/max/min_ratio/max_ratio")
            require(all(number(v) and v >= 0 for v in bounds.values()), "性能阈值必须是非负有限数")
            for low, high in (("min", "max"), ("min_ratio", "max_ratio")):
                require(low not in bounds or high not in bounds or bounds[low] <= bounds[high], "性能目标上下界冲突")
            if any(k.endswith("_ratio") for k in bounds):
                require(targets.get("baseline"), "相对性能目标必须绑定完整 baseline")
    if cases is not None:
        require([v["case"] for v in targets["cases"]] == cases,
                "性能目标必须逐一覆盖冻结场景，不能遗漏或重复")
    if targets.get("baseline"):
        from framework_evidence import reference
        reference(targets["baseline"])
    return targets


def performance_targets(reader, source, plan):
    targets = validate_performance_plan(plan, source["request"]["cases"])
    baseline = None
    if targets.get("baseline"):
        from perf_common import validate_report
        path = reader.file(targets["baseline"])
        baseline = reader.json(targets["baseline"])
        require(not validate_report(baseline, path), "性能 baseline 原生产物无效")
        for key in ("engine", "backend", "model", "tokenizer", "max_model_len", "cases", "profiling_requested"):
            require(baseline["request"].get(key) == source["request"].get(key), "baseline 场景不匹配: " + key)
    for index, (target, record) in enumerate(zip(targets["cases"], source["cases"])):
        limits = target.get("limits")
        require(isinstance(limits, dict) and limits, "每个场景至少需要一个性能目标")
        for metric, bounds in limits.items():
            require(metric not in {"Run", "Prefill", "Decode", "Conc", "Num Prompts"}, "目标必须是性能指标")
            value = (record.get("summary") or {}).get(metric)
            require(number(value) and value >= 0, "性能目标指标缺失: " + metric)
            require(isinstance(bounds, dict) and bounds and set(bounds) <= {"min", "max", "min_ratio", "max_ratio"},
                    "目标仅支持 min/max/min_ratio/max_ratio")
            for operator, threshold in bounds.items():
                require(number(threshold) and threshold >= 0, "性能阈值必须是非负有限数")
                actual = value
                if operator.endswith("_ratio"):
                    require(baseline is not None, "相对性能目标必须绑定完整 baseline")
                    base = (baseline["cases"][index].get("summary") or {}).get(metric)
                    require(number(base) and base > 0, "baseline 指标缺失或不能计算比值")
                    actual /= base
                require(actual >= threshold if operator.startswith("min") else actual <= threshold,
                        f"性能目标未达标: {metric}={actual}, {operator}={threshold}")


def delivery(reader, report):
    manifest = reader.json(report["native"]["delivery"])
    require(manifest.get("kind") == "delivery_manifest" and manifest.get("schema_version") == 1,
            "缺少 delivery_manifest")
    files = manifest.get("files", [])
    require(isinstance(files, list) and all(isinstance(f, dict) for f in files), "delivery.files 无效")
    require({"launcher", "config", "source", "lock", "restore"} <= {f.get("role") for f in files},
            "交付包需 launcher/config/source/lock/restore 五类文件")
    require(len({f.get("path") for f in files}) == len(files), "交付文件不得重复充当不同角色")
    for ref in files:
        reader.file(ref)
    launcher = next(f for f in files if f["role"] == "launcher")
    require(launcher["sha256"] == report["launcher"]["sha256"], "交付 launcher 与验收 launcher 不一致")
    image = manifest.get("image", {})
    require(image.get("validation") in {"pending", "passed"}, "明确镜像验证实际状态")
    if image["validation"] == "passed":
        require(isinstance(image.get("digest"), str) and re.fullmatch(r"sha256:[a-f0-9]{64}", image["digest"]),
                "已验证镜像需要完整 digest")
        reader.file(image["evidence"])
