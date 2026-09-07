"""Offline service identity/challenge fixtures; Docker is always mocked."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "service_observation_test_subject", ROOT / "scripts/service_observation.py"
)
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


class ServiceObservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="service-observation-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.host = self.root / "host"
        self.host.mkdir()
        self.run = self.host / "05-runs/fixture-run"
        self.run.mkdir(parents=True)
        self.identity = {
            "container_id": "c" * 64,
            "boot_id": "12345678-abcd-1234-abcd-123456789abc",
            "start_ticks": 1200,
            "cmdline_sha256": hashlib.sha256(b"fixture-service\x00--port\x008010\x00").hexdigest(),
        }
        self.nonce = "a" * 64
        self.manifest = {
            "workspace": {"host_root": str(self.host), "container_root": "/service/workspace",
                          "evaluator_root": "/evaluator/workspace", "evaluator_container": "fixture-evaluator"},
            "run_plan": {"run_id": "fixture-run", "service_port": 8010},
            "target_container_name": "fixture-service",
            "service_instance_id": "fixture-instance",
            "service_pid": 123,
            "service_process_identity": self.identity,
        }

    def challenge(self, **changes):
        value = {"nonce": self.nonce, "service_instance_id": self.manifest["service_instance_id"]}
        value.update(changes)
        observer.write_new(self.run / "service-challenge.json", value)
        return value

    def response(self, **changes):
        value = {"nonce": self.nonce, "status": "verified", "service_instance_id": "fixture-instance",
                 "pid": 123, "process_identity": copy.deepcopy(self.identity), "listening_port": 8010}
        value.update(changes)
        return value

    def docker(self, *, record=None, evaluator_record=None, identity=None, listening_port=8010, error=None):
        def run(argv, **kwargs):
            self.assertEqual(kwargs["cwd"], self.run)
            self.assertTrue(kwargs["check"])
            self.assertTrue(kwargs["capture_output"])
            self.assertTrue(kwargs["text"])
            if error:
                raise error
            if argv[:2] == ["docker", "inspect"]:
                self.assertIn(argv[2], ("fixture-service", "fixture-evaluator"))
                self.assertEqual(len(argv), 3)
                self.assertEqual(kwargs["timeout"], 10)
                if argv[2] == "fixture-service":
                    result = record if record is not None else {
                        "State": {"Running": True}, "Id": self.identity["container_id"],
                        "HostConfig": {"NetworkMode": "host"}}
                else:
                    result = evaluator_record if evaluator_record is not None else {
                        "State": {"Running": True}, "Id": "e" * 64,
                        "HostConfig": {"NetworkMode": "host"}}
                return subprocess.CompletedProcess(argv, 0, json.dumps([result]), "")
            self.assertEqual(argv[:3], ["docker", "exec", "--workdir"])
            self.assertEqual(argv[3], self.manifest["workspace"]["container_root"])
            self.assertEqual(argv[4], self.identity["container_id"])
            self.assertEqual(argv[5:8], ["python3", "-B", "-c"])
            self.assertEqual(argv[-2:], ["123", "8010"])
            self.assertEqual(kwargs["timeout"], 15)
            observed = identity if identity is not None else self.identity
            observed = {key: value for key, value in observed.items() if key != "container_id"}
            observed["listening_port"] = listening_port
            return subprocess.CompletedProcess(argv, 0, json.dumps(observed), "")
        return run

    def test_observer_pins_full_container_id_and_returns_bound_identity(self):
        self.challenge()
        with patch.object(observer.subprocess, "run", side_effect=self.docker()) as docker:
            response = observer.observe(self.run, self.manifest)
        self.assertEqual(docker.call_count, 3)
        self.assertEqual(response["status"], "verified")
        self.assertEqual(response["nonce"], self.nonce)
        self.assertEqual(response["process_identity"], self.identity)
        self.assertEqual(response["pid"], self.manifest["service_pid"])
        self.assertEqual(response["listening_port"], 8010)
        self.assertEqual(json.loads((self.run / "service-observation.json").read_text()), response)
        self.assertTrue(response["observed_at"].endswith("+00:00"))

    def test_service_restart_boot_or_command_change_publishes_failure_not_success(self):
        for key, value in (("start_ticks", 1201), ("boot_id", "00000000-0000-0000-0000-000000000000"),
                           ("cmdline_sha256", "d" * 64)):
            self.challenge()
            identity = dict(self.identity, **{key: value})
            with self.subTest(changed=key), patch.object(observer.subprocess, "run", side_effect=self.docker(identity=identity)):
                with self.assertRaisesRegex(ValueError, "identity differs"):
                    observer.observe(self.run, self.manifest)
            response_path = self.run / "service-observation.json"
            response = json.loads(response_path.read_text())
            self.assertEqual(response["status"], "failed")
            self.assertEqual(response["nonce"], self.nonce)
            self.assertNotIn("process_identity", response)
            response_path.unlink()
            (self.run / "service-challenge.json").unlink()

    def test_replaced_or_stopped_container_never_executes_pid_probe(self):
        for record in ({"State": {"Running": True}, "Id": "f" * 64, "HostConfig": {"NetworkMode": "host"}},
                       {"State": {"Running": False}, "Id": self.identity["container_id"], "HostConfig": {"NetworkMode": "host"}}):
            self.challenge()
            with self.subTest(record=record), patch.object(observer.subprocess, "run", side_effect=self.docker(record=record)) as docker:
                with self.assertRaises(ValueError):
                    observer.observe(self.run, self.manifest)
            self.assertTrue(all(call.args[0][1] == "inspect" for call in docker.call_args_list))
            self.assertEqual(json.loads((self.run / "service-observation.json").read_text())["status"], "failed")
            (self.run / "service-observation.json").unlink()
            (self.run / "service-challenge.json").unlink()

    def test_inference_and_evaluator_loopback_must_use_verified_host_network(self):
        for target in ("inference", "evaluator"):
            for mode in (None, "bridge", "container:another", "default"):
                self.challenge()
                record = {"State": {"Running": True}, "Id": self.identity["container_id"],
                          "HostConfig": {"NetworkMode": mode}}
                argument = "record" if target == "inference" else "evaluator_record"
                with self.subTest(target=target, mode=mode), \
                     patch.object(observer.subprocess, "run", side_effect=self.docker(**{argument: record})) as docker:
                    with self.assertRaisesRegex(ValueError, "host"):
                        observer.observe(self.run, self.manifest)
                self.assertTrue(all(call.args[0][1] == "inspect" for call in docker.call_args_list))
                self.assertEqual(json.loads((self.run / "service-observation.json").read_text())["status"], "failed")
                (self.run / "service-observation.json").unlink()
                (self.run / "service-challenge.json").unlink()

    def test_observed_listening_port_must_match_the_locked_service(self):
        for port in (None, 8011, True, "8010"):
            self.challenge()
            with self.subTest(port=port), patch.object(observer.subprocess, "run", side_effect=self.docker(listening_port=port)):
                with self.assertRaises(ValueError):
                    observer.observe(self.run, self.manifest)
            self.assertEqual(json.loads((self.run / "service-observation.json").read_text())["status"], "failed")
            (self.run / "service-observation.json").unlink()
            (self.run / "service-challenge.json").unlink()

    def test_command_failure_has_exclusive_failed_response(self):
        self.challenge()
        error = subprocess.TimeoutExpired(["docker", "inspect", "fixture-service"], 10)
        with patch.object(observer.subprocess, "run", side_effect=self.docker(error=error)):
            with self.assertRaisesRegex(ValueError, "timed out"):
                observer.observe(self.run, self.manifest)
        response = json.loads((self.run / "service-observation.json").read_text())
        self.assertEqual(response["status"], "failed")
        self.assertEqual(response["nonce"], self.nonce)

    def test_identity_schema_cannot_use_partial_hashes_or_boolean_pid_ticks(self):
        mutations = [lambda value: value.pop("boot_id"), lambda value: value.update(extra="value"),
                     lambda value: value.update(container_id="short"),
                     lambda value: value.update(cmdline_sha256="A" * 64),
                     lambda value: value.update(boot_id="unknown"),
                     lambda value: value.update(start_ticks=True),
                     lambda value: value.update(start_ticks=0),
                     lambda value: value.update(start_ticks="1200")]
        observer.validate_identity(self.identity)
        for mutation in mutations:
            identity = dict(self.identity)
            mutation(identity)
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                observer.validate_identity(identity)

    def test_observer_rejects_manifest_host_escape_and_alias_before_docker(self):
        outside = self.root / "outside"
        outside.mkdir()
        alias = self.root / "run-alias"
        alias.symlink_to(self.run, target_is_directory=True)
        before = set(self.root.rglob("*"))
        for root in (outside, self.run.parent, alias, Path("relative")):
            with self.subTest(root=root), patch.object(observer.subprocess, "run") as docker:
                with self.assertRaises(ValueError):
                    observer.observe(root, self.manifest, timeout=0)
                docker.assert_not_called()
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_observer_missing_or_malformed_challenge_does_not_query_service(self):
        with patch.object(observer.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "valid live challenge"):
                observer.observe(self.run, self.manifest, timeout=0)
            docker.assert_not_called()
        self.assertFalse((self.run / "service-observation.json").exists())
        self.challenge(nonce="short")
        with patch.object(observer.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "valid live challenge"):
                observer.observe(self.run, self.manifest)
            docker.assert_not_called()
        self.assertFalse((self.run / "service-observation.json").exists())

    def test_challenge_instance_mismatch_fails_without_service_probe(self):
        self.challenge(service_instance_id="old-instance")
        with patch.object(observer.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "challenge instance mismatch"):
                observer.observe(self.run, self.manifest)
            docker.assert_not_called()
        self.assertEqual(json.loads((self.run / "service-observation.json").read_text())["status"], "failed")

    def test_worker_ended_before_challenge_fails_without_service_probe(self):
        observer.write_new(self.run / "exit-status.json", {"returncode": 2})
        with patch.object(observer.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "worker ended"):
                observer.observe(self.run, self.manifest)
            docker.assert_not_called()
        self.assertFalse((self.run / "service-observation.json").exists())

    def test_response_publication_refuses_to_overwrite_prior_response(self):
        self.challenge()
        path = self.run / "service-observation.json"
        path.write_text('historical response bytes\n', encoding="utf-8")
        with patch.object(observer.subprocess, "run", side_effect=self.docker()):
            with self.assertRaises(FileExistsError):
                observer.observe(self.run, self.manifest)
        self.assertEqual(path.read_text(), "historical response bytes\n")

    def test_requester_accepts_only_current_nonce_and_exact_instance_pid_identity(self):
        mutations = [lambda value: value.update(nonce="b" * 64),
                     lambda value: value.update(status="failed", error="fixture failure"),
                     lambda value: value.update(service_instance_id="old-instance"),
                     lambda value: value.update(pid=124), lambda value: value.update(pid=True),
                     lambda value: value.update(listening_port=8011),
                     lambda value: value.update(listening_port=True),
                     lambda value: value["process_identity"].update(start_ticks=1201)]
        for mutation in mutations:
            response = self.response()
            mutation(response)
            with self.subTest(response=response), patch.object(observer.secrets, "token_hex", return_value=self.nonce), \
                 patch.object(observer, "read_complete", return_value=response):
                with self.assertRaises(ValueError):
                    observer.request_observation(self.run, self.manifest)
            (self.run / "service-challenge.json").unlink()
        with patch.object(observer.secrets, "token_hex", return_value=self.nonce), \
             patch.object(observer, "read_complete", return_value=self.response()):
            self.assertEqual(observer.request_observation(self.run, self.manifest), self.response())

    def test_missing_observer_times_out_without_retrying_or_reusing_challenge(self):
        with patch.object(observer.subprocess, "run") as docker, \
             patch.object(observer.secrets, "token_hex", return_value=self.nonce), \
             patch.object(observer.time, "sleep") as sleep:
            with self.assertRaisesRegex(ValueError, "no live host service observation"):
                observer.request_observation(self.run, self.manifest, timeout=0)
            docker.assert_not_called()
            sleep.assert_not_called()
        challenge = self.run / "service-challenge.json"
        before = challenge.read_bytes()
        self.assertEqual(json.loads(before)["nonce"], self.nonce)
        with self.assertRaises(FileExistsError):
            observer.request_observation(self.run, self.manifest, timeout=0)
        self.assertEqual(challenge.read_bytes(), before)

    def test_previous_observation_cannot_satisfy_new_challenge(self):
        path = self.run / "service-observation.json"
        observer.write_new(path, self.response(nonce="b" * 64))
        before = path.read_bytes()
        with patch.object(observer.secrets, "token_hex", return_value=self.nonce):
            with self.assertRaisesRegex(ValueError, "another challenge"):
                observer.request_observation(self.run, self.manifest)
        self.assertEqual(path.read_bytes(), before)

    def test_partial_response_is_pending_but_symlink_and_hardlink_are_rejected(self):
        path = self.run / "response.json"
        self.assertIsNone(observer.read_complete(path))
        path.write_text('{"nonce":', encoding="utf-8")
        self.assertIsNone(observer.read_complete(path))
        path.unlink()
        external = self.root / "external.json"
        external.write_text(json.dumps(self.response()), encoding="utf-8")
        path.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "unsafe observation"):
            observer.read_complete(path)
        path.unlink()
        os.link(external, path)
        with self.assertRaisesRegex(ValueError, "unsafe observation"):
            observer.read_complete(path)

    def test_fifo_and_oversized_response_are_rejected_before_opening(self):
        path = self.run / "unsafe-response.json"
        path.write_text("x" * 65537, encoding="utf-8")
        with patch.object(Path, "read_text", side_effect=AssertionError("unsafe input must not be opened")):
            with self.assertRaisesRegex(ValueError, "unsafe observation"):
                observer.read_complete(path)
        path.unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(path)
            # Never open a FIFO in the test: an attempted read fails immediately
            # rather than leaving a blocked fixture process behind.
            with patch.object(Path, "read_text", side_effect=AssertionError("FIFO must not be opened")):
                with self.assertRaisesRegex(ValueError, "unsafe observation"):
                    observer.read_complete(path)

    def test_proc_probe_rejects_pid_reuse_and_empty_command_even_under_optimization(self):
        self.challenge()
        with patch.object(observer.subprocess, "run", side_effect=self.docker()) as docker:
            observer.observe(self.run, self.manifest)
        probe = next(call.args[0] for call in docker.call_args_list if call.args[0][1] == "exec")
        payload = probe[probe.index("-c") + 1]
        # Fake the precise /proc file/socket reads in a real local Python process.
        # Unexpected paths fail: neither a real PID nor a container is accessed.
        bootstrap = '''import json,pathlib,sys
scenario=json.loads(sys.argv[3])
class FixturePath:
    reads=0
    def __init__(self, path): self.path=path
    def __truediv__(self, part): return FixturePath(self.path+'/'+part)
    def joinpath(self, part): return self/part
    def read_text(self):
        if self.path=='/proc/sys/kernel/random/boot_id': return scenario['boot_id']
        if self.path in ('/proc/123/net/tcp','/proc/123/net/tcp6'):
            return scenario['tables'][self.path.rsplit('/',1)[1]]
        if self.path!='/proc/123/stat': raise RuntimeError('unexpected fixture read '+self.path)
        ticks=scenario['ticks'][FixturePath.reads]
        FixturePath.reads+=1
        return '123 (worker (with) spaces) '+ ' '.join(['S']+['0']*18+[str(ticks)]+['0']*3)
    def read_bytes(self):
        if self.path!='/proc/123/cmdline': raise RuntimeError('unexpected fixture read '+self.path)
        return scenario['command'].encode()
    def exists(self):
        if self.path not in ('/proc/123/net/tcp','/proc/123/net/tcp6'): raise RuntimeError('unexpected exists '+self.path)
        return self.path.rsplit('/',1)[1] in scenario['tables']
    def iterdir(self):
        if self.path!='/proc/123/fd': raise RuntimeError('unexpected directory '+self.path)
        return [self/'10',self/'11',self/'12']
    def readlink(self):
        if self.path=='/proc/123/fd/10': return 'socket:['+scenario['socket_inode']+']'
        if self.path=='/proc/123/fd/11': return '/dev/null'
        if self.path=='/proc/123/fd/12': raise FileNotFoundError('fd closed during observation')
        raise RuntimeError('unexpected readlink '+self.path)
pathlib.Path=FixturePath
'''
        header = 'sl local_address rem_address st tx_queue tr retrnsmt uid timeout inode\n'
        def table(address='0100007F', port=8010, state='0A'):
            return header + f'0: {address}:{port:04X} 00000000:0000 {state} 00000000:00000000 00:00000000 00000000 0 0 42\n'
        valid = {"ticks": [1200, 1200], "command": "fixture-service\x00--port\x008010\x00",
                 "boot_id": self.identity["boot_id"], "socket_inode": "42", "tables": {"tcp": table()}}
        another_listener = table().splitlines()[-1].replace('0: ', '1: ', 1).replace('0 0 42', '0 0 99')
        scenarios = [(valid, True, None),
                     (dict(valid, tables={"tcp": table(address='00000000')}), True, None),
                     (dict(valid, ticks=[1200, 1201]), False, "PID changed"),
                     (dict(valid, command=""), False, "empty command"),
                     (dict(valid, socket_inode="99"), False, "LISTEN socket"),
                     (dict(valid, tables={"tcp": table(port=8011)}), False, "LISTEN socket"),
                     (dict(valid, tables={"tcp": table(state='01')}), False, "LISTEN socket"),
                     (dict(valid, tables={"tcp": table(address='0100000A')}), False, "LISTEN socket"),
                     (dict(valid, tables={"tcp": table() + another_listener + '\n'}), False, "LISTEN socket"),
                     (dict(valid, tables={"tcp6": table(address='0' * 32)}), False, "IPv6 listener scope"),
                     (dict(valid, tables={"tcp": table(), "tcp6": table(address='0' * 32)}), False, "IPv6 listener scope")]
        for optimized in (False, True):
            for scenario, accepted, error in scenarios:
                argv = [sys.executable, "-B"] + (["-O"] if optimized else [])
                argv += ["-c", bootstrap + payload, "123", "8010", json.dumps(scenario)]
                result = subprocess.run(argv, cwd=self.run, capture_output=True, text=True, timeout=5, check=False)
                with self.subTest(optimized=optimized, scenario=scenario):
                    if accepted:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        expected = {key: value for key, value in self.identity.items() if key != "container_id"}
                        expected["listening_port"] = 8010
                        self.assertEqual(json.loads(result.stdout), expected)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(error, result.stderr)


if __name__ == "__main__":
    unittest.main()
