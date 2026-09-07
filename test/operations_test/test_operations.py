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
if __name__ == "__main__":
    unittest.main()
