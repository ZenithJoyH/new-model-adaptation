"""Synthetic regressions for frozen capabilities, launchers and partial reviews."""
import copy
import hashlib
import json
from pathlib import Path

from test_collaboration_contract import ModernFixture
import test_collaboration_contract as fixtures
import framework_evidence as gate
import framework_workspace as workspace
import service_acceptance as service
import project_gates


def sanity_scope_fixture():
    manifest = {'schema_version': 2, 'model': 'Example', 'modalities': ['text', 'image'],
                'cases': [
                    {'id': 'text', 'request': {'messages': [{'role': 'user', 'content': 'Hello'}]}},
                    {'id': 'image', 'request': {'messages': [{'role': 'user', 'content': [
                        {'type': 'text', 'text': 'Describe this image'},
                        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,fixture'}}]}]}}]}
    return manifest, {'run_id': 'sanity-run'}, None


def freeze_service(test, modalities=None):
    launcher = test.f.remote / 'start-model.sh'
    launcher.write_text('#!/bin/sh\nexec python -m vllm serve /weights "$@"\n')
    launcher.chmod(0o755)
    host = {'launcher': test.ref(launcher),
            'argv': ['python', '-m', 'vllm', 'serve', '/weights', '--served-model-name', 'Example'],
            'environment': {'OMP_NUM_THREADS': '1'},
            'effective_config': {'served_model_names': ['Example'], 'prefix_caching_enabled': True,
                                 'settings': {'dtype': 'bfloat16', 'max_model_len': 50000, 'graph': 'full', 'tp': 2}}}
    test.cfg['acceptance_plan']['service_contract'] = {
        'schema_version': 1, 'required_modalities': modalities or ['text', 'image'],
        'architecture_sha256': gate.digest(test.f.root / 'models/Example/architecture-and-inference.md'),
        'hosts': {'PPU-01': host}}
    return host


def launch_record(test, stage):
    host = test.cfg['acceptance_plan']['service_contract']['hosts']['PPU-01']
    run = stage + '-run'
    binding = test.binding(run)
    argv = host['argv'] + ([service.CACHE_OFF] if stage == 'performance' else [])
    binding['process_identity']['cmdline_sha256'] = hashlib.sha256(b'\0'.join(a.encode() for a in argv) + b'\0').hexdigest()
    observation = test.reader.json(binding['observation'])
    observation.update(argv=argv, launch_environment=host['environment'], process_identity=binding['process_identity'])
    binding['observation'] = test.raw(stage + '-observation.json', observation)
    config = dict(copy.deepcopy(host['effective_config']), prefix_caching_enabled=stage != 'performance')
    proof = test.raw(stage + '-effective-config.json', config)
    record = {'kind': 'service_launch', 'schema_version': 1, 'run_id': run,
              'service_binding': binding, 'launcher': host['launcher'], 'effective_config': config,
              'configuration_review': {'reviewer': 'test operator', 'note': 'checked service runtime configuration', 'evidence': [proof]}}
    report = {'run_id': run, 'service_instance_id': 'service-A', 'launcher': host['launcher'],
              'native': {'service_launch': test.raw(stage + '-launch.json', record)}}
    return report, binding, record


class ServiceAcceptanceTests(ModernFixture):
    def setUp(self):
        super().setUp()
        freeze_service(self)

    def test_text_image_coverage_and_served_alias_are_bound(self):
        manifest, _, _ = sanity_scope_fixture()
        service.validate_sanity_scope(self.cfg, 'PPU-01', manifest)
        for field, value in [('modalities', ['text']), ('model', 'unrelated')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                service.validate_sanity_scope(self.cfg, 'PPU-01', dict(manifest, **{field: value}))
        plan = self.cfg['acceptance_plan']['service_contract']
        plan['hosts']['PPU-01']['effective_config']['served_model_names'].append('alias')
        service.validate_sanity_scope(self.cfg, 'PPU-01', dict(manifest, model='alias'))
        plan['required_modalities'] = ['text']
        service.validate_sanity_scope(self.cfg, 'PPU-01', dict(manifest, modalities=['text'], cases=[manifest['cases'][0]]))

    def test_native_gate_rejects_self_declared_text_only_or_wrong_model(self):
        manifest, result, review = sanity_scope_fixture()
        for change in ('coverage', 'model'):
            with self.subTest(change=change):
                current = copy.deepcopy(manifest)
                if change == 'coverage':
                    current['modalities'] = ['text']
                    current['cases'] = [current['cases'][0]]
                else:
                    current['model'] = 'wrong-service'
                ref = self.raw('manifest.json', current)
                result.update(manifest_sha256=ref['sha256'])
                report, binding, _ = launch_record(self, 'sanity')
                result['service_binding'] = binding
                report['native'].update(manifest=ref, sanity=self.raw('sanity.json', result))
                self.cfg['acceptance_plan']['sanity_manifest_sha256'] = ref['sha256']
                with self.assertRaisesRegex(ValueError, '模态覆盖|请求 model'):
                    gate.native_sanity(self.reader, report, self.cfg, 'PPU-01')

    def test_native_schema1_runner_can_use_bound_text_and_image_scope(self):
        manifest, _, _ = sanity_scope_fixture()
        manifest.update(schema_version=1, kind='sanity_manifest', concurrency=2, timeout=30)
        manifest.pop('modalities')
        for case in manifest['cases']:
            case['reference_text'] = 'answer'
        ref = self.raw('legacy-manifest.json', manifest)
        report, binding, _ = launch_record(self, 'sanity')
        result = {'kind': 'sanity_result', 'status': 'passed', 'run_id': 'sanity-run',
                  'concurrency': 2, 'manifest_sha256': ref['sha256'], 'service_binding': binding,
                  'cases': [{'id': case['id'], 'error': None, 'response': {
                      'choices': [{'message': {'content': 'answer'}}]}} for case in manifest['cases']]}
        report['native'].update(manifest=ref, sanity=self.raw('legacy-result.json', result))
        self.cfg['acceptance_plan']['sanity_manifest_sha256'] = ref['sha256']
        gate.native_sanity(self.reader, report, self.cfg, 'PPU-01')
        manifest['cases'] = [manifest['cases'][0]]
        ref = self.raw('legacy-manifest.json', manifest)
        result['manifest_sha256'] = ref['sha256']
        report['native'].update(manifest=ref, sanity=self.raw('legacy-result.json', result))
        self.cfg['acceptance_plan']['sanity_manifest_sha256'] = ref['sha256']
        with self.assertRaisesRegex(ValueError, '模态覆盖'):
            gate.native_sanity(self.reader, report, self.cfg, 'PPU-01')

    def test_native_performance_validates_shared_launch_with_no_baseline(self):
        import test_performance_evidence as perf
        import yaml
        fixture = perf.PerformanceEvidenceTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.f.remote = fixture.root
        self.cfg['workspace']['roots'] = [{'host_alias': 'PPU-01', 'host_root': str(fixture.root),
                                         'container_root': str(fixture.root.resolve())}]
        self.cfg['deployment']['fingerprint'] = perf.workflow.deployment_fingerprint(fixture.platform)
        self.reader = gate.Artifacts(self.cfg, 'PPU-01', {'PPU-01': str(fixture.root)})
        host = freeze_service(self)
        request = fixture.report['request']
        host['effective_config']['served_model_names'] = [request['model']]
        host['argv'][-1] = request['model']
        report, binding, launch = launch_record(self, 'performance')
        run_id = fixture.report['run_id']
        observation = self.reader.json(binding['observation'])
        observation.update(run_id=run_id, service_instance_id=fixture.instance, listening_port=request['port'])
        binding.update(service_instance_id=fixture.instance,
                       endpoint=f"http://{request['host']}:{request['port']}{request['endpoint']}",
                       observation=self.raw('perf-observation.json', observation))
        launch.update(run_id=run_id, service_binding=binding)
        report.update(run_id=run_id, service_instance_id=fixture.instance, scope={'host_alias': 'PPU-01'})
        report['native']['service_launch'] = self.raw('perf-launch.json', launch)
        runtime = workspace.load_yaml(fixture.runtime_path)
        runtime['service_binding'] = binding
        fixture.runtime_path.write_text(yaml.safe_dump(runtime))
        fixture.compact_path.write_text(json.dumps(perf.perf_acceptance.export_evidence(
            fixture.report_path, fixture.runtime_path, model='Example', platform='ppu',
            deployment_fingerprint=self.cfg['deployment']['fingerprint'], service_instance_id=fixture.instance)))
        self.cfg['acceptance_plan']['performance_request_sha256'] = gate.canonical(request)
        native = {'report': self.ref(fixture.compact_path), 'runtime': self.ref(fixture.runtime_path)}
        self.cfg['acceptance_plan']['performance_targets'] = {'cases': [
            {'case': case, 'limits': {'Req/s': {'min': 0.01}}} for case in request['cases']]}
        gate.native_performance(self.reader, native, report, self.cfg)
        launch['effective_config']['settings']['max_model_len'] = 1024
        report['native']['service_launch'] = self.raw('changed-perf-launch.json', launch)
        with self.assertRaisesRegex(ValueError, '有效推理配置'):
            gate.native_performance(self.reader, native, report, self.cfg)

    def test_pipeline_launch_uses_each_participant_command(self):
        # Reuse the real synthetic pipeline topology validator, not a mocked gate.
        binding = fixtures.ObjectiveEvidenceTests.pipeline_binding(self)
        plan = self.cfg['acceptance_plan']['service_contract']
        base = copy.deepcopy(plan['hosts']['PPU-01'])
        for participant in binding['distributed']['participants']:
            host = participant['host_alias']
            observed = self.reader.json(participant['observation'])
            observed['launch_environment'] = base['environment']
            participant['observation'] = self.raw(host + '-launch-observation.json', observed)
            plan['hosts'][host] = dict(copy.deepcopy(base), argv=observed['argv'])
        for host in self.cfg['target']['hosts']:
            launch = {'kind': 'service_launch', 'schema_version': 1, 'run_id': 'accuracy-run',
                      'service_binding': binding, 'launcher': base['launcher'],
                      'effective_config': base['effective_config'],
                      'configuration_review': {'reviewer': 'operator', 'note': 'pipeline service config',
                                               'evidence': [self.raw('pipeline-config.json', base['effective_config'])]}}
            report = {'run_id': 'accuracy-run', 'service_instance_id': 'service-A',
                      'native': {'service_launch': self.raw(host + '-launch.json', launch)}}
            service.validate_launch(self.reader, report, self.cfg, host, 'accuracy', binding)

    def test_changed_architecture_missing_contract_or_host_rejected(self):
        with self.assertRaisesRegex(ValueError, '结构分析已变化'):
            service.validate_plan(self.cfg, '0' * 64)
        self.cfg['target']['hosts'].append('PPU-02')
        with self.assertRaisesRegex(ValueError, 'Host'):
            service.validate_plan(self.cfg)
        self.cfg['acceptance_plan'].pop('service_contract')
        with self.assertRaisesRegex(ValueError, 'service_contract'):
            service.validate_plan(self.cfg)

    def test_same_launcher_and_config_allow_only_cache_switch(self):
        for stage in ('sanity', 'accuracy', 'performance', 'summary'):
            report, binding, _ = launch_record(self, stage)
            service.validate_launch(self.reader, report, self.cfg, 'PPU-01', stage, binding)

    def test_argument_environment_and_actual_config_drift_rejected(self):
        for change in ('argv', 'environment', 'settings', 'cache', 'identity', 'binding', 'evidence'):
            with self.subTest(change=change):
                report, binding, launch = launch_record(self, 'performance')
                observation = self.reader.json(binding['observation'])
                if change == 'argv':
                    observation['argv'].extend(['--max-model-len', '1024'])
                    observation['process_identity']['cmdline_sha256'] = hashlib.sha256(
                        b'\0'.join(a.encode() for a in observation['argv']) + b'\0').hexdigest()
                    binding['process_identity'] = observation['process_identity']
                elif change == 'environment':
                    observation['launch_environment']['OMP_NUM_THREADS'] = '8'
                elif change == 'settings':
                    launch['effective_config']['settings']['tp'] = 8
                elif change == 'cache':
                    launch['effective_config']['prefix_caching_enabled'] = True
                elif change == 'identity':
                    observation['argv'].append('--silent')
                elif change == 'binding':
                    binding['service_instance_id'] = 'different'
                else:
                    launch['configuration_review']['evidence'] = []
                binding['observation'] = self.raw('bad-observation.json', observation)
                launch['service_binding'] = binding
                report['native']['service_launch'] = self.raw('bad-launch.json', launch)
                with self.assertRaises((ValueError, KeyError)):
                    service.validate_launch(self.reader, report, self.cfg, 'PPU-01', 'performance')

    def test_changed_script_and_delivery_script_rejected(self):
        report, _, launch = launch_record(self, 'summary')
        other = self.f.remote / 'other.sh'; other.write_text('# different'); other.chmod(0o755)
        report['launcher'] = self.ref(other)
        with self.assertRaisesRegex(ValueError, '交付脚本'):
            service.validate_launch(self.reader, report, self.cfg, 'PPU-01', 'summary')
        report['launcher'] = launch['launcher']
        (self.f.remote / 'start-model.sh').write_text('# changed')
        with self.assertRaisesRegex(ValueError, '证据已变化'):
            service.validate_launch(self.reader, report, self.cfg, 'PPU-01', 'summary')

    def test_conflicting_or_ambiguous_cache_flags_rejected(self):
        for argv in (['serve', service.CACHE_ON, service.CACHE_OFF], ['serve', service.CACHE_ON + '=false']):
            with self.assertRaises(ValueError):
                service.normalized_argv(argv)

    def test_model_contract_is_part_of_accuracy_context_and_journal(self):
        profile = workspace.resolved_profile(self.f.root, 'vllm-plugin-fl')[1]
        self.cfg['workflow']['acceptance']['substeps'] = {name: 'not_started' for name in profile['acceptance']['steps']}
        before = gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'accuracy')
        execution = gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'execution-mode')
        self.cfg['acceptance_plan']['service_contract']['required_modalities'] = ['text']
        self.assertNotEqual(before, gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'accuracy'))
        self.assertEqual(execution, gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'execution-mode'))
        self.assertIn(Path(__file__).resolve().parents[2] / 'scripts/service_acceptance.py',
                      project_gates.source_files(Path(__file__).resolve().parents[2], {'before': []}))


class PartialRetrospectiveTests(ModernFixture):
    def test_failed_task_can_review_without_passing_acceptance(self):
        self.cfg['workflow']['environment']['status'] = 'failed'
        self.assertEqual(gate.dependencies(self.cfg, self.f.profile, 'retrospective'), [])
        self.f.bind('retrospective')
        self.assertEqual(gate.validate_workspace(self.f.root, self.f.directory, self.cfg, self.f.profile), [])
        self.assertEqual(self.cfg['workflow']['environment']['status'], 'failed')
        self.assertEqual(self.cfg['workflow']['acceptance']['status'], 'not_started')
        self.cfg['status'] = 'optimized'
        self.assertTrue(gate.validate_workspace(self.f.root, self.f.directory, self.cfg, self.f.profile))

    def test_review_context_changes_when_failed_stage_or_evidence_changes(self):
        before = gate.context_hash(self.f.root, self.f.directory, self.cfg, self.f.profile, 'retrospective')
        self.cfg['workflow']['environment']['status'] = 'failed'
        after = gate.context_hash(self.f.root, self.f.directory, self.cfg, self.f.profile, 'retrospective')
        self.assertNotEqual(before, after)
        self.cfg['workflow']['environment']['verification'] = {'evidence_sha256': 'a' * 64}
        self.assertNotEqual(after, gate.context_hash(self.f.root, self.f.directory, self.cfg, self.f.profile, 'retrospective'))

    def test_review_can_record_failed_architecture_without_inventing_analysis(self):
        path = self.f.root / 'models/Example/architecture-and-inference.md'
        path.unlink()
        self.cfg['workflow']['architecture']['status'] = 'failed'
        self.f.bind('retrospective')
        self.assertEqual(gate.validate_workspace(self.f.root, self.f.directory, self.cfg, self.f.profile), [])
        path.write_text('后续新增的结构分析')
        self.assertTrue(gate.validate_workspace(self.f.root, self.f.directory, self.cfg, self.f.profile))

    def test_new_service_profiles_enable_extension_but_torch_does_not(self):
        for name in ('vllm-plugin-fl', 'vllm-native', 'vllm-ppu', 'torch-fl'):
            cfg = {}
            workspace.pin_profile(cfg, workspace.resolved_profile(self.f.root, name)[1])
            self.assertEqual('service_contract' in cfg.get('acceptance_plan', {}), name != 'torch-fl')
