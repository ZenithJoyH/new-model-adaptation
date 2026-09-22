"""Offline operation safety tests; synthetic hosts always use connection=local."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import check_local_operations as checks  # noqa: E402


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
