"""Bound paths for cooperative accuracy workers; not an OS sandbox.

The host CLI is injected read-only before Ansible's first remote module, so
Ansible need not create ~/.ansible before the assigned workspace is checked.
Only --mode create writes, after both existing container mappings are checked.
"""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def absolute_path(value):
    require(isinstance(value, str) and value == value.strip() and value.startswith("/")
            and not value.startswith("//") and value != "/"
            and posixpath.normpath(value) == value
            and not any(ord(c) < 32 or ord(c) == 127 or c in "$~<>\\" for c in value),
            "workspace paths must be explicit normalized non-root absolute POSIX paths")
    return Path(value)


def workspace_paths(plan):
    require(type(plan.get("schema_version")) is int and plan["schema_version"] == 5,
            "workspace-aware workers require run plan schema_version=5")
    workspace = plan.get("workspace")
    require(isinstance(workspace, dict) and set(workspace) == {
        "host_root", "container_root", "evaluator_container", "evaluator_root"},
        "run plan requires explicit host, service-container and evaluator workspace mappings")
    for key in ("host_root", "container_root", "evaluator_root"):
        absolute_path(workspace[key])
    require(isinstance(workspace["evaluator_container"], str)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", workspace["evaluator_container"]),
            "evaluator_container must be an explicit container name or ID")
    run_id = plan.get("run_id")
    require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", run_id)
            and run_id not in ("auto", ".", ".."), "an explicit new run_id is required")
    return {"host_run_dir": str(Path(workspace["host_root"]) / "04-runs" / run_id),
            "container_run_dir": str(Path(workspace["evaluator_root"]) / "04-runs" / run_id),
            "evaluator_container": workspace["evaluator_container"]}


def real_path(path):
    """Reject existing symlink components, including parents of future outputs."""
    path = absolute_path(str(path))
    require(path.resolve() == path, f"symlink/alias path is not allowed: {path}")
    for part in (path, *path.parents):
        require(not part.is_symlink(), f"symlink path is not allowed: {part}")
    return path


def validate_run(plan, root, *, side="container", existing=True):
    paths = workspace_paths(plan)
    expected = Path(paths["host_run_dir" if side == "host" else "container_run_dir"])
    root = absolute_path(str(root))
    require(root == expected, f"run directory must be the declared workspace/04-runs/run_id: {expected}")
    base = real_path(plan["workspace"]["host_root" if side == "host" else "evaluator_root"])
    require(base.is_dir(), f"assigned workspace must already exist: {base}")
    real_path(root)
    if existing:
        require(root.is_dir(), f"prepared run directory is missing: {root}")
    return root


def validate_tree(root):
    """Do not let a staged symlink or hard link redirect a later helper write."""
    root = real_path(root)
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            info = path.lstat()
            require(not stat.S_ISLNK(info.st_mode), f"run contains a symlink: {path}")
            require(stat.S_ISDIR(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1),
                    f"run contains a special file or hard link: {path}")


def config_paths(config, run, *, check_filesystem=True):
    """Known evaluator write locations must be explicit and inside this run.

    Dataset inputs may be read elsewhere, but Hugging Face's *cache* is writable
    even offline. It is not treated as a read-only dataset exception.
    """
    run = absolute_path(str(run))
    paths = {}
    for key in ("output_root", "cache_root", "hf_datasets_cache"):
        value = config.get(key)
        require(isinstance(value, str) and value and value == value.strip()
                and not any(ord(c) < 32 or ord(c) == 127 or c in "$~<>\\" for c in value),
                f"accuracy config requires an explicit {key} under this run")
        require(".." not in PurePosixPath(value).parts, f"{key} must not traverse parents")
        path = Path(value)
        # llmrun resolves output/cache against its config, but HF receives its
        # datasets path verbatim. Require the latter absolute to avoid ambiguity.
        if key == "hf_datasets_cache":
            require(path.is_absolute(), "hf_datasets_cache must be absolute")
        if not path.is_absolute():
            path = run / path
        path = absolute_path(str(path))
        require(path != run and path.is_relative_to(run), f"{key} must stay under this run: {run}")
        if check_filesystem:
            real_path(path)
        paths[key] = path
    return paths


def scoped_environment(root, config, *, create=False):
    """Route supported library caches and temporary files, without changing HOME."""
    root = real_path(root)
    paths = config_paths(config, root)
    locations = {
        "TMPDIR": root / "tmp", "TMP": root / "tmp", "TEMP": root / "tmp",
        "XDG_CACHE_HOME": root / "cache/xdg", "XDG_CONFIG_HOME": root / "config/xdg",
        "XDG_DATA_HOME": root / "data/xdg", "XDG_STATE_HOME": root / "state/xdg",
        "HF_HOME": root / "cache/huggingface", "HF_HUB_CACHE": root / "cache/huggingface/hub",
        "HUGGINGFACE_HUB_CACHE": root / "cache/huggingface/hub",
        "HF_DATASETS_CACHE": paths["hf_datasets_cache"],
        "TRANSFORMERS_CACHE": root / "cache/transformers", "NUMBA_CACHE_DIR": root / "cache/numba",
        "TORCH_HOME": root / "cache/torch", "TORCH_EXTENSIONS_DIR": root / "cache/torch_extensions",
        "TRITON_CACHE_DIR": root / "cache/triton", "CUDA_CACHE_PATH": root / "cache/cuda",
        "MPLCONFIGDIR": root / "cache/matplotlib", "PIP_CACHE_DIR": root / "cache/pip",
    }
    for path in {*locations.values(), *paths.values()}:
        real_path(path)
    if create:
        for path in {*locations.values(), *paths.values()}:
            path.mkdir(parents=True, exist_ok=True)
            real_path(path)
    environment = os.environ.copy()
    environment.update({key: str(path) for key, path in locations.items()})
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    # Keep the observed loopback socket as the request destination even when
    # the operator has general HTTP(S)/ALL_PROXY settings. Preserve other hosts.
    bypass = []
    for value in (environment.get("NO_PROXY", ""), environment.get("no_proxy", ""), "127.0.0.1,localhost,::1"):
        for host in value.split(","):
            if host.strip() and host.strip() not in bypass:
                bypass.append(host.strip())
    environment["NO_PROXY"] = environment["no_proxy"] = ",".join(bypass)
    return environment


def mapped_host_root(container, container_root):
    """Require a writable bind, reject volume ambiguity and nested mount shadows."""
    require(container.get("State", {}).get("Running") is True, "required container is not running")
    target = absolute_path(container_root)
    covering = []
    for mount in container.get("Mounts", []):
        destination = Path(mount["Destination"])
        require(not (destination != target and destination.is_relative_to(target)),
                f"nested mount shadows the assigned workspace: {destination}")
        if target.is_relative_to(destination):
            covering.append(mount)
    require(bool(covering), f"no explicit bind mapping covers container root {target}")
    mount = max(covering, key=lambda item: len(Path(item["Destination"]).parts))
    require(mount.get("Type") == "bind" and mount.get("RW") is True,
            "workspace requires a writable bind; named volumes and read-only mounts are not inferred")
    source = real_path(mount["Source"])
    return real_path(source / target.relative_to(mount["Destination"]))


def inspect_host(plan, target_container, mode, *, evaluator_image=None):
    paths = workspace_paths(plan)
    require(isinstance(target_container, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", target_container),
            "target container must be explicit")
    workspace = plan["workspace"]
    root = validate_run(plan, paths["host_run_dir"], side="host", existing=mode == "existing")
    if root.exists():
        validate_tree(root)  # Includes Ansible's tmp before its first module.
    host_root = Path(workspace["host_root"])
    # No local/remote path is created until both actual mappings have passed.
    for name, container_root in ((target_container, workspace["container_root"]),
                                 (workspace["evaluator_container"], workspace["evaluator_root"])):
        result = subprocess.run(["docker", "inspect", name], cwd=host_root, capture_output=True,
                                text=True, check=True, timeout=10)
        records = json.loads(result.stdout)
        require(isinstance(records, list) and len(records) == 1, "docker inspect must identify exactly one container")
        require(records[0].get("HostConfig", {}).get("NetworkMode") == "host",
                "localhost accuracy endpoints require both containers to use the confirmed host network")
        if name == workspace["evaluator_container"] and evaluator_image is not None:
            require(records[0].get("Config", {}).get("Image") == evaluator_image,
                    "evaluator image differs from the workflow's accuracy_image")
        require(mapped_host_root(records[0], container_root) == host_root,
                f"{name}: container root does not map to the assigned host root")
        subprocess.run(["docker", "exec", "--workdir", container_root, name, "python3", "-B", "-c",
            "import pathlib,sys; p=pathlib.Path(sys.argv[1]); r=p/'runs'/sys.argv[2]; "
            "valid=p.is_dir() and p.resolve()==p and r.resolve()==r and not r.is_symlink(); "
            "sys.exit(0 if valid else 'workspace/run symlink or alias')",
            container_root, plan["run_id"]], cwd=host_root, check=True, capture_output=True, text=True, timeout=15)
    if mode == "create":
        require(not root.exists(), "run already exists; historical runs cannot be reused or overwritten")
        root.parent.mkdir(exist_ok=True)
        real_path(root.parent)
        root.mkdir()  # Exclusive, unlike an idempotent mkdir -p of the run itself.
        (root / "tmp").mkdir()
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-plan-json", required=True)
    parser.add_argument("--target-container", required=True)
    parser.add_argument("--evaluator-image", required=True)
    parser.add_argument("--mode", required=True, choices=("inspect", "create", "existing"))
    args = parser.parse_args(argv)
    require(bool(args.evaluator_image.strip()), "evaluator image must be explicit")
    print(json.dumps(inspect_host(json.loads(args.run_plan_json), args.target_container, args.mode,
                                 evaluator_image=args.evaluator_image)))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"workspace refused: {exc}")
