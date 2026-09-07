#!/usr/bin/env python3
"""Read-only audit of curated adaptation records; never probes remote hosts."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote

import adapt_model as workflow
from workflow_state import model_identity


def audit(root):
    findings = []

    def add(level, path, message):
        findings.append({"level": level, "path": str(path.relative_to(root)), "message": message})

    for model in sorted((root / "models").iterdir()):
        if not model.is_dir() or model.name.startswith("_"):
            continue
        try:
            model_identity(model)
        except ValueError as exc:
            add("error", model / "model.yml", str(exc))
        shared_dir = model / "_shared"
        if shared_dir.exists():
            for item in shared_dir.rglob("*"):
                if item.is_dir():
                    add("warning", item, "_shared 不允许过程材料子目录；需按新标准迁移")
                elif item.suffix.lower() != ".md":
                    add("warning", item, "_shared 仅允许 Markdown 跨平台分析；需按新标准迁移")
        for platform in workflow.PLATFORMS:
            directory = model / platform
            if not directory.exists():
                continue
            for item in directory.iterdir():
                if item.name not in {"README.md", "platform.yml", "environment", "adaptation", "acceptance"}:
                    add("error", item, "平台根目录存在未归属的材料")
            for section, label in (("environment", "environment"), ("acceptance", "acceptance")):
                section_dir = directory / section
                if not section_dir.exists():
                    continue
                for item in section_dir.rglob("*"):
                    if item.is_dir():
                        add("warning", item, f"{label} 不允许过程材料子目录；需按新标准迁移")
                    elif item.suffix.lower() != ".md":
                        add("warning", item, f"{label} 仅允许 Markdown 分析或验收文档；需按新标准迁移")
            numbers = set()
            for item in (directory / "adaptation").rglob("*"):
                if item.is_dir():
                    add("error", item, "adaptation 不允许过程材料子目录")
                if item.is_file() and re.match(r"^[0-9]{3}-", item.name):
                    number = item.name[:3]
                    if number in numbers:
                        add("error", item, f"问题编号重复: {number}")
                    numbers.add(number)
                if item.is_file() and (item.parent != directory / "adaptation" or
                    not re.fullmatch(r"(?:README|[0-9]{3}-[A-Za-z0-9._-]+)\.md", item.name)):
                    add("error", item, "adaptation 仅允许 README.md 和 NNN-title.md 问题记录")
            path = directory / "platform.yml"
            try:
                cfg = workflow.load_yaml(path)
                inventory_path = root / "inventory/hosts.yml"
                allowed = workflow.inventory_platform_hosts(root, platform) if inventory_path.is_file() else None
                schema_errors = workflow.platform_schema_errors(cfg, platform, allowed)
                for error in schema_errors:
                    add("error", path, error)
                if schema_errors:
                    continue
                phases = cfg.get("workflow", {})
                for stage in workflow.STEP_ORDER:
                    status = workflow.workflow_status(cfg, stage)
                    if status == "not_started":
                        continue
                    item = phases[stage]
                    if status in workflow.COMPLETE_STATUSES:
                        for error in workflow.verification_errors(item.get("verification"), directory, stage, cfg):
                            if (stage == "environment" and "environment-target.yml" in error
                                    and not (directory / "environment/environment-target.yml").exists()):
                                # Compact-layout environment scope is recorded in the
                                # Markdown analysis; do not demand the retired local YAML.
                                continue
                            add("warning", path, error)
                        evidence = item.get("evidence", "")
                        if not evidence or not (directory / evidence).is_file():
                            add("error", path, f"{stage} 已通过但证据文件缺失: {evidence}")
                    if status in workflow.COMPLETE_STATUSES | {"in_progress"}:
                        for dependency in workflow.ancestors(stage, workflow.DEPENDENCIES):
                            if workflow.workflow_status(cfg, dependency) not in workflow.COMPLETE_STATUSES:
                                add("warning", path, f"{stage} 已开始，但前置 {dependency} 尚未通过；需复核状态")
                acceptance = phases.get("acceptance", {})
                records = acceptance.get("records", {})
                for name, status in acceptance.get("substeps", {}).items():
                    if name not in workflow.ACCEPTANCE_SUBSTEPS or status not in workflow.VALID_STATUSES:
                        add("error", path, f"非法验收子步骤或状态: {name}={status}")
                    elif status in workflow.COMPLETE_STATUSES:
                        for error in workflow.verification_errors(records.get(name), directory, name, cfg):
                            add("warning", path, error)
                        for error in workflow.check_acceptance_dependencies(cfg, [name], directory):
                            add("warning", path, error)
            except (workflow.WorkflowError, TypeError, AttributeError) as exc:
                add("error", path, str(exc))
    docs = [root / "README.md", root / "AGENTS.md", root / "AGENTS.zh-CN.md"]
    docs += list((root / "docs").rglob("*.md")) + list((root / "models").rglob("*.md"))
    docs += list((root / "test").rglob("README.md"))
    for path in docs:
        if not path.is_file() or "_template" in path.parts:
            continue
        content = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        for link in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", content):
            target = unquote(link.split("#", 1)[0].strip("<>"))
            if not target or re.match(r"[a-zA-Z][\w+.-]*:", target) or target.startswith("/") or "<" in target:
                continue
            resolved = (path.parent / target).resolve()
            # Local history is an intentionally untracked artifact store, not a clone prerequisite.
            if resolved.is_relative_to(root / ".local"):
                continue
            if not resolved.exists():
                add("error", path, f"失效的本地 Markdown 链接: {target}")
    unique = {(f["level"], f["path"], f["message"]): f for f in findings}
    return sorted(unique.values(), key=lambda f: (f["level"], f["path"], f["message"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="历史证据待复核也返回失败")
    args = parser.parse_args()
    findings = audit(args.repo_root.resolve())
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        for item in findings:
            print(f"{item['level'].upper()} {item['path']}: {item['message']}")
        print(f"Audit: {sum(f['level']=='error' for f in findings)} errors, "
              f"{sum(f['level']=='warning' for f in findings)} need review. No remote verification performed.")
    return int(any(args.strict or f["level"] == "error" for f in findings))


if __name__ == "__main__":
    raise SystemExit(main())
