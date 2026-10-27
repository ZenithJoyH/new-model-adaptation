"""Offline operation safety tests; synthetic hosts always use connection=local."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import check_local_operations as checks  # noqa: E402


class SyntaxCheckTests(unittest.TestCase):
    def test_optional_arguments_with_system_bash(self) -> None:
        # macOS /bin/bash is 3.2; Linux also exercises the current Bash runtime.
        for arguments, expected_flag, expected_status in (
            ([], "", 0),
            (["--offline"], "--repository-only", 0),
            (["--unknown"], None, 2),
            (["--offline", "extra"], None, 2),
        ):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "scripts").mkdir()
                (root / ".venv/bin").mkdir(parents=True)
                shutil.copyfile(ROOT / "scripts/syntax-check", root / "scripts/syntax-check")
                # Stub all children: no Ansible, SSH, recursive tests or real audit.
                for name in ("scripts/inventory", "scripts/audit-workspace", ".venv/bin/python"):
                    stub = root / name
                    stub.write_text(
                        '#!/bin/sh\n'
                        'printf "%s|%s|%s\\n" "${0##*/}" "$#" "$*" >> calls.log\n',
                        encoding="utf-8",
                    )
                    stub.chmod(0o755)
                result = subprocess.run(
                    ["/bin/bash", str(root / "scripts/syntax-check"), *arguments],
                    cwd=root, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, expected_status, result.stderr)
                log = root / "calls.log"
                if expected_status:
                    self.assertIn("Usage:", result.stderr)
                    self.assertFalse(log.exists())
                    continue
                calls = log.read_text(encoding="utf-8").splitlines()
                count = int(bool(expected_flag))
                self.assertEqual(calls[0], f"inventory|{count}|{expected_flag}")
                self.assertEqual(calls[-1], f"audit-workspace|{count}|{expected_flag}")
                self.assertEqual(len(calls), 5)


class DiscoveryTests(unittest.TestCase):
    def test_detects_playbooks_not_configuration_or_task_lists(self) -> None:
        self.assertTrue(checks.is_playbook([{"hosts": "example", "tasks": []}]))
        self.assertTrue(checks.is_playbook([{"import_playbook": "other.yml"}]))
        self.assertFalse(checks.is_playbook({"hosts": ["example"], "engine": {}}))
        self.assertFalse(checks.is_playbook([{"name": "task", "ansible.builtin.debug": {}}]))
        self.assertFalse(checks.is_playbook(None))

    def test_discovery_includes_extensionless_shell_and_model_playbooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scripts").mkdir()
            (root / "models" / "Example" / "ppu" / "environment").mkdir(parents=True)
            wrapper = root / "scripts" / "operation"
            wrapper.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            (root / "scripts" / "not-shell.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            environment = root / "models" / "Example" / "ppu" / "environment"
            playbook = environment / "collect.yml"
            playbook.write_text("- hosts: example\n  tasks: []\n", encoding="utf-8")
            (environment / "runtime-config.yml").write_text("hosts: [example]\n", encoding="utf-8")
            self.assertEqual(checks.shell_files(root), [wrapper])
            self.assertEqual(checks.playbook_files(root), [playbook])

    def test_all_common_wrappers_are_checked(self) -> None:
        selected = checks.shell_files(ROOT)
        for name in ("playbook", "ansible", "inventory", "bootstrap-control-node", "syntax-check"):
            self.assertIn(ROOT / "scripts" / name, selected)

    def test_inventory_detects_alias_drift_and_includes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'inventory').mkdir()
            (root/'inventory/hosts.yml').write_text('all:\n  children:\n    managed:\n      children:\n        ppu:\n          hosts: {PPU-01: null}\n')
            (root/'config').write_text('Host *\n  User ignored\nInclude more.conf\n')
            (root/'more.conf').write_text('Host PPU-01\n')
            self.assertEqual(checks.inventory_alias_errors(root, root/'config'), [])
            (root/'more.conf').write_text('Host PPU-02\n')
            errors = checks.inventory_alias_errors(root, root/'config')
            self.assertEqual(len(errors), 2)

    def test_repository_inventory_check_does_not_require_ssh_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'inventory').mkdir()
            (root/'inventory/hosts.yml').write_text(
                'all:\n  children:\n    managed:\n      children:\n'
                '        ppu:\n          hosts: {PPU-01: null}\n',
                encoding='utf-8',
            )
            self.assertEqual(checks.inventory_structure_errors(root), [])
            errors = checks.inventory_alias_errors(root, root/'missing-ssh-config')
            self.assertEqual(errors, [f'SSH 配置不存在: {root / "missing-ssh-config"}'])

    def test_repository_inventory_check_rejects_duplicate_platform_membership(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'inventory').mkdir()
            (root/'inventory/hosts.yml').write_text(
                'all:\n  children:\n    managed:\n      children:\n'
                '        ppu:\n          hosts: {shared: null}\n'
                '        metax:\n          hosts: {shared: null}\n',
                encoding='utf-8',
            )
            self.assertEqual(checks.inventory_structure_errors(root), ['inventory 存在重复平台归属'])
if __name__ == "__main__":
    unittest.main()
