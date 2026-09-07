#!/usr/bin/env python3
"""Export a compact performance receipt after validating the full remote artifacts.

The compact receipt is a trusted validation record, not a signature or a way to
replay unavailable remote traces locally. Keep its source report and artifacts.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import urlsplit

import yaml

import perf_common as benchmark


def digest(data):
    return hashlib.sha256(data).hexdigest()


def is_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _time(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timestamp must include timezone")
    return stamp


def _request_errors(request, runtime):
    errors = []
    if not isinstance(request, dict):
        return ["performance request must be a mapping"]
    service, acceptance = runtime.get("service"), runtime.get("acceptance")
    if not isinstance(service, dict) or not isinstance(acceptance, dict):
        return ["runtime service/acceptance must be mappings"]
    if not isinstance(request.get("model"), str) or request["model"] != service.get("served_model_name"):
        errors.append("performance request model does not match served_model_name")
    if not isinstance(request.get("tokenizer"), str) or not request["tokenizer"].strip():
        errors.append("performance tokenizer is missing")
    elif service.get("tokenizer") and request["tokenizer"] != service["tokenizer"]:
        errors.append("performance tokenizer does not match the explicitly declared service tokenizer")
    host, port, endpoint = request.get("host"), request.get("port"), request.get("endpoint")
    if not isinstance(host, str) or not host.strip() or type(port) is not int or not 0 < port <= 65535:
        errors.append("performance request host/port is invalid")
    if not isinstance(endpoint, str) or not endpoint.startswith("/") or endpoint.startswith("//") or any(c.isspace() or c in "?#" for c in endpoint):
        errors.append("performance endpoint is invalid")
        endpoint = ""
    engine, backend = request.get("engine"), request.get("backend")
    if engine == "vllm":
        expected = "openai-chat" if endpoint.endswith("/chat/completions") else "vllm" if endpoint.endswith("/completions") else None
        if expected is None or backend != expected:
            errors.append("performance vLLM backend/endpoint mismatch")
    elif engine == "sglang":
        if backend != "sglang" or endpoint != "/generate":
            errors.append("performance SGLang backend/endpoint mismatch")
    else:
        errors.append("unsupported performance engine")
    try:
        base = urlsplit(acceptance.get("graph_base_url", ""))
        # Current benchmark wrappers pass host/port, not an HTTPS/base-url option.
        if base.scheme != "http" or not base.hostname or base.username or base.password or base.query or base.fragment:
            raise ValueError("expected a credential-free HTTP graph_base_url")
        base_port = 80 if base.port is None else base.port
        if not 0 < base_port <= 65535:
            raise ValueError("invalid graph service port")
        if not isinstance(host, str) or host.strip("[]").lower() != base.hostname.lower() or port != base_port:
            errors.append("performance host/port does not match graph_base_url")
        prefix = base.path.rstrip("/")
        if engine == "vllm":
            if prefix.endswith("/completions"):
                allowed = {prefix}
            else:
                suffixes = ("/completions", "/chat/completions")
                # An OpenAI base URL already ending in /v1 must not acquire a
                # second version component. Preserve any reverse-proxy prefix.
                roots = (prefix,) if prefix.endswith("/v1") else (prefix, prefix + "/v1")
                allowed = {root + suffix for root in roots for suffix in suffixes}
        else:
            # SGLang's native benchmark uses /generate on the same service as
            # its OpenAI /v1 API. Strip only that terminal API component, never
            # an unrelated proxy prefix (which this client cannot address).
            root = prefix[:-3] if prefix.endswith("/v1") else prefix
            allowed = {root} if root.endswith("/generate") else {root + "/generate"}
        if endpoint not in allowed:
            errors.append("performance API path does not match graph_base_url")
    except (ValueError, TypeError, AttributeError):
        errors.append("runtime graph_base_url is invalid or unsupported by this benchmark client")
    max_len = service.get("max_model_len")
    budget = max_len.get("current", max_len.get("initial")) if isinstance(max_len, dict) else None
    if type(budget) is not int or budget <= 0:
        errors.append("runtime must declare a positive service context budget")
    if type(request.get("max_model_len")) is not int or request["max_model_len"] <= 0:
        errors.append("performance context budget is invalid")
    elif type(budget) is int and request["max_model_len"] > budget:
        errors.append("performance context budget exceeds the declared service budget")
    runs, skip = request.get("runs"), request.get("skip_first")
    if type(runs) is not int or runs <= 0 or type(skip) is not int or not 0 <= skip < runs:
        errors.append("performance runs/warmup is invalid")
    if type(request.get("profiling_requested")) is not bool or request.get("profile_runs") not in ("first", "last", "all"):
        errors.append("performance profiling selection is invalid")
    if type(request.get("run_timeout")) is not int or request["run_timeout"] <= 0:
        errors.append("performance run timeout is invalid")
    for field in ("output_dir", "python_executable"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            errors.append(f"performance request.{field} is missing")
    cases = request.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("performance case set is empty")
    elif any(not isinstance(case, list) or len(case) != 4 or any(type(v) is not int or v <= 0 for v in case) for case in cases):
        errors.append("performance case shape is invalid")
    elif len({tuple(case) for case in cases}) != len(cases):
        errors.append("performance case set contains duplicates")
    elif type(request.get("max_model_len")) is int and any(sum(case[:2]) > request["max_model_len"] for case in cases):
        errors.append("performance case exceeds the requested context budget")
    return errors


def validate_evidence(evidence, *, runtime, runtime_sha256, model, platform,
                      deployment_fingerprint, service_instance_id, run_id):
    """Validate compact provenance/scope without needing any raw remote artifact."""
    errors = []
    try:
        if not isinstance(evidence, dict) or type(evidence.get("schema_version")) is not int or evidence["schema_version"] != 1 or evidence.get("kind") != "formal_performance":
            return ["performance requires a compact formal_performance validation receipt"]
        if evidence.get("status") != "passed" or evidence.get("errors") != []:
            return ["performance evidence is not an error-free pass"]
        if not isinstance(run_id, str) or not run_id.strip() or evidence.get("run_id") != run_id:
            errors.append("performance report and verification run_id differ")
        scope = evidence.get("scope")
        expected = {"model": model, "platform": platform, "service_instance_id": service_instance_id,
                    "deployment_fingerprint": deployment_fingerprint, "runtime_config_sha256": runtime_sha256}
        if (not isinstance(service_instance_id, str) or not service_instance_id.strip()
                or not isinstance(scope, dict) or any(scope.get(k) != v for k, v in expected.items())):
            errors.append("performance model/platform/service/deployment/runtime scope does not match this verification")
        if runtime.get("model") != model or runtime.get("platform") != platform:
            errors.append("runtime model/platform identity mismatch")
        if not is_digest(runtime_sha256) or not is_digest(deployment_fingerprint):
            errors.append("performance runtime/deployment fingerprints must be SHA-256")
        source = evidence.get("source_report")
        if not isinstance(source, dict) or not isinstance(source.get("path"), str) or not Path(source["path"]).is_absolute() or not is_digest(source.get("sha256")) or not is_digest(source.get("producer_sha256")):
            errors.append("performance source report provenance is missing")
        validation = evidence.get("validation")
        if (not isinstance(validation, dict) or validation.get("method") != "perf_common.validate_report"
                or validation.get("status") != "passed" or validation.get("errors") != []
                or not is_digest(validation.get("validator_sha256"))):
            errors.append("performance full-artifact validation receipt is missing")
        validated = _time(evidence.get("validated_at"))
        if validated > datetime.now(timezone.utc) or not isinstance(source, dict) or _time(source.get("created_at")) > validated:
            errors.append("performance report/validation dates are inconsistent or in the future")
        request = evidence.get("request")
        errors.extend(_request_errors(request, runtime))
        if errors:
            return errors
        requested = request["cases"]
        records = evidence.get("cases")
        if not isinstance(records, list) or len(records) != len(requested):
            return ["performance compact case records do not cover the requested suite"]
        if (type(validation.get("cases_verified")) is not int or validation["cases_verified"] != len(requested)
                or type(validation.get("runs_verified")) is not int or validation["runs_verified"] != len(requested) * request["runs"]
                or type(validation.get("artifacts_verified")) is not int or validation["artifacts_verified"] <= 0):
            errors.append("performance validation coverage counts are inconsistent")
        args = argparse.Namespace(**request)
        expected_labels = {benchmark.profile_this_run(args, i) for i in range(request["skip_first"] + 1, request["runs"] + 1)}
        minimum_artifacts = len(requested) * (2 * request["runs"] + 1 + sum(
            benchmark.profile_this_run(args, i) for i in range(1, request["runs"] + 1)))
        if type(validation.get("artifacts_verified")) is int and validation["artifacts_verified"] < minimum_artifacts:
            errors.append("performance artifact coverage is below the required stdout/stderr/CSV/trace minimum")
        for case, record in zip(requested, records):
            if not isinstance(record, dict) or record.get("case") != case or record.get("status") != "passed" or type(record.get("runs_verified")) is not int or record["runs_verified"] != request["runs"]:
                errors.append("performance case identity/status/coverage mismatch")
                continue
            for profiled, key, label in ((False, "summary", "SUMMARY"), (True, "profile_summary", "PROFILE_SUMMARY")):
                row = record.get(key)
                if profiled not in expected_labels:
                    if row is not None:
                        errors.append("performance contains an unexpected ordinary/profile summary")
                    continue
                if not isinstance(row, dict) or set(row) != set(benchmark.CSV_COLUMNS) or row.get("Run") != label or [row.get(k) for k in ("Prefill", "Decode", "Conc", "Num Prompts")] != case:
                    errors.append("performance summary shape/identity mismatch")
                    continue
                for value in row.values():
                    if isinstance(value, (int, float)) and (type(value) is bool or not math.isfinite(value)):
                        errors.append("performance summary contains invalid/nonfinite values")
                mapping = benchmark.format_result(case, {key: key for key in benchmark.PATTERNS})
                metrics = {metric: row[column] for column, metric in mapping.items() if isinstance(metric, str) and metric in benchmark.PATTERNS}
                errors.extend(benchmark.metric_errors(metrics, case[3], case[1] * case[3], request["engine"]))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        errors.append(f"invalid compact performance evidence: {exc}")
    return list(dict.fromkeys(errors))


def export_evidence(report_path, runtime_path, *, model, platform, deployment_fingerprint, service_instance_id):
    """Run beside the complete report and artifacts; return only compact evidence."""
    report_path, runtime_path = Path(report_path), Path(runtime_path)
    raw = report_path.read_bytes()
    report = json.loads(raw)
    errors = benchmark.validate_report(report, report_path)
    if errors:
        raise ValueError("full performance report did not validate: " + "; ".join(errors))
    if report_path.read_bytes() != raw:
        raise ValueError("performance source report changed during validation")
    runtime_raw = runtime_path.read_bytes()
    runtime = yaml.safe_load(runtime_raw)
    evidence = {"schema_version": 1, "kind": "formal_performance", "status": "passed", "errors": [],
        "run_id": report["run_id"], "validated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {"model": model, "platform": platform, "service_instance_id": service_instance_id,
                  "deployment_fingerprint": deployment_fingerprint, "runtime_config_sha256": digest(runtime_raw)},
        "source_report": {"path": str(report_path.resolve()), "sha256": digest(raw),
                          "producer_sha256": report["producer"]["sha256"], "created_at": report["created_at"]},
        "validation": {"method": "perf_common.validate_report", "status": "passed", "errors": [],
                       "validator_sha256": benchmark.file_sha256(benchmark.__file__),
                       "cases_verified": len(report["cases"]),
                       "runs_verified": sum(len(case["runs"]) for case in report["cases"]),
                       "artifacts_verified": len(report["artifacts"])},
        "request": report["request"],
        "cases": [{"case": case["case"], "status": "passed", "runs_verified": len(case["runs"]),
                   "summary": case["summary"], "profile_summary": case["profile_summary"]} for case in report["cases"]]}
    errors = validate_evidence(evidence, runtime=runtime, runtime_sha256=digest(runtime_raw), model=model,
                              platform=platform, deployment_fingerprint=deployment_fingerprint,
                              service_instance_id=service_instance_id, run_id=report["run_id"])
    if errors:
        raise ValueError("performance scope/compact evidence did not validate: " + "; ".join(errors))
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--runtime-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--deployment-fingerprint", required=True)
    parser.add_argument("--service-instance-id", required=True,
                        help="Actual recorded instance of this run, never inferred from current liveness")
    args = parser.parse_args(argv)
    try:
        evidence = export_evidence(args.report, args.runtime_config, model=args.model, platform=args.platform,
                                   deployment_fingerprint=args.deployment_fingerprint,
                                   service_instance_id=args.service_instance_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(evidence, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print(f"Validated compact performance evidence: {args.output}")
        return 0
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        parser.exit(2, f"Performance evidence export failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
