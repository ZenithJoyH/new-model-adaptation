#!/usr/bin/env python3
"""Framework-profile and per-model framework-workspace validation helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


FRAMEWORK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MUTATION_POLICIES = {
    "read_only",
    "editable_product_code",
    "authorized_sync_and_reproducer_only",
}
WORKSPACE_SECTIONS = ("environment", "adaptation", "acceptance")
WORKFLOW_PHASES = ("architecture", "environment", "adaptation", "acceptance", "retrospective")
WORKFLOW_STATUSES = {"not_started", "in_progress", "blocked", "failed", "passed", "complete"}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"无法读取 YAML {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"YAML 顶层必须是映射: {path}")
    return value


def profile_errors(profile: Any, expected_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(profile, dict):
        return ["profile 必须是映射"]
    if profile.get("schema_version") != 1:
        errors.append("schema_version 必须为 1")
    profile_id = profile.get("id")
    if not isinstance(profile_id, str) or not FRAMEWORK_ID_RE.fullmatch(profile_id):
        errors.append("id 必须是小写 framework ID")
    elif expected_id is not None and profile_id != expected_id:
        errors.append(f"id 必须为 {expected_id!r}")
    if type(profile.get("profile_version")) is not int or profile["profile_version"] < 1:
        errors.append("profile_version 必须是正整数")
    if profile.get("status") not in {"draft", "experimental", "active", "deprecated"}:
        errors.append("status 必须为 draft、experimental、active 或 deprecated")
    platforms = profile.get("platforms")
    if (not isinstance(platforms, list) or not platforms or
            not all(isinstance(p, str) and p in {"nvidia", "ppu", "metax", "ascend", "mthreads", "hygon"} for p in platforms)):
        errors.append("platforms 必须声明受支持平台")

    components = profile.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components 必须是非空列表")
    else:
        roles: set[str] = set()
        for index, component in enumerate(components):
            if not isinstance(component, dict):
                errors.append(f"components[{index}] 必须是映射")
                continue
            role = component.get("role")
            name = component.get("name")
            policy = component.get("mutation_policy")
            if not isinstance(role, str) or not role.strip():
                errors.append(f"components[{index}].role 不能为空")
            elif role in roles:
                errors.append(f"组件 role 重复: {role}")
            else:
                roles.add(role)
            if not isinstance(name, str) or not name.strip():
                errors.append(f"components[{index}].name 不能为空")
            if policy not in MUTATION_POLICIES:
                errors.append(f"components[{index}].mutation_policy 非法: {policy}")

        source_policy = profile.get("source_policy")
        if not isinstance(source_policy, dict):
            errors.append("source_policy 必须是映射")
        else:
            writable = source_policy.get("writable_roles")
            if not isinstance(writable, list) or not all(isinstance(item, str) for item in writable):
                errors.append("source_policy.writable_roles 必须是字符串列表")
            elif not set(writable).issubset(roles):
                errors.append("source_policy.writable_roles 包含未声明组件 role")
            else:
                editable = {c.get("role") for c in components if isinstance(c, dict)
                            and c.get("mutation_policy") == "editable_product_code"}
                if set(writable) != editable:
                    errors.append("writable_roles 必须与 editable_product_code 组件完全一致")
            if source_policy.get("default") != "read_only":
                errors.append("source_policy.default 必须为 read_only")

    modes = profile.get("execution_modes")
    if not isinstance(modes, dict):
        errors.append("execution_modes 必须是映射")
    else:
        required = modes.get("required")
        primary = modes.get("acceptance_primary")
        if not isinstance(required, list) or not required or not all(isinstance(item, str) and item for item in required):
            errors.append("execution_modes.required 必须是非空字符串列表")
        elif primary not in required:
            errors.append("execution_modes.acceptance_primary 必须属于 required")

    service = profile.get("service")
    if (not isinstance(service, dict) or not isinstance(service.get("protocols"), list)
            or not service["protocols"] or not all(isinstance(p, str) and p for p in service["protocols"])):
        errors.append("service.protocols 必须声明服务或 Python API 协议")
    acceptance = profile.get("acceptance")
    if not isinstance(acceptance, dict):
        errors.append("acceptance 必须声明框架自己的验收流程")
    else:
        steps = acceptance.get("steps")
        if not isinstance(steps, dict) or not steps:
            errors.append("acceptance.steps 必须是有序非空映射")
        else:
            for name, spec in steps.items():
                if not isinstance(name, str) or not FRAMEWORK_ID_RE.fullmatch(name) or not isinstance(spec, dict):
                    errors.append("非法 acceptance step")
                    continue
                if name in WORKFLOW_PHASES:
                    errors.append(f"{name}: 验收步骤不得与五阶段重名")
                if type(spec.get("optional", False)) is not bool:
                    errors.append(f"{name}: optional 必须是布尔值")
                if spec.get("validator") not in {"checks", "flageval", "vllm-performance"}:
                    errors.append(f"{name}: 未实现的 validator")
                checks = spec.get("checks")
                if not isinstance(checks, list) or not checks or not all(isinstance(c, str) and c for c in checks):
                    errors.append(f"{name}: checks 必须非空")
        for field in ("accuracy_adapter", "performance_adapter"):
            value = acceptance.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip() or value.startswith("pending")):
                errors.append(f"acceptance.{field} 必须为已实现入口或 null")
        for field, supported in (("accuracy_adapter", "flageval-openai"), ("performance_adapter", "vllm-bench-serve")):
            if acceptance.get(field) not in (None, supported):
                errors.append(f"{field}: adapter 尚未实现，不能声明可用")
        cache = acceptance.get("prefix_caching")
        if not isinstance(cache, dict) or cache.get("performance") not in {"disabled", "not_applicable", "unavailable"}:
            errors.append("必须声明前缀缓存适用性")
        elif cache["performance"] == "disabled" and not cache.get("disable_mechanism"):
            errors.append("性能缓存关闭机制不能为空")
        if profile.get("status") == "active" and (not acceptance.get("accuracy_adapter") or not acceptance.get("performance_adapter")):
            errors.append("active profile 必须具备正式精度和性能入口")
        if isinstance(steps, dict):
            for name, adapter, validator in (("accuracy", "accuracy_adapter", "flageval"),
                                               ("performance", "performance_adapter", "vllm-performance")):
                if acceptance.get(adapter) and (not isinstance(steps.get(name), dict) or steps[name].get("validator") != validator):
                    errors.append(f"{adapter} 与已实现 step validator 不一致")
    documents = profile.get("documents")
    if not isinstance(documents, dict):
        errors.append("documents 必须是映射")
    else:
        for name in ("workflow", "acceptance"):
            value = documents.get(name)
            if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
                errors.append(f"documents.{name} 必须是 profile 内相对路径")
        for name, value in documents.items():
            if not isinstance(value, str) or not value or Path(value).is_absolute() or ".." in Path(value).parts:
                errors.append(f"documents.{name} 必须是 profile 内相对路径")
    return errors


def workspace_errors(config: Any, *, model: str, platform: str, framework: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["framework.yml 必须是映射"]
    expected = {
        "schema_version": 1,
        "model": model,
        "platform": platform,
        "framework": framework,
    }
    for field, value in expected.items():
        if config.get(field) != value:
            errors.append(f"{field} 必须为 {value!r}")
    profile = config.get("profile")
    expected_profile = f"framework-profiles/{framework}/profile.yml"
    if profile != expected_profile:
        errors.append(f"profile 必须为 {expected_profile!r}")
    if type(config.get("profile_version")) is not int or config["profile_version"] < 1:
        errors.append("profile_version 必须是正整数")
    if config.get("status") not in {
        "not_started", "environment_ready", "model_loading", "functional", "optimized", "blocked"
    }:
        errors.append("status 非法")
    workflow = config.get("workflow")
    if not isinstance(workflow, dict):
        return errors + ["workflow 必须是映射"]
    if tuple(workflow) != WORKFLOW_PHASES:
        errors.append("workflow 必须按五阶段顺序完整声明")
    for phase in WORKFLOW_PHASES:
        item = workflow.get(phase)
        if not isinstance(item, dict):
            errors.append(f"workflow.{phase} 必须是映射")
        elif item.get("status") not in WORKFLOW_STATUSES:
            errors.append(f"workflow.{phase}.status 非法")
    return errors


def resolved_profile(root: Path, framework: str) -> tuple[Path, dict[str, Any]]:
    if not FRAMEWORK_ID_RE.fullmatch(framework):
        raise ValueError("framework ID 只能使用小写字母、数字、点、下划线和连字符")
    path = root / "framework-profiles" / framework / "profile.yml"
    if not path.is_file():
        raise ValueError(f"framework profile 不存在: {path}")
    profile = load_yaml(path)
    errors = profile_errors(profile, framework)
    if errors:
        raise ValueError(f"framework profile 无效: {path}\n" + "\n".join(errors))
    if profile.get("status") not in {"active", "experimental"}:
        raise ValueError(f"framework profile 尚不可用于新适配: {path} (status={profile.get('status')})")
    for name, relative in profile["documents"].items():
        if not (path.parent / relative).is_file():
            raise ValueError(f"framework profile 缺少 documents.{name}: {relative}")
    return path, profile
