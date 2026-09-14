"""Synthetic, local-only workflow snapshots; never contact a model or a host."""

import copy
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import accuracy_admission as admission
import adapt_model as workflow
from workflow_state import deployment_fingerprint


class AccuracyAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="test-accuracy-admission-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.prefix = "models/Example/ppu"
        self.platform = self.root / self.prefix
        self.scope = {"model": "Example", "platform": "ppu", "host_alias": "PPU-01", "service_port": 8010}
        for name in (*admission.GATE_FILES, "templates/adaptation/runtime-config.yml",
                     "templates/adaptation/acceptance-plan.md", "models/_template/ppu/platform.yml"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.put("inventory/hosts.yml", {"all": {"children": {"managed": {"children": {
            "ppu": {"hosts": {"PPU-01": None, "PPU-02": None}}}}}}})
        self.put("models/Example/model.yml", {"name": "Example", "source": {"revision": "synthetic"}})
        self.put("models/Example/architecture-and-inference.md", "Synthetic architecture evidence.")
        self.put(f"{self.prefix}/environment/environment-analysis.md", "Synthetic environment evidence.")
        self.put(f"{self.prefix}/environment/plugin-change-review.md", "Synthetic reviewed diff.")
        self.put(f"{self.prefix}/environment/environment-target.yml", {
            "schema_version": 1, "model": "Example", "platform": "ppu", "target": {"hosts": ["PPU-01"]}})
        self.put(f"{self.prefix}/acceptance/acceptance-plan.md", "Synthetic acceptance plan.")
        self.put(f"{self.prefix}/adaptation/README.md", "Synthetic verified adaptation.")
        self.put(f"{self.prefix}/acceptance/execution-mode.md", "Synthetic graph mode evidence.")
        self.put(f"{self.prefix}/acceptance/sanity.md", "Synthetic passing sanity evidence.")
        self.runtime = workflow.load_yaml(ROOT / "templates/adaptation/runtime-config.yml")
        self.runtime.update(model="Example", platform="ppu", configuration_status="ready")
        self.runtime["target"].update(hosts=["PPU-01"], container_name="model-container", container_image="synthetic:local")
        self.runtime["workspace"] = {"roots": [{"host_alias": "PPU-01", "host_root": "/operator/task",
                                                "container_root": "/model/task"}]}
        for name, component in self.runtime["stack"].items():
            component.update(path=f"/existing/{name}", revision="a" * 40)
        self.runtime["service"].update(model_path="/existing/weights", served_model_name="Example", port=8010,
                                       tensor_parallel_size=1)
        self.runtime["service"]["max_model_len"].update(model_supported=50000, initial=50000, evidence="synthetic config")
        self.accuracy_path = f"{self.prefix}/acceptance/llm_config.json"
        self.runtime["acceptance"].update(graph_base_url="http://127.0.0.1:8010",
            accuracy_image="harbor.baai.ac.cn/flageval/flageval-llmeval:v1", accuracy_config=self.accuracy_path)
        self.put(f"{self.prefix}/environment/runtime-config.yml", self.runtime)
        self.plan = {"schema_version": 5, **self.scope, "run_id": "synthetic-new-run",
                     "workspace": {"host_root": "/operator/task", "container_root": "/model/task",
                                   "evaluator_container": "evaluation-container", "evaluator_root": "/eval/task"}}
        self.accuracy = {"formal_acceptance": True, "service_mode": "graph", "num_concurrent": 32,
                         "limit": 0, "expected_samples": 198, "allow_timeouts": True,
                         "tasks": ["example"], "acceptance_criteria": {"example": {"metric": "acc", "minimum": 0.9}},
                         "model_name": "Example", "base_url": "http://127.0.0.1:8010/v1/chat/completions",
                         "run_id": self.plan["run_id"], "output_root": "outputs", "cache_root": "cache/eval",
                         "hf_datasets_cache": "/eval/task/04-runs/synthetic-new-run/cache/datasets"}
        self.put(self.accuracy_path, json.dumps(self.accuracy, indent=3) + "\n")
        identity = {"schema_version": 1, "model": "Example", "platform": "ppu", "model_revision": "actual-synthetic",
                    "container_image_digest": "sha256:" + "b" * 64,
                    "runtime_config_sha256": workflow.file_sha256(self.platform / "environment/runtime-config.yml"),
                    "stack": {name: {"revision": "a" * 40, "tracked_diff_sha256": "d" * 64,
                                      "untracked_files_sha256": "e" * 64} for name in self.runtime["stack"]}}
        self.put(f"{self.prefix}/environment/deployment-identity.yml", identity)
        now = datetime.now(timezone.utc)
        self.state = {"schema_version": 2, "model": "Example", "platform": "ppu", "host": "PPU-01",
                      "container_name": "model-container", "lifecycle_history": [], "service": {
                          "status": "ready", "mode": "graph", "readiness_result": "passed", "pid": 123, "port": 8010,
                          "instance_id": "synthetic-instance", "command_record": "environment/launch.md",
                          "started_at": (now - timedelta(minutes=5)).isoformat(), "readiness_checked_at": now.isoformat(),
                          "deployment_fingerprint": deployment_fingerprint(self.platform),
                          "process_identity": {"container_id": "c" * 64, "boot_id": "a1962ef9-61fe-4d7f-80a0-e3c4201a4592",
                                               "start_ticks": 45678, "cmdline_sha256": "f" * 64}}}
        self.put(f"{self.prefix}/environment/service-state.yml", self.state)
        self.config = workflow.load_yaml(ROOT / "models/_template/ppu/platform.yml")
        self.config["status"] = "model_loading"
        self.put(f"{self.prefix}/platform.yml", self.config)
        for stage, evidence in (("architecture", "../architecture-and-inference.md"),
                                ("environment", "environment/environment-analysis.md"),
                                ("adaptation", "adaptation/README.md"),
                                ("execution-mode", "acceptance/execution-mode.md"), ("sanity", "acceptance/sanity.md")):
            receipt = {"run_id": "synthetic-" + stage, "last_verified": date.today().isoformat(), "evidence": evidence,
                       "evidence_sha256": workflow.file_sha256(self.platform / evidence),
                       "context_sha256": workflow.context_sha256(self.platform, stage, self.config),
                       "service_instance_id": self.state["service"]["instance_id"]}
            if stage in ("execution-mode", "sanity"):
                self.config["workflow"]["acceptance"]["records"][stage] = receipt
                self.config["workflow"]["acceptance"]["substeps"][stage] = "passed"
            else:
                self.config["workflow"][stage].update(status="passed", evidence=evidence, verification=receipt)
            self.put(f"{self.prefix}/platform.yml", self.config)

    def put(self, name, value):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value if isinstance(value, str) else yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

    def build(self):
        return admission.build_snapshot(self.root, self.scope, self.plan)

    def deploy(self, payload):
        temporary = tempfile.TemporaryDirectory(prefix="test-deployed-admission-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        for name, content in payload["files"].items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return root

    def test_export_is_compact_read_only_and_runs_both_real_gates(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(admission, "_run_gate", wraps=admission._run_gate) as gate:
            payload = self.build()
        # Source gate is in this process; the deployed-form validation uses a
        # fresh interpreter and its own canonical gate, not this module cache.
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual(payload["files"][self.accuracy_path].encode(), before[Path(self.accuracy_path)])
        self.assertNotIn("test/Accuracy_test/llmrun.py", payload["files"])
        self.assertEqual(payload["manifest"]["service_pid"], 123)
        self.assertEqual(payload["manifest"]["service_process_identity"], self.state["service"]["process_identity"])
        self.assertEqual(payload["manifest"]["run_plan"], self.plan)
        self.assertEqual(payload["manifest"]["evaluator_image"], self.runtime["acceptance"]["accuracy_image"])

    def test_snapshot_is_relocatable_without_source_tree(self):
        payload = self.build()
        destination = self.deploy(payload)
        shutil.rmtree(self.root / "models")  # This test's synthetic tree only.
        admission.validate_snapshot(destination, payload["manifest"], self.scope, self.plan)

    def test_minimal_deployed_bundle_does_not_depend_on_controller_import_cache(self):
        payload = self.build()
        snapshot = self.deploy(payload)
        temporary = tempfile.TemporaryDirectory(prefix="test-minimal-worker-bundle-")
        self.addCleanup(temporary.cleanup)
        bundle = Path(temporary.name).resolve()
        for name in ("accuracy_admission.py", "remote_workspace.py", "service_observation.py"):
            shutil.copyfile(ROOT / "scripts" / name, bundle / name)
        code = ("import importlib.util,json,sys; import accuracy_admission; "
                "assert importlib.util.find_spec('adapt_model') is None; "
                "p=json.load(sys.stdin); "
                "accuracy_admission.validate_snapshot(sys.argv[1],p['manifest'],p['scope'],p['plan'])")
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        environment.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, "-B", "-c", code, str(snapshot)], cwd=bundle,
                                input=json.dumps({"manifest": payload["manifest"], "scope": self.scope, "plan": self.plan}),
                                capture_output=True, text=True, timeout=30, env=environment)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_snapshot_cannot_relabel_stale_service_as_current(self):
        payload = self.build()
        destination = self.deploy(payload)
        state_path = f"{self.prefix}/environment/service-state.yml"
        state = yaml.safe_load(payload["files"][state_path])
        state["service"]["readiness_checked_at"] = "2020-01-01T00:00:00+00:00"
        (destination / state_path).write_text(yaml.safe_dump(state))
        payload["manifest"]["files_sha256"][state_path] = workflow.file_sha256(destination / state_path)
        with self.assertRaisesRegex(ValueError, "workflow gate refused"):
            admission.validate_snapshot(destination, payload["manifest"], self.scope, self.plan)

    def test_manifest_file_set_hash_and_process_binding_fail_closed(self):
        payload = self.build()
        for mutation in ("edit", "extra", "missing", "pid", "process", "scope", "image", "plan"):
            with self.subTest(mutation=mutation):
                destination = self.deploy(payload)
                manifest = copy.deepcopy(payload["manifest"])
                if mutation == "edit":
                    (destination / self.accuracy_path).write_text("{}")
                elif mutation == "extra":
                    (destination / "unexpected.txt").write_text("not workflow evidence")
                elif mutation == "missing":
                    (destination / self.accuracy_path).unlink()
                elif mutation == "pid":
                    manifest["service_pid"] = True
                elif mutation == "process":
                    manifest["service_process_identity"]["start_ticks"] += 1
                elif mutation == "scope":
                    manifest["model"] = "AnotherModel"
                elif mutation == "image":
                    manifest["evaluator_image"] = "different:image"
                else:
                    manifest["run_plan"]["run_id"] = "different-run"
                with self.assertRaises(ValueError):
                    admission.validate_snapshot(destination, manifest, self.scope, self.plan)

    def test_source_and_snapshot_symlinks_are_rejected(self):
        payload = self.build()
        destination = self.deploy(payload)
        (destination / "unexpected-link").symlink_to(self.root / "models", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            admission.validate_snapshot(destination, payload["manifest"], self.scope, self.plan)
        evidence = self.platform / "acceptance/sanity.md"
        evidence.unlink()
        evidence.symlink_to(self.platform / "acceptance/execution-mode.md")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.build()

    def test_nonrelocatable_accuracy_paths_are_rejected(self):
        for path in (str(self.root / self.accuracy_path), "models/AnotherModel/ppu/acceptance/a.json",
                     "models/Example/ppu/acceptance/../acceptance/llm_config.json"):
            with self.subTest(path=path):
                runtime = copy.deepcopy(self.runtime)
                runtime["acceptance"]["accuracy_config"] = path
                self.put(f"{self.prefix}/environment/runtime-config.yml", runtime)
                with self.assertRaises(ValueError):
                    self.build()

    def test_plan_cannot_change_roots_or_host_scope(self):
        original = copy.deepcopy(self.plan)
        for mutate in (lambda p: p.update(schema_version=True), lambda p: p.update(host_alias="PPU-02"),
                       lambda p: p.update(service_port=8038), lambda p: p.update(run_id="other-run"),
                       lambda p: p["workspace"].update(host_root="/other/task"),
                       lambda p: p["workspace"].update(evaluator_root="/eval/task/../other")):
            self.plan = copy.deepcopy(original)
            mutate(self.plan)
            with self.assertRaises(ValueError):
                self.build()
        self.plan = original
        runtime = copy.deepcopy(self.runtime)
        runtime["target"]["hosts"].append("PPU-02")
        self.put(f"{self.prefix}/environment/runtime-config.yml", runtime)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.build()

    def test_known_write_paths_are_bound_without_remote_filesystem_resolution(self):
        with patch("remote_workspace.real_path", side_effect=AssertionError("remote path resolved on controller")):
            self.build()
        for field, value in (("run_id", "other-run"), ("output_root", "/outside"), ("cache_root", "../cache"),
                             ("hf_datasets_cache", "relative-cache"), ("hf_datasets_cache", "/outside/datasets")):
            with self.subTest(field=field, value=value):
                config = dict(self.accuracy, **{field: value})
                self.put(self.accuracy_path, json.dumps(config))
                with self.assertRaises(ValueError):
                    self.build()

    def test_new_background_admission_requires_explicit_process_identity(self):
        original = copy.deepcopy(self.state)
        for mutate in (lambda s: s["service"].pop("process_identity"), lambda s: s["service"].update(pid=True),
                       lambda s: s["service"]["process_identity"].update(container_id="short"),
                       lambda s: s["service"]["process_identity"].update(cmdline_sha256="F" * 64),
                       lambda s: s["service"]["process_identity"].update(boot_id="not-a-uuid"),
                       lambda s: s["service"]["process_identity"].update(start_ticks=True),
                       lambda s: s["service"]["process_identity"].update(start_ticks=0),
                       lambda s: s["service"]["process_identity"].update(unexpected="field")):
            state = copy.deepcopy(original)
            mutate(state)
            self.put(f"{self.prefix}/environment/service-state.yml", state)
            with self.assertRaises(ValueError):
                self.build()
            self.assertEqual(workflow.load_yaml(self.platform / "environment/service-state.yml"), state)

    def test_original_gate_refuses_stopped_service_and_failed_prerequisite(self):
        self.state["service"]["status"] = "stopped"
        self.put(f"{self.prefix}/environment/service-state.yml", self.state)
        with self.assertRaisesRegex(ValueError, "workflow gate refused"):
            self.build()
        self.state["service"]["status"] = "ready"
        self.put(f"{self.prefix}/environment/service-state.yml", self.state)
        self.config["workflow"]["acceptance"]["substeps"]["sanity"] = "failed"
        self.put(f"{self.prefix}/platform.yml", self.config)
        with self.assertRaisesRegex(ValueError, "workflow gate refused"):
            self.build()

    def test_source_mutation_during_gate_cannot_get_relabelled(self):
        original_gate = admission._run_gate
        def gate(root, scope):
            original_gate(root, scope)
            if root == self.root:
                path = self.platform / "acceptance/sanity.md"
                path.write_text("Evidence changed during local check.")
        with patch.object(admission, "_run_gate", side_effect=gate):
            with self.assertRaisesRegex(ValueError, "changed during admission"):
                self.build()

    def test_cli_emits_only_json_and_binds_original_plan_bytes(self):
        plan_file = self.root / "run-plan.json"
        plan_file.write_text(json.dumps(self.plan, indent=4) + "\n")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/accuracy_admission.py"), "Example",
                                 "--platform", "ppu", "--repo-root", str(self.root), "--run-plan", str(plan_file)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["manifest"]["run_plan_source_sha256"], hashlib.sha256(plan_file.read_bytes()).hexdigest())
        self.assertEqual(result.stderr, "")

    def test_cli_rejects_plan_symlink_parent_and_hardlink(self):
        plan_file = self.root / "run-plan.json"
        plan_file.write_text(json.dumps(self.plan))
        alias = self.root / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        hardlink = self.root / "hardlink-plan.json"
        os.link(plan_file, hardlink)
        for path in (alias / plan_file.name, hardlink, Path("run-plan.json")):
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/accuracy_admission.py"), "Example",
                                     "--platform", "ppu", "--repo-root", str(self.root), "--run-plan", str(path)],
                                    cwd=self.root, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
