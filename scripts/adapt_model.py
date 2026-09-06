#!/usr/bin/env python3
"""Prepare and validate selected model-adaptation workflow stages."""

from __future__ import annotations

import argparse
import copy
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml


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
VALID_STATUSES = {"not_started", "in_progress", "blocked", "passed", "complete"}
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
SECRET_KEY_PARTS = ("password", "passwd", "token", "secret", "private_key", "identity_file")
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


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
            if any(part in key_text for part in SECRET_KEY_PARTS):
                raise WorkflowError(
                    f"配置中禁止出现敏感连接字段 {child_path}；请使用 ~/.ssh/config 或密钥管理"
                )
            reject_secret_keys(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            reject_secret_keys(child, f"{path}[{index}]")


def require_mapping(config: dict[str, Any], key: str, source: Path) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise WorkflowError(f"{source} 缺少映射字段: {key}")
    return value


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
        if not isinstance(service.get(field), int) or service[field] <= 0:
            errors.append(f"service.{field} 必须是正整数")
    gpu_utilization = service.get("gpu_memory_utilization")
    if not isinstance(gpu_utilization, (int, float)) or not 0 < gpu_utilization <= 1:
        errors.append("service.gpu_memory_utilization 必须大于 0 且不超过 1")

    max_len = service.get("max_model_len")
    if not isinstance(max_len, dict):
        errors.append("service.max_model_len 必须是映射")
    else:
        supported = max_len.get("model_supported")
        initial = max_len.get("initial")
        evidence = max_len.get("evidence")
        if not isinstance(supported, int) or supported <= 0:
            errors.append("service.max_model_len.model_supported 必须是正整数")
        if not isinstance(initial, int) or initial <= 0:
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
        elif any(
            sensitive in arg.lower()
            for arg in extra_args
            for sensitive in ("password", "token", "secret", "private-key", "identity-file")
        ):
            errors.append(f"execution_modes.{mode}.extra_args 不得包含敏感参数")
        if mode == "graph" and isinstance(extra_args, list) and "--enforce-eager" in extra_args:
            errors.append("execution_modes.graph.extra_args 不得包含 --enforce-eager")

    acceptance = require_mapping(config, "acceptance", path)
    if acceptance.get("sanity_concurrency") != 8:
        errors.append("acceptance.sanity_concurrency 必须为 8")
    if acceptance.get("accuracy_runner") != "test/Accuracy_test/llmrun.py":
        errors.append("acceptance.accuracy_runner 必须为 test/Accuracy_test/llmrun.py")
    if acceptance.get("performance_directory") != "test/perf_test":
        errors.append("acceptance.performance_directory 必须为 test/perf_test")
    selected_acceptance = set(acceptance_substeps or ())
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
    platform_config: dict[str, Any], selected: list[str], platform_dir: Path
) -> list[str]:
    errors: list[str] = []
    selected_set = set(selected)
    for step in selected:
        for dependency in DEPENDENCIES[step]:
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
    return errors


def check_acceptance_dependencies(
    platform_config: dict[str, Any], selected_substeps: list[str]
) -> list[str]:
    if not selected_substeps:
        return []
    workflow = platform_config.get("workflow")
    acceptance = workflow.get("acceptance") if isinstance(workflow, dict) else None
    statuses = acceptance.get("substeps") if isinstance(acceptance, dict) else None
    if not isinstance(statuses, dict):
        raise WorkflowError("platform.yml 缺少 workflow.acceptance.substeps")
    errors: list[str] = []
    selected = set(selected_substeps)
    for substep in selected_substeps:
        for dependency in ACCEPTANCE_DEPENDENCIES[substep]:
            if dependency in selected:
                continue
            status = statuses.get(dependency)
            if status not in COMPLETE_STATUSES:
                errors.append(
                    f"验收子步骤 {substep} 依赖 {dependency}，"
                    f"但其状态为 {status!r}，且本次未选择该前置子步骤"
                )
    return errors


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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    if not MODEL_NAME_RE.fullmatch(args.model):
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
        dependency_errors = check_dependencies(platform_config, steps, platform_dir)
        if "acceptance" in steps:
            dependency_errors.extend(check_acceptance_dependencies(platform_config, substeps))
        if dependency_errors:
            raise WorkflowError("\n".join(dependency_errors))

        stage_templates = {
            "environment": (
                ("environment-analysis.md", "environment/environment-analysis.md"),
            ),
            "adaptation": (
                ("platform-adaptation-plan.md", "environment/platform-adaptation-plan.md"),
                ("service-state.yml", "environment/service-state.yml"),
                ("issue-index.md", "adaptation/README.md"),
            ),
            "acceptance": (
                ("acceptance-plan.md", "acceptance/acceptance-plan.md"),
            ),
            "retrospective": (
                ("adaptation-retrospective.md", "acceptance/adaptation-retrospective.md"),
            ),
        }
        for step in steps:
            for source_name, relative_destination in stage_templates.get(step, ()):
                destination = platform_dir / relative_destination
                if source_name == "service-state.yml":
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
        if "adaptation" in steps or "acceptance" in steps:
            if prepare_config(
                template_dir / "runtime-config.yml",
                config_path,
                args.model,
                args.platform,
                effective_hosts,
                args.check_only,
            ):
                created.append(config_path)
        if "adaptation" in steps or "acceptance" in steps:
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

    if args.check_only:
        print("检查通过：所选步骤的目录、前置状态和配置均有效。")
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
    print(f"执行步骤：{step_text}")
    if substeps:
        print(f"验收子步骤：{','.join(substeps)}")
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
