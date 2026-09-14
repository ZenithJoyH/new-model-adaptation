"""Cross-entrypoint and persisted-report tests; subprocesses and servers are mocked."""

import contextlib
import copy
import csv
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "test" / "perf_test"))
import perf_common as perf  # noqa: E402


ARGS = ["--model", "Example", "--tokenizer", "/models/Example", "--max-model-len", "8192",
        "--case", "4096,1024,2,4", "--runs", "3", "--skip-first", "1"]
GOOD = """Successful requests: 4
Failed requests: 0
Benchmark duration (s): 10.0
Total input tokens: 16384
Total generated tokens: 4096
Request throughput (req/s): 0.4
Output token throughput (tok/s): 409.6
Total token throughput (tok/s): 2048.0
Mean TTFT (ms): 10.0
Median TTFT (ms): 9.0
P99 TTFT (ms): 20.0
Mean TPOT (ms): 2.0
Median TPOT (ms): 1.9
P99 TPOT (ms): 3.0
Mean ITL (ms): 2.1
Median ITL (ms): 2.0
P99 ITL (ms): 3.1
"""


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        silence = contextlib.redirect_stdout(io.StringIO())
        silence.__enter__()
        self.addCleanup(silence.__exit__, None, None, None)

    def run_entry(self, entry, directory, outputs=None, extra=()):
        module = importlib.import_module(entry)
        flags = ARGS + ["--output-dir", str(directory)] + list(extra)
        if "profile" in entry and "--profile-dir" not in flags:
            flags.append("--no-profile")
        with patch.object(perf.subprocess, "run", side_effect=outputs or [subprocess.CompletedProcess([], 0, GOOD, "")] * 3) as run:
            rc = module.main(flags)
        paths = list(Path(directory).rglob("benchmark-result.json"))
        self.assertEqual(len(paths), 1)
        report = json.loads(paths[0].read_text())
        return rc, report, paths[0], run

    def test_every_entrypoint_uses_verified_reports_and_explicit_identity(self):
        for entry in ("vllm_perf", "sglang_perf", "vllm_profile", "sglang_profile", "all_perf"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as directory:
                rc, report, path, run = self.run_entry(entry, directory)
                self.assertEqual(rc, 0)
                self.assertEqual(perf.validate_report(report, path), [])
                self.assertEqual(report["request"]["model"], "Example")
                self.assertEqual(len(report["cases"][0]["runs"]), 3)
                self.assertEqual(report["cases"][0]["runs"][0]["run_id"], 1)
                command = run.call_args.args[0]
                if entry.startswith("sglang"):
                    self.assertIn("sglang.bench_serving", command)
                    self.assertNotIn("--endpoint", command)
                    self.assertNotIn("--ignore-eos", command)
                    self.assertNotIn("--random-prefix-len", command)
                    self.assertEqual(report["request"]["endpoint"], "/generate")
                else:
                    self.assertEqual(command[:3], ["vllm", "bench", "serve"])

    def test_failed_warmup_invalidates_all_entrypoints_without_any_summary(self):
        failed = subprocess.CompletedProcess([], 1, GOOD, "worker crashed after summary")
        good = subprocess.CompletedProcess([], 0, GOOD, "")
        for entry in ("vllm_perf", "sglang_perf", "vllm_profile", "sglang_profile", "all_perf"):
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as directory:
                rc, report, path, _ = self.run_entry(entry, directory, [failed, good, good])
                self.assertEqual(rc, 1)
                self.assertEqual(report["status"], "failed")
                self.assertEqual(report["cases"][0]["runs"][0]["returncode"], 1)
                self.assertIsNone(report["cases"][0]["summary"])
                self.assertTrue(perf.validate_report(report, path))
                with (path.parent / report["cases"][0]["csv"]["path"]).open() as stream:
                    rows = list(csv.DictReader(stream))
                self.assertFalse(any("SUMMARY" in row["Run"] for row in rows))

    def test_timeout_and_missing_executable_are_recorded_failures(self):
        for failure in (FileNotFoundError("missing executable"),
                        subprocess.TimeoutExpired("benchmark", 1, output=b"partial output")):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                rc, report, _, _ = self.run_entry("sglang_perf", directory, [failure] * 3)
                self.assertEqual(rc, 1)
                self.assertEqual(len(report["cases"][0]["runs"]), 3)
                for run in report["cases"][0]["runs"]:
                    self.assertIsNone(run["returncode"])
                    self.assertEqual(run["status"], "failed")
                    self.assertTrue(run["validation_errors"])

    def test_metrics_missing_short_nonfinite_or_explicit_failure_fail(self):
        for output in (GOOD.replace("Total generated tokens: 4096", "Total generated tokens: 1"),
                       GOOD.replace("Successful requests: 4", "Successful requests: 3"),
                       GOOD.replace("Failed requests: 0", "Failed requests: 1"),
                       GOOD.replace("Mean TTFT (ms): 10.0\n", ""),
                       GOOD.replace("Mean TTFT (ms): 10.0", "Mean TTFT (ms): nan"),
                       GOOD + "Successful requests: 4\n"):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as directory:
                rc, report, _, _ = self.run_entry("sglang_perf", directory,
                    [subprocess.CompletedProcess([], 0, output, "")] * 3)
                self.assertEqual(rc, 1)
                self.assertEqual(report["status"], "failed")

    def test_report_rejects_missing_runs_status_metrics_commands_and_tampered_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            _, original, path, _ = self.run_entry("vllm_perf", directory)
            mutations = (
                lambda report: report["cases"][0]["runs"].pop(0),
                lambda report: report["cases"][0]["runs"][0].update(returncode=1),
                lambda report: report["cases"][0]["runs"][0].update(returncode=False),
                lambda report: report["cases"][0]["runs"][0]["metrics"].update(total_output_tokens=1),
                lambda report: report["cases"][0]["runs"][0].update(command=["fake"]),
                lambda report: report["cases"][0]["summary"].update(**{"Req/s": 999}),
                lambda report: report["request"].update(skip_first=3),
                lambda report: report["request"].update(cases=[]),
                lambda report: report["request"].update(max_model_len=4096),
                lambda report: report["artifacts"][0].update(path="../outside.csv"),
                lambda report: report["artifacts"].append(dict(report["artifacts"][0])),
                lambda report: report.update(schema_version=True),
                lambda report: report.update(created_at="2026-09-06T10:00:00"),
                lambda report: report.update(producer={}),
            )
            for mutate in mutations:
                report = copy.deepcopy(original)
                mutate(report)
                self.assertTrue(perf.validate_report(report, path), mutate)
            csv_path = path.parent / original["cases"][0]["csv"]["path"]
            csv_path.write_text(csv_path.read_text().replace("SUMMARY", "FORGED"))
            self.assertTrue(perf.validate_report(original, path))
            # Rehashing the tampered CSV cannot hide disagreement with actual runs.
            report = copy.deepcopy(original)
            digest = perf.file_sha256(csv_path)
            report["cases"][0]["csv"]["sha256"] = digest
            for ref in report["artifacts"]:
                if ref["path"] == csv_path.name:
                    ref["sha256"] = digest
            self.assertTrue(perf.validate_report(report, path))

    def test_profile_requires_fresh_traces_and_does_not_mix_measurements(self):
        for engine in ("vllm", "sglang"):
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                traces = root / "server-traces"
                traces.mkdir()
                (traces / "stale.json").write_text("old")
                rc, failed, _, _ = self.run_entry(engine + "_profile", root / "failed",
                    extra=["--profile-dir", str(traces)])
                self.assertEqual(rc, 1)
                self.assertIn("no new or changed trace", " ".join(failed["cases"][0]["runs"][-1]["validation_errors"]))

                def benchmark(command, **kwargs):
                    output = GOOD
                    if "--profile" in command:
                        (traces / "new.json").write_text(json.dumps({"traceEvents": [
                            {"name": "model-step", "ph": "X", "ts": 1, "dur": 1}]}))
                        output = GOOD.replace("Mean TTFT (ms): 10.0", "Mean TTFT (ms): 100.0")
                    return subprocess.CompletedProcess(command, 0, output, "")

                entry = importlib.import_module(engine + "_profile")
                with patch.object(perf.subprocess, "run", side_effect=benchmark) as run:
                    self.assertEqual(entry.main(ARGS + ["--output-dir", str(root / "passed"),
                        "--profile-dir", str(traces)]), 0)
                path = next((root / "passed").rglob("benchmark-result.json"))
                report = json.loads(path.read_text())
                self.assertEqual(perf.validate_report(report, path), [])
                case = report["cases"][0]
                self.assertEqual(case["summary"]["Mean TTFT (ms)"], 10)
                self.assertEqual(case["profile_summary"]["Mean TTFT (ms)"], 100)
                self.assertEqual(["--profile" in call.args[0] for call in run.call_args_list], [False, False, True])

    def test_new_json_is_not_automatically_valid_profile_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traces = root / "traces"
            traces.mkdir()

            def benchmark(command, **kwargs):
                if "--profile" in command:
                    (traces / "not-a-trace.json").write_text('{"status":"ok"}')
                return subprocess.CompletedProcess(command, 0, GOOD, "")

            entry = importlib.import_module("vllm_profile")
            with patch.object(perf.subprocess, "run", side_effect=benchmark):
                self.assertEqual(entry.main(ARGS + ["--output-dir", str(root / "out"),
                    "--profile-dir", str(traces)]), 1)
            report = json.loads(next((root / "out").rglob("benchmark-result.json")).read_text())
            self.assertIn("no timed Chrome trace", " ".join(report["cases"][0]["runs"][-1]["validation_errors"]))

    def test_all_perf_legacy_parameters_and_dry_run_are_safe(self):
        entry = importlib.import_module("all_perf")
        identity_flags = ARGS[:6]
        with tempfile.TemporaryDirectory() as directory, patch.object(perf.subprocess, "run") as run:
            flags = identity_flags + ["--input-len", "4096", "--output-len", "1024", "--concurrency", "2",
                               "--dry-run", "--output-dir", directory]
            self.assertEqual(entry.main(flags), 0)
            run.assert_not_called()
            self.assertEqual(list(Path(directory).rglob("benchmark-result.json")), [])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            entry.main(identity_flags + ["--output-len", "1024", "--dry-run"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            entry.main(identity_flags + ["--num-prompts", "128", "--dry-run"])

    def test_invalid_identity_budget_protocol_and_duplicates_never_start(self):
        for engine, flags in (("sglang", ARGS + ["--endpoint", "/v1/chat/completions"]),
                              ("vllm", ARGS + ["--case", "4096,1024,2,4"]),
                              ("vllm", ARGS + ["--max-model-len", "4096"]),
                              ("sglang", ARGS + ["--model", ""])):
            with self.subTest(engine=engine), patch.object(perf.subprocess, "run") as run, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                perf.main(flags, engine=engine)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
