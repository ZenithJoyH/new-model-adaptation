#!/usr/bin/env python3
"""Prepare and validate selected model-adaptation workflow stages."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import posixpath
import re
import shutil
import sys
from pathlib import Path
from datetime import date
from typing import Any

import yaml

from workflow_state import deployment_fingerprint, service_state_errors, model_identity, environment_target


STEP_ALIASES = {
    "1": "architecture",
    "architecture": "architecture",
    "2": "environment",
    "environment": "environment",
    "3": "adaptation",
    "adaptation": "adaptation",
    "4": "acceptance",
    "acceptance": "acceptance",
    "5": "retrospective",
    "retrospective": "retrospective",
}
STEP_ORDER = tuple(dict.fromkeys(STEP_ALIASES.values()))
STEP_NUMBER = {name: index for index, name in enumerate(STEP_ORDER, start=1)}
STEP_LABEL = {
    "architecture": "模型结构与推理链路分析",
    "environment": "推理环境分析",
    "adaptation": "进行适配",
    "acceptance": "适配验收",
    "retrospective": "适配复盘",
}
DEPENDENCIES = {
    "architecture": (),
    "environment": (),
    "adaptation": ("architecture", "environment"),
    "acceptance": ("adaptation",),
    "retrospective": ("acceptance",),
}
PLATFORMS = ("nvidia", "ppu", "metax", "ascend", "mthreads", "hygon")
COMPLETE_STATUSES = {"passed", "complete"}
VALID_STATUSES = {"not_started", "in_progress", "blocked", "failed", "passed", "complete"}
PLATFORM_STATUSES = {"not_started", "environment_ready", "model_loading", "functional", "optimized", "blocked"}
ACCEPTANCE_SUBSTEP_ORDER = (
    "execution-mode",
    "sanity",
    "accuracy",
    "performance",
    "evidence",
    "summary",
)
ACCEPTANCE_SUBSTEPS = set(ACCEPTANCE_SUBSTEP_ORDER)
ACCEPTANCE_DEPENDENCIES = {
    "execution-mode": (),
    "sanity": ("execution-mode",),
    "accuracy": ("sanity",),
    "performance": ("accuracy",),
    "evidence": ("performance",),
    "summary": ("evidence",),
}
SECRET_KEYS = {
    "password", "passwd", "token", "secret", "api_key", "access_token",
    "auth_token", "private_key", "private_key_path", "identity_file",
    "hf_token", "huggingface_token", "github_token", "bearer_token", "session_token",
    "ansible_host", "ansible_user", "ansible_port", "ssh_user", "ssh_host",
    "ssh_private_key_file", "ansible_ssh_private_key_file", "proxy_jump",
}
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
FRAMEWORK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class WorkflowError(RuntimeError):
    pass


def parse_csv(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def parse_steps(value: str) -> list[str]:
    resolved: set[str] = set()
    for item in parse_csv(value):
        try:
            resolved.add(STEP_ALIASES[item])
        except KeyError as exc:
            raise WorkflowError(f"未知步骤: {item}") from exc
    if not resolved:
        raise WorkflowError("至少指定一个步骤")
    return [step for step in STEP_ORDER if step in resolved]


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise WorkflowError(f"无法读取 YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"YAML 顶层必须是映射: {path}")
    return value


def write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def copy_if_missing(source: Path, destination: Path, *, check_only: bool) -> bool:
    if destination.exists():
        return False
    if check_only:
        raise WorkflowError(f"缺少阶段文件: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return True


def merge_missing(destination: dict[str, Any], defaults: dict[str, Any]) -> bool:
    changed = False
    for key, value in defaults.items():
        if key not in destination:
            destination[key] = copy.deepcopy(value)
            changed = True
        elif isinstance(value, dict) and isinstance(destination[key], dict):
            changed = merge_missing(destination[key], value) or changed
    return changed


def reject_secret_keys(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            child_path = f"{path}.{key}" if path else str(key)
            if sensitive_key(key_text):
                raise WorkflowError(
                    f"配置中禁止出现敏感连接字段 {child_path}；请使用 ~/.ssh/config 或密钥管理"
                )
            reject_secret_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_secret_keys(child, f"{path}[{index}]")


def sensitive_key(key: str) -> bool:
    key = key.lower().lstrip("-").replace("-", "_")
    return key in SECRET_KEYS or key.endswith(("_password", "_passwd", "_secret", "_api_key", "_access_token", "_auth_token"))


def ancestors(name: str, dependencies: dict[str, tuple[str, ...]]) -> set[str]:
    result: set[str] = set()
    for dependency in dependencies[name]:
        result.add(dependency)
        result.update(ancestors(dependency, dependencies))
    return result


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context_sha256(platform_dir: Path, stage: str, platform_config: dict | None = None) -> str:
    """Bind evidence to recorded inputs; this never attests remote state."""
    model_dir = platform_dir.parent
    cfg = platform_config
    if cfg is None and (platform_dir / "platform.yml").is_file():
        cfg = load_yaml(platform_dir / "platform.yml")
    compact = isinstance(cfg, dict) and cfg.get("record_layout") == "compact"
    try:
        model_identity(model_dir)
        if stage == "environment":
            environment_target(platform_dir)
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    inputs = {"model": model_dir.name, "platform": platform_dir.name, "stage": stage}
    files = [model_dir / "model.yml"]
    if stage == "environment" and not compact:
        files.append(platform_dir / "environment/environment-target.yml")
    elif stage == "environment":
        inputs["scope"] = {
            "target": cfg.get("target"),
            "workspace": cfg.get("workspace"),
        }
    if stage != "architecture":
        files += [model_dir / "architecture-and-inference.md",
                  platform_dir / "environment/environment-analysis.md"]
    if stage not in {"architecture", "environment"}:
        if compact:
            inputs["scope"] = {
                "target": cfg.get("target"),
                "workspace": cfg.get("workspace"),
            }
            inputs["binding_schema"] = 3
        else:
            try:
                inputs["deployment_identity"] = deployment_fingerprint(platform_dir)
            except ValueError as exc:
                raise WorkflowError(str(exc)) from exc
            inputs["binding_schema"] = 2
        phases = cfg.get("workflow", {})
        # Bind receipts, not the entire mutable platform.yml. No self-reference,
        # status timestamps or unrelated progress notes enter this acyclic chain.
        if stage in ACCEPTANCE_SUBSTEPS:
            prerequisites = ("adaptation", *ACCEPTANCE_DEPENDENCIES[stage])
        elif stage == "acceptance":
            prerequisites = ("adaptation", *ACCEPTANCE_SUBSTEP_ORDER)
        else:
            prerequisites = DEPENDENCIES[stage]
        receipts = {}
        for prerequisite in prerequisites:
            if prerequisite in ACCEPTANCE_SUBSTEPS:
                record = phases.get("acceptance", {}).get("records", {}).get(prerequisite, {})
            else:
                record = phases.get(prerequisite, {}).get("verification", {})
            if not isinstance(record, dict):
                raise WorkflowError(f"{prerequisite} verification 必须为映射")
            receipts[prerequisite] = {key: record.get(key) for key in
                                     ("run_id", "evidence", "evidence_sha256", "context_sha256", "service_instance_id")}
        inputs["prerequisites"] = receipts
        runtime = platform_dir / "environment/runtime-config.yml"
        if not compact:
            files.append(runtime)
        if stage == "adaptation":
            files.append(platform_dir / "environment/plugin-change-review.md")
        if not compact and runtime.is_file() and stage in {"accuracy", "performance", "evidence", "summary", "acceptance", "retrospective"}:
            config = load_yaml(runtime)
            accuracy_path = config.get("acceptance", {}).get("accuracy_config")
            if isinstance(accuracy_path, str) and accuracy_path:
                path = Path(accuracy_path)
                files.append(path if path.is_absolute() else model_dir.parents[1] / path)
    for path in files:
        if not path.is_file():
            raise WorkflowError(f"证据上下文缺少输入文件: {path}")
        inputs[str(path.relative_to(model_dir)) if path.is_relative_to(model_dir) else str(path)] = file_sha256(path)
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()


def verification_errors(record: Any, platform_dir: Path, stage: str,
                        platform_config: dict | None = None) -> list[str]:
    if not isinstance(record, dict) or not record:
        return [f"{stage} 缺少 verification 记录；历史 passed 不能代替当前验证"]
    errors = []
    for key in ("run_id", "last_verified", "evidence", "evidence_sha256", "context_sha256"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            errors.append(f"{stage}.verification.{key} 不能为空")
    if errors:
        return errors
    try:
        if date.fromisoformat(record["last_verified"]) > date.today():
            errors.append(f"{stage} 验证日期不能在未来")
    except ValueError:
        errors.append(f"{stage} 验证日期必须为 YYYY-MM-DD")
    evidence = (platform_dir / record["evidence"]).resolve()
    owner = platform_dir.parent if stage == "architecture" else platform_dir
    if not evidence.is_relative_to(owner.resolve()) or not evidence.is_file():
        errors.append(f"{stage} 证据必须属于当前{'模型' if stage == 'architecture' else '平台'}: {evidence}")
    elif evidence.stat().st_size == 0 or file_sha256(evidence) != record["evidence_sha256"]:
        errors.append(f"{stage} 证据为空或内容已变化，需要重新验证")
    compact = isinstance(platform_config, dict) and platform_config.get("record_layout") == "compact"
    if compact and stage in {"accuracy", "performance"}:
        errors.append(f"{stage}: compact Markdown 不等于正式回执；请使用 --framework 工作区和远端原生证据校验")
    if not compact and stage == "accuracy":
        try:
            report = json.loads(evidence.read_text(encoding="utf-8"))
            if (report.get("kind") != "formal_accuracy" or report.get("status") != "passed"
                    or report.get("service_mode") != "graph" or report.get("failed_tasks") != []
                    or type(report.get("configured_concurrency")) is not int
                    or report["configured_concurrency"] < 32):
                errors.append("accuracy 需要 llmrun.py 生成的通过验收报告 acceptance-result.json")
            runtime = load_yaml(platform_dir / "environment/runtime-config.yml")
            config_path = Path(runtime["acceptance"]["accuracy_config"])
            if not config_path.is_absolute():
                config_path = platform_dir.parents[2] / config_path
            if report.get("source_config_sha256") != file_sha256(config_path):
                errors.append("accuracy 报告使用的配置与当前精度配置不一致")
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if (report.get("run_id") != record["run_id"]
                    or report.get("expected_samples") != config.get("expected_samples")
                    or report.get("criteria") != config.get("acceptance_criteria")
                    or report.get("allow_timeouts") is not True
                    or report.get("timeout_policy") != "count_as_incorrect"):
                errors.append("accuracy 报告的运行标识、样本数或验收标准不一致")
        except (OSError, ValueError, KeyError, AttributeError) as exc:
            errors.append(f"无法验证正式精度报告: {exc}")
    elif not compact and stage == "performance":
        # Full artifacts remain with the benchmark run. Only the compact receipt
        # exported after perf_common.validate_report may be bound in the workspace.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "test/perf_test"))
        try:
            from perf_acceptance import validate_evidence
            runtime_path = platform_dir / "environment/runtime-config.yml"
            report = json.loads(evidence.read_text(encoding="utf-8"))
            errors.extend(validate_evidence(
                report, runtime=load_yaml(runtime_path), runtime_sha256=file_sha256(runtime_path),
                model=platform_dir.parent.name, platform=platform_dir.name,
                deployment_fingerprint=deployment_fingerprint(platform_dir),
                service_instance_id=record.get("service_instance_id"), run_id=record["run_id"],
            ))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(f"无法验证正式性能回执: {exc}")
        finally:
            sys.path.pop(0)
    try:
        if context_sha256(platform_dir, stage, platform_config) != record["context_sha256"]:
            errors.append(f"{stage} 模型、配置或前置证据已变化，需要重新验证")
    except WorkflowError as exc:
        errors.append(str(exc))
    return errors


def require_mapping(config: dict[str, Any], key: str, source: Path) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise WorkflowError(f"{source} 缺少映射字段: {key}")
    return value


def workspace_errors(config: dict[str, Any]) -> list[str]:
    """Check declared remote roots, not remote mounts, permissions or confinement."""
    workspace = config.get("workspace")
    if not isinstance(workspace, dict) or set(workspace) != {"roots"}:
        return ["workspace 必须为仅含 roots 的映射；远端工作目录必须由用户明确指定"]
    roots = workspace.get("roots")
    if not isinstance(roots, list) or not roots:
        return ["workspace.roots 必须显式列出每台目标主机的 host_alias/host_root/container_root"]
    target = config.get("target")
    hosts = target.get("hosts") if isinstance(target, dict) else None
    errors = []
    container_name = target.get("container_name") if isinstance(target, dict) else None
    if (not isinstance(container_name, str) or not container_name
            or container_name != container_name.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in container_name)):
        errors.append("workspace.container_root 需要明确对应的 target.container_name")
    declared = []
    for index, item in enumerate(roots):
        prefix = f"workspace.roots[{index}]"
        if not isinstance(item, dict) or set(item) != {"host_alias", "host_root", "container_root"}:
            errors.append(f"{prefix} 必须且只能包含 host_alias、host_root、container_root")
            continue
        host = item.get("host_alias")
        if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", host):
            errors.append(f"{prefix}.host_alias 必须是明确的 SSH Host 别名")
        else:
            declared.append(host)
        for field in ("host_root", "container_root"):
            value = item.get(field)
            if (not isinstance(value, str) or not value.startswith("/") or value.startswith("//")
                    or value == "/" or value != value.strip() or posixpath.normpath(value) != value
                    or any(ord(char) < 32 or ord(char) == 127 or char in "$~<>\\" for char in value)):
                errors.append(f"{prefix}.{field} 必须是用户明确指定的规范 POSIX 绝对目录，不得为 /、变量或占位符")
    if (not isinstance(hosts, list) or not hosts or not all(isinstance(host, str) for host in hosts)
            or len(set(hosts)) != len(hosts) or len(set(declared)) != len(declared)
            or set(declared) != set(hosts)):
        errors.append("workspace.roots 的 host_alias 必须无重复且精确覆盖 target.hosts，不能跨主机猜测目录")
    return errors


def validate_adaptation_config(
    path: Path,
    model: str,
    platform: str,
    repo_root: Path | None = None,
    acceptance_substeps: list[str] | None = None,
) -> list[str]:
    config = load_yaml(path)
    reject_secret_keys(config)
    errors: list[str] = []

    if config.get("schema_version") != 1:
        errors.append("schema_version 必须为 1")
    if config.get("model") != model:
        errors.append(f"model 必须为 {model!r}")
    if config.get("platform") != platform:
        errors.append(f"platform 必须为 {platform!r}")
    if config.get("configuration_status") != "ready":
        errors.append("configuration_status 必须在远程状态复核完成后设为 ready")

    target = require_mapping(config, "target", path)
    hosts = target.get("hosts")
    if not isinstance(hosts, list) or not hosts or not all(isinstance(item, str) and item for item in hosts):
        errors.append("target.hosts 必须是非空 SSH Host 别名列表")
    elif len(hosts) != len(set(hosts)):
        errors.append("target.hosts 不得包含重复别名")
    elif repo_root is not None:
        inventory_path = repo_root / "inventory" / "hosts.yml"
        inventory = load_yaml(inventory_path)
        try:
            platform_hosts = (
                inventory["all"]["children"]["managed"]["children"][platform]["hosts"]
            )
        except (KeyError, TypeError) as exc:
            raise WorkflowError(f"inventory 缺少 managed.{platform}.hosts") from exc
        if not isinstance(platform_hosts, dict):
            raise WorkflowError(f"inventory 中 managed.{platform}.hosts 必须是映射")
        unknown_hosts = sorted(set(hosts) - set(platform_hosts))
        if unknown_hosts:
            errors.append(
                f"target.hosts 包含不属于 inventory {platform} 组的别名: "
                f"{', '.join(unknown_hosts)}"
            )
    for field in ("container_name", "container_image"):
        if not isinstance(target.get(field), str) or not target[field].strip():
            errors.append(f"target.{field} 不能为空")

    errors.extend(workspace_errors(config))

    boundaries = require_mapping(config, "boundaries", path)
    if boundaries.get("vllm_source_read_only") is not True:
        errors.append("boundaries.vllm_source_read_only 必须为 true")
    if boundaries.get("adaptation_container_must_remain_running") is not True:
        errors.append("boundaries.adaptation_container_must_remain_running 必须为 true")

    stack = require_mapping(config, "stack", path)
    for component in ("vllm", "plugin", "flaggems"):
        item = stack.get(component)
        if not isinstance(item, dict):
            errors.append(f"stack.{component} 必须是映射")
            continue
        for field in ("path", "revision"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"stack.{component}.{field} 不能为空")

    service = require_mapping(config, "service", path)
    for field in ("model_path", "served_model_name"):
        if not isinstance(service.get(field), str) or not service[field].strip():
            errors.append(f"service.{field} 不能为空")
    for field in ("port", "tensor_parallel_size"):
        if type(service.get(field)) is not int or service[field] <= 0:
            errors.append(f"service.{field} 必须是正整数")
    gpu_utilization = service.get("gpu_memory_utilization")
    if type(gpu_utilization) not in (int, float) or not 0 < gpu_utilization <= 1:
        errors.append("service.gpu_memory_utilization 必须大于 0 且不超过 1")

    max_len = service.get("max_model_len")
    if not isinstance(max_len, dict):
        errors.append("service.max_model_len 必须是映射")
    else:
        supported = max_len.get("model_supported")
        initial = max_len.get("initial")
        evidence = max_len.get("evidence")
        if type(supported) is not int or supported <= 0:
            errors.append("service.max_model_len.model_supported 必须是正整数")
        if type(initial) is not int or initial <= 0:
            errors.append("service.max_model_len.initial 必须是正整数")
        if isinstance(supported, int) and supported > 0 and isinstance(initial, int):
            expected = min(supported, 50000)
            if initial != expected:
                errors.append(
                    f"service.max_model_len.initial 应为 min({supported}, 50000) = {expected}"
                )
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append("service.max_model_len.evidence 不能为空")

    execution = require_mapping(config, "execution_modes", path)
    for mode in ("eager", "graph"):
        item = execution.get(mode)
        if not isinstance(item, dict):
            errors.append(f"execution_modes.{mode} 必须是映射")
            continue
        if item.get("enabled") is not True:
            errors.append(f"execution_modes.{mode}.enabled 必须为 true")
        extra_args = item.get("extra_args")
        if not isinstance(extra_args, list) or not all(isinstance(arg, str) for arg in extra_args):
            errors.append(f"execution_modes.{mode}.extra_args 必须是参数数组")
        elif any(sensitive_key(arg.split("=", 1)[0]) for arg in extra_args if arg.startswith("--")):
            errors.append(f"execution_modes.{mode}.extra_args 不得包含敏感参数")
        if mode == "graph" and isinstance(extra_args, list) and "--enforce-eager" in extra_args:
            errors.append("execution_modes.graph.extra_args 不得包含 --enforce-eager")

    acceptance = require_mapping(config, "acceptance", path)
    if acceptance.get("sanity_concurrency") != 10:
        errors.append("acceptance.sanity_concurrency 必须为 10")
    if acceptance.get("accuracy_runner") != "test/Accuracy_test/llmrun.py":
        errors.append("acceptance.accuracy_runner 必须为 test/Accuracy_test/llmrun.py")
    if acceptance.get("performance_directory") != "test/perf_test":
        errors.append("acceptance.performance_directory 必须为 test/perf_test")
    selected_acceptance = set(acceptance_substeps or ())
    if "performance" in selected_acceptance:
        graph_args = execution.get("graph", {}).get("extra_args")
        prefix_cache = service.get("prefix_caching")
        if not isinstance(prefix_cache, dict) or prefix_cache.get("default_enabled") is not True:
            errors.append("非性能测试必须保持 service.prefix_caching.default_enabled=true")
        else:
            performance_cache = prefix_cache.get("performance")
            if not isinstance(performance_cache, dict) or performance_cache.get("enabled") is not False:
                errors.append("正式性能测试前必须核实并记录 service.prefix_caching.performance.enabled=false")
            else:
                launch_args = performance_cache.get("launch_args")
                if not isinstance(launch_args, list) or launch_args != ["--no-enable-prefix-caching"]:
                    errors.append("性能测试专用服务的前缀缓存启动参数必须包含且仅包含 --no-enable-prefix-caching")
                if not isinstance(performance_cache.get("verification"), str) or not performance_cache["verification"].strip():
                    errors.append("正式性能测试前必须记录前缀缓存已关闭的现场证据")
        if isinstance(graph_args, list) and "--no-enable-prefix-caching" in graph_args:
            errors.append("--no-enable-prefix-caching 不得写入通用 graph 参数，只能用于性能测试服务")
    if selected_acceptance & {"sanity", "accuracy", "performance", "evidence", "summary"}:
        if not isinstance(acceptance.get("graph_base_url"), str) or not acceptance[
            "graph_base_url"
        ].strip():
            errors.append("graph 模式验收前 acceptance.graph_base_url 不能为空")
    if selected_acceptance & {"accuracy", "performance", "evidence", "summary"}:
        allowed_images = {
            "harbor.baai.ac.cn/flageval/flageval-llmeval:v1",
            "harbor.baai.ac.cn/flageval/flageval-llmeval:arm64",
        }
        if acceptance.get("accuracy_image") not in allowed_images:
            errors.append("accuracy_image 必须选择规定的 FlagEval v1 或 arm64 镜像")
        if not isinstance(acceptance.get("accuracy_config"), str) or not acceptance[
            "accuracy_config"
        ].strip():
            errors.append("正式精度验收前 acceptance.accuracy_config 不能为空")
        elif repo_root is not None:
            accuracy_path = Path(acceptance["accuracy_config"])
            if not accuracy_path.is_absolute():
                accuracy_path = repo_root / accuracy_path
            owner = repo_root / "models" / model / platform / "acceptance"
            if not accuracy_path.resolve().is_relative_to(owner.resolve()):
                errors.append("accuracy_config 必须位于当前模型平台的 acceptance/ 下")
            elif not accuracy_path.is_file():
                errors.append(f"精度配置文件不存在: {accuracy_path}")
            else:
                # Import the same contract the runner uses; do not duplicate policy.
                sys.path.insert(0, str(repo_root / "test/Accuracy_test"))
                try:
                    from acceptance_contract import validate_formal_config
                    accuracy = json.loads(accuracy_path.read_text(encoding="utf-8"))
                    errors.extend(validate_formal_config(accuracy, require_formal=True))
                    if accuracy.get("model_name") != service.get("served_model_name"):
                        errors.append("精度配置 model_name 与 served_model_name 不一致")
                    if accuracy.get("base_url", "").rstrip("/").removesuffix("/v1/chat/completions").removesuffix("/v1/completions") != acceptance.get("graph_base_url", "").rstrip("/").removesuffix("/v1"):
                        errors.append("精度配置 base_url 与 graph_base_url 不一致")
                except (OSError, ValueError, TypeError, AttributeError) as exc:
                    errors.append(f"无法读取精度配置: {exc}")
                finally:
                    sys.path.pop(0)

    return errors


def prepare_config(
    template: Path,
    destination: Path,
    model: str,
    platform: str,
    hosts: list[str],
    check_only: bool,
) -> bool:
    if destination.exists():
        return False
    if check_only:
        raise WorkflowError(f"缺少阶段文件: {destination}")
    config = load_yaml(template)
    config["model"] = model
    config["platform"] = platform
    config["target"]["hosts"] = hosts
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(destination, config)
    return True


def prepare_identified_yaml(
    template: Path,
    destination: Path,
    model: str,
    platform: str,
    check_only: bool,
) -> bool:
    if destination.exists():
        return False
    if check_only:
        raise WorkflowError(f"缺少阶段文件: {destination}")
    value = load_yaml(template)
    value["model"] = model
    value["platform"] = platform
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(destination, value)
    return True


def workflow_status(platform_config: dict[str, Any], step: str) -> str:
    workflow = platform_config.get("workflow")
    if not isinstance(workflow, dict):
        raise WorkflowError("platform.yml 缺少 workflow 映射，请从最新模板升级")
    item = workflow.get(step)
    if not isinstance(item, dict):
        raise WorkflowError(f"platform.yml 缺少 workflow.{step}")
    status = item.get("status")
    if status not in VALID_STATUSES:
        raise WorkflowError(f"workflow.{step}.status 非法: {status!r}")
    return status


def platform_schema_errors(config: dict, platform: str, allowed_hosts: set[str] | None = None) -> list[str]:
    """Structural/semantic errors only; historical receipt freshness is audited separately."""
    errors = []
    for key in ("platform", "inventory_group"):
        if config.get(key) != platform:
            errors.append(f"{key} 必须与平台目录 {platform} 一致")
    status = config.get("status")
    if not isinstance(status, str) or status not in PLATFORM_STATUSES:
        errors.append(f"非法平台 status: {status!r}")
        status = None
    frameworks = config.get("frameworks", {})
    if not isinstance(frameworks, dict):
        errors.append("frameworks 必须是映射（无显式工作区时为 {}）")
    else:
        for framework, entry in frameworks.items():
            if not isinstance(framework, str) or not FRAMEWORK_ID_RE.fullmatch(framework):
                errors.append(f"非法 framework ID: {framework!r}")
                continue
            expected_workspace = f"frameworks/{framework}/framework.yml"
            expected_profile = f"framework-profiles/{framework}/profile.yml"
            if not isinstance(entry, dict):
                errors.append(f"frameworks.{framework} 必须是映射")
            elif entry.get("workspace") != expected_workspace or entry.get("profile") != expected_profile:
                errors.append(
                    f"frameworks.{framework} 必须准确引用 {expected_workspace} 和 {expected_profile}"
                )
    hosts = config.get("validated_hosts")
    valid_hosts = (isinstance(hosts, list) and all(isinstance(h, str) and h.strip() for h in hosts))
    if not valid_hosts or len(hosts) != len(set(hosts)):
        errors.append("validated_hosts 必须是无重复的 SSH Host 别名列表")
    elif allowed_hosts is not None and set(hosts) - allowed_hosts:
        errors.append("validated_hosts 包含不属于当前平台 inventory 的别名")
    if status in {"functional", "optimized"}:
        if not valid_hosts or not hosts:
            errors.append(f"{status} 必须记录非空 validated_hosts")
        try:
            verified = date.fromisoformat(str(config.get("last_verified")))
            if verified > date.today():
                raise ValueError("future")
        except ValueError:
            errors.append(f"{status} 必须记录有效且非未来的 last_verified")
    phases = config.get("workflow")
    if not isinstance(phases, dict):
        return errors + ["platform.yml 缺少 workflow 映射"]
    for stage in STEP_ORDER:
        try:
            workflow_status(config, stage)
        except (WorkflowError, TypeError) as exc:
            errors.append(str(exc))
        item = phases.get(stage)
        if isinstance(item, dict) and not isinstance(item.get("verification"), dict):
            errors.append(f"workflow.{stage}.verification 必须是映射（待复核可为 {{}}）")
    acceptance = phases.get("acceptance")
    if not isinstance(acceptance, dict):
        return errors
    substeps, records = acceptance.get("substeps"), acceptance.get("records")
    if not isinstance(substeps, dict) or set(substeps) != ACCEPTANCE_SUBSTEPS:
        errors.append("workflow.acceptance.substeps 必须完整包含六个规定子步骤")
    if isinstance(substeps, dict):
        for name, value in substeps.items():
            if not isinstance(value, str) or value not in VALID_STATUSES:
                errors.append(f"非法验收子步骤状态: {name}={value!r}")
    if not isinstance(records, dict) or set(records) - ACCEPTANCE_SUBSTEPS:
        errors.append("workflow.acceptance.records 必须是仅含已知子步骤的映射（待复核可为 {}）")
    if status == "not_started" and any(isinstance(v, dict) and v.get("status") != "not_started" for v in phases.values()):
        errors.append("平台 not_started 与已开始的 workflow 状态冲突")
    acceptance_status = acceptance.get("status")
    acceptance_complete = isinstance(acceptance_status, str) and acceptance_status in COMPLETE_STATUSES
    if status == "optimized" or acceptance_complete:
        if not isinstance(substeps, dict) or any(not isinstance(substeps.get(s), str) or substeps[s] not in COMPLETE_STATUSES for s in ACCEPTANCE_SUBSTEP_ORDER):
            errors.append("optimized 或已完成 acceptance 必须完成全部验收子步骤")
    if status == "optimized" and not acceptance_complete:
        errors.append("optimized 必须有已完成的 acceptance 阶段")
    layout = config.get("record_layout", "legacy")
    if layout not in {"legacy", "compact"}:
        errors.append("record_layout 仅支持 legacy 或 compact")
    if layout == "compact":
        target = config.get("target")
        if not isinstance(target, dict):
            errors.append("compact platform.yml 必须记录 target")
        else:
            target_hosts = target.get("hosts")
            if (not isinstance(target_hosts, list) or not target_hosts or
                    not all(isinstance(host, str) and host.strip() for host in target_hosts) or
                    len(target_hosts) != len(set(target_hosts))):
                errors.append("compact target.hosts 必须是非空、无重复的 SSH Host 别名列表")
            elif allowed_hosts is not None and set(target_hosts) - allowed_hosts:
                errors.append("compact target.hosts 包含不属于当前平台 inventory 的别名")
            for field in ("container_name", "container_image"):
                if not isinstance(target.get(field), str) or not target[field].strip():
                    errors.append(f"compact target.{field} 不能为空")
        errors.extend(workspace_errors(config))
    return errors


def inventory_platform_hosts(repo_root: Path, platform: str) -> set[str]:
    inventory = load_yaml(repo_root / "inventory" / "hosts.yml")
    try:
        hosts = inventory["all"]["children"]["managed"]["children"][platform]["hosts"]
    except (KeyError, TypeError) as exc:
        raise WorkflowError(f"inventory 缺少 managed.{platform}.hosts") from exc
    if not isinstance(hosts, dict):
        raise WorkflowError(f"inventory 中 managed.{platform}.hosts 必须是映射")
    return set(hosts)


def check_dependencies(
    platform_config: dict[str, Any], selected: list[str], platform_dir: Path,
    *, expected_hosts: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    selected_set = set(selected)
    for step in selected:
        for dependency in sorted(ancestors(step, DEPENDENCIES), key=STEP_ORDER.index):
            if dependency in selected_set:
                continue
            status = workflow_status(platform_config, dependency)
            if status not in COMPLETE_STATUSES:
                errors.append(
                    f"步骤 {STEP_NUMBER[step]} 依赖步骤 {STEP_NUMBER[dependency]}，"
                    f"但其状态为 {status}，且本次未选择该前置步骤"
                )
                continue
            dependency_item = platform_config["workflow"][dependency]
            evidence = dependency_item.get("evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                errors.append(f"步骤 {STEP_NUMBER[dependency]} 已通过，但未记录 evidence 路径")
                continue
            evidence_path = (platform_dir / evidence).resolve()
            if not evidence_path.is_file():
                errors.append(
                    f"步骤 {STEP_NUMBER[dependency]} 已通过，但证据文件不存在: {evidence_path}"
                )
            verification = dependency_item.get("verification")
            if isinstance(verification, dict) and verification.get("evidence") != evidence:
                errors.append(f"{dependency} 的 evidence 与 verification.evidence 不一致")
            errors.extend(verification_errors(dependency_item.get("verification"), platform_dir, dependency, platform_config))
            if dependency == "environment":
                try:
                    declared = environment_target(platform_dir)
                    hosts = expected_hosts
                    if hosts is None:
                        runtime = load_yaml(platform_dir / "environment/runtime-config.yml")
                        target = runtime.get("target")
                        hosts = target.get("hosts") if isinstance(target, dict) else None
                    if (not isinstance(hosts, list) or not hosts or
                            not all(isinstance(host, str) for host in hosts) or
                            len(set(hosts)) != len(hosts) or sorted(hosts) != declared):
                        errors.append("environment target.hosts 与本次目标 hosts 不一致；需现场复核，不能跨主机复用环境证据")
                except (ValueError, WorkflowError) as exc:
                    errors.append(str(exc))
            if dependency == "acceptance":
                errors.extend(check_acceptance_dependencies(platform_config, [], platform_dir, require_all=True))
    return errors


def check_acceptance_dependencies(
    platform_config: dict[str, Any], selected_substeps: list[str],
    platform_dir: Path | None = None, *, require_all: bool = False,
) -> list[str]:
    if not selected_substeps and not require_all:
        return []
    workflow = platform_config.get("workflow")
    acceptance = workflow.get("acceptance") if isinstance(workflow, dict) else None
    statuses = acceptance.get("substeps") if isinstance(acceptance, dict) else None
    if not isinstance(statuses, dict):
        raise WorkflowError("platform.yml 缺少 workflow.acceptance.substeps")
    errors: list[str] = []
    selected = set(selected_substeps)
    records = acceptance.get("records", {})
    for substep in (ACCEPTANCE_SUBSTEP_ORDER if require_all else selected_substeps):
        required = ancestors(substep, ACCEPTANCE_DEPENDENCIES)
        if require_all:
            required.add(substep)
        for dependency in sorted(required, key=ACCEPTANCE_SUBSTEP_ORDER.index):
            if dependency in selected:
                continue
            status = statuses.get(dependency)
            if status not in COMPLETE_STATUSES:
                errors.append(
                    f"验收子步骤 {substep} 依赖 {dependency}，"
                    f"但其状态为 {status!r}，且本次未选择该前置子步骤"
                )
            elif platform_dir is not None:
                errors.extend(verification_errors(records.get(dependency), platform_dir, dependency, platform_config))
    return list(dict.fromkeys(errors))


def check_execution_readiness(platform_config: dict, selected_substeps: list[str], platform_dir: Path) -> list[str]:
    """New execution gate only. Evidence/summary/retrospective need no running service."""
    live = set(selected_substeps) & {"execution-mode", "sanity", "accuracy", "performance"}
    if not live:
        return []
    if platform_config.get("record_layout") == "compact":
        # Compact records deliberately keep mutable process observations and
        # executable configuration under the approved remote root. The local
        # gate validates receipts and scope; callers must re-observe the actual
        # process immediately before every live substep.
        return []
    errors = service_state_errors(platform_dir, require_ready=True,
                                  require_graph="execution-mode" not in live)
    if errors:
        return errors
    state = load_yaml(platform_dir / "environment/service-state.yml")
    records = platform_config["workflow"]["acceptance"].get("records", {})
    for stage in live:
        for dependency in ancestors(stage, ACCEPTANCE_DEPENDENCIES) - set(selected_substeps):
            if records.get(dependency, {}).get("service_instance_id") != state["service"]["instance_id"]:
                errors.append(f"{dependency} 未绑定当前 service.instance_id；不能沿用其他服务实例的验收")
    return list(dict.fromkeys(errors))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="初始化指定适配阶段、检查前置条件并生成可粘贴到 Codex 的调用文本。"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help=argparse.SUPPRESS,
    )
    parser.add_argument("model", help="models/ 下的模型目录名")
    parser.add_argument("--platform", choices=PLATFORMS)
    parser.add_argument("--framework", help="显式框架工作区；按 profile 选择流程")
    parser.add_argument("--artifact-root", action="append", default=[], metavar="HOST=PATH",
                        help="只读证据挂载根（或在远端执行时的批准工作根），可重复")
    parser.add_argument("--verify-records", action="store_true", help="验证所选阶段/子步骤已经完成的证据")
    parser.add_argument("--hosts", help="逗号分隔的目标 SSH Host 别名")
    parser.add_argument("--steps", required=True, help="逗号分隔的步骤编号或英文名称")
    parser.add_argument(
        "--acceptance-substeps",
        default="",
        help="逗号分隔: execution-mode,sanity,accuracy,performance,evidence,summary",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="只检查，不创建缺失文件，也不输出 Codex 调用文本",
    )
    parser.add_argument("--evidence-info",
                        help="只输出当前证据的绑定信息，不修改状态；需 --evidence 和 --run-id")
    parser.add_argument("--evidence", help="相对平台目录的已验证证据文件")
    parser.add_argument("--run-id", help="证据中记录的实际运行标识")
    parser.add_argument("--service-instance-id", help="证据中实际运行的服务实例 ID；不从当前服务推断")
    parser.add_argument("--verified-on", default=date.today().isoformat(), help="实际验证日期 YYYY-MM-DD，默认今天；历史绑定必须显式填写")
    parser.add_argument("--deployment-info", action="store_true",
                        help="只校验已记录的 deployment-identity 并输出指纹；不采集或核实远端")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.framework:
        from framework_evidence import check_command
        try:
            return check_command(args)
        except (ValueError, OSError, KeyError, TypeError, AttributeError, StopIteration) as exc:
            raise WorkflowError(str(exc)) from exc
    if args.evidence_info and args.evidence_info not in {*STEP_ORDER, *ACCEPTANCE_SUBSTEP_ORDER}:
        raise WorkflowError("旧入口不支持该证据阶段；框架特有步骤请指定 --framework")
    repo_root = args.repo_root.resolve()
    if not MODEL_NAME_RE.fullmatch(args.model) or args.model in {".", "..", "_template"}:
        raise WorkflowError("模型名只能包含字母、数字、点、下划线和连字符")
    steps = parse_steps(args.steps)
    needs_platform = any(step != "architecture" for step in steps)
    if needs_platform and not args.platform:
        raise WorkflowError("步骤 2 至 5 必须使用 --platform 指定平台")

    requested_substeps = parse_csv(args.acceptance_substeps)
    substeps = [item for item in ACCEPTANCE_SUBSTEP_ORDER if item in set(requested_substeps)]
    unknown_substeps = sorted(set(requested_substeps) - ACCEPTANCE_SUBSTEPS)
    if unknown_substeps:
        raise WorkflowError(f"未知验收子步骤: {', '.join(unknown_substeps)}")
    if substeps and "acceptance" not in steps:
        raise WorkflowError("--acceptance-substeps 只能与步骤 4/acceptance 一起使用")
    requested_hosts = [item.strip() for item in (args.hosts or "").split(",") if item.strip()]

    model_dir = repo_root / "models" / args.model
    if not model_dir.is_dir():
        raise WorkflowError(f"模型目录不存在: {model_dir}；请先运行 ./scripts/new-model {args.model}")
    try:
        model_identity(model_dir)
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    if args.deployment_info:
        if not args.platform or args.evidence_info:
            raise WorkflowError("--deployment-info 需要 --platform，且不能与 --evidence-info 同用")
        try:
            print(json.dumps({"deployment_fingerprint": deployment_fingerprint(model_dir / args.platform)}, indent=2))
        except ValueError as exc:
            raise WorkflowError(str(exc)) from exc
        return 0
    if args.evidence_info:
        if not args.platform or not args.evidence or not args.run_id:
            raise WorkflowError("--evidence-info 需要 --platform、--evidence 和 --run-id")
        platform_dir = model_dir / args.platform
        evidence = (platform_dir / args.evidence).resolve()
        owner = model_dir if args.evidence_info == "architecture" else platform_dir
        if not evidence.is_relative_to(owner.resolve()) or not evidence.is_file() or not evidence.stat().st_size:
            raise WorkflowError("证据必须是当前模型（architecture）或当前平台内的非空文件")
        extra = {}
        if args.evidence_info == "environment" and requested_hosts:
            try:
                if len(set(requested_hosts)) != len(requested_hosts) or sorted(requested_hosts) != environment_target(platform_dir):
                    raise WorkflowError("--hosts 与环境证据的 environment-target.yml 作用域不一致")
            except ValueError as exc:
                raise WorkflowError(str(exc)) from exc
        if args.evidence_info in {"execution-mode", "sanity", "accuracy", "performance"}:
            if not args.service_instance_id or not args.service_instance_id.strip():
                raise WorkflowError("执行证据需要 --service-instance-id 指定证据所属实际实例，不能自动使用当前实例")
            extra["service_instance_id"] = args.service_instance_id
        try:
            if date.fromisoformat(args.verified_on) > date.today():
                raise ValueError("future")
        except ValueError as exc:
            raise WorkflowError("--verified-on 必须为非未来的实际 YYYY-MM-DD 日期") from exc
        print(json.dumps({"run_id": args.run_id, "last_verified": args.verified_on,
                          "evidence": args.evidence, "evidence_sha256": file_sha256(evidence),
                          "context_sha256": context_sha256(platform_dir, args.evidence_info), **extra},
                         ensure_ascii=False, indent=2))
        return 0
    template_dir = repo_root / "templates" / "adaptation"
    created: list[Path] = []
    configuration_warnings: list[str] = []

    if "architecture" in steps:
        destination = model_dir / "architecture-and-inference.md"
        if copy_if_missing(
            template_dir / "architecture-and-inference.md",
            destination,
            check_only=args.check_only,
        ):
            created.append(destination)

    platform_config: dict[str, Any] | None = None
    platform_dir: Path | None = None
    if args.platform:
        platform_dir = model_dir / args.platform
        if not platform_dir.is_dir():
            raise WorkflowError(f"平台目录不存在: {platform_dir}")
        platform_yml = platform_dir / "platform.yml"
        if not platform_yml.is_file():
            raise WorkflowError(f"缺少平台状态文件: {platform_yml}")
        platform_config = load_yaml(platform_yml)
        if platform_config.get("platform") != args.platform:
            raise WorkflowError(f"{platform_yml} 中的平台名与 --platform 不一致")
        config_path = platform_dir / "environment" / "runtime-config.yml"
        configured_hosts: list[str] = []
        if config_path.is_file():
            existing_config = load_yaml(config_path)
            existing_target = existing_config.get("target")
            existing_hosts = existing_target.get("hosts") if isinstance(existing_target, dict) else None
            if isinstance(existing_hosts, list) and all(isinstance(item, str) for item in existing_hosts):
                configured_hosts = existing_hosts
        elif platform_config.get("record_layout") == "compact":
            compact_target = platform_config.get("target")
            compact_hosts = compact_target.get("hosts") if isinstance(compact_target, dict) else None
            if isinstance(compact_hosts, list) and all(isinstance(item, str) for item in compact_hosts):
                configured_hosts = compact_hosts
        if len(requested_hosts) != len(set(requested_hosts)):
            raise WorkflowError("--hosts 不得包含重复别名")
        if requested_hosts and configured_hosts and set(requested_hosts) != set(configured_hosts):
            raise WorkflowError(
                "--hosts 与 environment/runtime-config.yml 的 target.hosts 不一致；"
                "请先核实目标，工具不会自动覆盖已有配置"
            )
        effective_hosts = requested_hosts or configured_hosts
        if needs_platform and not effective_hosts:
            raise WorkflowError(
                "步骤 2 至 5 必须使用 --hosts 指定目标，"
                "或在 environment/runtime-config.yml 中已有 target.hosts"
            )
        unknown_hosts = sorted(set(effective_hosts) - inventory_platform_hosts(repo_root, args.platform))
        if unknown_hosts:
            raise WorkflowError(
                f"以下别名不属于 inventory {args.platform} 组: {', '.join(unknown_hosts)}"
            )
        template_platform = load_yaml(
            repo_root / "models" / "_template" / args.platform / "platform.yml"
        )
        workflow_defaults = template_platform.get("workflow")
        if not isinstance(workflow_defaults, dict):
            raise WorkflowError("平台模板缺少 workflow 状态定义")
        if "workflow" not in platform_config:
            if args.check_only:
                raise WorkflowError(f"{platform_yml} 缺少 workflow；请先使用非 check-only 模式升级")
            platform_config["workflow"] = copy.deepcopy(workflow_defaults)
            write_yaml(platform_yml, platform_config)
            created.append(platform_yml)
        elif not isinstance(platform_config["workflow"], dict):
            raise WorkflowError(f"{platform_yml} 的 workflow 必须是映射")
        elif merge_missing(platform_config["workflow"], workflow_defaults):
            if args.check_only:
                raise WorkflowError(f"{platform_yml} 的 workflow schema 需要升级")
            write_yaml(platform_yml, platform_config)
            created.append(platform_yml)
        schema_errors = platform_schema_errors(platform_config, args.platform,
                                               inventory_platform_hosts(repo_root, args.platform))
        if schema_errors:
            raise WorkflowError("\n".join(schema_errors))
        dependency_errors = check_dependencies(platform_config, steps, platform_dir, expected_hosts=effective_hosts)
        if "acceptance" in steps:
            dependency_errors.extend(check_acceptance_dependencies(platform_config, substeps, platform_dir))
        if dependency_errors:
            raise WorkflowError("\n".join(dependency_errors))

        compact_layout = platform_config.get("record_layout") == "compact"
        stage_templates = {
            "environment": (
                ("environment-analysis.md", "environment/environment-analysis.md"),
            ),
            "adaptation": (
                ("platform-adaptation-plan.md", "environment/platform-adaptation-plan.md"),
                ("plugin-change-review.md", "environment/plugin-change-review.md"),
                ("issue-index.md", "adaptation/README.md"),
            ),
            "acceptance": (
                ("acceptance-plan.md", "acceptance/acceptance-plan.md"),
            ),
            "retrospective": (
                ("adaptation-retrospective.md", "acceptance/adaptation-retrospective.md"),
            ),
        }
        if not compact_layout:
            stage_templates["adaptation"] = (
                *stage_templates["adaptation"][:2],
                ("service-state.yml", "environment/service-state.yml"),
                ("deployment-identity.yml", "environment/deployment-identity.yml"),
                stage_templates["adaptation"][-1],
            )
        for step in steps:
            for source_name, relative_destination in stage_templates.get(step, ()):
                destination = platform_dir / relative_destination
                if source_name in {"service-state.yml", "deployment-identity.yml"}:
                    was_created = prepare_identified_yaml(
                        template_dir / source_name,
                        destination,
                        args.model,
                        args.platform,
                        args.check_only,
                    )
                else:
                    was_created = copy_if_missing(
                        template_dir / source_name,
                        destination,
                        check_only=args.check_only,
                    )
                if was_created:
                    created.append(destination)
        if "acceptance" in steps and (not substeps or "summary" in substeps):
            destination = platform_dir / "acceptance" / "adaptation-summary.md"
            if copy_if_missing(
                template_dir / "adaptation-summary.md",
                destination,
                check_only=args.check_only,
            ):
                created.append(destination)
        if "environment" in steps and not compact_layout:
            target_path = platform_dir / "environment/environment-target.yml"
            if prepare_config(template_dir / "environment-target.yml", target_path,
                              args.model, args.platform, effective_hosts, args.check_only):
                created.append(target_path)
            try:
                if environment_target(platform_dir) != sorted(effective_hosts):
                    raise WorkflowError("environment-target.yml 的 target.hosts 与本次目标不一致；不自动覆盖已有作用域")
            except ValueError as exc:
                raise WorkflowError(str(exc)) from exc
        if ("adaptation" in steps or "acceptance" in steps) and not compact_layout:
            if prepare_config(
                template_dir / "runtime-config.yml",
                config_path,
                args.model,
                args.platform,
                effective_hosts,
                args.check_only,
            ):
                created.append(config_path)
        if ("adaptation" in steps or "acceptance" in steps) and not compact_layout:
            config_errors = validate_adaptation_config(
                config_path,
                args.model,
                args.platform,
                repo_root,
                (
                    substeps or list(ACCEPTANCE_SUBSTEP_ORDER)
                    if "acceptance" in steps
                    else None
                ),
            )
            if config_errors:
                formatted = "\n".join(f"- {item}" for item in config_errors)
                if args.check_only:
                    raise WorkflowError(f"适配配置尚未就绪: {config_path}\n{formatted}")
                configuration_warnings = config_errors
        if "acceptance" in steps and "adaptation" not in steps:
            readiness_errors = check_execution_readiness(
                platform_config, substeps or list(ACCEPTANCE_SUBSTEP_ORDER), platform_dir)
            if readiness_errors and args.check_only:
                raise WorkflowError("执行现场尚未就绪（不改变历史结果）:\n" + "\n".join(readiness_errors))
            configuration_warnings.extend(readiness_errors)

    if args.check_only:
        print("检查通过：所选步骤的目录、前置状态和配置均有效。")
        print("仅完成本地结构和前置检查；不代表远端工作目录/挂载已核实，不自动授权远端写入。")
        return 0

    if created:
        print("已创建缺失的阶段文件：")
        for path in created:
            print(f"- {path.relative_to(repo_root)}")
    else:
        print("阶段文件已存在，未覆盖任何文件。")

    if configuration_warnings:
        print("\n适配配置仍需完善；执行任何远程变更前必须解决：")
        for warning in configuration_warnings:
            print(f"- {warning}")

    step_text = "、".join(f"{STEP_NUMBER[step]}（{STEP_LABEL[step]}）" for step in steps)
    print("\n将下面的内容发送给 Codex：\n")
    print(f"模型：{args.model}")
    if args.platform:
        print(f"平台：{args.platform}")
        print(f"目标机器：{','.join(effective_hosts)}")
        if needs_platform:
            workspace_config = load_yaml(config_path) if config_path.is_file() else {}
            root_errors = workspace_errors(workspace_config)
            if root_errors:
                print("远端写入边界：工作目录尚未完整配置；停止远端新增/写入，先让用户明确每台主机的 host_root 和 container_root，不自动猜测或创建")
            else:
                print("远端新增内容归属（仅声明范围，不是 chroot 或任意子进程写入隔离）：")
                for item in workspace_config["workspace"]["roots"]:
                    print(f"- {item['host_alias']}: host_root={item['host_root']}; "
                          f"container={workspace_config['target']['container_name']}; container_root={item['container_root']}")
    print(f"执行步骤：{step_text}")
    if substeps:
        print(f"验收子步骤：{','.join(substeps)}")
    if "acceptance" in steps:
        print("验收衔接：同次选择只表示执行计划；每一子步骤执行前，单独用该子步骤 --check-only 复核新证据和当前服务")
    if "adaptation" in steps:
        print("代码交付要求：遵守 docs/plugin-contribution-policy.md，维护 environment/plugin-change-review.md，审查多模型/多平台影响和最终 PR diff")
    if "adaptation" in steps or "acceptance" in steps:
        print("执行前核实：确认目标 Host、工作根目录、容器映射、服务身份和阶段证据；后台任务由实际 worker 持有生命周期并写入独立 run 目录")
    print("执行边界：只执行指定步骤；其他步骤只检查前置产物，不自动执行")
    if configuration_warnings:
        print(
            "前置要求：先完善并重新校验 environment/runtime-config.yml，"
            "再执行任何远程变更"
        )
    print("完成条件：完成全部指定步骤后停止，并更新相应阶段证据和 platform.yml 状态")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WorkflowError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2)
