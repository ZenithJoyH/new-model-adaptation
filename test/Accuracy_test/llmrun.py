#!/usr/bin/env python3
"""Run reproducible lm-eval API accuracy jobs in flageval_llmeval."""

import argparse
import hashlib
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from acceptance_contract import metric_errors, validate_formal_config


class ConfigSnapshot(dict):
    """Keep the exact source bytes out of the effective JSON configuration."""

    def __init__(self, values: Dict, source_bytes: bytes):
        super().__init__(values)
        self.source_bytes = source_bytes


def log(level: str, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] [{level:<5}] {message}", flush=True)


def fail(message: str, code: int = 1) -> None:
    log("ERROR", message)
    raise SystemExit(code)


def resolve_path(value: str, config_dir: Path) -> str:
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = config_dir / path
    return str(path.resolve())


def load_config(config_path: Path) -> Dict:
    if not config_path.is_file():
        fail(f"Configuration file does not exist: {config_path}")
    source_bytes = config_path.read_bytes()
    cfg = json.loads(source_bytes)
    if not isinstance(cfg, dict):
        fail("Configuration must be a JSON object")
    for error in validate_formal_config(cfg):
        fail(error)
    cfg = ConfigSnapshot(cfg, source_bytes)
    cfg["source_config_sha256"] = hashlib.sha256(source_bytes).hexdigest()

    defaults = {
        "model_type": "openai-chat-completions",
        "base_url": "http://127.0.0.1:8010/v1/chat/completions",
        "tasks": ["gpqa_diamond_generative_cot"],
        "limit": 0,
        "num_concurrent": 1,
        "timeout": 3600,
        "api_max_retries": 3,
        "eval_max_retries": 0,
        "retry_delay": 60,
        "gen_kwargs": "",
        "apply_chat_template": True,
        "include_path": "",
        "output_root": "./outputs",
        "cache_root": "/tmp/lm_eval_cache",
        "run_id": "auto",
        "offline": True,
        "hf_datasets_cache": "/root/.cache/huggingface/datasets",
        "dataset_path": "",
        "dataset_name": "",
        "dataset_split": "train",
        "expected_samples": 0,
        "allow_timeouts": False,
        "wait_for_service": False,
        "service_poll_interval": 1800,
        "service_wait_timeout": 0,
        "progress_score_interval": 10,
        "progress_score_poll_seconds": 5,
    }
    for key, value in defaults.items():
        cfg.setdefault(key, value)

    for key in ("eval_model", "model_name", "base_url"):
        if not cfg.get(key):
            fail(f"Missing required configuration key: {key}")

    tasks = cfg.get("tasks", cfg.get("task"))
    if isinstance(tasks, str):
        tasks = [tasks]
    if not tasks or not all(isinstance(task, str) and task for task in tasks):
        fail("tasks must be a non-empty string or list of strings")
    cfg["tasks"] = tasks

    config_dir = config_path.parent.resolve()
    cfg["output_root"] = resolve_path(cfg["output_root"], config_dir)
    cfg["cache_root"] = resolve_path(cfg["cache_root"], config_dir)
    cfg["include_path"] = resolve_path(cfg["include_path"], config_dir)

    for key in (
        "limit",
        "num_concurrent",
        "timeout",
        "api_max_retries",
        "eval_max_retries",
        "retry_delay",
        "expected_samples",
        "service_poll_interval",
        "service_wait_timeout",
        "progress_score_interval",
        "progress_score_poll_seconds",
    ):
        try:
            cfg[key] = int(cfg[key])
        except (TypeError, ValueError):
            fail(f"{key} must be an integer")

    if cfg["limit"] < 0:
        fail("limit must be >= 0")
    if cfg["num_concurrent"] < 1:
        fail("num_concurrent must be >= 1")
    if cfg["timeout"] < 1:
        fail("timeout must be >= 1")
    if cfg["eval_max_retries"] < 0 or cfg["retry_delay"] < 0:
        fail("eval_max_retries and retry_delay must be >= 0")
    if cfg["service_poll_interval"] < 1:
        fail("service_poll_interval must be >= 1")
    if cfg["service_wait_timeout"] < 0:
        fail("service_wait_timeout must be >= 0")
    if cfg["progress_score_interval"] < 0 or cfg["progress_score_poll_seconds"] < 1:
        fail("progress_score_interval must be >= 0 and progress_score_poll_seconds must be >= 1")
    return cfg


def configure_environment(cfg: Dict) -> None:
    os.environ.setdefault("OPENAI_API_KEY", "EMPTY")
    os.environ["HF_DATASETS_CACHE"] = cfg["hf_datasets_cache"]
    if cfg["offline"]:
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"


def models_url(base_url: str) -> str:
    replaced = re.sub(r"/v1/.*$", "/v1/models", base_url.rstrip("/"))
    if replaced == base_url.rstrip("/"):
        return base_url.rstrip("/") + "/v1/models"
    return replaced


def probe_service(cfg: Dict, timeout: int = 10) -> Tuple[bool, str]:
    url = models_url(cfg["base_url"])
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        model_ids = [item.get("id") for item in body.get("data", [])]
        if cfg["model_name"] not in model_ids:
            return False, f"HTTP 200, but {cfg['model_name']!r} is not in {model_ids}"
        return True, f"HTTP 200, models={model_ids}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code} from {url}"
    except Exception as exc:  # noqa: BLE001 - preflight should report all failures
        return False, f"{type(exc).__name__}: {exc}"


def wait_for_service(cfg: Dict) -> None:
    started = time.monotonic()
    attempt = 0
    while True:
        attempt += 1
        healthy, detail = probe_service(cfg)
        if healthy:
            log("INFO", f"Model service ready after {attempt} probe(s): {detail}")
            return
        if not cfg.get("wait_for_service", False):
            fail(f"Model service is not ready: {detail}")

        elapsed = int(time.monotonic() - started)
        wait_timeout = cfg["service_wait_timeout"]
        if wait_timeout and elapsed >= wait_timeout:
            fail(
                f"Model service did not become ready within {wait_timeout} seconds; "
                f"last probe: {detail}"
            )
        interval = cfg["service_poll_interval"]
        if wait_timeout:
            interval = min(interval, max(1, wait_timeout - elapsed))
        next_probe = datetime.fromtimestamp(time.time() + interval).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        log(
            "WAIT",
            f"Service not ready (probe {attempt}: {detail}); "
            f"next probe in {interval}s at {next_probe}",
        )
        time.sleep(interval)


def verify_dataset(cfg: Dict) -> None:
    dataset_path = cfg.get("dataset_path")
    dataset_name = cfg.get("dataset_name")
    expected = cfg.get("expected_samples", 0)
    if not dataset_path:
        return
    try:
        from datasets import load_dataset

        dataset = load_dataset(
            dataset_path,
            dataset_name or None,
            split=cfg["dataset_split"],
            cache_dir=cfg["hf_datasets_cache"],
        )
    except Exception as exc:  # noqa: BLE001 - surface dataset/cache failures
        fail(f"Dataset preflight failed for {dataset_path}/{dataset_name}: {exc}")
    actual = len(dataset)
    if expected and actual != expected:
        fail(f"Dataset sample count mismatch: expected {expected}, found {actual}")
    log("INFO", f"Dataset ready: {dataset_path}/{dataset_name}, split={cfg['dataset_split']}, samples={actual}")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "run"


def create_run_dir(cfg: Dict) -> Path:
    run_id = cfg.get("run_id", "auto")
    if not run_id or run_id == "auto":
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = Path(cfg["output_root"]) / safe_name(cfg["eval_model"]) / safe_name(run_id)
    run_dir.mkdir(parents=True, exist_ok=False)
    # A fresh output root or a reused human-readable label must not resume a
    # previous service's responses. Only retries within this invocation share it.
    cfg["run_nonce"] = uuid.uuid4().hex
    if isinstance(cfg, ConfigSnapshot):
        cfg.snapshot_hashes = {"source_config": cfg["source_config_sha256"]}
        with (run_dir / "source_config.json").open("xb") as handle:
            handle.write(cfg.source_bytes)
    effective_bytes = (json.dumps(cfg, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if isinstance(cfg, ConfigSnapshot):
        cfg.snapshot_hashes["effective_config"] = hashlib.sha256(effective_bytes).hexdigest()
    with (run_dir / "effective_config.json").open("xb") as handle:
        handle.write(effective_bytes)
    return run_dir


def cache_identity(cfg: Dict, task: str) -> str:
    """Bind a response cache to this invocation and its complete configuration."""
    identity = {"schema_version": 1, "task": task, "config": cfg,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()


def build_command(cfg: Dict, task: str, task_dir: Path) -> List[str]:
    # SQLite WAL/locking is unreliable on shared NFS mounts. Keep response
    # cache local to the evaluation container while results remain on NFS.
    cache_dir = (
        Path(cfg["cache_root"])
        / safe_name(cfg["eval_model"])
        / task_dir.parent.name
        / safe_name(task)
        / cache_identity(cfg, task)
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "responses.sqlite"
    model_args = ",".join(
        [
            f"model={cfg['model_name']}",
            f"base_url={cfg['base_url']}",
            f"num_concurrent={cfg['num_concurrent']}",
            f"timeout={cfg['timeout']}",
            f"max_retries={cfg['api_max_retries']}",
        ]
    )
    command = [
        "lm_eval",
        "--tasks",
        task,
        "--output_path",
        str(task_dir),
        "--model",
        cfg["model_type"],
        "--model_args",
        model_args,
        "--use_cache",
        str(cache_file),
        "--log_samples",
        "--verbosity",
        "INFO",
    ]
    if cfg.get("gen_kwargs"):
        command.extend(["--gen_kwargs", cfg["gen_kwargs"]])
    if cfg.get("apply_chat_template"):
        command.append("--apply_chat_template")
    if cfg["limit"] > 0:
        command.extend(["--limit", str(cfg["limit"])])
    if cfg.get("include_path"):
        include_path = Path(cfg["include_path"])
        if not include_path.is_dir():
            fail(f"include_path is not a directory: {include_path}")
        command.extend(["--include_path", str(include_path)])
    return command


class RunInterrupted(KeyboardInterrupt):
    def __init__(self, signum=signal.SIGINT):
        self.signum = signum
        super().__init__(f"Run interrupted by signal {signum}")


class ProcessCleanupError(RuntimeError):
    """Do not retry while a previously created worker may still be running."""


@contextmanager
def termination_signals(cancel_event=None):
    """CLI-only signal handling; worker threads observe the shared cancellation."""
    previous = {}
    interrupted = False

    def interrupt(signum, _frame):
        nonlocal interrupted
        if cancel_event is not None:
            cancel_event.set()
        if interrupted:
            return  # A repeated signal must not interrupt owned-process cleanup.
        interrupted = True
        raise RunInterrupted(signum)

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, interrupt)
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def stop_owned_process(process) -> None:
    """Reap only a Popen started below with its own new POSIX session.

    No external PID, service, or process-name discovery is permitted here.
    SIGKILL of this supervisor itself cannot execute this cleanup; callers must
    not claim the supervisor can control descendants that escape its process group.
    """
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    # The leader may have exited while its children still own stdout or run.
    # This group was created exclusively for this invocation, not a service.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def run_streaming(
    command: List[str],
    log_file: Path,
    sidecar_command: Optional[List[str]] = None,
    *,
    cancel_event=None,
    logger=None,
) -> int:
    (logger or log)("INFO", "Command: " + " ".join(command))
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] command={' '.join(command)}\n")
        handle.flush()
        process = sidecar = reader = None
        lines = queue.Queue()
        reader_stop = threading.Event()

        def read_output():
            try:
                for line in process.stdout:
                    if reader_stop.is_set():
                        break
                    lines.put(line)
            except Exception as exc:
                lines.put(exc)
            finally:
                lines.put(None)

        try:
            if cancel_event is not None and cancel_event.is_set():
                raise RunInterrupted()
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, start_new_session=True,
            )
            if sidecar_command:
                sidecar = subprocess.Popen(sidecar_command + ["--pid", str(process.pid)],
                                           start_new_session=True)
            assert process.stdout is not None
            # A blocking readline in a shard thread cannot observe cancellation.
            # The consumer polls while this daemon only reads its owned pipe.
            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise RunInterrupted()
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                if isinstance(line, Exception):
                    raise line
                handle.write(line)
                handle.flush()
                print(line, end="", flush=True)
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    raise RunInterrupted()
                time.sleep(0.1)
            return process.wait()
        finally:
            reader_stop.set()
            cleanup_errors = []
            for owned in (sidecar, process):
                if owned is None:
                    continue
                try:
                    stop_owned_process(owned)
                except Exception as exc:
                    cleanup_errors.append(f"PID {owned.pid}: {exc}")
            if reader is not None:
                reader.join(timeout=5)
                if reader.is_alive():
                    cleanup_errors.append("owned stdout reader did not stop (detached descendants are unsupported)")
            if (process is not None and process.stdout is not None
                    and (reader is None or not reader.is_alive())):
                try:
                    process.stdout.close()
                except OSError as exc:
                    cleanup_errors.append(f"Cannot close owned stdout: {exc}")
            if cleanup_errors:
                raise ProcessCleanupError("Owned process cleanup failed: " + "; ".join(cleanup_errors))


def newest_result(task_dir: Path) -> Optional[Path]:
    files = list(task_dir.rglob("results_*.json"))
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def newest_samples(task: str, task_dir: Path) -> Optional[Path]:
    files = list(task_dir.rglob(f"samples_{task}_*.jsonl"))
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def validate_samples(cfg: Dict, task: str, task_dir: Path) -> bool:
    samples_file = newest_samples(task, task_dir)
    if samples_file is None:
        log("ERROR", f"No samples JSONL was found for {task} under {task_dir}")
        return False
    row_count = 0
    doc_timeouts: Dict[str, bool] = {}
    doc_filters = {}
    doc_identities = {}
    schema = None
    with samples_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row_count += 1
            try:
                record = json.loads(line)
            except ValueError:
                log("ERROR", f"Malformed samples JSON at row {row_count}")
                return False
            if not isinstance(record, dict):
                log("ERROR", f"Sample row {row_count} must be an object")
                return False
            responses = json.dumps(
                {
                    "resps": record.get("resps"),
                    "filtered_resps": record.get("filtered_resps"),
                },
                ensure_ascii=False,
            )
            doc_id = str(record.get("doc_id", f"line-{row_count}"))
            if cfg.get("formal_acceptance"):
                if type(record.get("doc_id")) not in (int, str) or not doc_id.strip():
                    log("ERROR", f"Missing or invalid doc_id at row {row_count}")
                    return False
                def valid_response(value):
                    if isinstance(value, str):
                        return bool(value.strip())
                    return isinstance(value, list) and bool(value) and all(valid_response(v) for v in value)
                if record.get("error") or record.get("errors") or not valid_response(record.get("resps")):
                    log("ERROR", f"Empty or failed response at row {row_count}")
                    return False
                # The prescribed FlagEval version writes one row per filter;
                # other harness versions write one row per document. Never mix
                # the two schemas or silently deduplicate a repeated result.
                row_schema = "filter" if "filter" in record else "document"
                if schema is not None and schema != row_schema:
                    log("ERROR", "Mixed document and per-filter sample schemas")
                    return False
                schema = row_schema
                sample_filter = record.get("filter")
                if row_schema == "filter" and (not isinstance(sample_filter, str) or not sample_filter.strip()):
                    log("ERROR", f"Invalid filter at row {row_count}")
                    return False
                filters = doc_filters.setdefault(doc_id, set())
                if sample_filter in filters:
                    log("ERROR", f"Duplicate (doc_id, filter) at row {row_count}")
                    return False
                filters.add(sample_filter)
                identity_fields = ("doc", "arguments", "target", "resps", "doc_hash", "prompt_hash", "target_hash")
                try:
                    identity = hashlib.sha256(json.dumps(
                        {key: record[key] for key in identity_fields if key in record},
                        sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
                except (ValueError, TypeError):
                    log("ERROR", f"Invalid sample identity at row {row_count}")
                    return False
                # Per-filter rows must carry real input identity, not just the
                # same document number. Keep legacy single-row samples usable.
                has_input = bool(record.get("arguments")) or bool(record.get("prompt_hash"))
                if doc_id in doc_identities:
                    previous_identity, previous_has_input = doc_identities[doc_id]
                    if not has_input or not previous_has_input or previous_identity != identity:
                        log("ERROR", f"Conflicting or unidentified input/response across filters for doc_id={doc_id}")
                        return False
                doc_identities[doc_id] = (identity, has_input)
            is_timeout = bool(record.get("timeout")) or "<TIMEOUT>" in responses
            doc_timeouts[doc_id] = doc_timeouts.get(doc_id, False) or is_timeout
    sample_count = len(doc_timeouts)
    timeout_count = sum(doc_timeouts.values())
    if cfg.get("formal_acceptance"):
        if not doc_filters:
            log("ERROR", "Samples file is empty")
            return False
        coverage = next(iter(doc_filters.values()))
        if any(filters != coverage for filters in doc_filters.values()):
            log("ERROR", "Incomplete per-filter document coverage")
            return False
        if len(coverage) > 1 and coverage != {"strict-match", "flexible-extract"}:
            log("ERROR", "Unsupported multi-filter schema; add a versioned schema fixture before using it")
            return False
        metric = cfg.get("acceptance_criteria", {}).get(task, {}).get("metric", "")
        if schema == "filter" and "," in metric and metric.rsplit(",", 1)[1] not in coverage:
            log("ERROR", "Samples do not cover the acceptance criterion's filter")
            return False
    expected = cfg["limit"] if cfg["limit"] > 0 else cfg.get("expected_samples", 0)
    log(
        "INFO",
        f"Samples file: {samples_file}, unique_samples={sample_count}, "
        f"rows={row_count}, timeouts={timeout_count}",
    )
    if expected and sample_count != expected:
        log("ERROR", f"Result sample count mismatch: expected {expected}, found {sample_count}")
        return False
    if timeout_count and not cfg.get("allow_timeouts", False):
        log("ERROR", f"Result contains {timeout_count} <TIMEOUT> responses and allow_timeouts is false")
        return False
    if timeout_count:
        log(
            "WARN",
            f"Accepting {timeout_count} <TIMEOUT> responses; lm-eval counts them as incorrect answers",
        )
    return True


def report_result(cfg: Dict, task: str, task_dir: Path) -> bool:
    result_file = newest_result(task_dir)
    if result_file is None:
        log("ERROR", f"lm-eval exited successfully but no results JSON was found under {task_dir}")
        return False
    try:
        with result_file.open("r", encoding="utf-8") as handle:
            result = json.load(handle)
        metrics = result.get("results", {}).get(task)
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        log("ERROR", f"Unreadable or malformed results JSON {result_file}: {exc}")
        return False
    if not isinstance(metrics, dict) or not metrics:
        log("ERROR", f"No metrics for task {task} in {result_file}")
        return False
    log("INFO", f"Result file: {result_file}")
    for key, value in metrics.items():
        if isinstance(value, (int, float, str, bool)) or value is None:
            log("RESULT", f"{task}: {key}={value}")
    errors = metric_errors(cfg, task, metrics)
    if errors:
        for error in errors:
            log("ERROR", error)
        return False
    try:
        return validate_samples(cfg, task, task_dir)
    except (OSError, ValueError, TypeError) as exc:
        log("ERROR", f"Cannot validate samples for {task}: {exc}")
        return False


def run_task(cfg: Dict, task: str, run_dir: Path, attempt_records=None) -> bool:
    if attempt_records is None:
        attempt_records = []
    task_dir = run_dir / safe_name(task)
    task_dir.mkdir(parents=True, exist_ok=False)
    command = build_command(cfg, task, task_dir)
    log_file = task_dir / "lm_eval.log"
    score_command = None
    score_interval = cfg.get("progress_score_interval", 0)
    score_helper = Path(__file__).resolve().with_name("score_progress.py")
    if score_interval and task == "gpqa_diamond_generative_cot":
        if not score_helper.is_file():
            log("WARN", f"Interim score helper not found: {score_helper}")
        else:
            cache_base = Path(command[command.index("--use_cache") + 1])
            score_command = [
                sys.executable,
                str(score_helper),
                "--config",
                str(run_dir / "effective_config.json"),
                "--cache-db",
                str(cache_base) + "_rank0.db",
                "--interval",
                str(score_interval),
                "--poll-seconds",
                str(cfg["progress_score_poll_seconds"]),
                "--output",
                str(task_dir / "progress_score.log"),
            ]

    attempts = cfg["eval_max_retries"] + 1
    for attempt in range(1, attempts + 1):
        log("STEP", f"Starting {task}, attempt {attempt}/{attempts}")
        # Isolate result files by attempt; only the response cache is shared.
        attempt_dir = task_dir / f"attempt-{attempt}"
        attempt_dir.mkdir(exist_ok=False)
        attempt_command = command.copy()
        attempt_command[attempt_command.index("--output_path") + 1] = str(attempt_dir)
        record = {"attempt": attempt, "output_dir": str(attempt_dir),
                  "returncode": None, "status": "failed", "errors": []}
        attempt_records.append(record)
        try:
            return_code = run_streaming(attempt_command, log_file, score_command)
        except (KeyboardInterrupt, ProcessCleanupError):
            record["errors"].append("evaluation interrupted or owned process cleanup failed")
            raise
        except Exception as exc:
            record["errors"].append(f"{type(exc).__name__}: {exc}")
            log("ERROR", f"Evaluation process failed: {exc}")
            return_code = None
        record["returncode"] = return_code
        if return_code == 0:
            if report_result(cfg, task, attempt_dir):
                record["status"] = "passed"
                return True
            record["errors"].append("result validation failed")
            log("ERROR", "lm_eval returned 0, but result validation failed")
        elif return_code is not None and return_code < 0:
            record["errors"].append(f"evaluation terminated by signal {-return_code}")
            log("ERROR", f"lm_eval was terminated by signal {-return_code}")
        elif return_code is not None:
            record["errors"].append(f"evaluation exited with code {return_code}")
            log("ERROR", f"lm_eval exited with code {return_code}")
        if attempt >= attempts:
            return False
        healthy, detail = probe_service(cfg)
        log("WARN", f"Retry preflight: service_healthy={healthy}, detail={detail}")
        log(
            "WARN",
            f"Retrying in {cfg['retry_delay']} seconds; completed responses remain "
            "in the container-local SQLite cache",
        )
        time.sleep(cfg["retry_delay"])
    return False


def write_acceptance_report(cfg, run_dir, failed, task_attempts, errors):
    """Publish one terminal report, without replacing any earlier evidence."""
    report = {
        "schema_version": 1, "kind": "formal_accuracy", "status": "failed" if failed or errors else "passed",
        "run_id": run_dir.name, "service_mode": cfg["service_mode"],
        "configured_concurrency": cfg["num_concurrent"], "observed_concurrency": None,
        "observation_note": "Actual concurrency must be recorded from service or client telemetry separately.",
        "expected_samples": cfg["expected_samples"], "allow_timeouts": False,
        "source_config_sha256": cfg["source_config_sha256"],
        "criteria": cfg["acceptance_criteria"], "failed_tasks": list(failed),
        "artifacts": {}, "task_attempts": task_attempts, "errors": list(errors),
        "config_artifacts": {},
    }
    for task in cfg["tasks"]:
        records = task_attempts.get(task, [])
        directory = Path(records[-1]["output_dir"]) if records else run_dir / safe_name(task)
        artifacts = {}
        try:
            for name, path in (("results", newest_result(directory)),
                               ("samples", newest_samples(task, directory))):
                if path:
                    artifacts[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        except OSError as exc:
            report["errors"].append(f"{task}: cannot bind result artifacts: {exc}")
        report["artifacts"][task] = artifacts
    for name in ("source_config", "effective_config"):
        path = run_dir / f"{name}.json"
        try:
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                report["config_artifacts"][name] = {"path": str(path), "sha256": digest}
                expected = getattr(cfg, "snapshot_hashes", {}).get(name)
                if expected is not None and digest != expected:
                    report["errors"].append(f"{name} snapshot changed after run creation")
            elif name in getattr(cfg, "snapshot_hashes", {}):
                report["errors"].append(f"{name} snapshot is missing")
        except OSError as exc:
            report["errors"].append(f"Cannot bind {name}: {exc}")
    if report["errors"]:
        report["status"] = "failed"
        if not report["failed_tasks"]:
            report["failed_tasks"] = list(cfg["tasks"])
    fd, temporary = tempfile.mkstemp(prefix=".acceptance-result-", suffix=".tmp", dir=run_dir)
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # link publishes a complete file atomically and refuses an existing
        # destination; unlike replace it cannot overwrite historical evidence.
        os.link(temporary, run_dir / "acceptance-result.json")
    finally:
        temporary.unlink(missing_ok=True)
    return report["status"] == "passed"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="explicit model-specific configuration path")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="validate service, model id, and offline dataset without starting lm-eval",
    )
    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve()
    cfg = load_config(config_path)
    configure_environment(cfg)

    if shutil.which("lm_eval") is None:
        fail("lm_eval is not available on PATH")
    verify_dataset(cfg)

    log("INFO", f"Tasks={cfg['tasks']}, limit={cfg['limit'] or 'full'}, concurrency={cfg['num_concurrent']}")
    if args.preflight_only:
        healthy, detail = probe_service(cfg)
        if not healthy:
            fail(f"Model service is not ready: {detail}")
        log("INFO", f"Model service ready: {detail}")
        log("INFO", "Preflight completed; lm-eval was not started")
        return
    wait_for_service(cfg)
    run_dir = create_run_dir(cfg)

    failed, completed, errors, task_attempts = [], set(), [], {}
    try:
        with termination_signals():
            log("INFO", f"Run directory: {run_dir}")
            for task in cfg["tasks"]:
                task_attempts[task] = []
                if not run_task(cfg, task, run_dir, task_attempts[task]):
                    failed.append(task)
                completed.add(task)
    except BaseException as exc:
        failed.extend(task for task in cfg["tasks"] if task not in completed)
        errors.append(f"{type(exc).__name__}: {exc}")
        if isinstance(exc, KeyboardInterrupt):
            raise SystemExit(128 + getattr(exc, "signum", signal.SIGINT)) from None
        if isinstance(exc, SystemExit) and not exc.code:
            raise SystemExit(1) from exc
        raise
    finally:
        if cfg.get("formal_acceptance"):
            if not write_acceptance_report(cfg, run_dir, failed, task_attempts, errors) and not failed:
                failed.extend(cfg["tasks"])
    if failed:
        fail("Failed tasks: " + ", ".join(failed))
    log("INFO", "All tasks completed successfully")


if __name__ == "__main__":
    main()
