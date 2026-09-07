"""Read-only service observation answering one admitted worker challenge.

Run the observer on the host after dispatch. No service is started/stopped and
no container permissions are changed.
The nonce prevents reuse of an earlier observation; this is cooperative local
coordination, not authentication against an actor who can rewrite run files.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
import stat
import subprocess
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_identity(value):
    require(isinstance(value, dict) and set(value) == {
        "container_id", "boot_id", "start_ticks", "cmdline_sha256"},
        "service process_identity requires container_id/boot_id/start_ticks/cmdline_sha256")
    for key in ("container_id", "cmdline_sha256"):
        require(isinstance(value[key], str) and re.fullmatch(r"[0-9a-f]{64}", value[key]),
                f"service process_identity.{key} must be a complete SHA-256/ID")
    require(isinstance(value["boot_id"], str) and re.fullmatch(
        r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", value["boot_id"]), "invalid Linux boot_id")
    require(type(value["start_ticks"]) is int and value["start_ticks"] > 0, "invalid service start_ticks")


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, allow_nan=False)
        stream.write("\n")


def read_complete(path):
    # The writer owns an exclusive file; readers may see its first partial write.
    # Partial content is never accepted, only retried within a fixed deadline.
    try:
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 65536,
                "unsafe observation file: expected one small regular unlinked file")
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def request_observation(root, manifest, *, timeout=60):
    root = Path(root)
    nonce = secrets.token_hex(32)
    write_new(root / "service-challenge.json", {"nonce": nonce, "service_instance_id": manifest["service_instance_id"]})
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = read_complete(root / "service-observation.json")
        if response is not None:
            require(response.get("nonce") == nonce, "service observation belongs to another challenge")
            require(response.get("status") == "verified", f"live service observation failed: {response.get('error')}")
            require(response.get("service_instance_id") == manifest["service_instance_id"], "service instance binding changed")
            require(type(response.get("pid")) is int and response["pid"] == manifest["service_pid"], "service PID changed")
            require(type(response.get("listening_port")) is int
                    and response["listening_port"] == manifest["run_plan"]["service_port"],
                    "observed process does not own the requested API listener")
            validate_identity(response.get("process_identity"))
            require(response["process_identity"] == manifest["service_process_identity"], "live service identity changed")
            return response
        time.sleep(0.1)
    raise ValueError("no live host service observation within 60 seconds; no model requests started")


def observe(root, manifest, *, timeout=45):
    root = Path(root)
    require(root.is_absolute() and root.resolve() == root and root.is_dir(), "observer needs a canonical prepared run")
    require(root == Path(manifest["workspace"]["host_root"]) / "05-runs" / manifest["run_plan"]["run_id"],
            "observer run does not match the manifest's assigned host workspace")
    validate_identity(manifest["service_process_identity"])
    deadline = time.monotonic() + timeout
    challenge = None
    while time.monotonic() < deadline:
        challenge = read_complete(root / "service-challenge.json")
        if challenge is not None:
            break
        terminal = read_complete(root / "exit-status.json")
        require(terminal is None, f"worker ended before service observation: {terminal}")
        time.sleep(0.1)
    require(isinstance(challenge, dict) and isinstance(challenge.get("nonce"), str)
            and re.fullmatch(r"[0-9a-f]{64}", challenge["nonce"]), "worker did not issue a valid live challenge")
    response = {"nonce": challenge["nonce"], "status": "failed",
                "service_instance_id": manifest["service_instance_id"], "pid": manifest["service_pid"]}
    try:
        require(challenge.get("service_instance_id") == manifest["service_instance_id"], "challenge instance mismatch")
        name = manifest["target_container_name"]
        pid = manifest["service_pid"]
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name), "invalid service container")
        require(type(pid) is int and pid > 0, "invalid service PID")
        result = subprocess.run(["docker", "inspect", name], cwd=root, check=True,
                                capture_output=True, text=True, timeout=10)
        records = json.loads(result.stdout)
        require(isinstance(records, list) and len(records) == 1, "service container is ambiguous")
        container = records[0]
        require(container["State"]["Running"] is True, "service container is stopped")
        require(container.get("HostConfig", {}).get("NetworkMode") == "host", "service must use the confirmed host network")
        evaluator = subprocess.run(["docker", "inspect", manifest["workspace"]["evaluator_container"]], cwd=root,
                                   check=True, capture_output=True, text=True, timeout=10)
        evaluators = json.loads(evaluator.stdout)
        require(isinstance(evaluators, list) and len(evaluators) == 1
                and evaluators[0].get("State", {}).get("Running") is True
                and evaluators[0].get("HostConfig", {}).get("NetworkMode") == "host",
                "evaluator must share the confirmed host network for localhost requests")
        # Pin the immutable container ID, not a name that could be replaced.
        container_id = container["Id"]
        require(container_id == manifest["service_process_identity"]["container_id"], "service container was replaced")
        port = manifest["run_plan"]["service_port"]
        require(type(port) is int and 0 < port <= 65535, "invalid service port")
        probe = """import pathlib,hashlib,json,sys
p=pathlib.Path('/proc')/sys.argv[1]
port=int(sys.argv[2])
s=p.joinpath('stat').read_text()
ticks=int(s[s.rfind(')')+2:].split()[19])
cmd=p.joinpath('cmdline').read_bytes()
sockets=set()
for fd in p.joinpath('fd').iterdir():
    try:
        sockets.add(str(fd.readlink()))
    except FileNotFoundError:
        continue
listeners=set()
for protocol in ('tcp','tcp6'):
    table=p/'net'/protocol
    if not table.exists():
        continue
    for line in table.read_text().splitlines()[1:]:
        fields=line.split()
        if len(fields)<=9 or fields[3]!='0A' or int(fields[1].rsplit(':',1)[1],16)!=port:
            continue
        if protocol=='tcp6':
            sys.exit('IPv6 listener scope is not supported by this IPv4 localhost observer')
        if fields[1].split(':')[0] in ('0100007F','00000000'):
            listeners.add('socket:['+fields[9]+']')
if not listeners or not listeners.issubset(sockets):
    sys.exit('recorded service PID does not own the requested LISTEN socket')
s2=p.joinpath('stat').read_text()
if not cmd or ticks!=int(s2[s2.rfind(')')+2:].split()[19]):
    sys.exit('empty command or PID changed during probe')
print(json.dumps({'start_ticks':ticks,'cmdline_sha256':hashlib.sha256(cmd).hexdigest(),
    'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'listening_port':port}))
"""
        result = subprocess.run(["docker", "exec", "--workdir", manifest["workspace"]["container_root"],
            container_id, "python3", "-B", "-c", probe, str(pid), str(port)], cwd=root, check=True,
            capture_output=True, text=True, timeout=15)
        details = json.loads(result.stdout)
        require(type(details.get("listening_port")) is int and details["listening_port"] == port,
                "service listener observation missing")
        identity = {key: details[key] for key in ("start_ticks", "cmdline_sha256", "boot_id")}
        identity["container_id"] = container_id
        validate_identity(identity)
        require(identity == manifest["service_process_identity"], "live PID/start/boot/command identity differs from recorded service")
        response.update(status="verified", process_identity=identity, listening_port=port)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        response["error"] = str(exc)
    response["observed_at"] = datetime.now(timezone.utc).isoformat()
    write_new(root / "service-observation.json", response)
    require(response["status"] == "verified", response.get("error", "service observation failed"))
    return response


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--manifest-json", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(observe(args.run_dir, json.loads(args.manifest_json))))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"service observation refused: {exc}")
