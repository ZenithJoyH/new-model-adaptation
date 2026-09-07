#!/usr/bin/env python3
"""Discover and syntax-check local operation entry points without remote execution."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SHELL_SHEBANG = re.compile(r"^#!\s*(?:/usr/bin/env\s+(?:-S\s+)?)?(?:[^\s]*/)?(?:bash|sh)\b")


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
    args = parser.parse_args()
    root = args.repo_root.resolve()
    shells, playbooks = shell_files(root), playbook_files(root)
    environment = dict(os.environ, ANSIBLE_HOME=str(root / ".ansible"))
    for path in shells:
        subprocess.run(["bash", "-n", str(path)], check=True, cwd=root)
    for path in playbooks:
        subprocess.run(
            [str(root / "scripts" / "playbook"), str(path), "--syntax-check"],
            check=True, cwd=root, env=environment,
        )
    print(f"Local syntax checks passed: {len(shells)} shell entry points, {len(playbooks)} playbooks; no remote tasks executed.")


if __name__ == "__main__":
    main()
