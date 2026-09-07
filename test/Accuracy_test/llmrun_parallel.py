#!/usr/bin/env python3
"""Run sharded lm-eval API accuracy jobs against multiple model services."""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import threading
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from llmrun import (ConfigSnapshot, ProcessCleanupError, RunInterrupted, cache_identity,
                    run_streaming as supervised_streaming, termination_signals,
                    validate_samples)


_LOG_LOCK = threading.Lock()


def log(level: str, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _LOG_LOCK:
        print(f"[{stamp}] [{level:<5}] {message}", flush=True)


def fail(message: str, code: int = 1) -> None:
    log("ERROR", message)
    raise SystemExit(code)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "run"


def resolve_path(value: str, config_dir: Path) -> str:
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = config_dir / path
    return str(path.resolve())


def parse_api_list(value: str) -> List[Tuple[str, str]]:
    services: List[Tuple[str, str]] = []
    for raw_entry in value.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        marker = entry.find(":http")
        if marker <= 0:
            fail(f"Invalid api_list entry {entry!r}; expected model:http://...")
        model = entry[:marker].strip()
        url = entry[marker + 1 :].strip()
        if not model or not re.match(r"^https?://", url):
            fail(f"Invalid api_list entry {entry!r}; expected model:http://...")
        services.append((model, url))
    if not services:
        fail("api_list contains no usable services")
    return services


def load_config(config_path: Path) -> Dict:
    if not config_path.is_file():
        fail(f"Configuration file does not exist: {config_path}")
    source_bytes = config_path.read_bytes()
    cfg = json.loads(source_bytes)
    if not isinstance(cfg, dict):
        fail("Configuration must be a JSON object")
    if cfg.get("formal_acceptance"):
        fail("The parallel runner is diagnostic only; use llmrun.py for formal acceptance")
    cfg = ConfigSnapshot(cfg, source_bytes)

    legacy_retries = cfg.get("max_retries", 3)
    defaults = {
        "task": "gpqa_diamond_generative_cot",
        "limit": 0,
        "gen_kwargs": "temperature=1,top_p=0.95,max_gen_toks=30000",
        "num_concurrent": 8,
        "timeout": 3600,
        "api_max_retries": legacy_retries,
        "eval_max_retries": 0,
        "retry_delay": 60,
        "tokenizer": "",
        "dataset_dir": "",
        "data_parallel_size": 0,
        "shards": [],
        "merge_only": False,
        "progress_interval": 10,
        "output_root": "./outputs",
        "cache_root": "/tmp/lm_eval_cache",
        "run_id": "auto",
        "offline": True,
        "hf_datasets_cache": "/root/.cache/huggingface/datasets",
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
    for key in ("eval_model", "api_list", "task"):
        if not cfg.get(key):
            fail(f"Missing required configuration key: {key}")

    integer_keys = (
        "limit", "num_concurrent", "timeout", "api_max_retries",
        "eval_max_retries", "retry_delay", "data_parallel_size",
        "progress_interval", "expected_samples", "service_poll_interval",
        "service_wait_timeout",
        "progress_score_interval", "progress_score_poll_seconds",
    )
    for key in integer_keys:
        try:
            cfg[key] = int(cfg[key])
        except (TypeError, ValueError):
            fail(f"{key} must be an integer")
    if cfg["limit"] < 0 or cfg["data_parallel_size"] < 0:
        fail("limit and data_parallel_size must be >= 0")
    if cfg["num_concurrent"] < 1 or cfg["timeout"] < 1:
        fail("num_concurrent and timeout must be >= 1")
    if cfg["api_max_retries"] < 0 or cfg["eval_max_retries"] < 0:
        fail("api_max_retries and eval_max_retries must be >= 0")
    if cfg["retry_delay"] < 0 or cfg["service_wait_timeout"] < 0:
        fail("retry_delay and service_wait_timeout must be >= 0")
    if cfg["service_poll_interval"] < 1:
        fail("service_poll_interval must be >= 1")
    if cfg["progress_score_interval"] < 0 or cfg["progress_score_poll_seconds"] < 1:
        fail("progress_score_interval must be >= 0 and progress_score_poll_seconds must be >= 1")

    config_dir = config_path.parent.resolve()
    for key in ("output_root", "cache_root", "dataset_dir", "hf_datasets_cache"):
        cfg[key] = resolve_path(cfg[key], config_dir)
    cfg["services"] = parse_api_list(str(cfg["api_list"]))
    if type(cfg.get("merge_only")) is not bool:
        fail("merge_only must be a JSON boolean")
    if cfg["merge_only"] and (not cfg.get("run_id") or cfg["run_id"] == "auto"):
        fail("merge_only requires the explicit run_id of the completed shard run")
    if not cfg.get("run_id") or cfg["run_id"] == "auto":
        cfg["run_id"] = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    else:
        cfg["run_id"] = safe_name(str(cfg["run_id"]))

    service_count = len(cfg["services"])
    if cfg["data_parallel_size"] == 0:
        cfg["data_parallel_size"] = service_count
    shards = cfg.get("shards") or list(range(service_count))
    try:
        shards = [int(item) for item in shards]
    except (TypeError, ValueError):
        fail("shards must be a list of integers")
    if len(set(shards)) != len(shards):
        fail("shards must not contain duplicates")
    if len(shards) > service_count:
        fail(f"shard count {len(shards)} exceeds service count {service_count}")
    if any(item < 0 or item >= cfg["data_parallel_size"] for item in shards):
        fail(f"shards must be within [0, {cfg['data_parallel_size'] - 1}]")
    cfg["shards"] = shards
    return cfg


def configure_environment(cfg: Dict) -> None:
    os.environ.setdefault("OPENAI_API_KEY", "EMPTY")
    os.environ["HF_DATASETS_CACHE"] = cfg["hf_datasets_cache"]
    if cfg.get("offline", True):
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"


def models_url(base_url: str) -> str:
    replaced = re.sub(r"/v1/.*$", "/v1/models", base_url.rstrip("/"))
    return replaced if replaced != base_url.rstrip("/") else base_url.rstrip("/") + "/v1/models"


def probe_service(model_name: str, base_url: str, timeout: int = 10) -> Tuple[bool, str]:
    url = models_url(base_url)
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        model_ids = [item.get("id") for item in body.get("data", [])]
        if model_name not in model_ids:
            return False, f"HTTP 200, but {model_name!r} is not in {model_ids}"
        return True, f"HTTP 200, models={model_ids}"
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code} from {url}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def wait_for_services(cfg: Dict, selected: List[Tuple[str, str]], cancel_event=None) -> None:
    started = time.monotonic()
    attempt = 0
    while True:
        if cancel_event is not None and cancel_event.is_set():
            raise RunInterrupted()
        attempt += 1
        failures = []
        for model_name, url in selected:
            healthy, detail = probe_service(model_name, url)
            if not healthy:
                failures.append(f"{model_name}@{url}: {detail}")
        if not failures:
            log("INFO", f"All {len(selected)} services are ready after {attempt} probe(s)")
            return
        if not cfg.get("wait_for_service", False):
            fail("Model services are not ready: " + "; ".join(failures))
        elapsed = int(time.monotonic() - started)
        wait_timeout = cfg["service_wait_timeout"]
        if wait_timeout and elapsed >= wait_timeout:
            fail(f"Services did not become ready within {wait_timeout}s: " + "; ".join(failures))
        interval = cfg["service_poll_interval"]
        if wait_timeout:
            interval = min(interval, max(1, wait_timeout - elapsed))
        log("WAIT", f"Services not ready (probe {attempt}); retry in {interval}s: {'; '.join(failures)}")
        if cancel_event is not None:
            if cancel_event.wait(interval):
                raise RunInterrupted()
        else:
            time.sleep(interval)


def sample_stats(samples_file: Path) -> Dict[str, int]:
    doc_timeout: Dict[str, bool] = {}
    rows = 0
    with samples_file.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            rows += 1
            doc_id = str(record.get("doc_id", f"line-{line_number}"))
            responses = json.dumps(
                {"resps": record.get("resps"), "filtered_resps": record.get("filtered_resps")},
                ensure_ascii=False,
            )
            timed_out = bool(record.get("timeout")) or "<TIMEOUT>" in responses
            doc_timeout[doc_id] = doc_timeout.get(doc_id, False) or timed_out
    return {"rows": rows, "samples": len(doc_timeout), "timeouts": sum(doc_timeout.values())}


class ProgressMonitor:
    def __init__(self, output_dir: Path, task: str, interval: int, total: int, label: str):
        self.output_dir = output_dir
        self.task = task
        self.interval = interval
        self.total = total
        self.label = label
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_reported = 0

    def start(self) -> None:
        if self.interval > 0:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.wait(3):
            files = list(self.output_dir.rglob(f"samples_{self.task}_*.jsonl"))
            if not files:
                continue
            stats = sample_stats(max(files, key=lambda path: path.stat().st_mtime))
            if stats["samples"] >= self._last_reported + self.interval:
                total = f"/{self.total}" if self.total else ""
                log("PROG", f"[{self.label}] {stats['samples']}{total} unique samples, timeouts={stats['timeouts']}")
                self._last_reported = stats["samples"]


LOCAL_TASKS = {
    "mmlu", "cmmlu", "gsm8k", "leaderboard_bbh", "hellaswag",
    "truthfulqa_mc1", "winogrande", "commonsense_qa", "piqa",
    "openbookqa", "boolq", "arc_easy", "arc_challenge",
    "minerva_math_algebra", "ceval-valid", "pubmedqa", "medqa_4options",
}


def output_base(cfg: Dict) -> Path:
    return Path(cfg["output_root"]) / safe_name(cfg["eval_model"]) / safe_name(cfg["task"]) / safe_name(cfg["run_id"])


def manifest_config(cfg: Dict) -> Dict:
    # Partial shard invocations and merge-only may select different operations,
    # but cannot change the model, services, task or generation configuration.
    return {key: value for key, value in cfg.items()
            if key not in {"shards", "merge_only", "services"} and not key.startswith("_")}


def initialize_run(cfg: Dict) -> None:
    base = output_base(cfg)
    manifest = {"schema_version": 1, "config": manifest_config(cfg),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "shared_runner_sha256": hashlib.sha256(Path(__file__).with_name("llmrun.py").read_bytes()).hexdigest()}
    encoded = json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n"
    manifest_path = base / "run-manifest.json"
    if base.exists():
        if not manifest_path.is_file() or manifest_path.read_text(encoding="utf-8") != encoded:
            fail("Existing run has no matching immutable manifest; use a new run_id")
    else:
        if cfg.get("merge_only"):
            fail("merge_only cannot create a new run")
        base.mkdir(parents=True, exist_ok=False)
        with manifest_path.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
        with (base / "effective_config.json").open("x", encoding="utf-8") as handle:
            json.dump({key: value for key, value in cfg.items() if key != "services"}, handle, indent=2)
            handle.write("\n")
        if isinstance(cfg, ConfigSnapshot):
            with (base / "source_config.json").open("xb") as handle:
                handle.write(cfg.source_bytes)
    cfg["_manifest_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()


def build_shard_command(cfg: Dict, model_name: str, url: str, shard_idx: int, output_path: Path) -> List[str]:
    task = cfg["task"]
    if task in LOCAL_TASKS:
        model_type = "local-completions"
        url = url.replace("/chat", "")
    else:
        model_type = "openai-chat-completions"
    model_args = ",".join([
        f"model={model_name}", f"base_url={url}",
        f"num_concurrent={cfg['num_concurrent']}", f"timeout={cfg['timeout']}",
        f"max_retries={cfg['api_max_retries']}",
        f"data_parallel_size={cfg['data_parallel_size']}",
        f"data_parallel_shard_id={shard_idx}",
    ])
    if model_type == "local-completions" and cfg.get("tokenizer"):
        model_args += f",tokenized_requests=False,tokenizer={cfg['tokenizer']}"

    # Never put SQLite on the shared NFS output filesystem.
    identity_cfg = {**manifest_config(cfg), "manifest_sha256": cfg["_manifest_sha256"],
                    "output_path": str(output_path.resolve()), "model_name": model_name, "base_url": url}
    cache_dir = (Path(cfg["cache_root"]) / safe_name(cfg["eval_model"]) / cfg["run_id"]
                 / f"shard-{shard_idx}" / cache_identity(identity_cfg, task))
    cache_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "lm_eval", "--tasks", task, "--output_path", str(output_path),
        "--model", model_type, "--model_args", model_args,
        "--use_cache", str(cache_dir / "responses.sqlite"),
        "--log_samples", "--verbosity", "INFO",
    ]
    if cfg.get("gen_kwargs"):
        command.extend(["--gen_kwargs", cfg["gen_kwargs"]])
    command.append("--apply_chat_template" if model_type != "local-completions" else "--trust_remote_code")
    if cfg["limit"] > 0:
        command.extend(["--limit", str(cfg["limit"])])
    if cfg.get("dataset_dir"):
        dataset_dir = Path(cfg["dataset_dir"])
        if not dataset_dir.is_dir():
            fail(f"dataset_dir is not a directory: {dataset_dir}")
        command.extend(["--include_path", str(dataset_dir)])
    return command


def run_streaming(
    command: List[str],
    log_file: Path,
    sidecar_command: Optional[List[str]] = None,
    *,
    cancel_event=None,
) -> int:
    return supervised_streaming(command, log_file, sidecar_command,
                                cancel_event=cancel_event, logger=log)


def newest_samples(task: str, directory: Path) -> Optional[Path]:
    files = list(directory.rglob(f"samples_{task}_*.jsonl"))
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def validate_shard(cfg: Dict, shard_idx: int, directory: Path) -> bool:
    results = list(directory.rglob("results_*.json"))
    samples = list(directory.rglob(f"samples_{cfg['task']}_*.jsonl"))
    if len(results) != 1 or len(samples) != 1 or results[0].parent != samples[0].parent:
        log("ERROR", f"[shard-{shard_idx}] expected one co-located result/sample pair for this attempt")
        return False
    try:
        if not json.loads(results[0].read_text()).get("results", {}).get(cfg["task"]):
            return False
    except (OSError, ValueError, AttributeError):
        return False
    samples_file = newest_samples(cfg["task"], directory)
    if samples_file is None:
        log("ERROR", f"[shard-{shard_idx}] no samples JSONL found under {directory}")
        return False
    stats = sample_stats(samples_file)
    log("INFO", f"[shard-{shard_idx}] samples={stats['samples']}, rows={stats['rows']}, timeouts={stats['timeouts']}")
    if stats["timeouts"] and not cfg.get("allow_timeouts", False):
        log("ERROR", f"[shard-{shard_idx}] result contains timeout responses")
        return False
    if stats["timeouts"]:
        log("WARN", f"[shard-{shard_idx}] accepting {stats['timeouts']} timeout samples")
    # Reuse strict row/schema validation but defer total coverage until merge.
    return validate_samples({**cfg, "formal_acceptance": True, "limit": 0,
                             "expected_samples": 0}, cfg["task"], directory)


def write_shard_receipt(cfg: Dict, shard_idx: int, directory: Path) -> None:
    base = output_base(cfg)
    paths = {"results": next(directory.rglob("results_*.json")),
             "samples": next(directory.rglob(f"samples_{cfg['task']}_*.jsonl"))}
    receipt = {"schema_version": 1, "shard_id": shard_idx,
               "manifest_sha256": cfg["_manifest_sha256"],
               "artifacts": {name: {"path": str(path.relative_to(base)),
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                             for name, path in paths.items()}}
    with (base / f"shard-{shard_idx}" / "shard-result.json").open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2)
        handle.write("\n")


def run_shard(cfg: Dict, shard_idx: int, model_name: str, url: str, cancel_event=None) -> bool:
    base = output_base(cfg)
    shard_output = base / f"shard-{shard_idx}"
    # An existing directory may belong to an active process or a failed run;
    # never overwrite it or consider its old files part of this invocation.
    shard_output.mkdir(exist_ok=False)
    command = build_shard_command(cfg, model_name, url, shard_idx, shard_output)
    label = f"shard-{shard_idx}"
    log("STEP", f"[{label}] model={model_name}, url={url}")
    log("INFO", f"[{label}] command={' '.join(command)}")
    score_command = None
    score_interval = cfg.get("progress_score_interval", 0)
    score_helper = Path(__file__).resolve().with_name("score_progress.py")
    if score_interval and cfg["task"] == "gpqa_diamond_generative_cot":
        if not score_helper.is_file():
            log("WARN", f"[{label}] interim score helper not found: {score_helper}")
        else:
            cache_base = Path(command[command.index("--use_cache") + 1])
            score_command = [
                os.sys.executable,
                str(score_helper),
                "--config",
                str(base / "effective_config.json"),
                "--cache-db",
                str(cache_base) + "_rank0.db",
                "--interval",
                str(score_interval),
                "--poll-seconds",
                str(cfg["progress_score_poll_seconds"]),
                "--output",
                str(shard_output / "progress_score.log"),
            ]
    attempts = cfg["eval_max_retries"] + 1
    for attempt in range(1, attempts + 1):
        attempt_output = shard_output / f"attempt-{attempt}"
        attempt_output.mkdir(exist_ok=False)
        attempt_command = command.copy()
        attempt_command[attempt_command.index("--output_path") + 1] = str(attempt_output)
        monitor = ProgressMonitor(attempt_output, cfg["task"], cfg["progress_interval"], cfg["limit"], label)
        monitor.start()
        valid = False
        return_code = None
        try:
            return_code = run_streaming(
                attempt_command,
                base / f"lm_eval_shard-{shard_idx}.log",
                score_command,
                **({"cancel_event": cancel_event} if cancel_event is not None else {}),
            )
            valid = return_code == 0 and validate_shard(cfg, shard_idx, attempt_output)
        except ProcessCleanupError:
            raise  # No retry if the previous scoped worker could still exist.
        except Exception as exc:
            log("ERROR", f"[{label}] process or result validation failed: {exc}")
        finally:
            monitor.stop()
        if valid:
            write_shard_receipt(cfg, shard_idx, attempt_output)
            log("INFO", f"[{label}] completed on attempt {attempt}/{attempts}")
            return True
        log("ERROR", f"[{label}] lm_eval terminated by signal {-return_code}"
            if return_code is not None and return_code < 0
            else f"[{label}] lm_eval/result validation failed (returncode={return_code})")
        if attempt >= attempts:
            return False
        healthy, detail = probe_service(model_name, url)
        log("WARN", f"[{label}] retry preflight: healthy={healthy}, detail={detail}")
        if not healthy and cfg.get("wait_for_service", False):
            wait_for_services(cfg, [(model_name, url)], cancel_event)
        elif not healthy:
            return False
        log("WARN", f"[{label}] retrying in {cfg['retry_delay']}s; local cache preserves successes")
        if cancel_event is not None:
            if cancel_event.wait(cfg["retry_delay"]):
                return False
        else:
            time.sleep(cfg["retry_delay"])
    return False


def merge_results(cfg: Dict, cancel_event=None) -> bool:
    base = output_base(cfg)
    merge_dirs = []
    seen_ids = set()
    try:
        for shard in range(cfg["data_parallel_size"]):
            shard_root = (base / f"shard-{shard}").resolve()
            receipt = json.loads((shard_root / "shard-result.json").read_text())
            if (receipt.get("schema_version") != 1 or receipt.get("shard_id") != shard
                    or receipt.get("manifest_sha256") != cfg["_manifest_sha256"]):
                raise ValueError(f"shard-{shard}: receipt does not belong to this run")
            paths = {}
            for name in ("results", "samples"):
                item = receipt["artifacts"][name]
                path = (base / item["path"]).resolve()
                if not path.is_relative_to(shard_root) or not path.is_file():
                    raise ValueError(f"shard-{shard}: artifact escapes its shard or is missing")
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                    raise ValueError(f"shard-{shard}: artifact changed after validation")
                paths[name] = path
            if paths["results"].parent != paths["samples"].parent:
                raise ValueError(f"shard-{shard}: result/sample pair differs")
            if not validate_shard(cfg, shard, paths["samples"].parent):
                raise ValueError(f"shard-{shard}: sample validation failed")
            ids = {str(json.loads(line)["doc_id"]) for line in paths["samples"].read_text().splitlines() if line.strip()}
            if seen_ids.intersection(ids):
                raise ValueError(f"shard-{shard}: document IDs overlap another shard")
            seen_ids.update(ids)
            merge_dirs.append(str(paths["results"].parent))
        expected = cfg["limit"] if cfg["limit"] > 0 else cfg["expected_samples"]
        if expected and len(seen_ids) != expected:
            raise ValueError(f"Full shard union has {len(seen_ids)} documents; expected {expected}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        log("ERROR", f"Cannot merge current shards: {exc}")
        return False
    # Each merge attempt also gets fresh output; a previous successful result
    # cannot rescue a current merger that exits zero without writing anything.
    merged = Path(tempfile.mkdtemp(prefix="merge-", dir=base))
    cfg["_merge_dir"] = str(merged)
    command = ["lm_eval", "--merge_results", ",".join(merge_dirs), "--output_path", str(merged)]
    log("INFO", "Merge command: " + " ".join(command))
    return run_streaming(command, merged / "merge.log",
                         **({"cancel_event": cancel_event} if cancel_event is not None else {})) == 0


def report_merged_result(cfg: Dict) -> bool:
    base = Path(cfg["_merge_dir"])
    files = sorted(base.glob("results_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        log("ERROR", f"No merged results JSON found directly under {base}")
        return False
    try:
        with files[0].open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        task_data = data.get("results", {}).get(cfg["task"], {})
        counts = data.get("n-samples", {}).get(cfg["task"], {})
        if not isinstance(counts, dict):
            raise ValueError("n-samples task counts must be an object")
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        log("ERROR", f"Malformed merged result: {exc}")
        return False
    if not isinstance(task_data, dict) or not task_data:
        log("ERROR", f"No metrics for {cfg['task']} in {files[0]}")
        return False
    for key, value in task_data.items():
        if isinstance(value, (int, float, str, bool)) or value is None:
            log("RESULT", f"{cfg['task']}: {key}={value}")
    effective = counts.get("effective", counts.get("original", 0))
    timeouts = counts.get("timeout", 0)
    expected = cfg["limit"] if cfg["limit"] > 0 else cfg["expected_samples"]
    log("INFO", f"Merged counts: effective={effective}, timeouts={timeouts}, expected={expected or 'unset'}")
    if expected and effective != expected:
        log("ERROR", f"Merged sample count mismatch: expected {expected}, found {effective}")
        return False
    if timeouts and not cfg.get("allow_timeouts", False):
        log("ERROR", f"Merged result contains {timeouts} timeout samples")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", nargs="?", default="llm_parallel_config.json")
    parser.add_argument("--preflight-only", action="store_true",
                        help="validate configuration and selected services without running lm-eval")
    args = parser.parse_args()
    cfg = load_config(Path(args.config).expanduser().resolve())
    configure_environment(cfg)
    if shutil.which("lm_eval") is None:
        fail("lm_eval is not available on PATH")

    selected = [cfg["services"][idx] for idx in range(len(cfg["shards"]))]
    log("INFO", f"model={cfg['eval_model']}, task={cfg['task']}, shards={cfg['shards']}, "
        f"parallel_size={cfg['data_parallel_size']}, concurrency={cfg['num_concurrent']}")
    log("INFO", f"output={output_base(cfg)}, local_cache={cfg['cache_root']}/{safe_name(cfg['eval_model'])}/{cfg['run_id']}")
    if args.preflight_only:
        wait_for_services({**cfg, "wait_for_service": False}, selected)
        log("INFO", "Preflight completed; lm-eval was not started")
        return

    initialize_run(cfg)
    cancel_event = threading.Event()
    try:
        with termination_signals(cancel_event):
            execute_run(cfg, selected, cancel_event)
    except KeyboardInterrupt as exc:
        raise SystemExit(128 + getattr(exc, "signum", signal.SIGINT)) from None


def execute_run(cfg, selected, cancel_event):
    started = time.time()
    if not cfg.get("merge_only", False):
        wait_for_services(cfg, selected, cancel_event)
        failed: List[int] = []
        with ThreadPoolExecutor(max_workers=len(selected)) as executor:
            futures = {}
            try:
                for service_index, shard_idx in enumerate(cfg["shards"]):
                    model_name, url = selected[service_index]
                    futures[executor.submit(run_shard, cfg, shard_idx, model_name, url, cancel_event)] = shard_idx
                for future in as_completed(futures):
                    shard_idx = futures[future]
                    try:
                        if not future.result():
                            failed.append(shard_idx)
                    except Exception as exc:
                        log("ERROR", f"[shard-{shard_idx}] unexpected error: {exc}")
                        failed.append(shard_idx)
            except BaseException:
                cancel_event.set()
                for future in futures:
                    future.cancel()
                raise
        if failed:
            fail(f"Failed shards: {sorted(failed)}")

    if cfg.get("merge_only", False) or len(cfg["shards"]) == cfg["data_parallel_size"]:
        if not merge_results(cfg, cancel_event):
            fail("Failed to merge shard results")
        if not report_merged_result(cfg):
            fail("Merged result validation failed")
        elapsed = int(time.time() - started)
        log("INFO", f"Parallel evaluation completed in {elapsed // 60}m{elapsed % 60}s")
    else:
        log("INFO", "Partial shard set completed; run merge_only after all shards are available")


if __name__ == "__main__":
    main()
