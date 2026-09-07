"""Offline operation safety tests; synthetic hosts always use connection=local."""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import check_local_operations as checks  # noqa: E402

ANSIBLE = ROOT / ".venv" / "bin" / "ansible-playbook"


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


@unittest.skipUnless(ANSIBLE.is_file(), "Bootstrap the local Ansible environment first")
class LocalPlaybookTests(unittest.TestCase):
    def run_playbook(self, plays: list, variables: dict, *, check: bool = False,
                     limit: str | None = None) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inventory = root / "hosts.yml"
            inventory.write_text(yaml.safe_dump({"all": {"children": {
                "modelscope_hosts": {"hosts": {"OPS-A": {"ansible_connection": "local"},
                                                "OPS-B": {"ansible_connection": "local"}}},
                "ppu": {"hosts": {"OPS-A": {}, "OPS-B": {}}},
            }}}), encoding="utf-8")
            playbook = root / "test.yml"
            playbook.write_text(yaml.safe_dump(plays, sort_keys=False), encoding="utf-8")
            var_file = root / "vars.yml"
            var_file.write_text(yaml.safe_dump(variables), encoding="utf-8")
            config = root / "ansible.cfg"
            config.write_text("[defaults]\nhost_key_checking=True\nretry_files_enabled=False\n", encoding="utf-8")
            command = [str(ANSIBLE), "-i", str(inventory), str(playbook), "-e", "@" + str(var_file)]
            if check:
                command.append("--check")
            if limit:
                command.extend(["--limit", limit])
            return subprocess.run(command, capture_output=True, text=True, check=False, timeout=45,
                                  cwd=root, env=dict(os.environ, ANSIBLE_CONFIG=str(config),
                                                     ANSIBLE_HOME=str(root / ".ansible")))

    def download_guard_plays(self) -> list:
        plays = yaml.safe_load((ROOT / "playbooks" / "download-model.yml").read_text())
        remote = copy.deepcopy(plays[1])
        # Only assert/debug are retained: never include the actual download or diagnostics.
        remote["pre_tasks"] = [remote["pre_tasks"][0]]
        remote["tasks"] = [{"ansible.builtin.debug": {"msg": "GUARD_PASSED"}}]
        self.assertIn("ansible.builtin.assert", remote["pre_tasks"][0])
        self.assertEqual(remote["serial"], 1)
        return [plays[0], remote]

    def test_download_guard_survives_limit_skipping_localhost(self) -> None:
        for target, limit, allowed in (("OPS-A", "OPS-A", True),
                                       ("ppu", "ppu", False),
                                       ("ppu", "OPS-A", False),
                                       ("OPS-A:OPS-B", "ppu", False)):
            with self.subTest(target=target, limit=limit):
                result = self.run_playbook(self.download_guard_plays(), {
                    "target": target, "model_id": "Example/Model", "model_local_dir": "/models/example",
                }, limit=limit)
                self.assertEqual(result.returncode == 0, allowed, result.stdout + result.stderr)
                self.assertEqual("GUARD_PASSED" in result.stdout, allowed, result.stdout)
                if not allowed:
                    self.assertIn("Downloads require one concrete", result.stdout + result.stderr)

    def test_download_guard_checks_inputs_after_localhost_is_limited_out(self) -> None:
        for overrides in ({"model_id": ""}, {"model_local_dir": "/"}, {"model_local_dir": "relative"}):
            with self.subTest(overrides=overrides):
                variables = {"target": "OPS-A", "model_id": "Example/Model", "model_local_dir": "/models/example"}
                variables.update(overrides)
                result = self.run_playbook(self.download_guard_plays(), variables, limit="OPS-A")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("Downloads require one concrete", result.stdout + result.stderr)

    def test_modelscope_check_mode_first_install_and_unchanged_package(self) -> None:
        for predicted_change in (True, False):
            with self.subTest(predicted_change=predicted_change), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                cli = root / "modelscope"
                if not predicted_change:
                    shutil.copy2(sys.executable, cli)
                plays = yaml.safe_load((ROOT / "playbooks" / "install-modelscope.yml").read_text())
                plays[0]["hosts"] = "OPS-A"
                pip_task = plays[0]["tasks"][0]
                self.assertIn("ansible.builtin.pip", pip_task)
                self.assertEqual(pip_task["register"], "modelscope_install")
                # Simulate only pip's prediction. No package is installed in this test.
                plays[0]["tasks"][0] = {"ansible.builtin.set_fact": {
                    "modelscope_install": {"changed": predicted_change}}}
                for task in plays[0]["tasks"]:
                    if "ansible.builtin.file" in task:
                        task["ansible.builtin.file"]["dest"] = str(root / "link")
                result = self.run_playbook(plays, {
                    "ansible_python_interpreter": sys.executable,
                    "modelscope_pip_executable": sys.executable,
                    "modelscope_version": "test-version",
                    "modelscope_cli_links": {"modelscope": str(cli)},
                }, check=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("package_change_predicted=" + str(predicted_change), result.stdout)
                self.assertNotIn("no changes were predicted", result.stdout)
                if predicted_change:
                    self.assertIn("deferred_until_package_install", result.stdout)
                    self.assertFalse(cli.exists())
                self.assertFalse((root / "link").exists())


if __name__ == "__main__":
    unittest.main()
