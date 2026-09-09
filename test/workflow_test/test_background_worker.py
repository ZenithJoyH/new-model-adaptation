"""Local tests for the background evaluation supervisor."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "test/Accuracy_test"))
import background_worker as worker


class BackgroundWorkerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="background-worker-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.run = self.base / "04-runs" / "test-run"
        self.run.mkdir(parents=True)
        self.plan = {
            "schema_version": 5,
            "model": "Example",
            "platform": "ppu",
            "host_alias": "PPU-01",
            "service_port": 8010,
            "run_id": "test-run",
            "workspace": {
                "host_root": str(self.base / "host"),
                "container_root": "/model/task",
                "evaluator_container": "evaluation-container",
                "evaluator_root": str(self.base),
            },
        }
        self.path = self.run / "run-plan.json"
        self.path.write_text(json.dumps(self.plan), encoding="utf-8")
        self.scope = {key: self.plan[key] for key in ("model", "platform", "host_alias", "service_port")}

    def args(self):
        return argparse.Namespace(
            run_plan=self.path,
            plan_sha256=worker.sha256(self.path),
            admission_sha256="admitted",
            workspace_plan_json=json.dumps(self.plan),
            worker=True,
            check_plan=False,
        )

    def test_plan_binds_scope_workspace_and_schema(self):
        plan, digest = worker.read_plan(self.path, self.run, self.scope)
        self.assertEqual(plan, self.plan)
        self.assertEqual(digest, worker.sha256(self.path))
        for field, value in (("schema_version", 4), ("run_id", "auto"), ("service_port", 8038)):
            changed = dict(self.plan, **{field: value})
            self.path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ValueError):
                worker.read_plan(self.path, self.run, self.scope)

    def test_missing_plan_fails_without_dispatch_artifacts(self):
        self.path.unlink()
        with self.assertRaises((OSError, ValueError)):
            worker.launch(self.run, Path("wrapper.py"), self.args(), ["runner"], Mock(), [],
                          expected_scope=self.scope)
        self.assertFalse((self.run / "launch.json").exists())
        self.assertFalse((self.run / "launch-claim").exists())

    def test_worker_records_success_after_rechecking_inputs(self):
        (self.run / "workflow-manifest.json").write_text("{}", encoding="utf-8")
        manifest = {"service_instance_id": "instance"}
        config = {}
        with patch.object(worker, "admission_hash", return_value="admitted"), \
             patch.object(worker, "input_hashes", return_value={"runner.py": "hash"}), \
             patch.object(worker, "admission", return_value=(manifest, config)), \
             patch.object(worker, "scoped_environment", return_value={}), \
             patch.object(worker, "request_observation", return_value={"status": "verified"}), \
             patch.object(worker, "run_attached", return_value=0) as run:
            rc = worker.worker(self.run, self.args(), ["runner"], Mock(), ["runner.py"],
                               expected_scope=self.scope)
        self.assertEqual(rc, 0)
        run.assert_called_once_with(["runner"], cwd=self.run, env={})
        status = json.loads((self.run / "exit-status.json").read_text())
        self.assertEqual(status["status"], "passed")
        started = json.loads((self.run / "worker-started.json").read_text())
        self.assertEqual(started["service_observation"], {"status": "verified"})

    def test_run_attached_reports_signal_exit(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = -15
        with patch.object(worker.subprocess, "Popen", return_value=process):
            self.assertEqual(worker.run_attached(["runner"], cwd=self.run), 143)


if __name__ == "__main__":
    unittest.main()
