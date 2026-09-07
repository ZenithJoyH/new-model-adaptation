"""Compact performance evidence gates; all benchmark processes are mocked."""

import copy
from datetime import date
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_evidence_and_acceptance as fixtures
from test_performance_hardening import BASE_ARGS, GOOD_OUTPUT

ROOT, workflow = fixtures.ROOT, fixtures.workflow
sys.path.insert(0, str(ROOT / "test/perf_test"))
import perf_common
import perf_acceptance


class PerformanceEvidenceTests(unittest.TestCase):
    def setUp(self):
        fixtures.EvidenceTests.setUp(self)
        self.cfg = self.platform_config
        acceptance = self.platform / "acceptance"
        acceptance.mkdir()
        self.accuracy_config = acceptance / "llm_config.json"
        self.accuracy_config.write_text(json.dumps(fixtures.formal_config()))
        self.runtime_path = self.platform / "environment/runtime-config.yml"
        runtime = workflow.load_yaml(ROOT / "templates/adaptation/runtime-config.yml")
        runtime.update(model="Example", platform="ppu", configuration_status="ready")
        runtime["target"].update(hosts=["PPU-01"], container_name="example", container_image="example-image")
        for item in runtime["stack"].values():
            item.update(path="/workspace/code", revision="a" * 40)
        runtime["service"].update(model_path="/models/Example", served_model_name="Example/Model",
                                   port=8010, tensor_parallel_size=1)
        runtime["service"]["max_model_len"].update(model_supported=50000, initial=50000, evidence="model-config")
        runtime["acceptance"].update(graph_base_url="http://127.0.0.1:8010",
                                     accuracy_config=str(self.accuracy_config.relative_to(self.root)))
        workflow.write_yaml(self.runtime_path, runtime)
        fixtures.EvidenceTests.bind_identity(self)
        self.instance = "actual-performance-instance"
        for stage in ("architecture", "environment", "adaptation", "execution-mode", "sanity", "accuracy"):
            path = self.platform / (stage + ".md")
            contents = "A verified controlled experiment."
            if stage == "accuracy":
                contents = json.dumps({"kind": "formal_accuracy", "status": "passed", "service_mode": "graph",
                    "failed_tasks": [], "configured_concurrency": 32,
                    "source_config_sha256": workflow.file_sha256(self.accuracy_config),
                    "run_id": "run-accuracy", "expected_samples": 2,
                    "criteria": fixtures.formal_config()["acceptance_criteria"], "allow_timeouts": False})
            path.write_text(contents)
            self.bind(stage, path, "run-" + stage)
        output = self.root / "remote-artifacts"
        with patch.object(perf_common.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, GOOD_OUTPUT, "")), \
             patch("sys.stdout", io.StringIO()):
            self.assertEqual(perf_common.main(BASE_ARGS + ["--output-dir", str(output)]), 0)
        self.report_path = next(output.rglob("benchmark-result.json"))
        self.report = json.loads(self.report_path.read_text())
        self.compact = self.export()
        self.compact_path = acceptance / "performance-acceptance.json"

    def bind(self, stage, path, run_id):
        record = {"run_id": run_id, "last_verified": date.today().isoformat(),
                  "evidence": str(path.relative_to(self.platform)), "evidence_sha256": workflow.file_sha256(path),
                  "context_sha256": workflow.context_sha256(self.platform, stage, self.cfg),
                  "service_instance_id": self.instance}
        if stage in workflow.ACCEPTANCE_SUBSTEPS:
            self.cfg["workflow"]["acceptance"]["records"][stage] = record
            self.cfg["workflow"]["acceptance"]["substeps"][stage] = "passed"
        else:
            self.cfg["workflow"][stage].update(status="passed", evidence=record["evidence"], verification=record)
        workflow.write_yaml(self.platform / "platform.yml", self.cfg)
        return record

    def export(self, **changes):
        options = dict(model="Example", platform="ppu", service_instance_id=self.instance,
                       deployment_fingerprint=workflow.deployment_fingerprint(self.platform))
        options.update(changes)
        return perf_acceptance.export_evidence(self.report_path, self.runtime_path, **options)

    def verify(self, compact):
        self.compact_path.write_text(json.dumps(compact))
        record = self.bind("performance", self.compact_path, self.report["run_id"])
        return workflow.verification_errors(record, self.platform, "performance", self.cfg)

    def test_full_artifact_validation_exports_compact_platform_evidence(self):
        self.assertEqual(self.verify(self.compact), [])
        self.assertEqual(workflow.check_acceptance_dependencies(self.cfg, ["evidence"], self.platform), [])
        serialized = json.dumps(self.compact)
        self.assertNotIn('"stdout"', serialized)
        self.assertNotIn('"traces"', serialized)
        self.assertLess(len(serialized), 12000)
        self.assertEqual(self.compact["source_report"]["sha256"], workflow.file_sha256(self.report_path))

    def test_local_gate_needs_no_raw_remote_files(self):
        remote_dir = self.report_path.parent
        remote_dir.rename(remote_dir.with_name(remote_dir.name + "-offline"))
        self.assertFalse(self.report_path.exists())
        self.assertEqual(self.verify(self.compact), [])

    def test_profile_and_plain_summaries_remain_distinct_without_local_traces(self):
        traces = self.root / "service-traces"
        traces.mkdir()
        output = self.root / "profile-benchmark"

        def fake_benchmark(command, **kwargs):
            if "--profile" in command:
                (traces / "trace.json").write_text(json.dumps({"traceEvents": [{"name": "kernel", "ph": "X", "ts": 1}]}))
            return subprocess.CompletedProcess(command, 0, GOOD_OUTPUT, "")

        with patch.object(perf_common.subprocess, "run", side_effect=fake_benchmark), patch("sys.stdout", io.StringIO()):
            self.assertEqual(perf_common.main(BASE_ARGS + ["--output-dir", str(output), "--profile-dir", str(traces),
                                                          "--runs", "3", "--skip-first", "1"], profile=True), 0)
        self.report_path = next(output.rglob("benchmark-result.json"))
        self.report = json.loads(self.report_path.read_text())
        compact = self.export()
        self.assertEqual(compact["cases"][0]["summary"]["Run"], "SUMMARY")
        self.assertEqual(compact["cases"][0]["profile_summary"]["Run"], "PROFILE_SUMMARY")
        remote_dir = self.report_path.parent
        remote_dir.rename(remote_dir.with_name(remote_dir.name + "-offline"))
        self.assertEqual(self.verify(compact), [])

    def test_failed_raw_report_and_plain_failure_cannot_satisfy_performance(self):
        for contents in ("FAILED: worker crashed",
                         json.dumps({"kind": "benchmark-result", "status": "failed", "errors": ["worker crashed"]}),
                         json.dumps(dict(self.compact, kind="model-performance-review"))):
            self.compact_path.write_text(contents)
            record = self.bind("performance", self.compact_path, self.report["run_id"])
            self.assertTrue(workflow.verification_errors(record, self.platform, "performance", self.cfg))
            self.assertTrue(workflow.check_acceptance_dependencies(self.cfg, ["evidence"], self.platform))

    def test_vllm_openai_base_routes_preserve_prefix_without_duplicate_version(self):
        routes = (
            ("", "/v1/completions", True),
            ("/v1/", "/v1/completions", True),
            ("/v1", "/v1/chat/completions", True),
            ("/v1", "/v1/v1/completions", False),
            ("/v1", "/v1/v1/chat/completions", False),
            ("/proxy", "/proxy/v1/completions", True),
            ("/proxy/v1", "/proxy/v1/chat/completions", True),
            ("/proxy/v1", "/proxy/v1/v1/completions", False),
            ("/proxy/v1", "/v1/completions", False),
            ("/proxy/v1/completions", "/proxy/v1/completions", True),
            ("/proxy/v1/completions", "/proxy/v1/chat/completions", False),
        )
        for base_path, endpoint, valid in routes:
            runtime = workflow.load_yaml(self.runtime_path)
            runtime["acceptance"]["graph_base_url"] = "http://127.0.0.1:8010" + base_path
            request = dict(self.compact["request"], endpoint=endpoint,
                           backend="openai-chat" if endpoint.endswith("/chat/completions") else "vllm")
            with self.subTest(base_path=base_path, endpoint=endpoint):
                self.assertEqual(perf_acceptance._request_errors(request, runtime), [] if valid else
                                 ["performance API path does not match graph_base_url"])

    def test_sglang_openai_base_maps_to_native_route_without_dropping_proxy_prefix(self):
        for base_path, valid in (("", True), ("/", True), ("/v1", True), ("/v1/", True),
                                 ("/generate", True), ("/proxy/v1", False), ("/proxy", False),
                                 ("/v1/v1", False), ("/other", False)):
            runtime = workflow.load_yaml(self.runtime_path)
            runtime["acceptance"]["graph_base_url"] = "http://127.0.0.1:8010" + base_path
            request = dict(self.compact["request"], engine="sglang", backend="sglang", endpoint="/generate")
            with self.subTest(base_path=base_path):
                self.assertEqual(perf_acceptance._request_errors(request, runtime), [] if valid else
                                 ["performance API path does not match graph_base_url"])

    def test_sglang_full_report_exports_against_openai_service_base(self):
        runtime = workflow.load_yaml(self.runtime_path)
        runtime["acceptance"]["graph_base_url"] = "http://127.0.0.1:8010/v1"
        workflow.write_yaml(self.runtime_path, runtime)
        fixtures.EvidenceTests.bind_identity(self)
        output = self.root / "sglang-artifacts"
        with patch.object(perf_common.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, GOOD_OUTPUT, "")), \
             patch("sys.stdout", io.StringIO()):
            self.assertEqual(perf_common.main(BASE_ARGS + ["--port", "8010", "--output-dir", str(output)], engine="sglang"), 0)
        self.report_path = next(output.rglob("benchmark-result.json"))
        self.report = json.loads(self.report_path.read_text())
        compact = self.export()
        self.assertEqual(compact["request"]["endpoint"], "/generate")
        self.assertEqual(self.verify(compact), [])

    def test_failed_or_corrupt_source_cannot_be_exported(self):
        failed = dict(self.report, status="failed", errors=["worker failed"])
        self.report_path.write_text(json.dumps(failed))
        with self.assertRaises(ValueError):
            self.export()
        self.report_path.write_text(json.dumps(self.report))
        artifact = self.report_path.parent / self.report["cases"][0]["runs"][0]["stdout"]["path"]
        artifact.write_text("incomplete output")
        with self.assertRaises(ValueError):
            self.export()

    def test_case_scope_coverage_metrics_and_validation_markers_are_checked(self):
        changes = (
            lambda c: c.update(status="failed"),
            lambda c: c.update(run_id="another-run"),
            lambda c: c["scope"].update(model="Other"),
            lambda c: c["scope"].update(platform="nvidia"),
            lambda c: c["scope"].update(service_instance_id="other-instance"),
            lambda c: c["scope"].update(deployment_fingerprint="0" * 64),
            lambda c: c["scope"].update(runtime_config_sha256="0" * 64),
            lambda c: c["request"].update(model="WrongModel"),
            lambda c: c["request"].update(host="other-host"),
            lambda c: c["request"].update(port=9999),
            lambda c: c["request"].update(endpoint="/other/v1/completions"),
            lambda c: c["request"].update(max_model_len=65536),
            lambda c: c["request"].update(cases=[[50000, 1024, 64, 128]]),
            lambda c: c["validation"].update(status="failed"),
            lambda c: c["validation"].update(artifacts_verified=0),
            lambda c: c["validation"].update(artifacts_verified=1),
            lambda c: c["validation"].update(runs_verified=1),
            lambda c: c["source_report"].update(sha256="not-a-digest"),
            lambda c: c["source_report"].update(path="not-an-absolute-source-path"),
            lambda c: c["request"].update(run_timeout=None),
            lambda c: c.update(cases=[]),
            lambda c: c["cases"][0]["summary"].update({"Req/s": float("nan")}),
            lambda c: c["cases"][0]["summary"].update({"Total Output Tokens": 1}),
            lambda c: c["cases"][0].update(profile_summary=c["cases"][0]["summary"]),
        )
        for index, change in enumerate(changes):
            compact = copy.deepcopy(self.compact)
            change(compact)
            with self.subTest(index=index):
                self.assertTrue(self.verify(compact))

    def test_export_rejects_wrong_runtime_or_explicit_tokenizer_scope(self):
        with self.assertRaises(ValueError):
            self.export(model="AnotherModel")
        runtime = workflow.load_yaml(self.runtime_path)
        runtime["service"]["tokenizer"] = "/different/tokenizer"
        workflow.write_yaml(self.runtime_path, runtime)
        fixtures.EvidenceTests.bind_identity(self)
        with self.assertRaises(ValueError):
            self.export()

    def test_export_cli_does_not_overwrite_existing_evidence(self):
        self.compact_path.write_text("user-owned evidence")
        argv = ["--report", str(self.report_path), "--runtime-config", str(self.runtime_path),
                "--output", str(self.compact_path), "--model", "Example", "--platform", "ppu",
                "--service-instance-id", self.instance, "--deployment-fingerprint", workflow.deployment_fingerprint(self.platform)]
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit) as caught:
            perf_acceptance.main(argv)
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(self.compact_path.read_text(), "user-owned evidence")


if __name__ == "__main__":
    unittest.main()
