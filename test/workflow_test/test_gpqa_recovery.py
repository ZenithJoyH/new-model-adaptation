"""Provenance and failure-closed coverage for authorized offline GPQA recovery."""
import copy
import hashlib
import json
from pathlib import Path
import pickle
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "test/Accuracy_test"))
import gpqa_recovery_contract as contract
import llmrun


class RecoveryContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.reader = contract.LocalArtifacts(self.root)
        task = contract.TASK
        identity = {"container_id": "c" * 64, "boot_id": "12345678-abcd-1234-abcd-123456789abc",
                    "start_ticks": 123, "cmdline_sha256": "d" * 64}
        binding = {"service_instance_id": "service", "deployment_fingerprint": "f" * 64,
                   "host_alias": "host", "endpoint": "http://127.0.0.1:8000/v1/chat/completions",
                   "observation": {"path": "observation.json", "sha256": "f" * 64},
                   "process_identity": identity}
        original = {"formal_acceptance": True, "formal_contract_version": 2,
                    "service_mode": "graph", "tasks": [task], "expected_samples": 198,
                    "limit": 0, "allow_timeouts": True, "num_concurrent": 4,
                    "concurrency_reason": "Verified original capacity", "run_id": "original",
                    "eval_model": "fixture", "model_name": "fixture", "base_url": binding["endpoint"],
                    "api_max_retries": 0, "eval_max_retries": 0,
                    "gen_kwargs": "temperature=1,top_p=0.95,max_gen_toks=60000,do_sample=True",
                    "output_root": str(self.root / "outputs"), "cache_root": str(self.root / "cache"),
                    "acceptance_criteria": {task: {"metric": "exact_match,strict-match", "minimum": .88}},
                    "service_binding": binding}
        self.original_ref = self.put("original.json", original)
        effective = dict(llmrun.load_config(self.root / "original.json"))
        effective["run_nonce"] = "a" * 32
        effective_ref = self.put("effective.json", effective)
        failure = {"kind": "formal_accuracy", "status": "failed", "errors": [],
                   "failed_tasks": [task], "run_id": "original",
                   "source_config_sha256": self.original_ref["sha256"],
                   "config_artifacts": {"source_config": self.original_ref, "effective_config": effective_ref},
                   "task_attempts": {task: [{"returncode": 1, "errors": ["evaluation exited with code 1"]}]}}
        for actual, expected in [("tasks", "tasks"), ("expected_samples", "expected_samples"),
                                 ("criteria", "acceptance_criteria"), ("configured_concurrency", "num_concurrent"),
                                 ("service_mode", "service_mode"), ("allow_timeouts", "allow_timeouts"),
                                 ("service_binding", "service_binding")]:
            failure[actual] = original[expected]
        runner = self.root / "llmrun.py"
        runner.write_bytes(Path(llmrun.__file__).read_bytes())
        self.config = copy.deepcopy(original)
        self.config["run_id"] = "recovery"
        self.policy = {"policy": contract.POLICY, "user_authorized": True,
                       "original_config": self.original_ref, "original_effective_config": effective_ref,
                       "original_report": self.put("failed.json", failure),
                       "original_runner": self.ref(runner),
                       "original_client_state": self.put("state.json", {"state": "failed", "returncode": 1,
                           "command": ["python3", str(runner), str(self.root / "original.json")]})}
        cache_identity = hashlib.sha256(json.dumps({"schema_version": 1, "task": task,
            "config": effective, "runner_sha256": self.policy["original_runner"]["sha256"]}, sort_keys=True, allow_nan=False).encode()).hexdigest()
        self.policy["original_cache_path"] = str(Path(effective["cache_root"]) / effective["eval_model"] / "original" / task / cache_identity / "responses.sqlite_rank0.db")
        self.config["offline_recovery"] = self.policy
        kwargs = contract.generation_kwargs(original["gen_kwargs"])
        prompts = {"task": task, "expected_samples": 198,
                   "items": [{"id": i, "prompt": f"original question {i}"} for i in range(198)]}
        prompt_ref = self.put("prompts.json", prompts)
        targets = {"task": task, "expected_samples": 198, "original_prompt_audit": prompt_ref,
                   "native_fixture_scores_correct_wrong_empty": [1, 0, 0],
                   "source_files": {"/app/lm_eval/filters/extraction.py": "e" * 64},
                   "items": [{"id": i, "prompt_sha256": hashlib.sha256(item["prompt"].encode()).hexdigest(),
                              "target": "(A)", "doc_sha256": "d" * 64} for i, item in enumerate(prompts["items"])]}
        self.policy.update(prompt_audit=prompt_ref, target_audit=self.put("targets.json", targets),
                           generation_audit=self.put("generation.json", {"task": task, "expected_samples": 198,
                                                                       "requests_sent": 0, "cli_gen_kwargs": original["gen_kwargs"],
                                                                       "effective_generation_kwargs": kwargs}))
        self.db = self.root / "cache.db"
        self.api_records = []
        connection = sqlite3.connect(self.db)
        connection.execute("CREATE TABLE unnamed (key TEXT PRIMARY KEY,value BLOB)")
        for i, item in enumerate(prompts["items"]):
            raw = None if i == 0 else f"The best answer is (A). {i}"
            chat = json.dumps([{"role": "user", "content": item["prompt"]}], ensure_ascii=False)
            key = hashlib.sha256(json.dumps(["generate_until", [chat], kwargs]).encode()).hexdigest()
            connection.execute("INSERT INTO unnamed VALUES (?,?)", (key, pickle.dumps(raw, protocol=5)))
            self.api_records.append({"id": f"response-{i}", "model": "fixture", "choices": [
                {"index": 0, "message": {"content": raw}, "finish_reason": "length" if raw is None else "stop"}],
                "usage": {"completion_tokens": 60000 if raw is None else 12}})
        connection.commit()
        connection.close()
        self.policy["cache_snapshot"] = self.ref(self.db)
        self.write_log()

    def ref(self, path):
        return {"path": str(path), "sha256": contract.digest(path)}

    def put(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, indent=2))
        return self.ref(path)

    def write_log(self):
        path = self.root / "original.log"
        path.write_text("".join("2026-10-28:02:12:45 INFO     [models.api_models:438] [async] get generate_until response, use 0.01s, output=" + repr(item) + "\n" for item in self.api_records)
                        + "TypeError: expected string or bytes-like object\n")
        self.policy["original_stdout"] = self.ref(path)

    def inputs(self):
        return contract.recovery_inputs(self.config, self.reader)

    def normalized_native_fixture(self):
        targets = self.reader.json(self.policy["target_audit"])
        targets["filter_list"] = [{"name": name} for name in ["strict-match", "flexible-extract"]]
        samples = []
        for i, api in enumerate(self.api_records):
            doc = {"fixture_id": i}
            targets["items"][i]["doc_sha256"] = contract.canonical(doc)
            raw = api["choices"][0]["message"]["content"]
            for name in ["strict-match", "flexible-extract"]:
                samples.append({"doc_id": i, "doc": doc, "target": "(A)", "filter": name,
                                "resps": [["<TIMEOUT>" if raw is None else raw]],
                                "timeout": raw is None, "exact_match": 0 if raw is None else 1})
        self.policy["target_audit"] = self.put("targets.json", targets)
        samples_path = self.root / "native-samples.jsonl"
        samples_path.write_text("".join(json.dumps(x) + "\n" for x in samples))
        result = {"results": {contract.TASK: {"exact_match,strict-match": 1.0}},
                  "n-samples": {contract.TASK: {"original": 198, "effective": 198, "timeout": 1}}}
        terminal = self.reader.json(self.policy["original_report"])
        terminal.update(status="passed", failed_tasks=[], task_attempts={contract.TASK: [{"returncode": 0, "errors": []}]},
                        artifacts={contract.TASK: {"samples": self.ref(samples_path), "results": self.put("native-results.json", result)}})
        self.policy["original_report"] = self.put("normalized-native.json", terminal)
        state = self.reader.json(self.policy["original_client_state"])
        state.update(state="passed", returncode=0)
        self.policy["original_client_state"] = self.put("state.json", state)
        log = self.root / "original.log"
        log.write_text(log.read_text().replace("TypeError: expected string or bytes-like object\n", ""))
        self.policy["original_stdout"] = self.ref(log)
        return samples, terminal

    def test_native_pass_with_excluded_null_is_recovered_over_all_198(self):
        self.normalized_native_fixture()
        data = self.inputs()
        self.assertEqual(data["proof"]["original_native_status"], "passed")
        self.assertEqual(data["proof"]["original_native_denominator"], 197)
        self.assertEqual(data["proof"]["strict_correct"], 197)
        self.assertEqual(data["rows"][0]["raw_resps"], [[None]])

    def test_explicit_new_threshold_preserves_original_configuration(self):
        self.config["acceptance_criteria"][contract.TASK]["minimum"] = .85
        with self.assertRaises(ValueError):
            self.inputs()
        self.policy["threshold_override"] = {"user_authorized": True, "task": contract.TASK,
            "metric": "exact_match,strict-match", "from": .88, "to": .85}
        proof = self.inputs()["proof"]
        self.assertEqual((proof["original_minimum"], proof["recovery_minimum"]), (.88, .85))
        self.assertEqual(self.reader.json(self.original_ref)["acceptance_criteria"][contract.TASK]["minimum"], .88)
        self.policy["threshold_override"]["user_authorized"] = False
        with self.assertRaises(ValueError):
            self.inputs()

    def test_native_normalization_must_match_each_original_response(self):
        samples, terminal = self.normalized_native_fixture()
        samples[0]["resps"] = [["rewritten"]]
        path = self.root / "native-samples.jsonl"
        path.write_text("".join(json.dumps(x) + "\n" for x in samples))
        terminal["artifacts"][contract.TASK]["samples"] = self.ref(path)
        self.policy["original_report"] = self.put("normalized-native.json", terminal)
        with self.assertRaisesRegex(ValueError, "response differs"):
            self.inputs()

    def test_native_normalization_rejects_duplicate_filter_rows(self):
        samples, terminal = self.normalized_native_fixture()
        samples[-1] = samples[0]
        path = self.root / "native-samples.jsonl"
        path.write_text("".join(json.dumps(x) + "\n" for x in samples))
        terminal["artifacts"][contract.TASK]["samples"] = self.ref(path)
        self.policy["original_report"] = self.put("normalized-native.json", terminal)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.inputs()

    def test_ordinary_gate_rejects_timeout_exclusion_and_accepts_full_denominator(self):
        from acceptance_contract import sample_metric_errors
        _, terminal = self.normalized_native_fixture()
        path = self.reader.file(terminal["artifacts"][contract.TASK]["samples"])
        errors = sample_metric_errors(self.config, contract.TASK, {"exact_match,strict-match": 1.0}, path)
        self.assertTrue(errors)
        self.assertIn("all-198-document mean", errors[0])
        self.assertEqual(sample_metric_errors(self.config, contract.TASK, {"exact_match,strict-match": 197 / 198}, path), [])

    def test_full_original_null_is_retained_and_counted_in_denominator(self):
        data = self.inputs()
        self.assertEqual(data["proof"]["strict_correct"], 197)
        self.assertEqual(data["proof"]["cache_rows"], 198)
        self.assertEqual(data["proof"]["truncated_empty_content"], 1)
        self.assertEqual(data["rows"][0]["raw_resps"], [[None]])
        self.assertEqual(data["rows"][0]["resps"], [[contract.EMPTY]])
        self.assertEqual(data["rows"][0]["exact_match,strict-match"], 0)

    def test_without_authorization_or_with_changed_policy_fails(self):
        for field, value in [("user_authorized", False), ("policy", "allow-all-errors")]:
            with self.subTest(field=field):
                cfg = copy.deepcopy(self.config)
                cfg["offline_recovery"][field] = value
                with self.assertRaises(ValueError):
                    contract.recovery_inputs(cfg, self.reader)

    def test_live_run_or_missing_original_failure_fails(self):
        for state in [{"state": "running"}, {"state": "passed", "returncode": 0}]:
            self.policy["original_client_state"] = self.put("state.json", state)
            with self.assertRaises(ValueError):
                self.inputs()

    def test_configuration_or_service_drift_fails(self):
        changes = [("gen_kwargs", "max_gen_toks=100"), ("num_concurrent", 8),
                   ("acceptance_criteria", {contract.TASK: {"metric": "exact_match,strict-match", "minimum": .1}})]
        for key, value in changes:
            with self.subTest(key=key):
                cfg = copy.deepcopy(self.config)
                cfg[key] = value
                with self.assertRaises(ValueError):
                    contract.recovery_inputs(cfg, self.reader)
        cfg = copy.deepcopy(self.config)
        cfg["service_binding"]["process_identity"] = "other-process"
        with self.assertRaises(ValueError):
            contract.recovery_inputs(cfg, self.reader)

    def test_source_nonce_or_cache_origin_drift_fails(self):
        effective = self.reader.json(self.policy["original_effective_config"])
        effective["run_nonce"] = "b" * 32
        self.policy["original_effective_config"] = self.put("effective.json", effective)
        with self.assertRaisesRegex(ValueError, "Cache is not bound"):
            self.inputs()

    def test_null_without_actual_length_and_limit_is_rejected(self):
        for field, value in [("finish_reason", "stop"), ("completion_tokens", 59999)]:
            record = copy.deepcopy(self.api_records[0])
            if field == "finish_reason":
                self.api_records[0]["choices"][0][field] = value
            else:
                self.api_records[0]["usage"][field] = value
            self.write_log()
            with self.assertRaises(ValueError):
                self.inputs()
            self.api_records[0] = record

    def test_missing_cache_row_or_extra_response_is_rejected(self):
        connection = sqlite3.connect(self.db)
        connection.execute("DELETE FROM unnamed WHERE rowid=1")
        connection.commit()
        connection.close()
        self.policy["cache_snapshot"] = self.ref(self.db)
        with self.assertRaises(ValueError):
            self.inputs()

    def test_raw_response_rewrite_is_rejected(self):
        self.api_records[1]["choices"][0]["message"]["content"] = "rewritten answer"
        self.write_log()
        with self.assertRaises(ValueError):
            self.inputs()

    def test_recovery_report_recomputes_every_sample_and_aggregate(self):
        data = self.inputs()
        samples = copy.deepcopy(data["rows"])
        samples[1]["unicode_note"] = "first\u2028second"
        for row in samples:
            row["filtered_resps"] = {"strict-match": row["strict_answer"]}
        def save_samples():
            path = self.root / "samples.jsonl"
            path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in samples))
            return self.ref(path)
        proof = dict(data["proof"], contract_sha256=contract.digest(contract.__file__),
                     producer_sha256=contract.digest(ROOT / "test/Accuracy_test/recover_gpqa.py"),
                     native_evaluator_source_hashes=data["targets"]["source_files"])
        result = {"results": {contract.TASK: {"exact_match,strict-match": 197 / 198}}}
        report = {"task_attempts": {contract.TASK: [{"operation": "score-existing-run", "requests_sent": 0,
                    "recovery_proof": self.put("proof.json", proof)}]},
                  "artifacts": {contract.TASK: {"samples": save_samples(), "results": self.put("results.json", result)}}}
        contract.validate_recovery_report(self.config, report, self.reader)
        samples[0]["exact_match,strict-match"] = 1
        report["artifacts"][contract.TASK]["samples"] = save_samples()
        with self.assertRaises(ValueError):
            contract.validate_recovery_report(self.config, report, self.reader)
        samples[0]["exact_match,strict-match"] = 0
        report["artifacts"][contract.TASK]["samples"] = save_samples()
        result["results"][contract.TASK]["exact_match,strict-match"] = 1.0
        report["artifacts"][contract.TASK]["results"] = self.put("results.json", result)
        with self.assertRaises(ValueError):
            contract.validate_recovery_report(self.config, report, self.reader)

    def test_reordered_prompt_or_target_identity_is_rejected(self):
        targets = self.reader.json(self.policy["target_audit"])
        targets["items"][0], targets["items"][1] = targets["items"][1], targets["items"][0]
        self.policy["target_audit"] = self.put("targets.json", targets)
        with self.assertRaises(ValueError):
            self.inputs()

    def test_framework_gate_requires_recovery_proof_and_keeps_normal_checks(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import framework_evidence as gate
        data = self.inputs()
        binding = self.config["service_binding"]
        binding["observation"] = self.put("observation.json", {
            "run_id": "recovery", "host_alias": "host", "status": "verified", "pid": 123,
            "service_instance_id": "service", "nonce": "a" * 64, "listening_port": 8000,
            "process_identity": binding["process_identity"]})
        config_ref = self.put("recovery.json", self.config)
        cfg = llmrun.load_config(self.root / "recovery.json")
        directory = llmrun.create_run_dir(cfg)
        attempt = directory / contract.TASK / "attempt-1"
        attempt.mkdir(parents=True)
        samples = attempt / ("samples_" + contract.TASK + "_recovery.jsonl")
        for row in data["rows"]:
            row["filtered_resps"] = {"strict-match": row["strict_answer"]}
        samples.write_text("".join(json.dumps(row) + "\n" for row in data["rows"]))
        (attempt / "results_recovery.json").write_text(json.dumps({"results": {
            contract.TASK: {"exact_match,strict-match": 197 / 198}}}))
        proof = dict(data["proof"], contract_sha256=contract.digest(contract.__file__),
                     producer_sha256=contract.digest(ROOT / "test/Accuracy_test/recover_gpqa.py"),
                     native_evaluator_source_hashes=data["targets"]["source_files"])
        proof_ref = self.put("proof.json", proof)
        llmrun.write_acceptance_report(cfg, directory, [], {contract.TASK: [{
            "attempt": 1, "output_dir": str(attempt), "returncode": 0, "status": "passed", "errors": [],
            "operation": "score-existing-run", "requests_sent": 0, "recovery_proof": proof_ref}]}, [])
        framework = {"evidence_contract": 2, "deployment": {"fingerprint": "f" * 64},
                     "workspace": {"roots": [{"host_alias": "host", "host_root": str(self.root), "container_root": str(self.root)}]},
                     "acceptance_plan": {"accuracy_config_sha256": config_ref["sha256"]}}
        reader = gate.Artifacts(framework, "host", {"host": str(self.root)})
        native = {"config": config_ref, "report": self.ref(directory / "acceptance-result.json")}
        envelope = {"run_id": "recovery", "service_instance_id": "service", "scope": {"host_alias": "host"}}
        gate.native_accuracy(reader, native, envelope, framework)
        proof["requests_sent"] = 1
        (self.root / "proof.json").write_text(json.dumps(proof))
        with self.assertRaises(ValueError):
            gate.native_accuracy(reader, native, envelope, framework)

    def test_duplicate_api_identity_or_error_response_is_rejected(self):
        original = copy.deepcopy(self.api_records[1])
        self.api_records[1]["id"] = self.api_records[0]["id"]
        self.write_log()
        with self.assertRaises(ValueError):
            self.inputs()
        self.api_records[1] = original
        self.api_records[1]["error"] = "request failed"
        self.write_log()
        with self.assertRaises(ValueError):
            self.inputs()

    def test_unknown_pickle_and_blank_string_remain_invalid(self):
        for value in [[], {"text": "answer is A."}, ""]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                contract.decode_scalar(pickle.dumps(value, protocol=5))
        self.assertIsNone(contract.decode_scalar(pickle.dumps(None, protocol=5)))
        with self.assertRaises(ValueError):
            contract.decode_scalar(pickle.dumps("answer", protocol=5) + b"trailing data")

    def test_digest_drift_and_path_escape_are_rejected(self):
        (self.root / "targets.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.inputs()
        with self.assertRaises(ValueError):
            self.reader.file({"path": "../outside", "sha256": "a" * 64})

    def test_normal_formal_sample_rule_still_rejects_null(self):
        path = self.root / "samples.jsonl"
        path.write_text(json.dumps({"doc_id": 0, "resps": [[None]]}) + "\n")
        cfg = copy.deepcopy(self.config)
        cfg["expected_samples"] = 1
        self.assertFalse(llmrun.validate_samples(cfg, contract.TASK, self.root, samples_file=path))


if __name__ == "__main__":
    unittest.main()
