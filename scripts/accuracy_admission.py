#!/usr/bin/env python3
"""Export/verify a relocatable snapshot of the existing accuracy workflow gate.

No remote calls or model requests. A snapshot records trusted local evidence,
not a signature or proof that a remote process is still alive. Export checks an
ephemeral local copy without changing source files or recorded workflow state.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import subprocess
import sys
import tempfile

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
GATE_FILES = ("scripts/adapt_model.py", "scripts/workflow_state.py",
              "scripts/remote_workspace.py",
              "scripts/service_observation.py",
              "test/Accuracy_test/acceptance_contract.py")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _scope(scope):
    _require(isinstance(scope, dict) and set(scope) == {"model", "platform", "host_alias", "service_port"},
             "scope must explicitly contain model/platform/host_alias/service_port")
    for field in ("model", "platform", "host_alias"):
        value = scope[field]
        _require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value)
                 and value not in ("_template", ".", ".."), f"invalid scope.{field}")
    _require(type(scope["service_port"]) is int and 0 < scope["service_port"] <= 65535, "invalid service port")


def _relative(value):
    _require(isinstance(value, str) and bool(value) and not value.startswith("/")
             and value == posixpath.normpath(value) and value not in (".", "..")
             and not value.startswith("../") and not any(ord(c) < 32 or c == "\\" for c in value),
             f"unsafe repository-relative path: {value!r}")
    return value


def _read(root, relative):
    relative = _relative(relative)
    path = root
    parts = relative.split("/")
    for index, part in enumerate(parts):
        path = path / part
        info = path.lstat()
        _require(not stat.S_ISLNK(info.st_mode), f"symlink is not permitted: {path}")
        _require(stat.S_ISREG(info.st_mode) if index == len(parts) - 1 else stat.S_ISDIR(info.st_mode),
                 f"unexpected file type: {path}")
    _require(info.st_size <= MAX_FILE_BYTES, f"snapshot source is too large: {path}")
    raw = path.read_bytes()
    _require(len(raw) <= MAX_FILE_BYTES, f"snapshot source grew too large: {path}")
    raw.decode("utf-8")
    return raw


def _mapping(raw, label):
    import yaml
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"{label} is not valid YAML: {exc}") from exc
    _require(isinstance(value, dict), f"{label} must be a mapping")
    return value


def _capture(root, scope):
    """Read each required source once; derive references from those same bytes."""
    model = f"models/{scope['model']}"
    platform = f"{model}/{scope['platform']}"
    mandatory = [*GATE_FILES, "inventory/hosts.yml", f"models/_template/{scope['platform']}/platform.yml",
                 "templates/adaptation/runtime-config.yml", "templates/adaptation/acceptance-plan.md",
                 f"{model}/model.yml", f"{model}/architecture-and-inference.md", f"{platform}/platform.yml",
                 *[f"{platform}/environment/{name}" for name in
                   ("runtime-config.yml", "environment-target.yml", "environment-analysis.md",
                    "plugin-change-review.md", "deployment-identity.yml", "service-state.yml")],
                 f"{platform}/acceptance/acceptance-plan.md"]
    captured = {name: _read(root, name) for name in mandatory}
    runtime = _mapping(captured[f"{platform}/environment/runtime-config.yml"], "runtime")
    config = _mapping(captured[f"{platform}/platform.yml"], "platform")
    accuracy = runtime.get("acceptance", {}).get("accuracy_config")
    _relative(accuracy)
    _require(accuracy.startswith(f"{platform}/acceptance/"), "accuracy_config must be repository-relative and owned by this platform")
    captured[accuracy] = _read(root, accuracy)
    workflow = config.get("workflow", {})
    for stage in ("architecture", "environment", "adaptation", "execution-mode", "sanity"):
        if stage in ("execution-mode", "sanity"):
            record = workflow.get("acceptance", {}).get("records", {}).get(stage, {})
            references = [record.get("evidence")]
        else:
            phase = workflow.get(stage, {})
            references = [phase.get("evidence"), phase.get("verification", {}).get("evidence")]
        for reference in references:
            _require(isinstance(reference, str) and bool(reference) and not reference.startswith("/"),
                     f"{stage} evidence must use a relocatable relative path")
            name = _relative(posixpath.normpath(f"{platform}/{reference}"))
            owner = model if stage == "architecture" else platform
            _require(name.startswith(owner + "/"), f"{stage} evidence escapes its model/platform")
            if name not in captured:
                captured[name] = _read(root, name)
    _require(sum(len(raw) for raw in captured.values()) <= MAX_TOTAL_BYTES, "snapshot exceeds compact evidence size limit")
    return captured, runtime, accuracy


def _check_plan(root, scope, plan, runtime):
    # Deployed callers place the canonical workspace helper beside this module.
    import adapt_model as workflow

    _require(isinstance(plan, dict) and type(plan.get("schema_version")) is int and plan["schema_version"] == 5,
             "accuracy admission requires run plan schema 5")
    for field, value in scope.items():
        _require(type(plan.get(field)) is type(value) and plan[field] == value, f"run plan {field} differs from scope")
    _require(runtime.get("model") == scope["model"] and runtime.get("platform") == scope["platform"], "runtime identity differs")
    target = runtime.get("target", {})
    _require(target.get("hosts") == [scope["host_alias"]], "accuracy snapshot requires exactly one target host")
    _require(not workflow.workspace_errors(runtime), "runtime workspace declaration is invalid")
    expected_root = runtime["workspace"]["roots"][0]
    workspace = plan.get("workspace")
    _require(isinstance(workspace, dict) and set(workspace) == {"host_root", "container_root", "evaluator_container", "evaluator_root"},
             "run plan workspace must contain both declared roots and explicit evaluator mapping")
    for field in ("host_root", "container_root"):
        _require(workspace[field] == expected_root[field], f"plan workspace.{field} differs from runtime")
    evaluation_scope = {"target": {"hosts": target["hosts"], "container_name": workspace["evaluator_container"]},
                        "workspace": {"roots": [{"host_alias": scope["host_alias"], "host_root": workspace["host_root"],
                                                   "container_root": workspace["evaluator_root"]}]}}
    _require(not workflow.workspace_errors(evaluation_scope), "invalid explicit evaluator workspace mapping")
    _require(runtime.get("service", {}).get("port") == scope["service_port"], "plan service port differs from runtime")


def _accuracy_paths(raw, plan):
    from remote_workspace import config_paths, workspace_paths
    config = json.loads(raw)
    _require(isinstance(config, dict) and config.get("run_id") == plan.get("run_id"),
             "accuracy config run_id must exactly match run plan")
    paths = workspace_paths(plan)
    # These are declarations about remote paths. Never resolve them against
    # the controller's unrelated filesystem during export or snapshot checks.
    config_paths(config, paths["container_run_dir"], check_filesystem=False)


def _service_identity(state):
    from service_observation import validate_identity
    service = state.get("service")
    _require(isinstance(service, dict), "service state requires a service mapping")
    _require(type(service.get("pid")) is int and service["pid"] > 0, "service.pid must be a positive integer")
    _require(isinstance(service.get("instance_id"), str) and bool(service["instance_id"].strip()),
             "service.instance_id must be explicitly recorded")
    identity = service.get("process_identity")
    validate_identity(identity)
    return service


def _run_gate(root, scope):
    command = [sys.executable, "-B", str(root / "scripts/adapt_model.py"), "--repo-root", str(root),
               scope["model"], "--platform", scope["platform"], "--hosts", scope["host_alias"],
               "--steps", "acceptance", "--acceptance-substeps", "accuracy", "--check-only"]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    _require(result.returncode == 0, "accuracy workflow gate refused: " + (result.stderr or result.stdout)[-5000:])


def _stable(root, captured):
    for name, raw in captured.items():
        _require(_read(root, name) == raw, f"workflow input changed during admission: {name}")


def validate_snapshot(snapshot_root, manifest, scope, plan):
    """Read-only verification of workflow, workspace and service bindings."""
    # The worker only deploys this small entry module at its run root. Resolve
    # every gate helper from the snapshot in a fresh interpreter, never from a
    # controller module cache or an unrelated top-level checkout. The snapshot
    # files are checked before _validate_snapshot imports these helpers.
    try:
        _require(not Path(snapshot_root).is_symlink(), "snapshot root must not be a symlink")
        root = Path(snapshot_root).resolve(strict=True)
        code = ("import importlib.util,json,pathlib,sys; "
                "spec=importlib.util.spec_from_file_location('admission_entry',sys.argv[1]); "
                "module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
                "sys.path.insert(0,str(pathlib.Path(sys.argv[2])/'scripts')); "
                "payload=json.load(sys.stdin); "
                "module._validate_snapshot(sys.argv[2],payload['manifest'],payload['scope'],payload['plan'])")
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        environment.pop("PYTHONPATH", None)
        result = subprocess.run([sys.executable, "-B", "-c", code, str(Path(__file__).resolve()), str(root)],
                                input=_canonical({"manifest": manifest, "scope": scope, "plan": plan}).decode("utf-8"),
                                cwd=root, capture_output=True, text=True, timeout=60, env=environment)
        _require(result.returncode == 0, "deployed accuracy workflow refused: " + (result.stderr or result.stdout)[-5000:])
    except (OSError, TypeError, subprocess.SubprocessError) as exc:
        raise ValueError(f"invalid accuracy admission snapshot: {exc}") from exc


def _validate_snapshot(snapshot_root, manifest, scope, plan):
    """Isolated implementation; use validate_snapshot from worker integrations."""
    try:
        _scope(scope)
        root = Path(snapshot_root).resolve(strict=True)
        _require(isinstance(manifest, dict) and type(manifest.get("schema_version")) is int and manifest["schema_version"] == 1,
                 "unsupported accuracy admission manifest")
        for field in ("model", "platform", "host_alias"):
            _require(manifest.get(field) == scope[field], f"manifest {field} differs from scope")
        _require(_canonical(manifest.get("run_plan")) == _canonical(plan)
                 and manifest.get("run_plan_sha256") == _digest(_canonical(plan)), "manifest is bound to a different run plan")
        hashes = manifest.get("files_sha256")
        _require(isinstance(hashes, dict) and bool(hashes), "manifest file hashes are missing")
        actual = set()
        for directory, subdirectories, filenames in os.walk(root, followlinks=False):
            for name in subdirectories + filenames:
                path = Path(directory) / name
                _require(not path.is_symlink(), f"snapshot contains symlink: {path}")
            actual.update((Path(directory) / name).relative_to(root).as_posix() for name in filenames)
        _require(actual == set(hashes), "snapshot file set differs from manifest")
        captured, runtime, accuracy = _capture(root, scope)
        _require(set(captured) == set(hashes), "snapshot contains missing or unnecessary workflow files")
        for name, raw in captured.items():
            _require(hashes[name] == _digest(raw), f"snapshot hash mismatch: {name}")
        _check_plan(root, scope, plan, runtime)
        _accuracy_paths(captured[accuracy], plan)
        platform = root / "models" / scope["model"] / scope["platform"]
        from workflow_state import deployment_fingerprint
        state = _mapping(captured[(platform.relative_to(root) / "environment/service-state.yml").as_posix()], "service state")
        service = _service_identity(state)
        _require(manifest.get("runtime_sha256") == _digest(captured[(platform.relative_to(root) / "environment/runtime-config.yml").as_posix()]), "runtime hash mismatch")
        _require(manifest.get("deployment_fingerprint") == deployment_fingerprint(platform), "deployment fingerprint mismatch")
        _require(manifest.get("service_instance_id") == service["instance_id"], "service instance mismatch")
        _require(type(manifest.get("service_pid")) is int and manifest["service_pid"] == service["pid"]
                 and _canonical(manifest.get("service_process_identity")) == _canonical(service["process_identity"]),
                 "service process identity mismatch")
        _require(manifest.get("workspace") == plan["workspace"] and manifest.get("target_container_name") == runtime["target"]["container_name"], "manifest workspace/container mismatch")
        _require(manifest.get("evaluator_image") == runtime["acceptance"]["accuracy_image"], "manifest evaluator image mismatch")
        _require(manifest.get("accuracy_config_repo_path") == accuracy and manifest.get("accuracy_config_sha256") == _digest(captured[accuracy]), "accuracy config binding mismatch")
        _run_gate(root, scope)
        _stable(root, captured)
    except (OSError, TypeError, KeyError, AttributeError, RuntimeError, subprocess.SubprocessError) as exc:
        raise ValueError(f"invalid accuracy admission snapshot: {exc}") from exc


def build_snapshot(repo_root, scope, plan):
    """Validate source and deployed-form gates, returning original UTF-8 contents."""
    try:
        _scope(scope)
        _require(not Path(repo_root).is_symlink(), "repository root must not be a symlink")
        root = Path(repo_root).resolve(strict=True)
        captured, runtime, accuracy = _capture(root, scope)
        _check_plan(root, scope, plan, runtime)
        _accuracy_paths(captured[accuracy], plan)
        prefix = f"models/{scope['model']}/{scope['platform']}"
        service = _service_identity(_mapping(captured[f"{prefix}/environment/service-state.yml"], "service state"))
        _run_gate(root, scope)
        _stable(root, captured)
        from workflow_state import deployment_fingerprint
        platform = root / "models" / scope["model"] / scope["platform"]
        prefix = platform.relative_to(root).as_posix()
        plan = json.loads(_canonical(plan))
        manifest = {"schema_version": 1, **{key: scope[key] for key in ("model", "platform", "host_alias")},
                    "runtime_sha256": _digest(captured[f"{prefix}/environment/runtime-config.yml"]),
                    "deployment_fingerprint": deployment_fingerprint(platform),
                    "service_instance_id": service["instance_id"], "service_pid": service["pid"],
                    "service_process_identity": service["process_identity"],
                    "target_container_name": runtime["target"]["container_name"], "workspace": plan["workspace"],
                    "evaluator_image": runtime["acceptance"]["accuracy_image"],
                    "run_plan": plan, "run_plan_sha256": _digest(_canonical(plan)),
                    "files_sha256": {name: _digest(raw) for name, raw in sorted(captured.items())},
                    "accuracy_config_repo_path": accuracy, "accuracy_config_sha256": _digest(captured[accuracy])}
        with tempfile.TemporaryDirectory(prefix="accuracy-admission-") as directory:
            snapshot_root = Path(directory)
            for name, raw in captured.items():
                target = snapshot_root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(raw)
            validate_snapshot(snapshot_root, manifest, scope, plan)
        _stable(root, captured)
        return {"manifest": manifest, "files": {name: raw.decode("utf-8") for name, raw in sorted(captured.items())}}
    except (OSError, TypeError, KeyError, AttributeError, RuntimeError, subprocess.SubprocessError) as exc:
        raise ValueError(f"cannot export accuracy admission: {exc}") from exc


def _plan_bytes(path):
    _require(path.is_absolute(), "run plan path must be absolute")
    for component in (path, *path.parents):
        _require(not component.is_symlink(), f"run plan path must not contain a symlink: {component}")
    info = path.stat()
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "run plan must be a regular file, not a hard link")
    _require(info.st_size <= MAX_FILE_BYTES, "run plan is too large")
    raw = path.read_bytes()
    _require(len(raw) <= MAX_FILE_BYTES, "run plan grew too large")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--run-plan", type=Path)
    parser.add_argument("--framework", help="新框架使用 profile gate，不导出旧目录快照")
    parser.add_argument("--hosts")
    parser.add_argument("--artifact-root", action="append", default=[])
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.framework:
            _require(args.check_only and args.run_plan is None,
                     "framework admission 使用 --check-only；旧 background snapshot 不支持框架工作区")
            from types import SimpleNamespace
            from framework_evidence import check_command
            return check_command(SimpleNamespace(**vars(args), steps="acceptance", acceptance_substeps="accuracy",
                                 verify_records=False, evidence_info=None))
        _require(args.run_plan is not None, "legacy snapshot 必须提供 --run-plan")
        raw = _plan_bytes(args.run_plan)
        plan = json.loads(raw)
        scope = {"model": args.model, "platform": args.platform, "host_alias": plan["host_alias"], "service_port": plan["service_port"]}
        payload = build_snapshot(args.repo_root, scope, plan)
        _require(_plan_bytes(args.run_plan) == raw, "run plan changed during export")
        payload["manifest"]["run_plan_source_sha256"] = _digest(raw)
        print(json.dumps(payload, ensure_ascii=False, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"Accuracy admission export refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
