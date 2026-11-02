"""Offline provenance checks for explicitly authorized GPQA null-answer recovery.

Ordinary accuracy runs retain their existing empty-response rejection. This
contract accepts only the complete, original 198-response invocation, with null
responses independently evidenced as successful API length truncations.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import pickletools
import re
import sqlite3

from score_progress import generation_kwargs, normalize_exact, strict_extract

TASK = "gpqa_diamond_generative_cot"
POLICY = "gpqa-length-null-as-incorrect/v1"
EMPTY = "<TRUNCATED_EMPTY_CONTENT>"
COUNT = 198


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


class LocalArtifacts:
    """The producer uses the same approved-root/hash boundary as the gate."""
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)

    def file(self, ref):
        require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, "Invalid artifact reference")
        value = Path(ref["path"])
        require(".." not in value.parts, "Artifact traversal")
        path = (self.root / value).resolve(strict=True)
        require(path.is_relative_to(self.root) and path.is_file(), "Artifact outside approved root")
        require(digest(path) == ref["sha256"], "Artifact digest changed")
        return path

    def json(self, ref):
        return json.loads(self.file(ref).read_text())

    def logical_path(self, value):
        if not value:
            return ""
        path = Path(value)
        if not path.is_absolute():
            return {"relative": str(path)}
        resolved = path.resolve(strict=False)
        return {"root_relative": str(resolved.relative_to(self.root))} if resolved.is_relative_to(self.root) else {"absolute": str(path)}


def decode_scalar(blob):
    """Inspect only scalar protocol-5 cache values; never execute pickle."""
    blob = bytes(blob)
    if blob == bytes.fromhex("80054e2e"):
        return None
    allowed = {"PROTO", "FRAME", "SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8", "MEMOIZE", "STOP"}
    ops = list(pickletools.genops(blob))
    require(ops and ops[0][0].name == "PROTO" and ops[0][1] == 5
            and ops[-1][0].name == "STOP" and ops[-1][2] == len(blob) - 1, "Unsupported cache protocol")
    require(all(op.name in allowed for op, _, _ in ops), "Non-scalar pickle opcode")
    values = [value for op, value, _ in ops if op.name in {"SHORT_BINUNICODE", "BINUNICODE", "BINUNICODE8"}]
    require(len(values) == 1 and isinstance(values[0], str), "Cache value is not one scalar string")
    require(values[0].strip(), "Unapproved empty string response")
    return values[0]


def read_cache(path):
    connection = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        pairs = connection.execute('SELECT key, value FROM "unnamed"').fetchall()
    finally:
        connection.close()
    require(len(pairs) == COUNT, "Original cache must contain exactly 198 responses")
    require(len({key for key, _ in pairs}) == COUNT, "Duplicate cache keys")
    require(all(isinstance(key, str) and re.fullmatch("[0-9a-f]{64}", key) for key, _ in pairs), "Invalid cache key")
    return {key: decode_scalar(blob) for key, blob in pairs}


def api_responses(log_path, model_name, max_tokens, *, require_type_error=True):
    """Audit the actual pinned adapter log, including raw successful nulls."""
    responses = []
    terminal_type_error = False
    with Path(log_path).open(errors="strict") as stream:
        for line in stream:
            if line.startswith("TypeError: expected string or bytes-like object"):
                terminal_type_error = True
            if not re.search(r"INFO\s+\[models\.api_models:\d+\]\s+\[async\] get generate_until response, use [^,\n]+, output=", line):
                continue
            require(len(line) < 4 * 1024 * 1024, "Unexpected adapter log record size")
            raw = ast.literal_eval(line.split("output=", 1)[1].strip())
            require(isinstance(raw, dict) and not raw.get("error"), "Non-timeout API error cannot be recovered")
            require(raw.get("model") == model_name and len(raw.get("choices", [])) == 1, "Response model or choice drift")
            choice = raw["choices"][0]
            require(choice.get("index") == 0, "Unexpected choice index")
            content = choice["message"].get("content")
            if content is None:
                require(choice.get("finish_reason") == "length", "Null without length-truncation evidence")
                require(raw.get("usage", {}).get("completion_tokens") == max_tokens, "Null did not reach original output limit")
            else:
                require(isinstance(content, str) and content.strip(), "Unapproved empty/malformed API response")
            responses.append({"id": raw["id"], "content": content,
                              "finish_reason": choice.get("finish_reason"),
                              "response_sha256": canonical(raw)})
    require(not require_type_error or terminal_type_error, "Original native None scoring failure missing")
    require(len({item["id"] for item in responses}) == len(responses), "Repeated API response identity")
    return responses


def verify_normalized_native_report(terminal, rows, targets, reader):
    """Recognize the observed null-to-timeout conversion and excluded denominator."""
    refs = terminal["artifacts"][TASK]
    with reader.file(refs["samples"]).open(encoding="utf-8") as stream:
        samples = [json.loads(line) for line in stream if line.strip()]
    expected_filters = {item["name"] for item in targets["filter_list"]}
    require(expected_filters == {"strict-match", "flexible-extract"}, "Unexpected native filters")
    require(len(samples) == COUNT * len(expected_filters), "Incomplete original per-filter samples")
    seen = set()
    for sample in samples:
        doc_id, name = sample.get("doc_id"), sample.get("filter")
        require(type(doc_id) is int and 0 <= doc_id < COUNT and name in expected_filters, "Unexpected original sample identity")
        require((doc_id, name) not in seen, "Duplicate original per-filter sample")
        seen.add((doc_id, name))
        row = rows[doc_id]
        require(canonical(sample.get("doc")) == row["doc_hash"] and sample.get("target") == row["target"], "Original document or target changed")
        raw = row["raw_resps"][0][0]
        require(sample.get("resps") == [["<TIMEOUT>" if raw is None else raw]], "Original response differs from raw cache")
        require(sample.get("timeout") is (raw is None), "Unverified original timeout normalization")
        if name == "strict-match":
            require(sample.get("exact_match") == row["exact_match,strict-match"], "Original per-document strict score differs")
    nulls = sum(row["truncated_empty_content"] for row in rows)
    require(0 < nulls < COUNT and all(row["raw_resps"] != [["<TIMEOUT>"]] for row in rows), "Only proven null normalization is supported")
    result = reader.json(refs["results"])
    count = result["n-samples"][TASK]
    require(count.get("original") == count.get("effective") == COUNT and count.get("timeout") == nulls, "Original sample count drift")
    declared = result["results"][TASK]["exact_match,strict-match"]
    require(declared == sum(row["exact_match,strict-match"] for row in rows) / (COUNT - nulls), "Original excluded-denominator behavior differs")
    return {"original_native_denominator": COUNT - nulls, "original_reported_strict_metric": declared}


def recovery_inputs(config, reader):
    """Verify inputs without loading lm-eval or making any network requests."""
    import llmrun

    policy = config.get("offline_recovery", {})
    require(isinstance(policy, dict), "Invalid recovery policy")
    require(policy.get("policy") == POLICY and policy.get("user_authorized") is True, "Explicit user authorization is required")
    source = reader.json(policy["original_config"])
    require("offline_recovery" not in source, "Recovery cannot chain another recovery")
    require(source.get("tasks") == [TASK] and source.get("expected_samples") == COUNT, "Only original full GPQA Diamond198 is supported")
    require(source.get("limit") == 0 and source.get("api_max_retries") == 0 and source.get("eval_max_retries") == 0, "Original invocation must be full and have no retries")
    require(config.get("run_id") != source.get("run_id"), "Recovery needs its own run identity")
    excluded = {"run_id", "service_binding", "offline_recovery"}
    override = policy.get("threshold_override")
    if override is not None:
        require(isinstance(override, dict) and override.get("user_authorized") is True, "Threshold change requires explicit authorization")
        before = source["acceptance_criteria"][TASK]
        after = config["acceptance_criteria"][TASK]
        require(override.get("task") == TASK and override.get("metric") == before["metric"] == after["metric"], "Threshold override metric changed")
        require(override.get("from") == before["minimum"] and override.get("to") == after["minimum"], "Threshold override does not match frozen configurations")
        require(type(override["to"]) in (int, float) and 0 < override["to"] <= 1, "Invalid authorized threshold")
        require({k: v for k, v in before.items() if k != "minimum"} == {k: v for k, v in after.items() if k != "minimum"}
                and set(config["acceptance_criteria"]) == {TASK}, "Threshold override changed other criteria")
        excluded.add("acceptance_criteria")
    require({k: v for k, v in config.items() if k not in excluded} == {k: v for k, v in source.items() if k not in excluded}, "Recovery changed inference/data/threshold configuration")
    for key in ["deployment_fingerprint", "service_instance_id", "host_alias", "endpoint", "process_identity"]:
        require(config["service_binding"].get(key) == source["service_binding"].get(key), "Source service identity drift")
    original_effective = reader.json(policy["original_effective_config"])
    expected_effective = dict(llmrun.load_config(reader.file(policy["original_config"])))
    def normalized(value):
        return {k: reader.logical_path(v) if k in {"output_root", "cache_root", "include_path"} else v
                for k, v in value.items() if k != "run_nonce"}
    require(normalized(original_effective) == normalized(expected_effective), "Original effective configuration drift")
    require(re.fullmatch("[0-9a-f]{32}", original_effective.get("run_nonce", "")), "Missing original invocation nonce")
    require(digest(reader.file(policy["original_runner"])) == digest(llmrun.__file__), "Original inference runner changed")
    cache_identity = hashlib.sha256(json.dumps({"schema_version": 1, "task": TASK,
        "config": original_effective, "runner_sha256": policy["original_runner"]["sha256"]},
        sort_keys=True, allow_nan=False).encode()).hexdigest()
    original_cache = Path(original_effective["cache_root"]) / llmrun.safe_name(original_effective["eval_model"]) / source["run_id"] / TASK / cache_identity / "responses.sqlite_rank0.db"
    require(policy.get("original_cache_path") == str(original_cache), "Cache is not bound to the original configuration/nonce/runner")
    terminal = reader.json(policy["original_report"])
    require(terminal.get("kind") == "formal_accuracy" and terminal.get("status") in {"failed", "passed"} and terminal.get("errors") == [], "Original terminal native report must be retained")
    normalized_native = terminal["status"] == "passed"
    require(terminal.get("run_id") == source["run_id"] and terminal.get("source_config_sha256") == policy["original_config"]["sha256"], "Original report/config identity mismatch")
    for actual, expected in [("tasks", "tasks"), ("expected_samples", "expected_samples"),
                             ("criteria", "acceptance_criteria"), ("configured_concurrency", "num_concurrent"),
                             ("service_mode", "service_mode"), ("allow_timeouts", "allow_timeouts"),
                             ("service_binding", "service_binding")]:
        require(terminal.get(actual) == source.get(expected), "Original native report drift: " + actual)
    require(terminal.get("failed_tasks") == ([] if normalized_native else [TASK]), "Unexpected original task failure")
    attempts = terminal["task_attempts"][TASK]
    require(len(attempts) == 1 and attempts[0].get("returncode") == (0 if normalized_native else 1) and attempts[0].get("errors") == ([] if normalized_native else ["evaluation exited with code 1"]), "Original execution/retry outcome is unsupported")
    for name, ref in [("source_config", policy["original_config"]), ("effective_config", policy["original_effective_config"])]:
        require(digest(reader.file(terminal["config_artifacts"][name])) == ref["sha256"], "Original native snapshot mismatch")
    state = reader.json(policy["original_client_state"])
    require(state.get("state") == ("passed" if normalized_native else "failed") and state.get("returncode") == (0 if normalized_native else 1), "Original invocation has not terminated with the matching outcome")
    require([reader.logical_path(value) for value in state.get("command", [])[-2:]] ==
            [reader.logical_path(policy[name]["path"]) for name in ["original_runner", "original_config"]],
            "Original client executed a different runner/config")
    generation = reader.json(policy["generation_audit"])
    require(generation.get("task") == TASK and generation.get("expected_samples") == COUNT and generation.get("requests_sent") == 0, "Invalid original generation audit")
    kwargs = generation_kwargs(source["gen_kwargs"])
    require(generation.get("cli_gen_kwargs") == source["gen_kwargs"] and json.dumps(generation["effective_generation_kwargs"]) == json.dumps(kwargs), "Generation serialization drift")
    prompts = reader.json(policy["prompt_audit"])
    targets = reader.json(policy["target_audit"])
    require(prompts.get("task") == targets.get("task") == TASK and prompts.get("expected_samples") == targets.get("expected_samples") == COUNT, "Audit dataset scope mismatch")
    require(bool(targets.get("source_files")) and all(re.fullmatch("[0-9a-f]{64}", value) for value in targets["source_files"].values()), "Missing native evaluator source identities")
    require(targets.get("original_prompt_audit") == policy["prompt_audit"], "Prompt/target audit mismatch")
    require(targets.get("native_fixture_scores_correct_wrong_empty") == [1, 0, 0], "Native empty-answer fixture not verified")
    require(len(prompts["items"]) == len(targets["items"]) == COUNT, "Incomplete prompt/target audit")
    cache = read_cache(reader.file(policy["cache_snapshot"]))
    api = api_responses(reader.file(policy["original_stdout"]), source["model_name"], kwargs["max_gen_toks"], require_type_error=not normalized_native)
    non_timeouts = [value for value in cache.values() if value != "<TIMEOUT>"]
    require(Counter(canonical(value) for value in non_timeouts) == Counter(canonical(item["content"]) for item in api if item["content"] != "<TIMEOUT>"), "API log and original cache responses differ")
    rows = []
    used = set()
    for index, (prompt, target) in enumerate(zip(prompts["items"], targets["items"])):
        require(prompt.get("id") == target.get("id") == index, "Missing/duplicate/reordered original document")
        require(hashlib.sha256(prompt["prompt"].encode()).hexdigest() == target["prompt_sha256"], "Prompt audit changed")
        require(target.get("target") in ["(A)", "(B)", "(C)", "(D)"], "Invalid audited target")
        chat = json.dumps([{"role": "user", "content": prompt["prompt"]}], ensure_ascii=False)
        key = hashlib.sha256(json.dumps(["generate_until", [chat], kwargs]).encode()).hexdigest()
        require(key in cache and key not in used, "Unmatched or duplicate cache document")
        used.add(key)
        raw = cache[key]
        filtered = strict_extract("" if raw is None else raw)
        score = int(normalize_exact(filtered) == normalize_exact(target["target"]))
        require(raw is not None or score == 0, "Null answer cannot receive credit")
        rows.append({"doc_id": index, "target": target["target"], "doc_hash": target["doc_sha256"],
                     "prompt_hash": target["prompt_sha256"], "cache_key": key, "arguments": [chat, kwargs],
                     "raw_resps": [[raw]], "resps": [[EMPTY if raw is None else raw]],
                     "truncated_empty_content": raw is None, "strict_answer": filtered,
                     "exact_match,strict-match": score})
    require(used == set(cache), "Extra cached documents")
    normalized_proof = verify_normalized_native_report(terminal, rows, targets, reader) if normalized_native else {}
    return {"rows": rows, "source": source, "targets": targets, "generation": generation,
            "proof": {"kind": "gpqa_offline_recovery_proof", "policy": POLICY,
                      "original_native_status": terminal["status"], **normalized_proof,
                      "original_minimum": source["acceptance_criteria"][TASK]["minimum"],
                      "recovery_minimum": config["acceptance_criteria"][TASK]["minimum"],
                      "source_run_id": source["run_id"], "source_run_nonce": original_effective["run_nonce"],
                      "requests_sent": 0, "cache_rows": COUNT, "api_responses": len(api),
                      "api_response_ids_sha256": canonical(sorted(item["id"] for item in api)),
                      "truncated_empty_content": sum(row["truncated_empty_content"] for row in rows),
                      "strict_correct": sum(row["exact_match,strict-match"] for row in rows),
                      "timeouts": sum(row["raw_resps"] == [["<TIMEOUT>"]] for row in rows)}}


def validate_recovery_report(config, report, reader):
    """The gate recomputes every selected score from the original inputs."""
    data = recovery_inputs(config, reader)
    attempts = report["task_attempts"][TASK]
    require(len(attempts) == 1 and attempts[0].get("operation") == "score-existing-run", "Not an offline recovery attempt")
    require(attempts[0].get("requests_sent") == 0, "Recovery sent model requests")
    proof = reader.json(attempts[0]["recovery_proof"])
    require(proof.get("contract_sha256") == digest(__file__), "Recovery contract identity changed")
    require(proof.get("producer_sha256") == digest(Path(__file__).with_name("recover_gpqa.py")), "Recovery producer identity changed")
    require(proof.get("native_evaluator_source_hashes") == data["targets"]["source_files"], "Native evaluator identity changed")
    for key, value in data["proof"].items():
        require(proof.get(key) == value, "Recovery provenance/score mismatch: " + key)
    samples_path = reader.file(report["artifacts"][TASK]["samples"])
    with samples_path.open(encoding="utf-8") as stream:
        samples = [json.loads(line) for line in stream if line.strip()]
    require(len(samples) == COUNT, "Recovery sample coverage is incomplete")
    for sample, expected in zip(samples, data["rows"]):
        require(all(sample.get(key) == value for key, value in expected.items()), "Recovery altered raw response, target, order or score")
        require(sample.get("filtered_resps", {}).get("strict-match") == expected["strict_answer"], "Native strict filter disagrees")
    result = reader.json(report["artifacts"][TASK]["results"])
    score = data["proof"]["strict_correct"] / COUNT
    require(result["results"][TASK].get("exact_match,strict-match") == score, "Recovered aggregate mismatch")
