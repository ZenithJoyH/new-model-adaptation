#!/usr/bin/env python3
"""Discover and syntax-check local operation entry points without remote execution."""

from __future__ import annotations

import argparse
import os
import re
import glob
import shlex
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SHELL_SHEBANG = re.compile(r"^#!\s*(?:/usr/bin/env\s+(?:-S\s+)?)?(?:[^\s]*/)?(?:bash|sh)\b")


def concrete_ssh_aliases(config: Path, *, ssh_directory: Path | None = None, seen=None) -> set[str]:
    """Read Host aliases (including Include files), never connection credentials."""
    seen = set() if seen is None else seen
    config = config.expanduser().resolve()
    if config in seen:
        return set()
    seen.add(config)
    ssh_directory = config.parent if ssh_directory is None else ssh_directory
    aliases = set()
    for line in config.read_text(encoding="utf-8").splitlines():
        parts = shlex.split(line, comments=True)
        if not parts:
            continue
        if "=" in parts[0]:
            key, value = parts[0].split("=", 1)
            parts = [key, value, *parts[1:]]
        key = parts[0].lower()
        if key == "host":
            aliases.update(a for a in parts[1:] if a and not any(c in a for c in "*?!"))
        elif key == "include":
            for pattern in parts[1:]:
                path = Path(pattern).expanduser()
                if not path.is_absolute():
                    path = ssh_directory / path
                for included in sorted(glob.glob(str(path))):
                    aliases.update(concrete_ssh_aliases(Path(included), ssh_directory=ssh_directory, seen=seen))
    return aliases


def managed_inventory_entries(root: Path) -> list[str]:
    """Return concrete managed hosts; Ansible performs the full YAML validation."""
    document = yaml.safe_load((root / "inventory/hosts.yml").read_text(encoding="utf-8"))
    try:
        groups = document["all"]["children"]["managed"]["children"]
    except (KeyError, TypeError) as exc:
        raise ValueError("inventory/hosts.yml 缺少 all.children.managed.children") from exc
    if not isinstance(groups, dict):
        raise ValueError("inventory managed.children 必须是映射")
    entries: list[str] = []
    for name, group in groups.items():
        if not isinstance(name, str) or not isinstance(group, dict):
            raise ValueError("inventory 平台组必须是映射")
        hosts = group.get("hosts") or {}
        if not isinstance(hosts, dict) or not all(isinstance(host, str) and host for host in hosts):
            raise ValueError(f"inventory 平台组 {name} 的 hosts 必须是 Host 映射")
        entries.extend(hosts)
    return entries


def inventory_structure_errors(root: Path) -> list[str]:
    entries = managed_inventory_entries(root)
    errors = []
    if len(entries) != len(set(entries)):
        errors.append("inventory 存在重复平台归属")
    return errors


def inventory_alias_errors(root: Path, ssh_config: Path) -> list[str]:
    entries = managed_inventory_entries(root)
    errors = inventory_structure_errors(root)
    if not ssh_config.expanduser().is_file():
        return [*errors, f"SSH 配置不存在: {ssh_config.expanduser()}"]
    aliases = concrete_ssh_aliases(ssh_config)
    if set(entries) - aliases:
        errors.append("inventory 中不存在于 SSH 配置的别名: " + ", ".join(sorted(set(entries)-aliases)))
    if aliases - set(entries):
        errors.append("SSH 别名尚未纳入 inventory: " + ", ".join(sorted(aliases-set(entries))))
    return errors


def shell_files(root: Path) -> list[Path]:
    """Include extensionless wrappers; never source or execute their contents."""
    result = []
    for directory in ("scripts", "models", "test"):
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            with path.open("rb") as handle:
                first_line = handle.readline(256).decode("utf-8", errors="replace")
            if SHELL_SHEBANG.match(first_line):
                result.append(path)
    return sorted(result)


def is_playbook(document: object) -> bool:
    """Do not pass runtime, inventory, model, or vendor configuration to Ansible."""
    return isinstance(document, list) and any(
        isinstance(item, dict)
        and any(key in item for key in ("hosts", "import_playbook", "ansible.builtin.import_playbook"))
        for item in document
    )


def playbook_files(root: Path) -> list[Path]:
    result = []
    for directory in ("playbooks", "models"):
        for path in sorted((root / directory).rglob("*")):
            if path.suffix not in (".yml", ".yaml") or not path.is_file() or path.is_symlink():
                continue
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            if is_playbook(document):
                result.append(path)
            elif directory == "playbooks":
                raise ValueError(f"Expected an Ansible playbook: {path}")
    return sorted(result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    inventory_mode = parser.add_mutually_exclusive_group()
    inventory_mode.add_argument("--inventory-only", action="store_true")
    inventory_mode.add_argument("--inventory-structure-only", action="store_true")
    parser.add_argument("--ssh-config", type=Path, default=Path.home()/".ssh/config")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    if args.inventory_only:
        errors = inventory_alias_errors(root, args.ssh_config)
        if errors:
            raise SystemExit("\n".join(errors))
        print("Inventory 与 SSH 具体别名一致。")
        return
    if args.inventory_structure_only:
        errors = inventory_structure_errors(root)
        if errors:
            raise SystemExit("\n".join(errors))
        print("Inventory 仓库结构有效；未读取操作者 SSH 配置。")
        return
    shells, playbooks = shell_files(root), playbook_files(root)
    environment = dict(os.environ, ANSIBLE_HOME=str(root / ".ansible"))
    for path in shells:
        subprocess.run(["bash", "-n", str(path)], check=True, cwd=root)
    for path in playbooks:
        subprocess.run(
            ["./scripts/playbook", str(path), "--syntax-check"],
            check=True, cwd=root, env=environment,
        )
    print(f"Local syntax checks passed: {len(shells)} shell entry points, {len(playbooks)} playbooks; no remote tasks executed.")


if __name__ == "__main__":
    main()
