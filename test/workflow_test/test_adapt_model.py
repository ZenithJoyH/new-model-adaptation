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

    def test_legacy_platform_creation_is_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for steps in ('environment', 'architecture,environment,adaptation'):
                result = subprocess.run([sys.executable, str(REPO_ROOT / 'scripts/adapt_model.py'),
                    '--repo-root', str(root), 'Example', '--platform', 'ppu', '--hosts', 'PPU-01',
                    '--steps', steps], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('创建入口已停用', result.stderr)
                self.assertEqual(list(root.iterdir()), [])

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
            errors = adapt_model.check_dependencies({"workflow": workflow}, ["adaptation"], platform_dir)
            self.assertEqual(sum("verification" in error for error in errors), 2)
            self.assertTrue(any(
                "environment-target.yml" in error or "platform.yml" in error
                for error in errors
            ))

    def test_selected_acceptance_substeps_obey_order(self) -> None:
        statuses = {name: "not_started" for name in adapt_model.ACCEPTANCE_SUBSTEP_ORDER}
        config = {"workflow": {"acceptance": {"substeps": statuses}}}
        errors = adapt_model.check_acceptance_dependencies(config, ["accuracy"])
        self.assertEqual(len(errors), 2)
        statuses["sanity"] = "passed"
        self.assertTrue(adapt_model.check_acceptance_dependencies(config, ["accuracy"]))
        statuses["execution-mode"] = "passed"
        self.assertEqual(adapt_model.check_acceptance_dependencies(config, ["accuracy"]), [])

    def test_config_enforces_max_model_len_rule(self) -> None:
        template = adapt_model.load_yaml(
            REPO_ROOT / "templates" / "adaptation" / "runtime-config.yml"
        )
        config = copy.deepcopy(template)
        config["model"] = "Example"
        config["platform"] = "ppu"
        config["configuration_status"] = "ready"
        config["target"].update(
            hosts=["PPU-01"], container_name="adaptation", container_image="image:tag"
        )
        config["workspace"] = {"roots": [{"host_alias": "PPU-01", "host_root": "/operator/Example",
                                           "container_root": "/work/Example"}]}
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
            config["configuration_status"] = "draft"
            path.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            errors = adapt_model.validate_adaptation_config(path, "Example", "ppu")
            self.assertTrue(any("configuration_status" in error for error in errors))
            config["configuration_status"] = "ready"
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

    def test_performance_config_requires_disabled_prefix_cache_evidence(self) -> None:
        config = adapt_model.load_yaml(
            REPO_ROOT / "templates" / "adaptation" / "runtime-config.yml"
        )
        config.update(model="Example", platform="ppu", configuration_status="ready")
        config["target"].update(
            hosts=["PPU-01"], container_name="adaptation", container_image="image:tag"
        )
        config["workspace"] = {"roots": [{
            "host_alias": "PPU-01", "host_root": "/operator/Example",
            "container_root": "/work/Example",
        }]}
        for component in config["stack"].values():
            component.update(path="/workspace/repo", revision="abc123")
        config["service"].update(
            model_path="/models/Example", served_model_name="Example", port=8000,
            tensor_parallel_size=2,
        )
        config["service"]["max_model_len"].update(
            model_supported=50000, initial=50000, evidence="model config",
        )
        config["acceptance"].update(
            graph_base_url="http://127.0.0.1:8000",
            accuracy_image="harbor.baai.ac.cn/flageval/flageval-llmeval:v1",
            accuracy_config="/remote/llm_config.json",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yml"
            for field, value in (("enabled", True), ("launch_args", []), ("verification", "")):
                performance = {"enabled": False, "launch_args": ["--no-enable-prefix-caching"],
                               "verification": "/runs/prefix-cache-disabled.txt"}
                performance[field] = value
                config["service"]["prefix_caching"] = {
                    "default_enabled": True,
                    "performance": performance,
                }
                path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
                errors = adapt_model.validate_adaptation_config(
                    path, "Example", "ppu", acceptance_substeps=["performance"]
                )
                with self.subTest(field=field):
                    self.assertTrue(any("前缀缓存" in error or "prefix_caching" in error for error in errors))

            config["service"]["prefix_caching"] = {
                "default_enabled": True,
                "performance": {
                    "enabled": False,
                    "launch_args": ["--no-enable-prefix-caching"],
                    "verification": "/runs/prefix-cache-disabled.txt",
                },
            }
            path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
            errors = adapt_model.validate_adaptation_config(
                path, "Example", "ppu", acceptance_substeps=["performance"]
            )
            self.assertFalse(any("前缀缓存" in error or "prefix_caching" in error for error in errors))

            config["execution_modes"]["graph"]["extra_args"] = ["--no-enable-prefix-caching"]
            path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
            errors = adapt_model.validate_adaptation_config(
                path, "Example", "ppu", acceptance_substeps=["performance"]
            )
            self.assertTrue(any("--no-enable-prefix-caching" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
