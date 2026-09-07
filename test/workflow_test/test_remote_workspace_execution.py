"""Local workspace fixtures and mocked Docker only; never contact a container."""

import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "remote_workspace_execution_test_subject", ROOT / "scripts/remote_workspace.py"
)
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


class WorkspaceExecutionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="workspace-execution-")
        self.addCleanup(temporary.cleanup)
        # macOS temporary directories may be presented via /var -> /private/var.
        # Fixtures use the canonical backing path, as production requires.
        self.root = Path(temporary.name).resolve()
        self.host = self.root / "host"
        self.evaluator = self.root / "evaluator"
        self.host.mkdir()
        self.evaluator.mkdir()
        self.plan = {
            "schema_version": 4,
            "run_id": "fixture-run-01",
            "workspace": {
                "host_root": str(self.host),
                "container_root": "/service/workspace",
                "evaluator_container": "fixture-evaluator",
                "evaluator_root": str(self.evaluator),
            },
        }
        self.run = self.evaluator / "05-runs" / self.plan["run_id"]
        self.host_run = self.host / "05-runs" / self.plan["run_id"]
        self.config = {
            "output_root": "outputs",
            "cache_root": "cache/evaluation",
            "hf_datasets_cache": str(self.run / "cache/datasets"),
        }

    def record(self, destination, *, source=None, **mount_changes):
        mount = {
            "Type": "bind", "RW": True,
            "Source": str(self.host if source is None else source),
            "Destination": destination,
        }
        mount.update(mount_changes)
        return {"State": {"Running": True}, "HostConfig": {"NetworkMode": "host"},
                "Config": {"Image": "fixture-evaluation:v1"}, "Mounts": [mount]}

    def docker(self, *, before_call=None, evaluator_record=None, exec_error=False):
        """Return a strict fake: unexpected commands fail instead of executing."""
        def run(argv, **kwargs):
            if before_call:
                before_call(argv)
            self.assertEqual(kwargs["cwd"], self.host)
            self.assertTrue(kwargs["check"])
            self.assertTrue(kwargs["capture_output"])
            self.assertTrue(kwargs["text"])
            if argv[:2] == ["docker", "inspect"]:
                self.assertEqual(kwargs["timeout"], 10)
                self.assertEqual(len(argv), 3)
                if argv[2] == "fixture-service":
                    record = self.record(self.plan["workspace"]["container_root"])
                else:
                    self.assertEqual(argv[2], "fixture-evaluator")
                    record = evaluator_record or self.record(str(self.evaluator))
                return subprocess.CompletedProcess(argv, 0, json.dumps([record]), "")
            self.assertEqual(argv[:3], ["docker", "exec", "--workdir"])
            self.assertEqual(kwargs["timeout"], 15)
            self.assertIn(argv[4], ("fixture-service", "fixture-evaluator"))
            self.assertEqual(argv[5:8], ["python3", "-B", "-c"])
            self.assertEqual(argv[-2:], [argv[3], self.plan["run_id"]])
            if exec_error:
                raise subprocess.CalledProcessError(1, argv, stderr="fixture invalid path")
            return subprocess.CompletedProcess(argv, 0, "", "")
        return run

    def test_schema2_uses_evaluator_mapping_for_container_run(self):
        self.assertEqual(workspace.workspace_paths(self.plan), {
            "host_run_dir": str(self.host_run),
            "container_run_dir": str(self.run),
            "evaluator_container": "fixture-evaluator",
        })

    def test_schema_workspace_and_run_identity_must_be_explicit(self):
        mutations = [
            lambda value: value.pop("workspace"),
            lambda value: value.update(workspace=[]),
            lambda value: value["workspace"].pop("container_root"),
            lambda value: value["workspace"].update(extra="ambiguous"),
        ]
        mutations += [lambda value, version=version: value.update(schema_version=version)
                      for version in (None, 1, True, "2", 2.0)]
        mutations += [lambda value, run_id=run_id: value.update(run_id=run_id)
                      for run_id in (None, "", "auto", ".", "..", "../old", "a/b", "x\n")]
        mutations += [lambda value, name=name: value["workspace"].update(evaluator_container=name)
                      for name in (None, "", "-option", "a b", "a\n")]
        for mutation in mutations:
            plan = copy.deepcopy(self.plan)
            mutation(plan)
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                workspace.workspace_paths(plan)

    def test_declared_roots_reject_noncanonical_or_interpolated_paths(self):
        for key in ("host_root", "container_root", "evaluator_root"):
            for value in (None, "/", "//work", "relative", "/work/../other", "/work/./run",
                          "/work//run", "/work/run/", " /work", "/work/$USER", "/work/<root>",
                          "/work/~user", "/work/\\root", "/work/\x00", "/work/\x7f"):
                plan = copy.deepcopy(self.plan)
                plan["workspace"][key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    workspace.workspace_paths(plan)

    def test_run_validation_requires_exact_side_root_and_existing_preparation(self):
        for side, run in (("host", self.host_run), ("container", self.run)):
            with self.subTest(side=side):
                self.assertEqual(workspace.validate_run(self.plan, run, side=side, existing=False), run)
                with self.assertRaisesRegex(ValueError, "missing"):
                    workspace.validate_run(self.plan, run, side=side)
                run.mkdir(parents=True)
                self.assertEqual(workspace.validate_run(self.plan, run, side=side), run)
                for wrong in (run.parent, run.parent / "old-run", self.root / "outside", Path(str(run) + "-other")):
                    with self.assertRaisesRegex(ValueError, "declared workspace/05-runs/run_id"):
                        workspace.validate_run(self.plan, wrong, side=side)

    def test_run_validation_rejects_missing_base_and_parent_or_root_symlinks(self):
        missing = copy.deepcopy(self.plan)
        missing["workspace"]["evaluator_root"] = str(self.root / "missing")
        with self.assertRaisesRegex(ValueError, "already exist"):
            workspace.validate_run(missing, self.root / "missing/05-runs/fixture-run-01", existing=False)
        destination = self.root / "outside"
        destination.mkdir()
        (self.evaluator / "05-runs").symlink_to(destination, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink/alias"):
            workspace.validate_run(self.plan, self.run, existing=False)
        (self.evaluator / "05-runs").unlink()
        self.run.parent.mkdir()
        self.run.symlink_to(destination, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink/alias"):
            workspace.validate_run(self.plan, self.run)
        self.assertEqual(list(destination.iterdir()), [])

    def test_tree_accepts_regular_files_but_rejects_symlinks_hardlinks_and_special_files(self):
        self.run.mkdir(parents=True)
        nested = self.run / "nested"
        nested.mkdir()
        (nested / "normal.txt").write_text("fixture", encoding="utf-8")
        workspace.validate_tree(self.run)
        external = self.root / "external.txt"
        external.write_text("do not modify", encoding="utf-8")
        linked = nested / "linked"
        linked.symlink_to(external)
        with self.assertRaisesRegex(ValueError, "symlink"):
            workspace.validate_tree(self.run)
        linked.unlink()
        os.link(external, linked)
        with self.assertRaisesRegex(ValueError, "hard link"):
            workspace.validate_tree(self.run)
        linked.unlink()
        if hasattr(os, "mkfifo"):
            os.mkfifo(linked)
            with self.assertRaisesRegex(ValueError, "special file"):
                workspace.validate_tree(self.run)
            linked.unlink()
        self.assertEqual(external.read_text(encoding="utf-8"), "do not modify")

    def test_output_cache_and_dataset_cache_are_explicit_run_owned_paths(self):
        config = dict(self.config, dataset_path=str(self.root / "readonly-dataset"))
        self.assertEqual(workspace.config_paths(config, self.run), {
            "output_root": self.run / "outputs",
            "cache_root": self.run / "cache/evaluation",
            "hf_datasets_cache": self.run / "cache/datasets",
        })
        for key in self.config:
            for bad in (None, "", "auto", "../old", "cache/../other", str(self.run),
                        str(self.root / "outside"), str(self.run) + "-other/cache"):
                # The relative directory name "auto" has no special meaning for
                # output/cache paths; only the declared run identity rejects it.
                if bad == "auto" and key != "hf_datasets_cache":
                    continue
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    workspace.config_paths(dict(self.config, **{key: bad}), self.run)
            missing = dict(self.config)
            missing.pop(key)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                workspace.config_paths(missing, self.run)
        with self.assertRaisesRegex(ValueError, "must be absolute"):
            workspace.config_paths(dict(self.config, hf_datasets_cache="cache/datasets"), self.run)

    def test_output_parent_symlink_is_rejected_even_when_output_does_not_exist(self):
        self.run.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        (self.run / "aliased").symlink_to(outside, target_is_directory=True)
        config = dict(self.config, output_root="aliased/new-output")
        with self.assertRaisesRegex(ValueError, "symlink/alias"):
            workspace.config_paths(config, self.run)
        self.assertFalse((outside / "new-output").exists())
        # Pure snapshot validation cannot inspect a not-yet-deployed filesystem.
        self.assertEqual(workspace.config_paths(config, self.run, check_filesystem=False)["output_root"],
                         self.run / "aliased/new-output")

    def test_scoped_environment_default_is_readonly_and_preserves_home(self):
        original = {"HOME": "/operator/original-home", "TMPDIR": "/outside/tmp",
                    "HF_HOME": "/outside/hf", "UNCHANGED_FIXTURE": "yes"}
        before = set(self.root.rglob("*"))
        with patch.dict(os.environ, original, clear=True):
            environment = workspace.scoped_environment(self.run, self.config)
            self.assertEqual(dict(os.environ), original)
        self.assertEqual(set(self.root.rglob("*")), before)
        self.assertEqual(environment["HOME"], original["HOME"])
        self.assertEqual(environment["UNCHANGED_FIXTURE"], "yes")
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(environment["HF_DATASETS_CACHE"], self.config["hf_datasets_cache"])
        for key, value in environment.items():
            if key not in {"HOME", "UNCHANGED_FIXTURE", "PYTHONDONTWRITEBYTECODE", "NO_PROXY", "no_proxy"}:
                with self.subTest(key=key):
                    self.assertTrue(Path(value).is_relative_to(self.run))

    def test_scoped_environment_create_makes_only_supported_run_paths(self):
        with patch.dict(os.environ, {"HOME": "/operator/original-home"}, clear=True):
            environment = workspace.scoped_environment(self.run, self.config, create=True)
        expected = {Path(value) for key, value in environment.items()
                    if key not in {"HOME", "PYTHONDONTWRITEBYTECODE", "NO_PROXY", "no_proxy"}}
        expected.update(workspace.config_paths(self.config, self.run).values())
        for path in expected:
            self.assertTrue(path.is_dir(), path)
        allowed = set(expected)
        for path in expected:
            allowed.update(parent for parent in path.parents if parent.is_relative_to(self.evaluator))
        self.assertEqual(set(self.evaluator.rglob("*")), allowed - {self.evaluator})
        self.assertEqual(list(self.host.iterdir()), [])

    def test_proxy_environment_without_exceptions_cannot_redirect_localhost_observation(self):
        original = {"HOME": "/operator/original-home", "HTTP_PROXY": "http://fixture.invalid:3128",
                    "ALL_PROXY": "socks5://fixture.invalid:1080"}
        before = set(self.root.rglob("*"))
        with patch.dict(os.environ, original, clear=True):
            environment = workspace.scoped_environment(self.run, self.config)
            self.assertEqual(dict(os.environ), original)
        self.assertEqual(set(self.root.rglob("*")), before)
        self.assertEqual(environment["HTTP_PROXY"], original["HTTP_PROXY"])
        self.assertEqual(environment["ALL_PROXY"], original["ALL_PROXY"])
        for key in ("NO_PROXY", "no_proxy"):
            self.assertTrue({"127.0.0.1", "localhost", "::1"}.issubset(environment[key].split(',')))
        with patch.dict(os.environ, environment, clear=True):
            # Read only urllib's proxy selection; do not issue an HTTP request.
            self.assertTrue(urllib.request.proxy_bypass_environment("127.0.0.1"))
            self.assertTrue(urllib.request.proxy_bypass_environment("localhost"))

    def test_proxy_bypass_preserves_both_case_variant_existing_lists(self):
        original = {"HOME": "/operator/original-home", "NO_PROXY": "upper.example,127.0.0.1",
                    "no_proxy": "lower.example,localhost", "http_proxy": "http://fixture.invalid:3128"}
        before = set(self.root.rglob("*"))
        with patch.dict(os.environ, original, clear=True):
            environment = workspace.scoped_environment(self.run, self.config)
            self.assertEqual(dict(os.environ), original)
        for key in ("NO_PROXY", "no_proxy"):
            entries = set(environment[key].split(','))
            self.assertTrue({"upper.example", "lower.example", "127.0.0.1", "localhost", "::1"}.issubset(entries))
        self.assertEqual(environment["http_proxy"], original["http_proxy"])
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_scoped_environment_prechecks_all_implicit_paths_before_creating_any(self):
        self.run.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        (self.run / "config").symlink_to(outside, target_is_directory=True)
        before = set(self.root.rglob("*"))
        with self.assertRaisesRegex(ValueError, "symlink/alias"):
            workspace.scoped_environment(self.run, self.config, create=True)
        self.assertEqual(set(self.root.rglob("*")), before)

    def test_bind_mapping_supports_distinct_container_roots_and_ancestor_binds(self):
        for destination in ("/service/workspace", "/evaluation/another/workspace"):
            self.assertEqual(workspace.mapped_host_root(self.record(destination), destination), self.host)
        self.assertEqual(workspace.mapped_host_root(self.record("/mounted", source=self.root),
                                                   "/mounted/host"), self.host)

    def test_mapping_rejects_nested_shadows_readonly_volume_stopped_or_missing_bind(self):
        target = "/service/workspace"
        records = [
            self.record(target, Type="volume"), self.record(target, RW=False),
            self.record(target, RW="true"), self.record("/unrelated"),
            {"State": {"Running": False}, "Mounts": [self.record(target)["Mounts"][0]]},
            {"State": {"Running": True}, "Mounts": []},
        ]
        nested = self.record(target)
        nested["Mounts"].append(self.record(target + "/cache")["Mounts"][0])
        records.append(nested)
        for record in records:
            with self.subTest(record=record), self.assertRaises(ValueError):
                workspace.mapped_host_root(record, target)
        unrelated = self.record(target)
        unrelated["Mounts"].append(self.record(target + "-other")["Mounts"][0])
        self.assertEqual(workspace.mapped_host_root(unrelated, target), self.host)

    def test_mapping_rejects_host_source_symlink(self):
        alias = self.root / "host-alias"
        alias.symlink_to(self.host, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink/alias"):
            workspace.mapped_host_root(self.record("/workspace", source=alias), "/workspace")

    def test_host_inspect_is_readonly_and_checks_both_distinct_container_paths(self):
        before = set(self.root.rglob("*"))
        with patch.object(workspace.subprocess, "run", side_effect=self.docker()) as docker:
            paths = workspace.inspect_host(self.plan, "fixture-service", "inspect")
        self.assertEqual(set(self.root.rglob("*")), before)
        self.assertEqual(paths["host_run_dir"], str(self.host_run))
        commands = [call.args[0] for call in docker.call_args_list]
        self.assertEqual([argv[2] for argv in commands if argv[1] == "inspect"],
                         ["fixture-service", "fixture-evaluator"])
        self.assertEqual([argv[3] for argv in commands if argv[1] == "exec"],
                         ["/service/workspace", str(self.evaluator)])

    def test_host_create_waits_for_every_mapping_then_creates_run_exclusively(self):
        def no_writes_yet(argv):
            self.assertFalse(self.host_run.parent.exists(), argv)
        with patch.object(workspace.subprocess, "run", side_effect=self.docker(before_call=no_writes_yet)) as docker:
            workspace.inspect_host(self.plan, "fixture-service", "create")
        self.assertEqual(docker.call_count, 4)
        self.assertTrue((self.host_run / "tmp").is_dir())
        marker = self.host_run / "historical.txt"
        marker.write_text("old evidence", encoding="utf-8")
        with patch.object(workspace.subprocess, "run", side_effect=self.docker()):
            with self.assertRaisesRegex(ValueError, "historical runs cannot be reused"):
                workspace.inspect_host(self.plan, "fixture-service", "create")
            workspace.inspect_host(self.plan, "fixture-service", "existing")
        self.assertEqual(marker.read_text(encoding="utf-8"), "old evidence")
        self.assertEqual(list(self.evaluator.iterdir()), [])

    def test_failed_second_mapping_or_container_path_probe_does_not_create_host_run(self):
        wrong = self.record(str(self.evaluator), source=self.evaluator)
        for fake, error in ((self.docker(evaluator_record=wrong), ValueError),
                            (self.docker(exec_error=True), subprocess.CalledProcessError)):
            with self.subTest(error=error), patch.object(workspace.subprocess, "run", side_effect=fake):
                with self.assertRaises(error):
                    workspace.inspect_host(self.plan, "fixture-service", "create")
            self.assertFalse(self.host_run.parent.exists())

    def test_localhost_chain_requires_explicit_host_network_before_creating_run(self):
        for mode in (None, "bridge", "container:other-service", "default"):
            record = self.record(str(self.evaluator))
            record["HostConfig"]["NetworkMode"] = mode
            with self.subTest(mode=mode), patch.object(workspace.subprocess, "run", side_effect=self.docker(evaluator_record=record)):
                with self.assertRaisesRegex(ValueError, "host"):
                    workspace.inspect_host(self.plan, "fixture-service", "create")
            self.assertFalse(self.host_run.parent.exists())

    def test_evaluator_image_must_match_admission_before_run_creation(self):
        with patch.object(workspace.subprocess, "run", side_effect=self.docker()):
            with self.assertRaisesRegex(ValueError, "evaluator image differs"):
                workspace.inspect_host(self.plan, "fixture-service", "create", evaluator_image="other-evaluator:v2")
        self.assertFalse(self.host_run.parent.exists())
        with patch.object(workspace.subprocess, "run", side_effect=self.docker()):
            workspace.inspect_host(self.plan, "fixture-service", "create", evaluator_image="fixture-evaluation:v1")
        self.assertTrue(self.host_run.is_dir())

    def test_cli_requires_explicit_evaluator_image(self):
        argv = ["--run-plan-json", json.dumps(self.plan), "--target-container", "fixture-service",
                "--mode", "inspect"]
        with patch.object(workspace, "inspect_host") as inspect, patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                workspace.main(argv)
            self.assertEqual(failure.exception.code, 2)
            inspect.assert_not_called()
        with patch.object(workspace, "inspect_host") as inspect:
            with self.assertRaises(ValueError):
                workspace.main(argv + ["--evaluator-image", " "])
            inspect.assert_not_called()
        with patch.object(workspace, "inspect_host", return_value={}) as inspect, patch("sys.stdout", io.StringIO()):
            workspace.main(argv + ["--evaluator-image", "fixture-evaluation:v1"])
            inspect.assert_called_once_with(self.plan, "fixture-service", "inspect", evaluator_image="fixture-evaluation:v1")

    def test_inspect_cardinality_and_existing_mode_fail_closed(self):
        for records in ([], [{}, {}], {}):
            result = subprocess.CompletedProcess(["docker", "inspect"], 0, json.dumps(records), "")
            with self.subTest(records=records), patch.object(workspace.subprocess, "run", return_value=result):
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    workspace.inspect_host(self.plan, "fixture-service", "create")
            self.assertFalse(self.host_run.parent.exists())
        with patch.object(workspace.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "missing"):
                workspace.inspect_host(self.plan, "fixture-service", "existing")
            docker.assert_not_called()

    def test_existing_run_tree_is_checked_before_docker_or_ansible_staging(self):
        self.host_run.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        (self.host_run / "tmp").symlink_to(outside, target_is_directory=True)
        with patch.object(workspace.subprocess, "run") as docker:
            with self.assertRaisesRegex(ValueError, "symlink"):
                workspace.inspect_host(self.plan, "fixture-service", "existing")
            docker.assert_not_called()
        self.assertEqual(list(outside.iterdir()), [])

    def test_concurrent_run_creation_does_not_overwrite_or_add_tmp_to_other_run(self):
        original_mkdir = Path.mkdir
        marker = self.host_run / "other-owner.txt"

        def race(path, *args, **kwargs):
            if path == self.host_run:
                original_mkdir(path)
                marker.write_text("other owner", encoding="utf-8")
            return original_mkdir(path, *args, **kwargs)

        with patch.object(workspace.subprocess, "run", side_effect=self.docker()), patch.object(Path, "mkdir", race):
            with self.assertRaises(FileExistsError):
                workspace.inspect_host(self.plan, "fixture-service", "create")
        self.assertEqual(marker.read_text(encoding="utf-8"), "other owner")
        self.assertFalse((self.host_run / "tmp").exists())

    def test_container_path_probe_still_rejects_aliases_with_python_optimization(self):
        # Execute only the extracted, path-checking Python snippet locally. No
        # Docker/SSH/model command is executed, even if the production probe changes.
        with patch.object(workspace.subprocess, "run", side_effect=self.docker()) as docker:
            workspace.inspect_host(self.plan, "fixture-service", "inspect")
        probe = next(call.args[0] for call in docker.call_args_list if call.args[0][1] == "exec")
        payload = probe[probe.index("-c") + 1]
        alias = self.root / "container-alias"
        alias.symlink_to(self.evaluator, target_is_directory=True)
        before = set(self.root.rglob("*"))
        for optimized in (False, True):
            for path in (alias, self.evaluator):
                argv = [sys.executable, "-B"] + (["-O"] if optimized else [])
                argv += ["-c", payload, str(path), self.plan["run_id"]]
                completed = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, check=False)
                with self.subTest(optimized=optimized, path=path):
                    if path == alias:
                        self.assertNotEqual(completed.returncode, 0, "container path checks must not rely on assert")
                    else:
                        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(set(self.root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
