from __future__ import annotations

import copy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import adapt_model  # noqa: E402


class AdaptModelTests(unittest.TestCase):
    def test_every_platform_template_has_complete_workflow_schema(self) -> None:
        for platform in adapt_model.PLATFORMS:
            config = adapt_model.load_yaml(
                REPO_ROOT / "models" / "_template" / platform / "platform.yml"
            )
            self.assertEqual(config["platform"], platform)
            self.assertEqual(tuple(config["workflow"]), adapt_model.STEP_ORDER)
            self.assertEqual(
                set(config["workflow"]["acceptance"]["substeps"]),
                adapt_model.ACCEPTANCE_SUBSTEPS,
            )

    def test_cli_initializes_only_selected_stage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(REPO_ROOT / "templates", root / "templates")
            platform_dir = root / "models" / "Example" / "ppu"
            platform_dir.mkdir(parents=True)
            template_platform = REPO_ROOT / "models" / "_template" / "ppu" / "platform.yml"
            destination_template = root / "models" / "_template" / "ppu"
            destination_template.mkdir(parents=True)
            shutil.copy2(template_platform, platform_dir / "platform.yml")
            shutil.copy2(template_platform, destination_template / "platform.yml")
            inventory_dir = root / "inventory"
            inventory_dir.mkdir()
            inventory_dir.joinpath("hosts.yml").write_text(
                """---
all:
  children:
    managed:
      children:
        ppu:
          hosts:
            PPU-01:
""",
                encoding="utf-8",
            )

            command = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "adapt_model.py"),
                "--repo-root",
                str(root),
                "Example",
                "--platform",
                "ppu",
                "--hosts",
                "PPU-01",
                "--steps",
                "environment",
            ]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (platform_dir / "environment" / "environment-analysis.md").is_file()
            )
            self.assertFalse(
                (platform_dir / "environment" / "platform-adaptation-plan.md").exists()
            )
            self.assertFalse(
                (platform_dir / "environment" / "runtime-config.yml").exists()
            )
            self.assertFalse(
                (platform_dir / "environment" / "service-state.yml").exists()
            )
            self.assertFalse((platform_dir / "adaptation").exists())
            self.assertFalse((platform_dir / "acceptance").exists())

            checked = subprocess.run(
                [*command, "--check-only"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)

            combined = subprocess.run(
                [
                    *command[:-1],
                    "architecture,environment,adaptation",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(combined.returncode, 0, combined.stderr)
            self.assertTrue((root / "models" / "Example" / "architecture-and-inference.md").is_file())
            self.assertTrue(
                (platform_dir / "environment" / "platform-adaptation-plan.md").is_file()
            )
            self.assertTrue(
                (platform_dir / "environment" / "runtime-config.yml").is_file()
            )
            self.assertTrue(
                (platform_dir / "environment" / "service-state.yml").is_file()
            )
            self.assertEqual(
                sorted(path.name for path in (platform_dir / "adaptation").iterdir()),
                ["README.md"],
            )
            self.assertIn("适配配置仍需完善", combined.stdout)

    def test_steps_are_deduplicated_and_ordered(self) -> None:
        self.assertEqual(
            adapt_model.parse_steps("5,environment,1,environment"),
            ["architecture", "environment", "retrospective"],
        )

    def test_unselected_dependency_must_be_complete(self) -> None:
        workflow = {
            step: {"status": "not_started"} for step in adapt_model.STEP_ORDER
        }
        with tempfile.TemporaryDirectory() as directory:
            platform_dir = Path(directory)
            errors = adapt_model.check_dependencies(
                {"workflow": workflow}, ["adaptation"], platform_dir
            )
        self.assertEqual(len(errors), 2)
        workflow["architecture"]["status"] = "passed"
        workflow["environment"]["status"] = "complete"
        workflow["architecture"]["evidence"] = "architecture.md"
        workflow["environment"]["evidence"] = "environment.md"
        with tempfile.TemporaryDirectory() as directory:
            platform_dir = Path(directory)
            (platform_dir / "architecture.md").write_text("ok", encoding="utf-8")
            (platform_dir / "environment.md").write_text("ok", encoding="utf-8")
            self.assertEqual(
                adapt_model.check_dependencies(
                    {"workflow": workflow}, ["adaptation"], platform_dir
                ),
                [],
            )

    def test_selected_acceptance_substeps_obey_order(self) -> None:
        statuses = {name: "not_started" for name in adapt_model.ACCEPTANCE_SUBSTEP_ORDER}
        config = {"workflow": {"acceptance": {"substeps": statuses}}}
        errors = adapt_model.check_acceptance_dependencies(config, ["accuracy"])
        self.assertEqual(len(errors), 1)
        statuses["sanity"] = "passed"
        self.assertEqual(adapt_model.check_acceptance_dependencies(config, ["accuracy"]), [])

    def test_config_enforces_max_model_len_rule(self) -> None:
        template = adapt_model.load_yaml(
            REPO_ROOT / "templates" / "adaptation" / "runtime-config.yml"
        )
        config = copy.deepcopy(template)
        config["model"] = "Example"
        config["platform"] = "ppu"
        config["target"].update(
            hosts=["PPU-01"], container_name="adaptation", container_image="image:tag"
        )
        for component in config["stack"].values():
            component.update(path="/workspace/repo", revision="abc123")
        config["service"].update(
            model_path="/models/Example",
            served_model_name="Example",
            port=8000,
            tensor_parallel_size=2,
        )
        config["service"]["max_model_len"].update(
            model_supported=131072,
            initial=50000,
            evidence="config.json:max_position_embeddings",
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yml"
            path.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            self.assertEqual(
                adapt_model.validate_adaptation_config(path, "Example", "ppu"), []
            )
            config["service"]["max_model_len"]["initial"] = 8192
            path.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            errors = adapt_model.validate_adaptation_config(path, "Example", "ppu")
            self.assertTrue(any("50000" in error for error in errors))

    def test_config_rejects_secret_fields(self) -> None:
        with self.assertRaises(adapt_model.WorkflowError):
            adapt_model.reject_secret_keys({"ssh_password": "do-not-store"})


if __name__ == "__main__":
    unittest.main()
