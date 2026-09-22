"""Read-only, profile-driven gates. Native artifacts stay at an explicit mounted/remote root."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath

from framework_workspace import load_yaml, resolved_profile, workspace_errors, WORKFLOW_PHASES

DONE = {"passed", "complete"}
SHA = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def step_names(cfg, profile):
    steps = profile["acceptance"]["steps"]
    enabled = cfg["workflow"]["acceptance"].get("substeps", {})
    require(isinstance(enabled, dict), "acceptance.substeps 必须为映射")
    require(not set(enabled) - set(steps), "验收子步骤不属于所选框架")
    require(all(name in enabled for name, spec in steps.items() if not spec.get("optional")), "缺少框架必需验收子步骤")
    require(list(enabled) == [name for name in steps if name in enabled], "验收子步骤顺序必须按 profile")
    require(all(value in {"not_started", "in_progress", "blocked", "failed", *DONE} for value in enabled.values()), "非法验收状态")
    return list(enabled)


def record_for(cfg, stage):
    if stage in WORKFLOW_PHASES:
        return cfg["workflow"][stage].get("verification", {})
    return cfg["workflow"]["acceptance"].get("records", {}).get(stage, {})


def dependencies(cfg, profile, stage):
    steps = step_names(cfg, profile)
    if stage in steps:
        return ["architecture", "environment", "adaptation", *steps[:steps.index(stage)]]
    phases = list(WORKFLOW_PHASES)
    require(stage in phases, f"未知阶段: {stage}")
    previous = phases[:phases.index(stage)]
    if stage == "retrospective" and profile["status"] == "experimental":
        previous.remove("acceptance")
    if stage in {"acceptance", "retrospective"}:
        previous += steps
    return previous


def state(cfg, stage):
    if stage in WORKFLOW_PHASES:
        return cfg["workflow"][stage]["status"]
    return cfg["workflow"]["acceptance"]["substeps"][stage]


def context_hash(root, directory, cfg, profile, stage):
    model = root / "models" / cfg["model"]
    files = [model / "model.yml", root / cfg["profile"]]
    files += [(root / cfg["profile"]).parent / value for value in profile["documents"].values()]
    if stage != "architecture":
        files.append(model / "architecture-and-inference.md")
    for path in files:
        require(path.is_file(), f"缺少上下文文件: {path}")
    scope = {key: cfg.get(key) for key in ("model", "platform", "framework", "profile_version")}
    if stage != "architecture":
        scope.update({key: cfg.get(key) for key in ("target", "workspace", "deployment")})
    if stage not in {"architecture", "environment", "adaptation"}:
        scope["acceptance_plan"] = cfg.get("acceptance_plan")
    return canonical({"scope": scope, "stage": stage,
                      "files": {str(p.relative_to(root)): digest(p) for p in files},
                      "prerequisites": {s: record_for(cfg, s) for s in dependencies(cfg, profile, stage)}})


def reference(ref):
    require(isinstance(ref, dict) and isinstance(ref.get("path"), str) and ref["path"], "缺少证据 path")
    require(isinstance(ref.get("sha256"), str) and SHA.fullmatch(ref["sha256"]), "缺少证据 SHA-256")
    require(".." not in PurePosixPath(ref["path"]).parts, "证据路径不得包含 ..")


class Artifacts:
    def __init__(self, cfg, host, mounts):
        rows = [r for r in cfg["workspace"]["roots"] if r["host_alias"] == host]
        require(len(rows) == 1, "Host 工作根不唯一")
        row = rows[0]
        require(host in mounts, f"未读取远端证据: 缺少 --artifact-root {host}=<已核实可读根目录>")
        self.root = Path(mounts[host]).resolve(strict=True)
        require(self.root.is_dir(), "artifact-root 必须是目录")
        self.prefixes = [PurePosixPath(row[k]) for k in ("host_root", "container_root")]
        self.prefixes += [PurePosixPath(p) for p in row.get("evaluator_roots", [])]

    def file(self, ref):
        reference(ref)
        path = PurePosixPath(ref["path"])
        if path.is_absolute():
            matches = [path.relative_to(prefix) for prefix in self.prefixes if path.is_relative_to(prefix)]
            require(bool(matches), f"证据不属于批准工作根: {path}")
            path = min(matches, key=lambda p: len(p.parts))
        target = (self.root / str(path)).resolve(strict=True)
        require(target.is_relative_to(self.root) and target.is_file(), "证据越界或不是文件")
        require(digest(target) == ref["sha256"], f"证据已变化: {ref['path']}")
        return target

    def json(self, ref):
        return json.loads(self.file(ref).read_text(encoding="utf-8"))

    def logical_path(self, value):
        """Normalize the same approved-root path across host/container/local mounts."""
        if not value:
            return ""
        path = PurePosixPath(value)
        if not path.is_absolute():
            return {"relative": path.as_posix()}
        for prefix in self.prefixes:
            if path.is_relative_to(prefix):
                return {"root_relative": path.relative_to(prefix).as_posix()}
        local = Path(value).resolve(strict=False)
        if local.is_relative_to(self.root):
            return {"root_relative": local.relative_to(self.root).as_posix()}
        return {"absolute": path.as_posix()}


def native_accuracy(reader, native, envelope, cfg):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "test/Accuracy_test"))
    try:
        from acceptance_contract import validate_formal_config, metric_errors
        from llmrun import load_config, validate_samples
        report = reader.json(native["report"])
        frozen_path = reader.file(native["config"])
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        require(not validate_formal_config(frozen, require_formal=True), "无效正式精度配置")
        require(report.get("kind") == "formal_accuracy" and report.get("status") == "passed"
                and report.get("errors") == [] and report.get("failed_tasks") == [], "正式精度未通过")
        require(report.get("run_id") == envelope["run_id"], "精度 run_id 不匹配")
        require(report.get("source_config_sha256") == native["config"]["sha256"], "精度配置哈希不匹配")
        snapshots = report.get("config_artifacts", {})
        source = reader.file(snapshots["source_config"])
        require(digest(source) == native["config"]["sha256"], "原始配置快照与冻结输入不一致")
        effective = reader.json(snapshots["effective_config"])
        require(not validate_formal_config(effective, require_formal=True), "生效精度配置不符合正式契约")
        try:
            expected_effective = dict(load_config(frozen_path))
        except SystemExit as exc:
            raise ValueError("冻结精度配置无法按原生 runner 解析") from exc
        # Path roots differ across host/container/read-only mounts, so compare
        # their approved-root-relative identity. run_nonce is generated only
        # after configuration loading and is separately unique per invocation.
        path_fields = {"output_root", "cache_root", "include_path"}
        def normalized_config(value):
            return {key: reader.logical_path(item) if key in path_fields else item
                    for key, item in value.items() if key != "run_nonce"}
        normalized_actual = normalized_config(effective)
        normalized_expected = normalized_config(expected_effective)
        require(normalized_actual == normalized_expected,
                "生效精度配置与冻结配置不一致")
        for report_key, config_key in (("tasks", "tasks"), ("expected_samples", "expected_samples"),
                                     ("criteria", "acceptance_criteria"), ("configured_concurrency", "num_concurrent"),
                                     ("service_mode", "service_mode"), ("allow_timeouts", "allow_timeouts")):
            require(report.get(report_key) == frozen.get(config_key), f"精度配置不一致: {report_key}")
            require(effective.get(config_key) == frozen.get(config_key), f"生效精度配置已漂移: {config_key}")
        require(report.get("timeout_policy") == "count_as_incorrect", "超时未计入错误样本")
        expected = cfg["acceptance_plan"].get("accuracy_config_sha256")
        require(expected == native["config"]["sha256"], "精度配置未在 acceptance_plan 冻结")
        for task in frozen["tasks"]:
            attempts = report["task_attempts"][task]
            require(bool(attempts) and attempts[-1].get("returncode") == 0 and attempts[-1].get("status") == "passed"
                    and attempts[-1].get("errors") == [], f"{task}: 评测进程未完整结束")
            result = reader.json(report["artifacts"][task]["results"])
            require(not metric_errors(frozen, task, result.get("results", {}).get(task, {})), f"{task}: 指标未达到冻结阈值")
            samples = reader.file(report["artifacts"][task]["samples"])
            require(validate_samples(frozen, task, samples.parent, samples_file=samples), f"{task}: 样本不完整或无效")
    finally:
        sys.path.pop(0)


def native_performance(reader, native, envelope, cfg):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "test/perf_test"))
    try:
        from perf_acceptance import validate_evidence
        from perf_common import validate_report
        report = reader.json(native["report"])
        runtime = load_yaml(reader.file(native["runtime"]))
        errors = validate_evidence(report, runtime=runtime, runtime_sha256=native["runtime"]["sha256"],
                                  model=cfg["model"], platform=cfg["platform"],
                                  deployment_fingerprint=cfg["deployment"]["fingerprint"],
                                  service_instance_id=envelope["service_instance_id"], run_id=envelope["run_id"])
        require(not errors, "; ".join(errors))
        source_path = reader.file(report["source_report"])
        source = json.loads(source_path.read_text())
        require(source.get("request", {}).get("engine") == "vllm", "vllm profile 不接受其他引擎性能回执")
        require(source["request"].get("profiling_requested") is False,
                "正式性能验收必须使用无 profiler 的独立测量轮次")
        require(not validate_report(source, source_path), "完整性能产物校验失败")
        require(report["request"] == source["request"], "紧凑回执与原生性能请求不一致")
        expected_cases = [{"case": item["case"], "status": "passed", "runs_verified": len(item["runs"]),
                           "summary": item["summary"], "profile_summary": item["profile_summary"]}
                          for item in source["cases"]]
        require(report["cases"] == expected_cases, "性能回执指标与完整产物不一致")
        require(canonical(source["request"]) == cfg["acceptance_plan"].get("performance_request_sha256"), "性能场景未冻结或已变化")
    finally:
        sys.path.pop(0)


def check_graph_level(reader, report, ref, cfg, profile, stage):
    """Enforce the profile's graph preference and bind later receipts to it."""
    policy = profile.get("execution_modes", {}).get("graph_policy")
    if not policy or report.get("mode") != "graph":
        return
    order = policy["preference_order"]
    level = report.get("graph_level")
    require(level in order, f"{stage}: graph_level 必须属于 {order}")
    if stage == "execution-mode":
        checks = report.get("checks", {})
        require(all(checks.get(name) is True for name in policy["level_checks"][level]),
                f"{stage}: graph_level={level} 缺少级别检查 {policy['level_checks'][level]}")
        if level == order[0]:
            return
        fallback = report.get("graph_fallback")
        require(isinstance(fallback, dict), "graph 降级缺少 graph_fallback 记录")
        require(fallback.get("attempted_levels") == order[:order.index(level)],
                "graph 降级必须按 preference_order 逐级尝试")
        require(fallback.get("selected_level") == level, "graph_fallback 选定级别不匹配")
        for field in ("attempted_configuration", "failure_signature", "reason",
                      "limitations", "exit_conditions"):
            require(isinstance(fallback.get(field), str) and fallback[field].strip(),
                    f"graph 降级缺少 {field}")
        evidence = fallback.get("evidence")
        require(isinstance(evidence, list) and evidence, "graph 降级缺少全量图阻塞证据")
        for item in evidence:
            reader.file(item)
        return

    execution = record_for(cfg, "execution-mode")
    refs = execution.get("receipts", []) if isinstance(execution, dict) else []
    matching = [item for item in refs if item.get("host_alias") == ref["host_alias"]]
    require(len(matching) == 1, f"{stage}: 缺少该 Host 的执行模式回执")
    selected = reader.json(matching[0]).get("graph_level")
    require(level == selected, f"{stage}: graph_level 与执行模式验收不一致")


def check_receipt(reader, ref, cfg, profile, stage, rec):
    report = reader.json(ref)
    require(report.get("schema_version") == 1 and report.get("kind") == "framework_check"
            and report.get("status") == "passed", "缺少框架验证回执")
    require(report.get("stage") == stage and report.get("run_id") == rec["run_id"]
            and report.get("context_sha256") == rec["context_sha256"], "回执阶段/运行/上下文不匹配")
    scope = report.get("scope", {})
    for key in ("model", "platform", "framework", "profile_version"):
        require(scope.get(key) == cfg[key], f"回执 {key} 不匹配")
    require(scope.get("host_alias") == ref["host_alias"] and
            scope.get("deployment_fingerprint") == cfg["deployment"]["fingerprint"], "回执 Host 或部署不匹配")
    spec = profile["acceptance"]["steps"].get(stage)
    required = spec["checks"] if spec else ["environment_identity" if stage == "environment" else "source_review"]
    checks = report.get("checks", {})
    require(all(checks.get(name) is True for name in required), f"{stage}: 缺少必需检查 {required}")
    artifacts = report.get("artifacts")
    require(isinstance(artifacts, list) and artifacts, "验证回执缺少原始证据引用")
    for item in artifacts:
        reader.file(item)
    if spec and stage not in {"device", "operators", "wheel"}:
        require(report.get("mode") == profile["execution_modes"]["acceptance_primary"], "验收执行模式不匹配")
        check_graph_level(reader, report, ref, cfg, profile, stage)
    if spec and spec["validator"] == "flageval":
        require(bool(report.get("service_instance_id")), "缺少精度服务身份")
        native_accuracy(reader, report["native"], report, cfg)
    elif spec and spec["validator"] == "vllm-performance":
        native_performance(reader, report["native"], report, cfg)
        accuracy_refs = record_for(cfg, "accuracy")["receipts"]
        expected = next(r["sha256"] for r in accuracy_refs if r["host_alias"] == ref["host_alias"])
        require(report.get("accuracy_receipt_sha256") == expected, "性能未绑定该 Host 的正式精度回执")
    if cfg["framework"] == "vllm-plugin-fl" and stage in {"execution-mode", "sanity", "accuracy", "summary"}:
        require(report.get("prefix_caching_enabled") is True, "非性能验收必须开启前缀缓存")
    if stage == "summary" and profile["status"] == "active":
        launcher = report.get("launcher", {})
        path = reader.file(launcher)
        require(path == reader.root / "start-model.sh" and path.stat().st_mode & 0o111,
                "最终启动脚本必须位于根目录且可执行")


def verify_record(root, directory, cfg, profile, stage, mounts=None):
    rec = record_for(cfg, stage)
    require(isinstance(rec, dict) and rec, f"{stage}: 缺少 verification")
    require(isinstance(rec.get("run_id"), str) and rec["run_id"].strip(), f"{stage}: 缺少 run_id")
    require(date.fromisoformat(rec.get("last_verified", "")) <= date.today(), f"{stage}: 验证日期非法")
    evidence = rec.get("evidence")
    require(isinstance(evidence, str) and evidence and not Path(evidence).is_absolute(), f"{stage}: 缺少本地证据路径")
    file = (directory / evidence).resolve()
    owner = root / "models" / cfg["model"] if stage == "architecture" else directory
    require(file.is_relative_to(owner.resolve()) and file.is_file() and file.stat().st_size > 0, f"{stage}: 证据缺失或越界")
    if stage in WORKFLOW_PHASES:
        require(cfg["workflow"][stage].get("evidence") == evidence, f"{stage}: evidence 与 verification 不一致")
    if stage == "architecture":
        require(file == (owner / "architecture-and-inference.md").resolve(), "架构证据必须是模型级 architecture-and-inference.md")
    require(digest(file) == rec.get("evidence_sha256"), f"{stage}: 本地证据已变化")
    require(context_hash(root, directory, cfg, profile, stage) == rec.get("context_sha256"), f"{stage}: 上下文已变化")
    if stage == "architecture":
        return
    hosts = cfg["target"]["hosts"]
    refs = rec.get("receipts")
    require(isinstance(refs, list) and len(refs) == len(hosts), f"{stage}: 必须逐 Host 记录回执")
    require({ref.get("host_alias") for ref in refs} == set(hosts), f"{stage}: 回执 Host 不匹配")
    for ref in refs:
        reference(ref)
        if mounts is not None:
            check_receipt(Artifacts(cfg, ref["host_alias"], mounts), ref, cfg, profile, stage, rec)


def validate_workspace(root, directory, cfg, profile, mounts=None):
    errors = workspace_errors(cfg, model=directory.parents[2].name, platform=directory.parents[1].name, framework=directory.name)
    if errors:
        return errors
    try:
        require(cfg["platform"] in profile["platforms"], "框架不支持该平台")
        require(cfg["profile_version"] == profile["profile_version"], "profile revision 已变化，必须复核证据")
        steps = step_names(cfg, profile)
        started = any(state(cfg, s) != "not_started" for s in [*WORKFLOW_PHASES[1:], *steps])
        if started:
            hosts = cfg.get("target", {}).get("hosts")
            require(isinstance(hosts, list) and hosts and all(isinstance(h, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", h) for h in hosts)
                    and len(set(hosts)) == len(hosts), "缺少准确 Host 集合")
            roots = cfg.get("workspace", {}).get("roots")
            require(isinstance(roots, list) and len(roots) == len(hosts) and {r.get("host_alias") for r in roots} == set(hosts), "工作根必须逐 Host 声明")
            for row in roots:
                for field in ("host_root", "container_root"):
                    path = PurePosixPath(row.get(field, ""))
                    require(path.is_absolute() and str(path) != "/" and ".." not in path.parts, "工作根必须是绝对非根目录")
                aliases = row.get("evaluator_roots", [])
                require(isinstance(aliases, list), "evaluator_roots 必须是已核实容器根列表")
                for value in aliases:
                    path = PurePosixPath(value)
                    require(path.is_absolute() and str(path) != "/" and ".." not in path.parts, "评测容器根非法")
            require(SHA.fullmatch(cfg.get("deployment", {}).get("fingerprint", "")), "缺少已核实部署指纹")
            if (root / "inventory/hosts.yml").is_file():
                from adapt_model import inventory_platform_hosts
                require(set(hosts) <= inventory_platform_hosts(root, cfg["platform"]), "工作区 Host 不属于目标平台")
        for stage in [*WORKFLOW_PHASES, *steps]:
            status = state(cfg, stage)
            if status in DONE | {"in_progress"}:
                # Acceptance in progress requires phases 1-3, not all its future substeps.
                deps = dependencies(cfg, profile, stage)
                if stage == "acceptance" and status == "in_progress":
                    deps = list(WORKFLOW_PHASES[:3])
                for previous in deps:
                    require(state(cfg, previous) in DONE, f"{stage} 的前置 {previous} 未完成")
            if status in DONE:
                verify_record(root, directory, cfg, profile, stage, mounts)
        if cfg["status"] in {"functional", "optimized"}:
            basic = "execution-mode" if "execution-mode" in steps else "model-eager"
            require(basic in steps and state(cfg, basic) in DONE, "functional/optimized 缺少模型推理证据")
        if cfg["status"] == "optimized":
            require(profile["status"] == "active" and all(state(cfg, s) in DONE for s in steps)
                    and state(cfg, "acceptance") in DONE, "optimized 需要 active profile 和完整验收")
        if profile["status"] == "experimental":
            require(state(cfg, "acceptance") not in DONE, "experimental 只能完成独立验证子步骤，不能标记整体验收完成")
    except (ValueError, KeyError, TypeError, AttributeError, OSError, StopIteration) as exc:
        errors.append(str(exc) or type(exc).__name__)
    return errors


def check_command(args):
    require(args.check_only, "框架入口仅做 --check-only；创建请用 new-framework，执行用所选框架工作流")
    require(args.platform, "必须指定 --platform")
    root = args.repo_root.resolve()
    _, profile = resolved_profile(root, args.framework)
    require(isinstance(args.model, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.model), "非法模型名")
    directory = root / "models" / args.model / args.platform / "frameworks" / args.framework
    cfg = load_yaml(directory / "framework.yml")
    mounts = {}
    for item in args.artifact_root:
        host, sep, path = item.partition("=")
        require(sep and Path(path).is_absolute() and host not in mounts, "artifact-root 必须为唯一 HOST=/绝对路径")
        mounts[host] = path
    errors = validate_workspace(root, directory, cfg, profile)
    require(not errors, "\n".join(errors))
    if args.evidence_info:
        stage = args.evidence_info
        require(stage in WORKFLOW_PHASES or stage in step_names(cfg, profile), "该框架不支持此证据阶段")
        require(args.evidence and args.run_id, "--evidence-info 需要 --evidence 和 --run-id")
        path = (directory / args.evidence).resolve()
        owner = root / "models" / cfg["model"] if stage == "architecture" else directory
        require(path.is_relative_to(owner.resolve()) and path.is_file(), "证据缺失或越界")
        print(json.dumps({"run_id": args.run_id, "last_verified": args.verified_on,
                          "evidence": args.evidence, "evidence_sha256": digest(path),
                          "context_sha256": context_hash(root, directory, cfg, profile, stage)}, ensure_ascii=False, indent=2))
        print("仅计算本地绑定；必须另行核实逐 Host 远端 receipts，不能据此标记通过。")
        return 0
    selected = [WORKFLOW_PHASES[int(v)-1] if v in {"1", "2", "3", "4", "5"} else v for v in args.steps.split(",")]
    require(all(s in WORKFLOW_PHASES for s in selected), "未知阶段")
    selected = [s for s in WORKFLOW_PHASES if s in selected]
    if selected != ["architecture"]:
        hosts = args.hosts.split(",") if args.hosts else []
        require(hosts and len(hosts) == len(set(hosts)) and set(hosts) == set(cfg.get("target", {}).get("hosts", [])), "--hosts 必须与工作区准确 Host 集合一致")
        from adapt_model import inventory_platform_hosts
        require(set(hosts) <= inventory_platform_hosts(root, args.platform), "目标 Host 不属于平台 inventory")
    steps = step_names(cfg, profile)
    substeps = args.acceptance_substeps.split(",") if args.acceptance_substeps else []
    require(not substeps or "acceptance" in selected, "验收子步骤需选择 acceptance")
    require(set(substeps) <= set(steps), f"该框架可用验收子步骤: {', '.join(steps)}")
    targets = []
    for phase in selected:
        if phase == "acceptance":
            targets.extend(s for s in steps if not substeps or s in substeps)
            if args.verify_records and not substeps:
                targets.append("acceptance")
        else:
            targets.append(phase)
    for target in targets:
        for previous in dependencies(cfg, profile, target):
            # Selection never waives an incomplete prerequisite in a read-only gate.
            require(state(cfg, previous) in DONE, f"{target} 前置 {previous} 未完成")
            verify_record(root, directory, cfg, profile, previous, mounts)
        if args.verify_records:
            require(state(cfg, target) in DONE, f"{target} 未完成")
            verify_record(root, directory, cfg, profile, target, mounts)
    print(f"Framework gate passed: {args.framework}; selected={','.join(targets)}; "
          f"mode={'record-verification' if args.verify_records else 'prerequisites-only'}")
    print(f"Workflow: framework-profiles/{args.framework}/{profile['documents']['workflow']}")
    return 0
