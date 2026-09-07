"""Local-only regression checks: no model, accelerator or vLLM installation needed."""

import contextlib
import csv
import importlib.util
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("performance_under_test", ROOT / "test/perf_test/perf_common.py")
perf = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(perf)

BASE_ARGS = ["--model", "Example/Model", "--tokenizer", "/models/Example",
             "--max-model-len", "50000", "--case", "4096,1024,64,128"]
GOOD_OUTPUT = """Successful requests: 128
Benchmark duration (s): 10.0
Total input tokens: 524288
Total generated tokens: 131072
Request throughput (req/s): 12.8
Output token throughput (tok/s): 13107.2
Peak output token throughput (tok/s): 20000.0
Total token throughput (tok/s): 65536.0
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


class PerformanceHardeningTests(unittest.TestCase):
    def setUp(self):
        silence = contextlib.redirect_stdout(io.StringIO())
        silence.__enter__()
        self.addCleanup(silence.__exit__, None, None, None)

    def passing_run(self):
        return dict(perf.extract_metrics(GOOD_OUTPUT), status="passed", returncode=0,
                    validation_errors=[], elapsed_sec=10.0)

    def test_explicit_model_tokenizer_endpoint_and_service_target(self):
        args = perf.parse_args(BASE_ARGS + ["--host", "example-host", "--port", "8080",
                                            "--endpoint", "/v1/chat/completions"])
        command = perf.build_common_args(args)
        for flag, value in [("--model", "Example/Model"), ("--tokenizer", "/models/Example"),
                            ("--host", "example-host"), ("--port", "8080"),
                            ("--endpoint", "/v1/chat/completions"), ("--backend", "openai-chat")]:
            self.assertEqual(command[command.index(flag) + 1], value)

    def test_endpoint_selects_matching_wire_protocol_and_fixed_lengths(self):
        for endpoint, backend in (("/v1/completions", "vllm"),
                                  ("/v1/chat/completions", "openai-chat"),
                                  ("/gateway/v1/chat/completions", "openai-chat")):
            with self.subTest(endpoint=endpoint):
                args = perf.parse_args(BASE_ARGS + ["--endpoint", endpoint])
                command = perf.build_common_args(args)
                self.assertEqual(command[command.index("--backend") + 1], backend)
                self.assertEqual(command[command.index("--random-range-ratio") + 1], "0.0")
                self.assertEqual(command[command.index("--random-prefix-len") + 1], "0")
                self.assertIn("--ignore-eos", command)
        for endpoint in ("/v1/embeddings", "//example/v1/completions", "https://example/v1/completions",
                         "/v1/completions?backend=chat", "/v1/chat/completions/"):
            with self.subTest(endpoint=endpoint), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                perf.parse_args(BASE_ARGS + ["--endpoint", endpoint])

    def test_short_or_excess_output_is_not_a_completed_fixed_workload(self):
        args = perf.parse_args(BASE_ARGS)
        for count in (1, 131071, 131073):
            output = GOOD_OUTPUT.replace("Total generated tokens: 131072", f"Total generated tokens: {count}")
            with self.subTest(count=count), \
                 patch.object(perf.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")), \
                 patch.object(perf, "save_error_log"):
                result = perf.run_once(args.cases[0], 1, "/unused", args)
            self.assertEqual(result["status"], "failed")
            self.assertIn("fixed output budget", " ".join(result["validation_errors"]))
        self.assertEqual(perf.metric_errors(perf.extract_metrics(GOOD_OUTPUT), 128, 131072), [])

    def test_missing_identity_or_budget_is_rejected(self):
        for flag in ("--model", "--tokenizer", "--max-model-len"):
            argv = BASE_ARGS.copy()
            index = argv.index(flag)
            del argv[index:index + 2]
            with self.subTest(flag=flag), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                perf.parse_args(argv)

    def test_oversized_default_or_explicit_cases_never_launch(self):
        options = [BASE_ARGS[:-2], BASE_ARGS[:-1] + ["50000,1,1,1"],
                   BASE_ARGS[:-2] + ["--enable-all"]]
        for argv in options:
            with self.subTest(argv=argv), patch.object(perf.subprocess, "run") as run, \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                perf.main(argv)
            run.assert_not_called()
        exact = perf.parse_args(BASE_ARGS[:-1] + ["48976,1024,1,1"])
        self.assertEqual(sum(exact.cases[0][:2]), exact.max_model_len)

    def test_invalid_cases_warmup_or_port_are_rejected(self):
        for extra in [["--skip-first", "3"], ["--skip-first", "-1"], ["--port", "65536"],
                      ["--case", "0,1,1,1"], ["--case", "1,2,3"], ["--enable-all"]]:
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                perf.parse_args(BASE_ARGS + extra)

    def test_nonzero_exit_cannot_be_rescued_by_successful_request_count(self):
        args = perf.parse_args(BASE_ARGS)
        process = subprocess.CompletedProcess([], 1, GOOD_OUTPUT, "late worker failure")
        with patch.object(perf.subprocess, "run", return_value=process), \
             patch.object(perf, "save_error_log") as save:
            result = perf.run_once(args.cases[0], 1, "/unused", args)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["successful_requests"], 128)
        self.assertEqual(result["returncode"], 1)
        save.assert_called_once()

    def test_missing_and_nonfinite_metrics_fail(self):
        good = perf.extract_metrics(GOOD_OUTPUT)
        self.assertEqual(perf.metric_errors(good, 128), [])
        for key in perf.REQUIRED_METRICS:
            for value in [None, float("nan"), float("inf"), float("-inf")]:
                metrics = dict(good, **{key: value})
                with self.subTest(key=key, value=value):
                    self.assertTrue(perf.metric_errors(metrics, 128))
        for token in ("NaN", "inf", "-inf", "invalid"):
            text = GOOD_OUTPUT.replace("Mean TTFT (ms): 10.0", f"Mean TTFT (ms): {token}")
            self.assertTrue(perf.metric_errors(perf.extract_metrics(text), 128))

    def test_optional_peak_is_optional_but_invalid_value_fails(self):
        output = GOOD_OUTPUT.replace("Peak output token throughput (tok/s): 20000.0\n", "")
        self.assertEqual(perf.metric_errors(perf.extract_metrics(output), 128), [])
        invalid = GOOD_OUTPUT.replace("Peak output token throughput (tok/s): 20000.0",
                                      "Peak output token throughput (tok/s): invalid")
        self.assertTrue(perf.metric_errors(perf.extract_metrics(invalid), 128))

    def test_scientific_notation_and_exact_success_label(self):
        output = GOOD_OUTPUT.replace("Benchmark duration (s): 10.0", "Benchmark duration (s): 1e1")
        self.assertEqual(perf.extract_metrics(output)["benchmark_duration"], 10.0)
        output = output.replace("Successful requests:", "Unsuccessful requests:")
        self.assertIsNone(perf.extract_metrics(output)["successful_requests"])

    def test_missing_metric_with_zero_exit_marks_run_failed(self):
        args = perf.parse_args(BASE_ARGS)
        output = GOOD_OUTPUT.replace("Mean ITL (ms): 2.1\n", "")
        with patch.object(perf.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")), \
             patch.object(perf, "save_error_log"):
            result = perf.run_once(args.cases[0], 1, "/unused", args)
        self.assertEqual(result["status"], "failed")

    def test_failed_warmup_is_not_hidden_and_no_summary_is_written(self):
        args = perf.parse_args(BASE_ARGS)
        bad = dict(self.passing_run(), status="failed", returncode=1)
        with patch.object(perf, "run_once", side_effect=[bad, self.passing_run(), self.passing_run()]), \
             patch.object(perf, "append_csv") as write:
            summary, failed = perf.run_test_case(args.cases[0], "/unused.csv", "/unused", args)
        self.assertIsNone(summary)
        self.assertTrue(failed)
        self.assertEqual(write.call_count, 3)
        self.assertFalse(any(call.args[0]["Run"] == "SUMMARY" for call in write.call_args_list))
        self.assertEqual(write.call_args_list[0].args[0]["Run"], "Run1(FAILED)")

    def test_passing_case_averages_only_after_warmup(self):
        args = perf.parse_args(BASE_ARGS)
        runs = [dict(self.passing_run(), mean_ttft_ms=value) for value in (999, 10, 20)]
        with patch.object(perf, "run_once", side_effect=runs), patch.object(perf, "append_csv") as write:
            summary, failed = perf.run_test_case(args.cases[0], "/unused.csv", "/unused", args)
        self.assertFalse(failed)
        self.assertEqual(summary["Mean TTFT (ms)"], 15)
        self.assertEqual(write.call_count, 4)

    def test_average_rejects_empty_or_failed_runs(self):
        for runs in ([], [dict(self.passing_run(), status="failed")]):
            with self.assertRaises(ValueError):
                perf.average_metrics(runs)

    def test_cli_failure_and_exception_return_nonzero_without_overall_summary(self):
        for outcome in ((None, True), RuntimeError("vllm unavailable")):
            with tempfile.TemporaryDirectory() as directory, \
                 patch.object(perf, "run_test_case") as run, patch.object(perf, "print_summary") as summary:
                if isinstance(outcome, Exception):
                    run.side_effect = outcome
                else:
                    run.return_value = outcome
                self.assertEqual(perf.main(BASE_ARGS + ["--output-dir", directory]), 1)
                summary.assert_not_called()

    def test_cli_passing_run_returns_zero_with_summary(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(perf.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, GOOD_OUTPUT, "")):
            self.assertEqual(perf.main(BASE_ARGS + ["--output-dir", directory]), 0)
            files = list(Path(directory).rglob("*.csv"))
            self.assertEqual(len(files), 1)
            with files[0].open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[-1]["Run"], "SUMMARY")
            self.assertEqual(len(rows), 4)


if __name__ == "__main__":
    unittest.main()
