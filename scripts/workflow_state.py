"""Recorded deployment identity and observed service checks; never contact a host.

Desired runtime, immutable code identity and mutable observations are deliberately
separate. A stopped service cannot invalidate an otherwise valid historical run.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

import yaml


def read_mapping(path):
    try:
        value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"无法读取 {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} 必须为映射")
    return value


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def is_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def model_identity(model_dir):
    """A copied metadata file cannot identify a different model directory."""
    metadata = read_mapping(model_dir / "model.yml")
    if metadata.get("name") != model_dir.name:
        raise ValueError(f"{model_dir / 'model.yml'}: name 必须与模型目录 {model_dir.name!r} 一致")
    # source.revision may be a branch/tag or a documented local snapshot, while
    # deployment.model_revision is resolved identity; do not compare them as aliases.
    return metadata


def environment_target(platform_dir):
    """Declared host scope, separate from later mutable inference settings.

    Compact platform records keep this small declaration in ``platform.yml``.
    The legacy environment-target file remains readable for historical records,
    but is no longer required for a compact directory.
    """
    path = platform_dir / "environment/environment-target.yml"
    if path.is_file():
        target = read_mapping(path)
        if type(target.get("schema_version")) is not int or target["schema_version"] != 1:
            raise ValueError(f"{path}: schema_version 必须为 1")
        if target.get("model") != platform_dir.parent.name or target.get("platform") != platform_dir.name:
            raise ValueError(f"{path}: model/platform 与当前目录不一致")
        scope = target.get("target")
        source = path
    else:
        platform_path = platform_dir / "platform.yml"
        target = read_mapping(platform_path)
        if target.get("record_layout") != "compact":
            raise ValueError(
                f"{path}: 缺少旧版作用域文件，且 {platform_path} 未声明 "
                "record_layout: compact"
            )
        if target.get("platform") != platform_dir.name:
            raise ValueError(f"{platform_path}: platform 与当前目录不一致")
        scope = target.get("target")
        source = platform_path
    hosts = scope.get("hosts") if isinstance(scope, dict) else None
    if (not isinstance(hosts, list) or not hosts or
            not all(isinstance(host, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", host) for host in hosts) or
            len(set(hosts)) != len(hosts)):
        raise ValueError(f"{source}: target.hosts 必须是具体、无重复的 SSH Host 别名列表")
    return sorted(hosts)


def deployment_fingerprint(platform_dir):
    """Canonical fingerprint excludes observation dates and narrative annotations."""
    model_identity(platform_dir.parent)
    path = platform_dir / "environment/deployment-identity.yml"
    identity = read_mapping(path)
    runtime = read_mapping(platform_dir / "environment/runtime-config.yml")
    runtime_stack = runtime.get("stack")
    if not isinstance(runtime_stack, dict):
        raise ValueError("runtime-config.stack 必须为映射")
    errors = []
    expected = {"schema_version": 1, "model": platform_dir.parent.name, "platform": platform_dir.name}
    for field, value in expected.items():
        if identity.get(field) != value:
            errors.append(f"{field} 应为 {value!r}")
    for field in ("model_revision", "container_image_digest"):
        if not isinstance(identity.get(field), str) or not identity[field].strip():
            errors.append(f"{field} 不能为空")
    image = identity.get("container_image_digest", "")
    if not isinstance(image, str) or not image.startswith("sha256:") or not is_digest(image[7:]):
        errors.append("container_image_digest 必须是实际镜像 sha256 digest，不是可变 tag")
    if identity.get("runtime_config_sha256") != sha256_file(platform_dir / "environment/runtime-config.yml"):
        errors.append("runtime_config_sha256 与当前 runtime-config.yml 不一致")
    components = identity.get("stack")
    canonical_stack = {}
    if not isinstance(components, dict):
        errors.append("stack 必须为映射")
        components = {}
    for name in ("vllm", "plugin", "flaggems"):
        component = components.get(name)
        if not isinstance(component, dict):
            errors.append(f"stack.{name} 缺失")
            continue
        revision = component.get("revision")
        runtime_component = runtime_stack.get(name)
        declared = runtime_component.get("revision") if isinstance(runtime_component, dict) else None
        if declared != revision:
            errors.append(f"stack.{name}.revision 与 runtime-config.yml 不一致")
        kind = component.get("source_kind", "git")
        if kind == "git":
            if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", revision):
                errors.append(f"stack.{name}.revision 必须为完整 Git HEAD")
            fields = ("tracked_diff_sha256", "untracked_files_sha256")
            canonical_stack[name] = {"source_kind": kind, "revision": revision}
        elif kind == "installed_distribution":
            # Wheels/source installs may not contain Git metadata. Hash the code
            # actually installed, not merely a wheel that could have been patched.
            fields = ("installed_files_sha256",)
            for field in ("package", "revision", "import_path"):
                if not isinstance(component.get(field), str) or not component[field].strip():
                    errors.append(f"stack.{name}.{field} 不能为空")
            if not isinstance(runtime_component, dict) or component.get("import_path") != runtime_component.get("path"):
                errors.append(f"stack.{name}.import_path 与 runtime-config.path 不一致")
            canonical_stack[name] = {key: component.get(key) for key in ("package", "revision", "import_path")}
            canonical_stack[name]["source_kind"] = kind
        else:
            errors.append(f"stack.{name}.source_kind 仅支持 git 或 installed_distribution")
            continue
        for field in fields:
            if not is_digest(component.get(field)):
                errors.append(f"stack.{name}.{field} 必须记录 SHA-256；干净树也不能省略")
            canonical_stack[name][field] = component.get(field)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    canonical = {**expected, "stack": canonical_stack,
                 **{key: identity[key] for key in ("model_revision", "container_image_digest", "runtime_config_sha256")}}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


def service_state_errors(platform_dir, *, require_ready=False, require_graph=False,
                         now=None, max_age=timedelta(hours=24)):
    """Validate observations for a *new* execution, not historical acceptance.

    Freshness is only a local stale-record guard, never an assertion of liveness.
    Re-observe the actual process immediately before sending remote work.
    """
    path = platform_dir / "environment/service-state.yml"
    try:
        state = read_mapping(path)
        runtime = read_mapping(platform_dir / "environment/runtime-config.yml")
    except ValueError as exc:
        return [str(exc)]
    if state.get("schema_version") != 2:
        return [f"{path}: service-state schema 需要现场复核后迁移为 2；不自动推断历史字段"]
    errors = []
    for field, expected in (("model", platform_dir.parent.name), ("platform", platform_dir.name)):
        if state.get(field) != expected:
            errors.append(f"service-state.{field} 与当前目录不一致")
    target = runtime.get("target", {})
    if not isinstance(target, dict) or not isinstance(target.get("hosts"), list):
        return errors + ["runtime-config.target.hosts 必须为列表"]
    if state.get("host") not in target.get("hosts", []):
        errors.append("service-state.host 不属于 runtime target.hosts")
    if not state.get("container_name") or state.get("container_name") != target.get("container_name"):
        errors.append("service-state.container_name 与 runtime target 不一致")
    service = state.get("service")
    if not isinstance(service, dict):
        return errors + ["service-state.service 必须为映射"]
    for field, allowed in (("status", {"unknown", "starting", "ready", "failed", "stopped"}),
                           ("mode", {"unknown", "eager", "graph"}),
                           ("readiness_result", {"unknown", "passed", "failed"})):
        value = service.get(field)
        if not isinstance(value, str) or value not in allowed:
            errors.append(f"service-state.service.{field} 非法: {value!r}")
    if not isinstance(state.get("lifecycle_history"), list):
        errors.append("service-state.lifecycle_history 必须为列表")
    if not require_ready:
        return errors
    if service.get("status") != "ready" or service.get("readiness_result") != "passed":
        errors.append("新验收执行要求 service.status=ready 且 readiness_result=passed")
    if require_graph and service.get("mode") != "graph":
        errors.append("sanity/accuracy/performance 要求实际服务为 graph，不能以期望配置代替")
    if type(service.get("pid")) is not int or service["pid"] <= 0:
        errors.append("service-state.service.pid 必须为实际正整数 PID")
    desired_service = runtime.get("service")
    desired_port = desired_service.get("port") if isinstance(desired_service, dict) else None
    if type(service.get("port")) is not int or service["port"] != desired_port:
        errors.append("service-state.service.port 与 runtime 不一致")
    for field in ("instance_id", "command_record"):
        if not isinstance(service.get(field), str) or not service[field].strip():
            errors.append(f"service-state.service.{field} 不能为空")
    now = now or datetime.now(timezone.utc)
    parsed = {}
    for field in ("started_at", "readiness_checked_at"):
        try:
            stamp = datetime.fromisoformat(service[field])
            if stamp.tzinfo is None or stamp > now:
                raise ValueError("missing timezone or future")
            parsed[field] = stamp
            if field == "readiness_checked_at" and now - stamp > max_age:
                errors.append("service readiness 记录超过 24 小时；执行前需要重新观察")
        except (ValueError, TypeError, KeyError):
            errors.append(f"service-state.service.{field} 必须为带时区且非未来的 ISO 时间")
    if len(parsed) == 2 and parsed["started_at"] > parsed["readiness_checked_at"]:
        errors.append("readiness_checked_at 不能早于当前实例 started_at")
    try:
        if service.get("deployment_fingerprint") != deployment_fingerprint(platform_dir):
            errors.append("服务加载的 deployment_fingerprint 与当前记录不一致，需核实已加载代码")
    except ValueError as exc:
        errors.append(str(exc))
    return errors
