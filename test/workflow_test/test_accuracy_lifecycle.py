"""Offline accuracy snapshots, terminal reports and real local worker lifetimes.

No lm_eval executable, inference service, network or model is used. The only
real children are Python sleepers created by each test in their own session.
"""

import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

ACCURACY = Path(__file__).resolve().parents[1] / "Accuracy_test"
sys.path.insert(0, str(ACCURACY))
import llmrun
import llmrun_parallel as parallel


def config(root):
    return {"formal_acceptance": True, "service_mode": "graph", "num_concurrent": 32,
            "limit": 0, "expected_samples": 1, "allow_timeouts": True,
            "tasks": ["example"], "acceptance_criteria": {
                "example": {"metric": "exact_match,none", "minimum": 0.8}},
            "eval_model": "fixture", "model_name": "old-model", "run_id": "run-1",
            "output_root": str(root / "outputs"), "cache_root": str(root / "cache"),
            "eval_max_retries": 2, "retry_delay": 0, "progress_score_interval": 0}


class SnapshotAndReportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="accuracy-contract-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "config.json"
        self.path.write_text(json.dumps(config(self.root)))
        self.run_dir = self.root / "outputs/fixture/run-1"

    def main_context(self):
        stack = ExitStack()
        for target, kwargs in [("configure_environment", {}), ("verify_dataset", {}),
                               ("wait_for_service", {}), ("log", {}),
                               ("probe_service", {"return_value": (True, "local mock")})]:
            stack.enter_context(patch.object(llmrun, target, **kwargs))
        stack.enter_context(patch.object(llmrun.shutil, "which", return_value="/mock/lm_eval"))
        stack.enter_context(patch.object(sys, "argv", ["llmrun.py", str(self.path)]))
        return stack

    def test_source_is_read_once_and_snapshot_keeps_exact_original_bytes(self):
        original = self.path.read_bytes()
        changed = json.dumps({**config(self.root), "model_name": "new-model"}).encode()
        read_bytes = Path.read_bytes
        count = []

        def replace_after_read(path):
            data = read_bytes(path)
            if path == self.path:
                count.append(path)
                path.write_bytes(changed)
            return data

        with patch.object(Path, "read_bytes", replace_after_read):
            cfg = llmrun.load_config(self.path)
        self.assertEqual(len(count), 1)
        self.assertEqual(cfg["model_name"], "old-model")
        self.assertEqual(cfg["source_config_sha256"], hashlib.sha256(original).hexdigest())
        directory = llmrun.create_run_dir(cfg)
        self.assertEqual((directory / "source_config.json").read_bytes(), original)
        self.assertEqual(self.path.read_bytes(), changed)
        with self.assertRaises(FileExistsError):
            llmrun.create_run_dir(cfg)

    def test_parallel_preserves_first_invocation_source_snapshot(self):
        values = {"eval_model": "fixture", "api_list": "model:http://localhost/v1/chat/completions",
                  "run_id": "parallel", "output_root": str(self.root / "parallel")}
        original = json.dumps(values).encode()
        self.path.write_bytes(original)
        cfg = parallel.load_config(self.path)
        parallel.initialize_run(cfg)
        source = parallel.output_base(cfg) / "source_config.json"
        self.assertEqual(source.read_bytes(), original)
        cfg["merge_only"] = True
        parallel.initialize_run(cfg)
        self.assertEqual(source.read_bytes(), original)

    def fake_result(self, command, valid=False):
        output = Path(command[command.index("--output_path") + 1])
        data = {"results": {"example": {"exact_match,none": 1.0}}}
        (output / "results_1.json").write_text(json.dumps(data) if valid else "{malformed")
        if valid:
            (output / "samples_example_1.jsonl").write_text(json.dumps({"doc_id": 0, "resps": [["answer"]]}))
        return 0

    def test_malformed_results_retry_and_exhaustion_publishes_failed_report(self):
        with self.main_context(), patch.object(llmrun, "run_streaming", side_effect=lambda cmd, *_: self.fake_result(cmd)) as run:
            with self.assertRaises(SystemExit) as exc:
                llmrun.main()
        self.assertEqual(exc.exception.code, 1)
        self.assertEqual(run.call_count, 3)
        report = json.loads((self.run_dir / "acceptance-result.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failed_tasks"], ["example"])
        self.assertEqual(len(report["task_attempts"]["example"]), 3)
        self.assertIn("attempt-3", report["artifacts"]["example"]["results"]["path"])
        self.assertEqual(report["config_artifacts"]["source_config"]["sha256"], report["source_config_sha256"])
        self.assertEqual(list(self.run_dir.glob(".acceptance-result-*.tmp")), [])

    def test_malformed_first_result_can_retry_to_valid_current_attempt(self):
        attempts = []

        def result(cmd, *_):
            attempts.append(cmd)
            return self.fake_result(cmd, valid=len(attempts) == 2)

        with self.main_context(), patch.object(llmrun, "run_streaming", side_effect=result):
            llmrun.main()
        report = json.loads((self.run_dir / "acceptance-result.json").read_text())
        self.assertEqual(report["status"], "passed")
        self.assertEqual([item["status"] for item in report["task_attempts"]["example"]], ["failed", "passed"])
        self.assertIn("attempt-2", report["artifacts"]["example"]["results"]["path"])

    def test_structurally_invalid_result_metrics_fail_validation(self):
        cfg = llmrun.load_config(self.path)
        for value in ([], None, {"results": []}, {"results": {"example": [1]}}):
            with self.subTest(value=value), patch.object(llmrun, "log"):
                (self.root / "results_1.json").write_text(json.dumps(value))
                self.assertFalse(llmrun.report_result(cfg, "example", self.root))

    def test_unexpected_task_error_and_interrupt_still_publish_failed_report(self):
        for failure in (RuntimeError("synthetic setup failure"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                values = config(self.root)
                values["run_id"] = type(failure).__name__
                self.path.write_text(json.dumps(values))
                with self.main_context(), patch.object(llmrun, "run_task", side_effect=failure):
                    with self.assertRaises((RuntimeError, SystemExit)):
                        llmrun.main()
                report = json.loads((self.root / "outputs/fixture" / values["run_id"] / "acceptance-result.json").read_text())
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["failed_tasks"], ["example"])
                self.assertTrue(report["errors"])

    def test_cleanup_failure_aborts_without_retry_and_publishes_failed_report(self):
        with self.main_context(), patch.object(llmrun, "run_streaming", side_effect=llmrun.ProcessCleanupError("not reaped")) as run:
            with self.assertRaises(llmrun.ProcessCleanupError):
                llmrun.main()
        self.assertEqual(run.call_count, 1)
        report = json.loads((self.run_dir / "acceptance-result.json").read_text())
        self.assertEqual(report["status"], "failed")

    def test_terminal_report_does_not_overwrite_existing_history(self):
        cfg = llmrun.load_config(self.path)
        directory = llmrun.create_run_dir(cfg)
        report_path = directory / "acceptance-result.json"
        report_path.write_bytes(b"historical evidence")
        with self.assertRaises(FileExistsError):
            llmrun.write_acceptance_report(cfg, directory, ["example"], {}, ["failed"])
        self.assertEqual(report_path.read_bytes(), b"historical evidence")
        self.assertEqual(list(directory.glob(".acceptance-result-*.tmp")), [])

    def test_changed_effective_snapshot_cannot_publish_passing_report(self):
        cfg = llmrun.load_config(self.path)
        directory = llmrun.create_run_dir(cfg)
        (directory / "effective_config.json").write_text('{}')
        self.assertFalse(llmrun.write_acceptance_report(cfg, directory, [], {}, []))
        report = json.loads((directory / "acceptance-result.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failed_tasks"], ["example"])
        self.assertTrue(any("snapshot changed" in error for error in report["errors"]))


@unittest.skipUnless(os.name == "posix", "Owned sessions require POSIX")
class LocalProcessLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="accuracy-process-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.real_popen = subprocess.Popen
        self.children = []
        self.addCleanup(self.cleanup_children)
        self.sleeper = [sys.executable, "-B", "-u", "-c", "import time; time.sleep(60)"]

    def cleanup_children(self):
        for child in self.children:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=5)
            for stream in (child.stdout, child.stderr):
                if stream is not None:
                    stream.close()

    def spawn(self, *args, **kwargs):
        child = self.real_popen(*args, **kwargs)
        self.children.append(child)
        return child

    def test_sidecar_spawn_failure_reaps_real_worker_without_touching_other_process(self):
        unrelated = self.spawn(self.sleeper, start_new_session=True)
        for module in (llmrun, parallel):
            with self.subTest(runner=module.__name__):
                calls = []

                def spawn_then_fail(*args, **kwargs):
                    calls.append(args)
                    if len(calls) == 2:
                        raise OSError("synthetic sidecar spawn failure")
                    return self.spawn(*args, **kwargs)

                with patch.object(llmrun.subprocess, "Popen", side_effect=spawn_then_fail):
                    with self.assertRaisesRegex(OSError, "sidecar"):
                        module.run_streaming(self.sleeper, self.root / f"{module.__name__}.log", ["unexecuted-score"])
                self.assertIsNotNone(self.children[-1].poll())
                self.assertIsNone(unrelated.poll())

    def test_output_exception_reaps_real_worker_and_sidecar(self):
        command = [sys.executable, "-B", "-u", "-c", "import time; print('ready'); time.sleep(60)"]
        with patch.object(llmrun.subprocess, "Popen", side_effect=self.spawn), patch.object(llmrun, "log"), \
             patch("builtins.print", side_effect=BrokenPipeError("synthetic closed consumer")):
            with self.assertRaises(BrokenPipeError):
                llmrun.run_streaming(command, self.root / "broken.log", self.sleeper)
        self.assertEqual(len(self.children), 2)
        self.assertTrue(all(child.poll() is not None for child in self.children))

    def test_success_keeps_exit_code_and_reaps_silent_sidecar(self):
        command = [sys.executable, "-B", "-c", "raise SystemExit(7)"]
        with patch.object(llmrun.subprocess, "Popen", side_effect=self.spawn):
            result = llmrun.run_streaming(command, self.root / "done.log", self.sleeper)
        self.assertEqual(result, 7)
        self.assertTrue(all(child.poll() is not None for child in self.children))

    def test_cancel_event_stops_silent_threaded_worker(self):
        for module in (llmrun, parallel):
            with self.subTest(runner=module.__name__):
                started, cancel = threading.Event(), threading.Event()

                def spawn(*args, **kwargs):
                    process = self.spawn(*args, **kwargs)
                    started.set()
                    return process

                with patch.object(llmrun.subprocess, "Popen", side_effect=spawn), ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(module.run_streaming, self.sleeper, self.root / f"cancel-{module.__name__}.log", cancel_event=cancel)
                    self.assertTrue(started.wait(5))
                    cancel.set()
                    with self.assertRaises(llmrun.RunInterrupted):
                        future.result(timeout=8)
                self.assertIsNotNone(self.children[-1].poll())

    def test_parallel_main_interrupt_cancels_threads_before_executor_wait(self):
        started, cancel = threading.Event(), threading.Event()

        def worker(_cfg, _shard, _model, _url, event):
            started.set()
            return parallel.run_streaming(self.sleeper, self.root / "pool.log", cancel_event=event)

        def interrupted(_futures):
            self.assertTrue(started.wait(5))
            raise KeyboardInterrupt()

        with patch.object(parallel, "wait_for_services"), patch.object(parallel, "run_shard", side_effect=worker), \
             patch.object(parallel, "as_completed", side_effect=interrupted), \
             patch.object(llmrun.subprocess, "Popen", side_effect=self.spawn):
            with self.assertRaises(KeyboardInterrupt):
                parallel.execute_run({"shards": [0]}, [("fixture", "unused")], cancel)
        self.assertTrue(cancel.is_set())
        self.assertTrue(all(child.poll() is not None for child in self.children))

    def test_mock_cleanup_escalates_only_owned_group(self):
        worker = MagicMock(pid=456789)
        worker.wait.side_effect = [subprocess.TimeoutExpired("fixture", 5), 0]
        with patch.object(llmrun.os, "killpg") as killpg:
            llmrun.stop_owned_process(worker)
        self.assertEqual(killpg.call_args_list, [unittest.mock.call(456789, signal.SIGTERM),
                                                unittest.mock.call(456789, signal.SIGKILL)])
        self.assertEqual(worker.wait.call_count, 2)

    def test_mock_permission_denial_is_never_ignored(self):
        worker = MagicMock(pid=456789, stdout=io.StringIO(""))
        worker.poll.return_value = 0
        worker.wait.return_value = 0
        with patch.object(llmrun.subprocess, "Popen", return_value=worker), \
             patch.object(llmrun.os, "killpg", side_effect=PermissionError("synthetic EPERM")):
            with self.assertRaises(llmrun.ProcessCleanupError):
                llmrun.run_streaming(["never-executed"], self.root / "permission.log")

    def test_parallel_retry_service_wait_observes_cancellation(self):
        cancel = threading.Event()
        probed = threading.Event()

        def unavailable(*_):
            probed.set()
            return False, "local fixture"

        cfg = {"wait_for_service": True, "service_wait_timeout": 0, "service_poll_interval": 1800}
        with patch.object(parallel, "probe_service", side_effect=unavailable), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(parallel.wait_for_services, cfg, [("fixture", "unused")], cancel)
            self.assertTrue(probed.wait(5))
            cancel.set()
            with self.assertRaises(llmrun.RunInterrupted):
                future.result(timeout=3)

    def test_cancel_stops_real_owned_parent_and_child_group(self):
        pid_path = self.root / "owned-child.pid"
        leader_code = f"""
import signal, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(60)'])
def stop(_signal, _frame):
    child.wait(timeout=3)
    raise SystemExit(0)
signal.signal(signal.SIGTERM, stop)
Path({str(pid_path)!r}).write_text(str(child.pid))
time.sleep(60)
"""
        command = [sys.executable, "-B", "-c", leader_code]
        cancel = threading.Event()
        with patch.object(llmrun.subprocess, "Popen", side_effect=self.spawn), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(llmrun.run_streaming, command, self.root / "owned-child.log", cancel_event=cancel)
            deadline = time.monotonic() + 5
            while not pid_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            cancel.set()
            with self.assertRaises(llmrun.RunInterrupted):
                future.result(timeout=8)
        self.assertTrue(pid_path.exists())
        self.assertIsNotNone(self.children[-1].poll())
        with self.assertRaises(ProcessLookupError):
            os.kill(int(pid_path.read_text()), 0)

    @unittest.skipUnless(sys.platform.startswith("linux"),
                         "Linux target coverage: macOS may return EPERM for SIGKILL after TERM reaps an orphan group")
    def test_cancellation_also_stops_owned_descendant_after_leader_exit(self):
        # The leader exits immediately. Its descendant retains stdout and must
        # not keep the cancelled consumer or the old process group alive.
        pid_path = self.root / "descendant.pid"
        child_code = f"import os,time; from pathlib import Path; Path({str(pid_path)!r}).write_text(str(os.getpid())); time.sleep(60)"
        leader_code = f"import subprocess,sys; subprocess.Popen([sys.executable, '-B', '-c', {child_code!r}])"
        command = [sys.executable, "-B", "-c", leader_code]
        cancel = threading.Event()
        with patch.object(llmrun.subprocess, "Popen", side_effect=self.spawn), ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(llmrun.run_streaming, command, self.root / "descendant.log", cancel_event=cancel)
            deadline = time.monotonic() + 5
            while not pid_path.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            cancel.set()
            with self.assertRaises(llmrun.RunInterrupted):
                future.result(timeout=8)
        self.assertTrue(pid_path.exists())
        self.assertIsNotNone(self.children[-1].poll())
        descendant_pid = int(pid_path.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(descendant_pid, 0)
            except ProcessLookupError:
                break
            # A minimal container's PID 1 may not reap an adopted zombie. It
            # holds no executing client or open FD; do not require init policy.
            try:
                if Path(f"/proc/{descendant_pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
                    break
            except FileNotFoundError:
                break
            time.sleep(0.02)
        else:
            self.fail("Owned descendant was not reaped by the local OS after cancellation")

    def test_real_sigterm_produces_failed_report_and_reaps_local_eval(self):
        path, pid_path = self.root / "config.json", self.root / "worker.pid"
        path.write_text(json.dumps(config(self.root)))
        worker_code = f"import os,time; from pathlib import Path; Path({str(pid_path)!r}).write_text(str(os.getpid())); time.sleep(60)"
        command = [sys.executable, "-B", "-u", "-c", worker_code, "--output_path", "unused"]
        code = f"""
import sys
from unittest.mock import patch
sys.path.insert(0, {str(ACCURACY)!r})
import llmrun
sys.argv = ['llmrun.py', {str(path)!r}]
with patch.object(llmrun, 'configure_environment'), patch.object(llmrun, 'verify_dataset'), patch.object(llmrun, 'wait_for_service'), patch.object(llmrun.shutil, 'which', return_value='/mock/lm_eval'), patch.object(llmrun, 'build_command', return_value={command!r}):
    llmrun.main()
"""
        supervisor = self.spawn([sys.executable, "-B", "-c", code], start_new_session=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 5
        while not pid_path.exists() and supervisor.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(pid_path.exists())
        worker_pid = int(pid_path.read_text())
        supervisor.send_signal(signal.SIGTERM)
        stdout, stderr = supervisor.communicate(timeout=10)
        self.assertEqual(supervisor.returncode, 143, (stdout, stderr))
        with self.assertRaises(ProcessLookupError):
            os.kill(worker_pid, 0)
        report = json.loads((self.root / "outputs/fixture/run-1/acceptance-result.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failed_tasks"], ["example"])
        self.assertTrue(any("RunInterrupted" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
