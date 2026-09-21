from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from argparse import Namespace
import copy
import json
from datetime import date
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_workspace  # noqa: E402
import framework_workspace  # noqa: E402
import framework_evidence as gate  # noqa: E402


class FrameworkWorkspaceTests(unittest.TestCase):
    def prepare(self, directory: str) -> Path:
        root = Path(directory)
        shutil.copytree(ROOT / "framework-profiles", root / "framework-profiles")
        shutil.copytree(ROOT / "templates" / "framework-workspace", root / "templates" / "framework-workspace")
        shutil.copytree(ROOT / "docs", root / "docs", ignore=shutil.ignore_patterns("legacy-entrypoints.md", "troubleshooting"))
        shutil.copytree(ROOT / "inventory", root / "inventory")
        platform = root / "models" / "Example" / "ppu"
        platform.mkdir(parents=True)
        model = yaml.safe_load((ROOT / "models" / "_template" / "model.yml").read_text())
        model["name"] = "Example"
        (platform.parent / "model.yml").write_text(yaml.safe_dump(model), encoding="utf-8")
        shutil.copy2(ROOT / "models" / "_template" / "ppu" / "platform.yml", platform / "platform.yml")
        return root

    def test_vllm_profile_is_complete(self):
        path, profile = framework_workspace.resolved_profile(ROOT, "vllm-plugin-fl")
        self.assertEqual(path.parent.name, "vllm-plugin-fl")
        self.assertEqual(profile["execution_modes"]["required"], ["eager", "graph"])
        self.assertEqual(profile["source_policy"]["writable_roles"], ["platform_adapter"])

    def test_torch_fl_experimental_profile_allows_declared_checks_only(self):
        path = ROOT / "framework-profiles" / "torch-fl" / "profile.yml"
        profile = framework_workspace.load_yaml(path)
        self.assertEqual(framework_workspace.profile_errors(profile, "torch-fl"), [])
        self.assertEqual(profile["status"], "experimental")
        self.assertEqual(profile["execution_modes"]["required"], ["eager"])
        self.assertEqual(profile["source_policy"]["writable_roles"], ["framework_runtime"])
        framework_workspace.resolved_profile(ROOT, "torch-fl")
        self.assertNotIn("accuracy", profile["acceptance"]["steps"])
        self.assertNotIn("execution-mode", profile["acceptance"]["steps"])

    def test_profile_rejects_missing_contract_and_conflicting_mutation_policy(self):
        _, original = framework_workspace.resolved_profile(ROOT, "vllm-plugin-fl")
        for change in (
            lambda p: p.pop("acceptance"),
            lambda p: p.pop("service"),
            lambda p: p["source_policy"].update(writable_roles=["inference_engine"]),
            lambda p: p["acceptance"].update(accuracy_adapter="unimplemented"),
            lambda p: p.update(platforms=[]),
        ):
            cfg = copy.deepcopy(original)
            change(cfg)
            self.assertTrue(framework_workspace.profile_errors(cfg))

    def test_new_framework_creates_scoped_workspace_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.prepare(directory)
            command = [
                sys.executable,
                str(ROOT / "scripts" / "new_framework.py"),
                "--repo-root",
                str(root),
                "Example",
                "ppu",
                "vllm-plugin-fl",
            ]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            workspace = root / "models" / "Example" / "ppu" / "frameworks" / "vllm-plugin-fl"
            self.assertTrue((workspace.parent / "README.md").is_file())
            config = framework_workspace.load_yaml(workspace / "framework.yml")
            platform_config = framework_workspace.load_yaml(workspace.parents[1] / "platform.yml")
            self.assertEqual(
                platform_config["frameworks"]["vllm-plugin-fl"]["workspace"],
                "frameworks/vllm-plugin-fl/framework.yml",
            )
            self.assertEqual(
                framework_workspace.workspace_errors(
                    config, model="Example", platform="ppu", framework="vllm-plugin-fl"
                ),
                [],
            )
            for section in framework_workspace.WORKSPACE_SECTIONS:
                self.assertTrue((workspace / section / "README.md").is_file())
            repeated = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("拒绝覆盖", repeated.stdout)
            findings = audit_workspace.audit(root)
            self.assertFalse([item for item in findings if item["level"] == "error"], findings)

    def test_workspace_rejects_profile_identity_mismatch(self):
        config = framework_workspace.load_yaml(ROOT / "templates" / "framework-workspace" / "framework.yml")
        config.update({
            "model": "Example",
            "platform": "ppu",
            "framework": "vllm-plugin-fl",
            "profile": "framework-profiles/another/profile.yml",
            "profile_version": 1,
        })
        errors = framework_workspace.workspace_errors(
            config, model="Example", platform="ppu", framework="vllm-plugin-fl"
        )
        self.assertTrue(any("profile 必须" in item for item in errors))


class FrameworkGateTests(unittest.TestCase):
    prepare = FrameworkWorkspaceTests.prepare
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.prepare(self.temp.name)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/new_framework.py'),
            '--repo-root', str(self.root), 'Example', 'ppu', 'torch-fl'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.directory = self.root / 'models/Example/ppu/frameworks/torch-fl'
        self.cfg = framework_workspace.load_yaml(self.directory / 'framework.yml')
        _, self.profile = framework_workspace.resolved_profile(self.root, 'torch-fl')
        self.remote = self.root / 'remote'
        self.remote.mkdir()
        (self.root / 'models/Example/architecture-and-inference.md').write_text('模型结构与推理分析')
        self.cfg['target'] = {'hosts': ['PPU-01'], 'container_name': 'test'}
        self.cfg['workspace'] = {'roots': [{'host_alias': 'PPU-01', 'host_root': '/approved', 'container_root': '/container'}]}
        self.cfg['deployment'] = {'fingerprint': 'a' * 64}
        self.mounts = {'PPU-01': str(self.remote)}

    def bind(self, stage):
        evidence = self.directory / ('environment' if stage == 'environment' else 'acceptance') / f'{stage}.md'
        if stage == 'architecture':
            evidence = self.root/'models/Example/architecture-and-inference.md'
        evidence.write_text('verified analysis')
        rec = {'run_id': stage + '-run', 'last_verified': date.today().isoformat(),
               'evidence': '../../../architecture-and-inference.md' if stage == 'architecture' else str(evidence.relative_to(self.directory)), 'evidence_sha256': gate.digest(evidence),
               'context_sha256': gate.context_hash(self.root, self.directory, self.cfg, self.profile, stage)}
        if stage != 'architecture':
            raw = self.remote / f'{stage}.txt'; raw.write_text('controlled result')
            checks = self.profile['acceptance']['steps'].get(stage, {}).get('checks',
                ['environment_identity' if stage == 'environment' else 'source_review'])
            envelope = {'schema_version': 1, 'kind': 'framework_check', 'status': 'passed', 'stage': stage,
                'run_id': rec['run_id'], 'context_sha256': rec['context_sha256'], 'mode': 'eager',
                'scope': {**{k: self.cfg[k] for k in ('model', 'platform', 'framework', 'profile_version')},
                          'host_alias': 'PPU-01', 'deployment_fingerprint': 'a' * 64},
                'checks': {k: True for k in checks}, 'artifacts': [{'path': raw.name, 'sha256': gate.digest(raw)}]}
            path = self.remote / f'{stage}.json'; path.write_text(json.dumps(envelope))
            rec['receipts'] = [{'host_alias': 'PPU-01', 'path': path.name, 'sha256': gate.digest(path)}]
        if stage in gate.WORKFLOW_PHASES:
            self.cfg['workflow'][stage].update(status='passed', evidence=rec['evidence'], verification=rec)
        else:
            self.cfg['workflow']['acceptance']['substeps'][stage] = 'passed'
            self.cfg['workflow']['acceptance']['records'][stage] = rec
        return rec

    def test_missing_receipts_and_forged_complete_are_rejected(self):
        self.cfg['status'] = 'optimized'
        for item in self.cfg['workflow'].values():
            item.update(status='complete', verification={}, evidence='absent.md')
        errors = gate.validate_workspace(self.root, self.directory, self.cfg, self.profile)
        self.assertTrue(errors)
        (self.directory/'framework.yml').write_text(yaml.safe_dump(self.cfg, sort_keys=False))
        self.assertTrue([f for f in audit_workspace.audit(self.root) if f['level'] == 'error'])

    def test_torch_eager_flow_and_optional_wheel(self):
        self.assertEqual(gate.step_names(self.cfg, self.profile), ['device', 'operators', 'model-eager', 'summary'])
        for stage in ('architecture', 'environment', 'adaptation', 'device', 'operators', 'model-eager', 'summary'):
            self.bind(stage)
        self.cfg['status'] = 'functional'
        self.assertEqual(gate.validate_workspace(self.root, self.directory, self.cfg, self.profile, self.mounts), [])
        self.cfg['status'] = 'optimized'
        self.assertTrue(gate.validate_workspace(self.root, self.directory, self.cfg, self.profile, self.mounts))

    def test_missing_remote_or_changed_artifact_rejected(self):
        for stage in ('architecture', 'environment'):
            self.bind(stage)
        with self.assertRaisesRegex(ValueError, 'artifact-root'):
            gate.verify_record(self.root, self.directory, self.cfg, self.profile, 'environment', {})
        (self.remote/'environment.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, '证据已变化'):
            gate.verify_record(self.root, self.directory, self.cfg, self.profile, 'environment', self.mounts)

    def test_cross_framework_receipt_and_changed_profile_rejected(self):
        self.bind('architecture'); rec = self.bind('environment')
        path = self.remote/'environment.json'
        envelope = json.loads(path.read_text()); envelope['scope']['framework'] = 'vllm-plugin-fl'
        path.write_text(json.dumps(envelope)); rec['receipts'][0]['sha256'] = gate.digest(path)
        with self.assertRaisesRegex(ValueError, 'framework 不匹配'):
            gate.verify_record(self.root, self.directory, self.cfg, self.profile, 'environment', self.mounts)
        self.cfg['profile_version'] = 1
        self.assertTrue(gate.validate_workspace(self.root, self.directory, self.cfg, self.profile))

    def test_unsupported_platform_rejected_without_writes(self):
        platform = self.root/'models/Example/nvidia'; platform.mkdir()
        shutil.copy2(ROOT/'models/_template/nvidia/platform.yml', platform/'platform.yml')
        result = subprocess.run([sys.executable, str(ROOT/'scripts/new_framework.py'), '--repo-root', str(self.root),
                                'Example','nvidia','torch-fl'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((platform/'frameworks').exists())

    def test_cli_checks_selected_framework_prerequisites(self):
        for stage in ('architecture', 'environment'):
            self.bind(stage)
        (self.directory/'framework.yml').write_text(yaml.safe_dump(self.cfg, sort_keys=False))
        command = [sys.executable, str(ROOT/'scripts/adapt_model.py'), '--repo-root', str(self.root), 'Example',
                   '--platform', 'ppu', '--framework', 'torch-fl', '--hosts', 'PPU-01', '--steps', 'adaptation',
                   '--check-only', '--artifact-root', f'PPU-01={self.remote}']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run(command + ['--verify-records'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_artifact_escape_rejected(self):
        reader = gate.Artifacts(self.cfg, 'PPU-01', self.mounts)
        outside = self.root/'outside'; outside.write_text('private')
        (self.remote/'escape').symlink_to(outside)
        for path in ('../outside', 'escape', '/unapproved/outside'):
            with self.assertRaises(ValueError):
                reader.file({'path': path, 'sha256': gate.digest(outside)})

    def test_whole_acceptance_verifies_parent_before_retrospective(self):
        args = Namespace(check_only=True, platform='ppu', repo_root=self.root, framework='torch-fl',
                         model='Example', artifact_root=[], evidence_info=None,
                         steps='retrospective,acceptance', hosts='PPU-01',
                         acceptance_substeps=None, verify_records=True)
        (self.directory/'framework.yml').write_text(yaml.safe_dump(self.cfg, sort_keys=False))
        with patch.object(gate, 'validate_workspace', return_value=[]), \
             patch.object(gate, 'state', return_value='passed'), \
             patch.object(gate, 'dependencies', return_value=[]), \
             patch.object(gate, 'verify_record') as verify:
            gate.check_command(args)
        self.assertEqual([call.args[4] for call in verify.call_args_list],
                         ['device', 'operators', 'model-eager', 'summary', 'acceptance', 'retrospective'])

    def test_formal_accuracy_rechecks_real_results_and_samples(self):
        from test_evidence_and_acceptance import formal_config, llmrun
        self.cfg['workspace']['roots'][0]['host_root'] = str(self.remote)
        reader = gate.Artifacts(self.cfg, 'PPU-01', self.mounts)
        config = formal_config()
        config['acceptance_criteria']['example']['minimum'] = 0.5
        config_path = self.remote/'config.json'; config_path.write_text(json.dumps(config))
        run = self.remote/'accuracy-run'; run.mkdir()
        (run/'source_config.json').write_bytes(config_path.read_bytes())
        (run/'effective_config.json').write_bytes(config_path.read_bytes())
        samples = run/'samples_example_1.jsonl'
        samples.write_text('\n'.join(json.dumps({'doc_id': i, 'resps': [[answer]]})
                                     for i, answer in enumerate(['answer', '<TIMEOUT>'])))
        result_path = run/'results_1.json'
        result_path.write_text(json.dumps({'results': {'example': {'acc': 0.5}}}))
        config['source_config_sha256'] = gate.digest(config_path)
        llmrun.write_acceptance_report(config, run, [], {'example': [
            {'output_dir': str(run), 'returncode': 0, 'status': 'passed', 'errors': []}]}, [])
        report_path = run/'acceptance-result.json'
        ref = lambda p: {'path': str(p), 'sha256': gate.digest(p)}
        native = {'report': ref(report_path), 'config': ref(config_path)}
        self.cfg['acceptance_plan'] = {'accuracy_config_sha256': gate.digest(config_path)}
        gate.native_accuracy(reader, native, {'run_id': 'accuracy-run'}, self.cfg)
        # A reported pass is insufficient when its current metric misses the threshold.
        result_path.write_text(json.dumps({'results': {'example': {'acc': 0.1}}}))
        report = json.loads(report_path.read_text())
        report['artifacts']['example']['results'] = ref(result_path)
        report_path.write_text(json.dumps(report)); native['report'] = ref(report_path)
        with self.assertRaisesRegex(ValueError, '指标未达到'):
            gate.native_accuracy(reader, native, {'run_id': 'accuracy-run'}, self.cfg)

    def test_formal_performance_rechecks_native_artifacts(self):
        from test_performance_evidence import PerformanceEvidenceTests, workflow
        fixture = PerformanceEvidenceTests(); fixture.setUp()
        try:
            fixture.compact_path.write_text(json.dumps(fixture.compact))
            cfg = {'model': 'Example', 'platform': 'ppu',
                   'workspace': {'roots': [{'host_alias': 'PPU-01', 'host_root': str(fixture.root), 'container_root': str(fixture.root.resolve())}]},
                   'deployment': {'fingerprint': workflow.deployment_fingerprint(fixture.platform)},
                   'acceptance_plan': {'performance_request_sha256': gate.canonical(fixture.report['request'])}}
            reader = gate.Artifacts(cfg, 'PPU-01', {'PPU-01': str(fixture.root)})
            ref = lambda p: {'path': str(p), 'sha256': gate.digest(p)}
            native = {'report': ref(fixture.compact_path), 'runtime': ref(fixture.runtime_path)}
            envelope = {'service_instance_id': fixture.instance, 'run_id': fixture.report['run_id']}
            gate.native_performance(reader, native, envelope, cfg)
            profiled_source = copy.deepcopy(fixture.report)
            profiled_source['request']['profiling_requested'] = True
            # Keep the compact validator isolated: this check belongs to the
            # framework's formal gate, not the diagnostic report reader.
            with patch.object(reader, 'json', return_value=fixture.compact), \
                 patch('perf_acceptance.validate_evidence', return_value=[]), \
                 patch.object(gate.json, 'loads', return_value=profiled_source):
                with self.assertRaisesRegex(ValueError, '无 profiler'):
                    gate.native_performance(reader, native, envelope, cfg)
            raw = fixture.report_path.parent/fixture.report['artifacts'][0]['path']
            raw.write_text('tampered')
            with self.assertRaisesRegex(ValueError, '完整性能产物'):
                gate.native_performance(reader, native, envelope, cfg)
        finally:
            fixture.doCleanups()

    def test_compact_markdown_cannot_pass_formal_gate(self):
        from test_evidence_and_acceptance import EvidenceTests, workflow
        fixture = EvidenceTests(); fixture.setUp()
        try:
            cfg = fixture.platform_config; cfg['record_layout'] = 'compact'
            for stage in ('accuracy', 'performance'):
                rec = {'run_id': 'test', 'last_verified': date.today().isoformat(),
                       'evidence': 'evidence.md', 'evidence_sha256': gate.digest(fixture.evidence),
                       'context_sha256': workflow.context_sha256(fixture.platform, stage, cfg)}
                self.assertTrue(workflow.verification_errors(rec, fixture.platform, stage, cfg))
        finally:
            fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
