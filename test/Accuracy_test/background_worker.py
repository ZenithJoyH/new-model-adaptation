"""Bound run plans for isolated background evaluations.

The long-lived worker, not its detached launcher, owns the evaluation lifecycle.
This module validates the declared workspace and service scope without reserving
shared devices, services, or source checkouts.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

from remote_workspace import validate_run, validate_tree, config_paths, scoped_environment
from service_observation import request_observation


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_plan(path, root, expected_scope):
    """Validate caller-owned model/platform identity and workspace binding."""
    require(isinstance(expected_scope, dict) and set(expected_scope) == {"model", "platform", "host_alias", "service_port"},
            "caller must explicitly supply model/platform/host_alias/service_port")
    require(all(isinstance(expected_scope[key], str) and expected_scope[key].strip() for key in ("model", "platform", "host_alias"))
            and type(expected_scope["service_port"]) is int and 0 < expected_scope["service_port"] <= 65535,
            "invalid expected model/platform/service scope")
    path, root = Path(path), Path(root)
    require(path.is_absolute() and path.is_file() and not path.is_symlink(),
            "run plan must be an explicit regular absolute JSON path")
    raw = path.read_bytes()
    plan = json.loads(raw)
    require(isinstance(plan, dict), "run plan must be a JSON object")
    require(type(plan.get("schema_version")) is int and plan["schema_version"] == 5,
            "unsupported run plan schema")
    validate_run(plan, root)
    require(path.parent == root, "run plan must be deployed directly in its assigned run")
    require(all(plan.get(key) == value for key, value in expected_scope.items()),
            "run plan identity does not match the caller's expected scope")
    require(isinstance(plan.get("run_id"), str) and bool(re.fullmatch(r"[A-Za-z0-9_.-]+", plan["run_id"]))
            and plan["run_id"] not in ("auto", ".", ".."), "run plan requires an explicit new run_id")
    require(type(plan.get("service_port")) is int, "run plan service_port must be an integer")
    return plan, hashlib.sha256(raw).hexdigest()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-plan", required=True, type=Path)
    parser.add_argument("--worker", action="store_true", help="Internal long-lived worker; owns the evaluation lifecycle")
    parser.add_argument("--plan-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--admission-sha256", help=argparse.SUPPRESS)
    parser.add_argument("--workspace-plan-json", help=argparse.SUPPRESS)
    parser.add_argument("--check-plan", action="store_true", help="Read-only validation; no process or HTTP request")
    args = parser.parse_args(argv)
    if args.worker and (args.check_plan or not args.plan_sha256 or not args.workspace_plan_json or not args.admission_sha256):
        parser.error("worker requires bound plan digest/workspace and cannot use --check-plan")
    return args


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def input_hashes(root, names):
    return {name: sha256(Path(root) / name) for name in names}


def admission_hash(root, tracked_names):
    bound = {"inputs": input_hashes(root, tracked_names),
             "manifest": sha256(Path(root) / "workflow-manifest.json")}
    return hashlib.sha256(json.dumps(bound, sort_keys=True).encode()).hexdigest()


def admission(root, plan, expected_scope):
    """Re-run the canonical gate, not a second interpretation of passed labels."""
    from accuracy_admission import validate_snapshot

    validate_run(plan, root)
    validate_tree(root)
    manifest = json.loads((root / "workflow-manifest.json").read_text())
    validate_snapshot(root / "workflow", manifest, expected_scope, plan)
    require(sha256(root / "llm_config.json") == manifest["accuracy_config_sha256"],
            "deployed accuracy config differs from the current workflow-bound config")
    config = json.loads((root / "llm_config.json").read_text())
    require(config.get("run_id") == plan["run_id"], "accuracy config must use the explicit plan run_id")
    config_paths(config, root)
    return manifest, config


@contextmanager
def environment_scope(environment):
    previous = os.environ.copy()
    os.environ.clear()
    os.environ.update(environment)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


def run_attached(command, *, cwd, env=None):
    """Forward controlled termination until the direct runner exits."""
    process = None
    cancelled = None

    def forward(signum, frame):
        nonlocal cancelled
        cancelled = signum
        if process is not None and process.poll() is None:
            process.send_signal(signum)

    previous = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        if cancelled is not None:
            return 128 + cancelled
        process = subprocess.Popen(command, cwd=cwd, env=env)
        if cancelled is not None and process.poll() is None:
            process.send_signal(cancelled)
        try:
            result = process.wait()
        except BaseException:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
            process.wait()
            raise
        if cancelled is not None and result == 0:
            return 128 + cancelled  # A cancelled run must not publish a pass.
        return result if result >= 0 else 128 - result
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def worker(root, args, command, verify, tracked_names, *, expected_scope):
    root = Path(root)
    # The dispatch-bound workspace survives a deleted/corrupted run plan.
    # Validate it *before* creating even a failure receipt. Never resolve an
    # unexpected caller root into an apparently acceptable location.
    bound_plan = json.loads(args.workspace_plan_json)
    validate_run(bound_plan, root)
    validate_tree(root)
    # Exclusive claim prevents direct --worker invocations from overwriting an
    # existing worker's evidence.
    require(not (root / "exit-status.json").exists(), "exit status exists; do not reuse a historical run")
    write_new(root / "worker-claim.json", {"pid": os.getpid(), "plan_sha256": args.plan_sha256})
    status = {"returncode": 2, "status": "failed", "plan_sha256": args.plan_sha256}
    try:
        plan, digest = read_plan(args.run_plan, root, expected_scope)
        require(digest == args.plan_sha256, "run plan changed since dispatch")
        require(sha256(args.run_plan) == digest, "run plan changed before admission")
        require(admission_hash(root, tracked_names) == args.admission_sha256,
                "workflow/configuration/bundle changed since dispatch")
        manifest_digest = sha256(root / "workflow-manifest.json")
        before = input_hashes(root, tracked_names)
        manifest, config = admission(root, plan, expected_scope)
        require(admission_hash(root, tracked_names) == args.admission_sha256,
                "workflow/configuration/bundle changed during admission")
        environment = scoped_environment(root, config, create=True)
        with environment_scope(environment):
            observation = request_observation(root, manifest)
            verify(root, command)
            admission(root, plan, expected_scope)
        require(input_hashes(root, tracked_names) == before, "runner/configuration/evidence changed during preflight")
        require(sha256(args.run_plan) == digest, "run plan changed during preflight")
        require(sha256(root / "workflow-manifest.json") == manifest_digest, "workflow manifest changed during preflight")
        require(admission_hash(root, tracked_names) == args.admission_sha256, "admission changed during preflight")
        write_new(root / "worker-started.json", {"status": "running", "pid": os.getpid(),
            "run_id": plan["run_id"], "plan_sha256": digest, "input_sha256": before,
            "command": command, "service_observation": observation,
            "workflow_manifest_sha256": manifest_digest,
            "admission_sha256": args.admission_sha256,
            "started_at": datetime.now().astimezone().isoformat()})
        rc = run_attached(command, cwd=root, env=environment)
        status.update(returncode=rc, status="passed" if rc == 0 else "failed")
        status["finished_at"] = datetime.now().astimezone().isoformat()
        write_new(root / "exit-status.json", status)
        return rc
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, ImportError, subprocess.SubprocessError) as exc:
        status["error"] = str(exc)
    status["finished_at"] = datetime.now().astimezone().isoformat()
    write_new(root / "exit-status.json", status)
    return status["returncode"]


def launch(root, script, args, command, verify, tracked_names, *, expected_scope):
    """Dispatch only; worker-started/exit-status are the authoritative states."""
    root = Path(root)
    if args.worker:
        # The dispatched worker must record plan deletion/corruption/visibility
        # failures itself, rather than escaping before its exclusive claim.
        return worker(root, args, command, verify, tracked_names, expected_scope=expected_scope)
    plan, digest = read_plan(args.run_plan, root, expected_scope)
    admitted_digest = admission_hash(root, tracked_names)
    manifest, config = admission(root, plan, expected_scope)
    require(admission_hash(root, tracked_names) == admitted_digest and sha256(args.run_plan) == digest,
            "plan/workflow/configuration/bundle changed during dispatch admission")
    if args.check_plan:
        print(json.dumps({"status": "plan_validated_only", "run_id": plan["run_id"], "plan_sha256": digest}))
        return 0
    require(not any((root / name).exists() for name in ("launch.json", "worker-claim.json", "worker-started.json", "exit-status.json")),
            "run already dispatched or completed; inspect it instead of relaunching")
    (root / "launch-claim").mkdir()
    with (root / "gpqa-launcher.log").open("x") as log:
        process = subprocess.Popen([sys.executable, "-B", "-u", str(script), "--worker",
            "--run-plan", str(args.run_plan), "--plan-sha256", digest,
            "--admission-sha256", admitted_digest, "--workspace-plan-json", json.dumps(plan)], cwd=root,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True, close_fds=True, env=scoped_environment(root, config))
    record = {"status": "dispatched", "supervisor_pid": process.pid,
        "run_id": plan["run_id"], "plan_sha256": digest, "command": command,
        "admission_sha256": admitted_digest,
        "started_at": datetime.now().astimezone().isoformat(),
        "note": "Dispatch is not admission or success; inspect worker-started.json and exit-status.json."}
    write_new(root / "launch.json", record)
    print(json.dumps(record), flush=True)
    return 0
