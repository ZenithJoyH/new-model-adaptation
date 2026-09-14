#!/usr/bin/env python3

"""Benchmark an explicitly identified service; failed runs never produce averages.

Example (the server must already be running with this context budget):
  python test/perf_test/vllm_perf.py --model MODEL --tokenizer /models/MODEL \
      --max-model-len 50000 --case 4096,1024,64,128

The checks validate CLI success and reported aggregate metrics/output budget.
They do not establish per-request lengths, observed concurrency, model
correctness, or the server's actual context configuration.
"""


import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from statistics import mean

RUNS = 3
SKIP_FIRST = 1

# Baseline cases used when --enable-all is not set.
# Each case is a tuple:
# (random_input_len, random_output_len, max_concurrency, num_prompts)
DEFAULT_TEST_CASES = [
    (1024, 1024, 64, 128),
    (4096, 1024, 64, 128),
    (16384, 1024, 64, 128),
    (32768, 1024, 64, 128),
    (65536, 1024, 64, 128),
]

ALL_TEST_CASES = [
    *DEFAULT_TEST_CASES,
    (4096, 1024, 1, 256),
    (4096, 1024, 4, 256),
    (4096, 1024, 16, 256),
    (4096, 1024, 256, 256),
    (131072, 1024, 64, 64),
    (262144, 1024, 64, 64),
]

ALL_ENTRY_CASES = [(size, 1024, concurrency, 256) for size, concurrency in (
    (1024, 16), (4096, 16), (16384, 16), (32768, 64),
    (65536, 16), (65536, 32), (65536, 48), (65536, 52), (65536, 64))]

SERVER_PREFIX_CACHE_DISABLE_ARG = "--no-enable-prefix-caching"


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def parse_case(value):
    try:
        case = tuple(positive_int(part) for part in value.split(","))
    except (ValueError, argparse.ArgumentTypeError) as exc:
        raise argparse.ArgumentTypeError("case must contain four positive integers") from exc
    if len(case) != 4:
        raise argparse.ArgumentTypeError("case must be INPUT,OUTPUT,CONCURRENCY,NUM_PROMPTS")
    return case


def parse_args(argv=None, *, engine="vllm", profile=False, all_entrypoint=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Served model name")
    parser.add_argument("--tokenizer", required=True, help="Tokenizer path or model identifier")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=positive_int, default=8010 if engine == "vllm" else 30000)
    parser.add_argument("--endpoint", default="/v1/completions" if engine == "vllm" else "/generate",
                        help="Completions or chat/completions API path; selects the matching request backend")
    parser.add_argument("--max-model-len", type=positive_int, required=True,
                        help="Verified context budget of the running service (input + output)")
    parser.add_argument("--case", type=parse_case, action="append", dest="cases",
                        help="Repeatable INPUT,OUTPUT,CONCURRENCY,NUM_PROMPTS; overrides the default suite")
    parser.add_argument("--runs", type=positive_int, default=5 if all_entrypoint else 2 if profile and engine == "sglang" else RUNS)
    parser.add_argument("--skip-first", type=int, default=2 if profile and engine == "vllm" else SKIP_FIRST,
                        help="Warmup runs omitted from averages, but not from failure checks")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "results"),
                        help="Local artifact directory (default: ignored test/perf_test/results/)")
    parser.add_argument("--run-timeout", type=positive_int, default=21600,
                        help="Maximum seconds per benchmark subprocess (default: six hours)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands only; produces no passing report")
    if profile:
        parser.add_argument("--no-profile", action="store_true")
        parser.add_argument("--profile-runs", choices=("first", "last", "all"), default="last")
        parser.add_argument("--profile-dir", help="Existing locally visible server trace directory; never created or configured by this client")
    if all_entrypoint:
        parser.add_argument("--input-len", type=positive_int)
        parser.add_argument("--output-len", type=positive_int)
        parser.add_argument("--concurrency", type=positive_int)
        parser.add_argument("--num-prompts", type=positive_int)
    parser.add_argument(
        "--enable-all",
        action="store_true",
        help=f"Enable all {len(ALL_TEST_CASES)} cases; default is {len(DEFAULT_TEST_CASES)} cases.",
    )
    args = parser.parse_args(argv)
    args.engine = engine
    args.profiling_requested = profile and not args.no_profile
    args.profile_runs = getattr(args, "profile_runs", "last")
    args.profile_dir = getattr(args, "profile_dir", None)
    if args.profiling_requested and not args.dry_run and (not args.profile_dir or not Path(args.profile_dir).is_dir()):
        parser.error("profiling requires an existing, locally visible --profile-dir for fresh trace verification")
    if args.profile_dir:
        args.profile_dir = str(Path(args.profile_dir).resolve())
        if Path(args.output_dir).resolve().is_relative_to(Path(args.profile_dir)):
            parser.error("output-dir must be outside profile-dir to avoid recapturing copied traces")
    if not args.model.strip() or not args.tokenizer.strip() or not args.host.strip():
        parser.error("model, tokenizer and host must not be blank")
    if args.port > 65535:
        parser.error("port must not exceed 65535")
    if not args.endpoint.startswith("/") or args.endpoint.startswith("//") or any(char.isspace() or char in "?#" for char in args.endpoint):
        parser.error("endpoint must be an absolute API path, not a URL")
    if engine == "sglang":
        if args.endpoint != "/generate":
            parser.error("the SGLang native adapter supports /generate only; it does not use vLLM endpoint flags")
        args.backend = "sglang"
    elif args.endpoint.endswith("/chat/completions"):
        args.backend = "openai-chat"
    elif args.endpoint.endswith("/completions"):
        args.backend = "vllm"
    else:
        parser.error("endpoint must end in /completions or /chat/completions; other protocols are unsupported")
    if args.cases and args.enable_all:
        parser.error("--case and --enable-all cannot be combined")
    if all_entrypoint:
        legacy = any(getattr(args, key) is not None for key in ("input_len", "output_len", "concurrency", "num_prompts"))
        if legacy and (args.cases or args.enable_all):
            parser.error("legacy --input-len options cannot be combined with --case or --enable-all")
        if legacy:
            if args.input_len is None:
                parser.error("--output-len/--concurrency/--num-prompts require --input-len")
            args.cases = [(args.input_len, args.output_len or 1024, args.concurrency or 64, args.num_prompts or 256)]
    if not 0 <= args.skip_first < args.runs:
        parser.error("skip-first must be nonnegative and smaller than runs")
    defaults = ALL_ENTRY_CASES if all_entrypoint else [(4096, 1024, 64, 64)] if profile else DEFAULT_TEST_CASES
    args.cases = args.cases or (ALL_TEST_CASES if args.enable_all else defaults)
    if len(set(args.cases)) != len(args.cases):
        parser.error("duplicate cases are not allowed")
    oversized = [case for case in args.cases if case[0] + case[1] > args.max_model_len]
    if oversized:
        parser.error(f"cases exceed input + output context budget {args.max_model_len}: {oversized}; "
                     "select valid cases explicitly with --case")
    return args


def build_common_args(args):
    if args.engine == "sglang":
        # SGLang native API has its own backend, length sampling and ignore-EOS
        # defaults. Do not forward vLLM-only endpoint/ignore-eos/prefix flags.
        return [getattr(args, "python_executable", sys.executable), "-m", "sglang.bench_serving", "--backend", "sglang",
                "--model", args.model, "--tokenizer", args.tokenizer,
                "--host", args.host, "--port", str(args.port),
                "--dataset-name", "random", "--random-range-ratio", "0.0"]
    # Preserve the existing vllm bench interface; no version-specific JSON flags.
    return ["vllm", "bench", "serve", "--backend", args.backend, "--model", args.model,
            "--tokenizer", args.tokenizer, "--endpoint", args.endpoint, "--host", args.host,
            "--port", str(args.port), "--dataset-name", "random", "--ignore-eos",
            "--random-range-ratio", "0.0", "--random-prefix-len", "0"]


PATTERNS = {
    "successful_requests": r"Successful requests:\s+([0-9.]+)",
    "failed_requests": r"Failed requests:\s+([0-9.]+)",
    "benchmark_duration": r"Benchmark duration \(s\):\s+([0-9.]+)",
    "total_input_tokens": r"Total input tokens:\s+([0-9.]+)",
    "total_output_tokens": r"Total generated tokens:\s+([0-9.]+)",
    "request_throughput": r"Request throughput \(req/s\):\s+([0-9.]+)",
    "output_throughput": r"Output token throughput \(tok/s\):\s+([0-9.]+)",
    "peak_output_throughput": r"Peak output token throughput \(tok/s\):\s+([0-9.]+)",
    "total_token_throughput": r"Total token throughput \(tok/s\):\s+([0-9.]+)",
    "mean_ttft_ms": r"Mean TTFT \(ms\):\s+([0-9.]+)",
    "median_ttft_ms": r"Median TTFT \(ms\):\s+([0-9.]+)",
    "p99_ttft_ms": r"P99 TTFT \(ms\):\s+([0-9.]+)",
    "mean_tpot_ms": r"Mean TPOT \(ms\):\s+([0-9.]+)",
    "median_tpot_ms": r"Median TPOT \(ms\):\s+([0-9.]+)",
    "p99_tpot_ms": r"P99 TPOT \(ms\):\s+([0-9.]+)",
    "mean_itl_ms": r"Mean ITL \(ms\):\s+([0-9.]+)",
    "median_itl_ms": r"Median ITL \(ms\):\s+([0-9.]+)",
    "p99_itl_ms": r"P99 ITL \(ms\):\s+([0-9.]+)",
}

SGLANG_EXTRA_PATTERNS = {
    f"{stat}_e2el_ms": rf"{label} E2EL \(ms\):\s+([0-9.]+)"
    for stat, label in (("mean", "Mean"), ("median", "Median"), ("p99", "P99"))
}

# Peak throughput is absent from some supported vLLM text summaries. All other
# displayed metrics must be present; a changed CLI format fails closed.
REQUIRED_METRICS = set(PATTERNS) - {"peak_output_throughput", "failed_requests"}
COUNT_METRICS = {"successful_requests", "total_input_tokens", "total_output_tokens"}

CSV_COLUMNS = [
    "Prefill",
    "Decode",
    "Conc",
    "Num Prompts",
    "Run",
    "Successful Requests",
    "Failed Requests",
    "Benchmark Duration (s)",
    "Total Input Tokens",
    "Total Output Tokens",
    "Req/s",
    "Output tok/s",
    "Peak Output tok/s",
    "Total tok/s",
    "Mean TTFT (ms)",
    "Median TTFT (ms)",
    "P99 TTFT (ms)",
    "Mean TPOT (ms)",
    "Median TPOT (ms)",
    "P99 TPOT (ms)",
    "Mean ITL (ms)",
    "Median ITL (ms)",
    "P99 ITL (ms)",
]


def extract_metrics(output_text, engine="vllm"):
    result = {}

    patterns = PATTERNS | (SGLANG_EXTRA_PATTERNS if engine == "sglang" else {})
    for key, pattern in patterns.items():
        matches = list(re.finditer(
            r"^\s*" + pattern.replace("([0-9.]+)", r"(\S+)"),
            output_text,
            re.IGNORECASE | re.MULTILINE,
        ))
        match = matches[0] if len(matches) == 1 else None
        try:
            result[key] = float(match.group(1)) if match else (float("nan") if matches else None)
        except ValueError:
            result[key] = float("nan")

    return result


def metric_errors(metrics, expected_requests, expected_output_tokens=None, engine="vllm"):
    if not isinstance(metrics, dict):
        return ["metrics must be a mapping"]
    errors = []
    for key in PATTERNS:
        value = metrics.get(key)
        if value is None and key not in REQUIRED_METRICS:
            continue
        if type(value) not in (int, float) or not math.isfinite(value):
            errors.append(f"missing or nonfinite metric: {key}")
        elif value < 0 or (key in COUNT_METRICS and (value <= 0 or not float(value).is_integer())):
            errors.append(f"invalid metric: {key}={value}")
        elif key in {"benchmark_duration", "request_throughput", "output_throughput", "total_token_throughput"} and value <= 0:
            errors.append(f"metric must be positive: {key}")
    if metrics.get("successful_requests") != expected_requests:
        errors.append("successful_requests does not match num_prompts")
    if metrics.get("failed_requests") not in (None, 0):
        errors.append("benchmark explicitly reports failed requests")
    # Fixed random output length + ignore_eos must deliver this aggregate budget.
    # vLLM may retokenize output when API usage is unavailable. A discrepancy is
    # an unverified workload/counting contract, not proof of a server defect.
    if expected_output_tokens is not None and metrics.get("total_output_tokens") != expected_output_tokens:
        errors.append("reported total_output_tokens does not match the requested fixed output budget: "
                      f"expected {expected_output_tokens}, got {metrics.get('total_output_tokens')}; "
                      "workload completion is unverified")
    for key in SGLANG_EXTRA_PATTERNS if engine == "sglang" else ():
        value = metrics.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            errors.append(f"invalid optional SGLang metric: {key}")
    return errors


def save_error_log(cmd, case, run_id, stdout, stderr, returncode, output_dir, errors=None):
    """当测试出现服务端报错时，保存完整的请求信息到错误日志文件"""
    error_log_dir = os.path.join(output_dir, "error_logs")
    os.makedirs(error_log_dir, exist_ok=True)

    input_len, output_len, concurrency, num_prompts = case
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"error_in{input_len}_out{output_len}_c{concurrency}_n{num_prompts}_run{run_id}_{timestamp}.json"
    filepath = os.path.join(error_log_dir, filename)

    error_record = {
        "timestamp": datetime.now().isoformat(),
        "request_params": {
            "input_len": input_len,
            "output_len": output_len,
            "concurrency": concurrency,
            "num_prompts": num_prompts,
            "run_id": run_id,
        },
        "command": " ".join(cmd),
        "command_list": cmd,
        "returncode": returncode,
        "validation_errors": errors or [],
        "stdout": stdout,
        "stderr": stderr,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(error_record, f, ensure_ascii=False, indent=2)

    print(f"[ERROR LOG] 错误信息已保存到: {filepath}")


def format_result(case, metrics, run_label=""):
    input_len, output_len, concurrency, num_prompts = case

    result = {
        "Prefill": input_len,
        "Decode": output_len,
        "Conc": concurrency,
        "Num Prompts": num_prompts,
        "Run": run_label,
        "Successful Requests": metrics.get("successful_requests"),
        "Failed Requests": metrics.get("failed_requests"),
        "Benchmark Duration (s)": metrics.get("benchmark_duration"),
        "Total Input Tokens": metrics.get("total_input_tokens"),
        "Total Output Tokens": metrics.get("total_output_tokens"),
        "Req/s": metrics.get("request_throughput"),
        "Output tok/s": metrics.get("output_throughput"),
        "Peak Output tok/s": metrics.get("peak_output_throughput"),
        "Total tok/s": metrics.get("total_token_throughput"),
        "Mean TTFT (ms)": metrics.get("mean_ttft_ms"),
        "Median TTFT (ms)": metrics.get("median_ttft_ms"),
        "P99 TTFT (ms)": metrics.get("p99_ttft_ms"),
        "Mean TPOT (ms)": metrics.get("mean_tpot_ms"),
        "Median TPOT (ms)": metrics.get("median_tpot_ms"),
        "P99 TPOT (ms)": metrics.get("p99_tpot_ms"),
        "Mean ITL (ms)": metrics.get("mean_itl_ms"),
        "Median ITL (ms)": metrics.get("median_itl_ms"),
        "P99 ITL (ms)": metrics.get("p99_itl_ms"),
    }

    return result


def append_csv(row, filename, columns):
    file_exists = os.path.exists(filename)

    with open(filename, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=columns,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    return {"path": str(path.relative_to(root)), "sha256": file_sha256(path)}


def json_safe(value):
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def profile_this_run(args, run_id):
    return args.profiling_requested and run_id > args.skip_first and (
        args.profile_runs == "all" or (args.profile_runs == "first" and run_id == args.skip_first + 1)
        or (args.profile_runs == "last" and run_id == args.runs)
    )


def trace_snapshot(directory):
    """Read only the configured trace tree; do not configure or restart servers."""
    root = Path(directory)
    return {str(path.relative_to(root)): file_sha256(path)
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()
            and (path.name.endswith(".json") or path.name.endswith(".json.gz"))}


def trace_errors(path):
    """Require readable Chrome trace events, not merely a new JSON filename."""
    try:
        opener = gzip.open if Path(path).name.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as stream:
            trace = json.load(stream)
        events = trace.get("traceEvents") if isinstance(trace, dict) else trace
        if not isinstance(events, list) or not any(
            isinstance(event, dict) and isinstance(event.get("name"), str)
            and event.get("ph") in ("X", "B", "E", "i", "I", "C", "b", "e", "n")
            and type(event.get("ts")) in (int, float) and math.isfinite(event["ts"])
            for event in events
        ):
            return ["profile artifact has no timed Chrome trace events"]
    except (OSError, ValueError, EOFError) as exc:
        return [f"unreadable profile trace: {exc}"]
    return []


def build_command(args, case, run_id):
    input_len, output_len, concurrency, num_prompts = case
    command = build_common_args(args) + ["--random-input-len", str(input_len),
        "--random-output-len", str(output_len), "--max-concurrency", str(concurrency),
        "--num-prompts", str(num_prompts)]
    if profile_this_run(args, run_id):
        command.append("--profile")
    return command


def run_once(case, run_id, output_dir, args):
    input_len, output_len, concurrency, num_prompts = case

    name = f"{input_len}_{output_len}_c{concurrency}"

    print("=" * 80)
    print(f"Running: {name} | Run {run_id}/{args.runs}")
    print("=" * 80)

    if input_len + output_len > args.max_model_len:
        raise ValueError("case exceeds the verified context budget")
    cmd = build_command(args, case, run_id)

    print(" ".join(cmd))
    print()

    start_time = time.monotonic()
    profiled = profile_this_run(args, run_id)
    before = trace_snapshot(args.profile_dir) if profiled else {}
    exception_errors = []
    try:
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, timeout=args.run_timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        stdout = getattr(exc, "stdout", "") or ""
        stderr = getattr(exc, "stderr", "") or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        process = subprocess.CompletedProcess(cmd, None, stdout, stderr + "\n" + repr(exc))
        exception_errors.append(f"benchmark launch/timeout failure: {type(exc).__name__}")
    elapsed = time.monotonic() - start_time
    output = process.stdout or ""

    print(output)
    if process.stderr:
        print(process.stderr)

    metrics = extract_metrics(output, args.engine)

    metrics["elapsed_sec"] = round(elapsed, 2)

    errors = exception_errors + metric_errors(metrics, num_prompts, output_len * num_prompts, args.engine)
    if process.returncode != 0:
        errors.insert(0, f"benchmark process exited {process.returncode}")
    metrics["status"] = "failed" if errors else "passed"
    metrics["returncode"] = process.returncode
    metrics["validation_errors"] = errors
    metrics["profiled"] = profiled
    metrics["command"] = cmd
    metrics["traces"] = []
    if profiled:
        after = trace_snapshot(args.profile_dir)
        label = "_".join(map(str, case)) + f"_run{run_id}"
        for path, digest in after.items():
            if before.get(path) == digest:
                continue
            destination = Path(output_dir) / "traces" / label / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(args.profile_dir) / path, destination)
            captured = artifact(destination, output_dir)
            if captured["sha256"] != digest:
                errors.append("trace changed during capture; profiling evidence is unstable")
            errors.extend(trace_errors(destination))
            metrics["traces"].append(captured)
        if not metrics["traces"]:
            errors.append("profiling requested but no new or changed trace artifact was verified")
    metrics["status"] = "failed" if errors else "passed"
    if hasattr(args, "_artifact_root"):
        label = "_".join(map(str, case)) + f"_run{run_id}"
        for name, contents in (("stdout", output), ("stderr", process.stderr or "")):
            destination = Path(output_dir) / f"{label}.{name}.txt"
            destination.write_text(contents, encoding="utf-8")
            metrics[name] = artifact(destination, output_dir)
    if errors:
        save_error_log(
            cmd, case, run_id,
            stdout=process.stdout, stderr=process.stderr,
            returncode=process.returncode, output_dir=output_dir, errors=errors
        )

    return metrics


def average_metrics(results):
    if not results or any(run.get("status") != "passed" for run in results):
        raise ValueError("only nonempty, verified passing runs may be averaged")
    avg_result = {}
    for key in (*PATTERNS, *SGLANG_EXTRA_PATTERNS, "elapsed_sec"):
        values = [r[key] for r in results if type(r.get(key)) in (int, float) and math.isfinite(r[key])]

        if len(values) == len(results):
            avg_result[key] = round(mean(values), 2)

    return avg_result


def run_test_case(case, csv_file, output_dir, args):
    all_runs = []

    for run_id in range(1, args.runs + 1):
        metrics = run_once(case, run_id, output_dir, args)
        status = "SUCCESS" if metrics["status"] == "passed" else "FAILED"

        tag = "+profile" if metrics.get("profiled") else ""
        raw_row = format_result(case, metrics, run_label=f"Run{run_id}({status}){tag}")
        append_csv(raw_row, csv_file, CSV_COLUMNS)

        all_runs.append(metrics)

    failed = any(run["status"] != "passed" for run in all_runs)
    summary_row = profile_summary = None
    if not failed:
        for profiled, label in ((False, "SUMMARY"), (True, "PROFILE_SUMMARY")):
            measured = [run for run in all_runs[args.skip_first:] if bool(run.get("profiled")) == profiled]
            if measured:
                row = format_result(case, average_metrics(measured), run_label=label)
                append_csv(row, csv_file, CSV_COLUMNS)
                if profiled:
                    profile_summary = row
                else:
                    summary_row = row
    if hasattr(args, "_case_records"):
        records = []
        for run_id, result in enumerate(all_runs, 1):
            records.append({"run_id": run_id, "status": result["status"],
                "returncode": result["returncode"], "validation_errors": result["validation_errors"],
                "metrics": {key: result.get(key) for key in (*PATTERNS, *SGLANG_EXTRA_PATTERNS, "elapsed_sec")
                            if key in result},
                "profiled": bool(result.get("profiled")), "traces": result.get("traces", []),
                "command": result.get("command"), "stdout": result.get("stdout"), "stderr": result.get("stderr")})
        args._case_records.append({"case": list(case), "status": "failed" if failed else "passed",
            "runs": records, "csv": artifact(csv_file, output_dir), "summary": summary_row,
            "profile_summary": profile_summary})
    return summary_row or profile_summary, failed


def print_summary(results):
    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)

    for r in results:
        print(
            f"{r['Run']}: "
            f"Prefill={r['Prefill']} "
            f"Decode={r['Decode']} "
            f"Conc={r['Conc']} "
            f"NumPrompts={r['Num Prompts']} "
            f"Req/s={r['Req/s']} "
            f"Total tok/s={r['Total tok/s']} "
            f"TTFT={r['Mean TTFT (ms)']}ms"
        )


def request_record(args):
    return {"engine": args.engine, "backend": args.backend, "model": args.model,
        "tokenizer": args.tokenizer, "host": args.host, "port": args.port, "endpoint": args.endpoint,
        "max_model_len": args.max_model_len, "runs": args.runs, "skip_first": args.skip_first,
        "cases": [list(case) for case in args.cases], "output_dir": str(Path(args.output_dir).resolve()),
        "run_timeout": args.run_timeout, "profiling_requested": args.profiling_requested,
        "profile_runs": args.profile_runs, "profile_dir": args.profile_dir,
        "python_executable": sys.executable}


def _verified_artifact(record, root):
    if not isinstance(record, dict) or not isinstance(record.get("path"), str):
        raise ValueError("missing artifact reference")
    relative = Path(record["path"])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("artifact path must remain inside the report directory")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink() or not path.is_file():
        raise ValueError("missing or escaped artifact: " + str(relative))
    digest = record.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or file_sha256(path) != digest:
        raise ValueError("artifact sha256 mismatch: " + str(relative))
    return path


def validate_report(report, path):
    """Return acceptance errors, not just schema errors; [] means a verified pass.

    Validate every run (including warmup), replay stdout parsing and metrics,
    reconstruct commands/summaries/CSV, and verify artifact bytes. This is an
    integrity contract, not a signature or independent proof of service identity.
    No benchmark, HTTP, shell command, or remote operation is performed here.
    """
    errors = []
    try:
        if not isinstance(report, dict) or type(report.get("schema_version")) is not int or report.get("schema_version") != 1 or report.get("kind") != "benchmark-result":
            return ["unsupported benchmark report schema"]
        if report.get("status") != "passed" or report.get("errors") != []:
            return ["benchmark report is not an error-free pass"]
        if not isinstance(report.get("run_id"), str) or not report["run_id"].strip():
            return ["report run_id is missing"]
        created_at = datetime.fromisoformat(report.get("created_at", ""))
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            return ["report created_at must include a timezone"]
        producer = report.get("producer")
        if not isinstance(producer, dict) or producer.get("implementation") != "perf_common.py" or not isinstance(producer.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", producer["sha256"]):
            return ["missing benchmark producer provenance"]
        request = report.get("request")
        if not isinstance(request, dict):
            return ["request configuration is missing"]
        for key in ("model", "tokenizer", "host", "endpoint", "python_executable", "output_dir"):
            if not isinstance(request.get(key), str) or not request[key].strip():
                errors.append(f"invalid request.{key}")
        for key in ("port", "max_model_len", "runs", "run_timeout"):
            if type(request.get(key)) is not int or request[key] <= 0:
                errors.append(f"invalid request.{key}")
        if type(request.get("skip_first")) is not int or type(request.get("runs")) is not int or not 0 <= request["skip_first"] < request["runs"]:
            errors.append("invalid warmup/run count")
        if type(request.get("profiling_requested")) is not bool or request.get("profile_runs") not in ("first", "last", "all"):
            errors.append("invalid profiling configuration")
        engine = request.get("engine")
        endpoint = request.get("endpoint", "")
        if engine not in ("vllm", "sglang"):
            errors.append("unsupported benchmark engine")
        elif engine == "sglang":
            if request.get("backend") != "sglang" or endpoint != "/generate":
                errors.append("SGLang protocol mismatch")
        elif not isinstance(endpoint, str) or not endpoint.startswith("/") or endpoint.startswith("//") or any(char.isspace() or char in "?#" for char in endpoint):
            errors.append("invalid endpoint")
        else:
            backend = "openai-chat" if endpoint.endswith("/chat/completions") else "vllm" if endpoint.endswith("/completions") else None
            if backend is None or backend != request.get("backend"):
                errors.append("vLLM protocol mismatch")
        if type(request.get("port")) is int and request["port"] > 65535:
            errors.append("invalid port")
        requested = request.get("cases")
        if not isinstance(requested, list) or not requested:
            errors.append("empty requested case set")
        elif any(not isinstance(case, list) or len(case) != 4 or any(type(value) is not int or value <= 0 for value in case) for case in requested):
            errors.append("invalid requested case shape")
        elif len({tuple(case) for case in requested}) != len(requested):
            errors.append("duplicate requested cases")
        if errors:
            return errors
        args = argparse.Namespace(**request)
        root = Path(path).resolve().parent
        records = report.get("cases")
        if not isinstance(records, list) or len(records) != len(requested):
            return ["case records do not cover the requested suite"]
        artifacts = report.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return ["artifact manifest is missing"]
        manifest = {}
        for ref in artifacts:
            _verified_artifact(ref, root)
            if ref["path"] in manifest:
                errors.append("duplicate artifact manifest path")
            manifest[ref["path"]] = ref["sha256"]
        used = set()

        def get_artifact(ref):
            file_path = _verified_artifact(ref, root)
            if manifest.get(ref["path"]) != ref["sha256"]:
                raise ValueError("artifact absent or inconsistent in manifest")
            used.add(ref["path"])
            return file_path

        for index, (case, record) in enumerate(zip(requested, records), 1):
            if sum(case[:2]) > request["max_model_len"]:
                errors.append(f"case {index} exceeds context budget")
            if not isinstance(record, dict) or record.get("case") != case or record.get("status") != "passed":
                errors.append(f"case {index} identity/status mismatch")
                continue
            runs = record.get("runs")
            if not isinstance(runs, list) or len(runs) != request["runs"]:
                errors.append(f"case {index} has missing/extra runs")
                continue
            expected_rows, measured = [], {False: [], True: []}
            for run_id, run in enumerate(runs, 1):
                prefix = f"case {index} run {run_id}"
                if not isinstance(run, dict):
                    errors.append(prefix + " is not a run record")
                    continue
                if type(run.get("run_id")) is not int or run["run_id"] != run_id:
                    errors.append(prefix + " identity mismatch")
                if run.get("status") != "passed" or type(run.get("returncode")) is not int or run["returncode"] != 0 or run.get("validation_errors") != []:
                    errors.append(prefix + " failed or lacks an actual zero exit")
                profiled = profile_this_run(args, run_id)
                if type(run.get("profiled")) is not bool or run["profiled"] != profiled:
                    errors.append(prefix + " profile selection mismatch")
                if run.get("command") != build_command(args, case, run_id):
                    errors.append(prefix + " command/configuration mismatch")
                stdout = get_artifact(run.get("stdout")).read_text(encoding="utf-8")
                get_artifact(run.get("stderr"))
                parsed = extract_metrics(stdout, engine)
                metrics = run.get("metrics")
                current_errors = metric_errors(metrics, case[3], case[1] * case[3], engine)
                errors.extend(prefix + ": " + error for error in current_errors)
                if not isinstance(metrics, dict):
                    continue
                if any(metrics.get(key) != value for key, value in parsed.items()):
                    errors.append(prefix + " metrics differ from stdout")
                elapsed = metrics.get("elapsed_sec")
                if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
                    errors.append(prefix + " has invalid client elapsed time")
                traces = run.get("traces")
                if not isinstance(traces, list) or (profiled and not traces) or (not profiled and traces):
                    errors.append(prefix + " missing/unexpected profile traces")
                else:
                    for ref in traces:
                        errors.extend(prefix + ": " + error for error in trace_errors(get_artifact(ref)))
                tag = "+profile" if profiled else ""
                expected_rows.append(format_result(case, metrics, f"Run{run_id}(SUCCESS){tag}"))
                if run_id > request["skip_first"]:
                    measured[profiled].append(dict(metrics, status="passed"))
            for profiled, key, label in ((False, "summary", "SUMMARY"), (True, "profile_summary", "PROFILE_SUMMARY")):
                expected = format_result(case, average_metrics(measured[profiled]), label) if measured[profiled] else None
                if record.get(key) != expected:
                    errors.append(f"case {index} {key} does not match measured runs")
                if expected is not None:
                    expected_rows.append(expected)
            with get_artifact(record.get("csv")).open(newline="", encoding="utf-8") as stream:
                reader = csv.DictReader(stream)
                actual_rows = list(reader)
                if reader.fieldnames != CSV_COLUMNS:
                    errors.append(f"case {index} CSV columns mismatch")
                expected_rows = [{key: "" if row.get(key) is None else str(row[key]) for key in CSV_COLUMNS} for row in expected_rows]
                if actual_rows != expected_rows:
                    errors.append(f"case {index} CSV data/status/summary mismatch")
        if used != set(manifest):
            errors.append("manifest contains unreferenced artifacts")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append("invalid benchmark evidence: " + str(exc))
    return errors


def main(argv=None, *, engine="vllm", profile=False, all_entrypoint=False):
    args = parse_args(argv, engine=engine, profile=profile, all_entrypoint=all_entrypoint)

    if args.dry_run:
        for case in args.cases:
            for run_id in range(1, args.runs + 1):
                print(" ".join(build_command(args, case, run_id)))
        print("DRY RUN: no benchmark executed and no acceptance report produced.")
        return 0

    test_cases = args.cases

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    model_label = re.sub(r"[^A-Za-z0-9._-]+", "_", args.model).strip(".") or "model"
    output_dir = os.path.join(args.output_dir, model_label, timestamp)
    os.makedirs(output_dir, exist_ok=False)
    args._artifact_root = output_dir
    args._case_records = []

    all_summary = []

    print()
    print(f"RUNS={args.runs}")
    print(f"SKIP_FIRST={args.skip_first}")
    print(f"ENABLE_ALL={args.enable_all}")
    print(f"TOTAL_CASES={len(test_cases)}")
    print(f"TEST_CASES={test_cases}")
    print()

    csv_files = []
    failed_cases = []

    for case_index, case in enumerate(test_cases):
        input_len, output_len, concurrency, num_prompts = case
        scenario_name = f"{input_len}in_{output_len}out_c{concurrency}_n{num_prompts}"
        csv_file = os.path.join(
            output_dir, f"{model_label}_{scenario_name}_{timestamp}.csv"
        )

        try:
            summary_row, has_failed_run = run_test_case(
                case,
                csv_file,
                output_dir,
                args,
            )

            csv_files.append(csv_file)

            if has_failed_run:
                failed_cases.append(case)
                print(f"SKIP SUMMARY ROW (failed case): {case}")
                continue

            all_summary.append(summary_row)

        except Exception as e:
            failed_cases.append(case)
            if len(args._case_records) <= case_index:
                args._case_records.append({"case": list(case), "status": "failed", "runs": [],
                    "csv": None, "summary": None, "profile_summary": None, "error": repr(e)})
            print(f"ERROR: {e}")

    # Missing records (including unexpected callback/collection failures) cannot
    # turn a partial suite into a passing report.
    artifacts = []
    for record in args._case_records:
        if record.get("csv"):
            artifacts.append(record["csv"])
        for run in record.get("runs", []):
            artifacts.extend(ref for ref in (run.get("stdout"), run.get("stderr")) if ref)
            artifacts.extend(run.get("traces", []))
    report = {"schema_version": 1, "kind": "benchmark-result", "run_id": str(uuid.uuid4()),
        "created_at": datetime.now().astimezone().isoformat(),
        "producer": {"implementation": "perf_common.py", "sha256": file_sha256(__file__)},
        "status": "failed" if failed_cases else "passed", "request": request_record(args),
        "cases": args._case_records, "artifacts": artifacts,
        "errors": [f"case failed: {case}" for case in failed_cases]}
    report = json_safe(report)
    report_path = Path(output_dir) / "benchmark-result.json"
    if not failed_cases:
        report_errors = validate_report(report, report_path)
        if report_errors:
            failed_cases.append("report integrity")
            report["status"] = "failed"
            report["errors"] = report_errors
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(f"Benchmark report: {report_path}")

    if failed_cases:
        print(f"Benchmark FAILED: {len(failed_cases)} case(s); no overall success summary.")
    else:
        print_summary(all_summary)

    print()
    print("CSV files:")
    for f in csv_files:
        print(f"  {f}")
    return 1 if failed_cases else 0


if __name__ == "__main__":
    sys.exit(main())
