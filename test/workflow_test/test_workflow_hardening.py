import copy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
import io
import json
import sys

import test_evidence_and_acceptance as fixtures
from workflow_state import deployment_fingerprint, service_state_errors

ROOT, workflow = fixtures.ROOT, fixtures.workflow


class WorkflowHardeningTests(unittest.TestCase):
    bind_identity = fixtures.EvidenceTests.bind_identity
    record = fixtures.EvidenceTests.record
    # Reuse the isolated evidence fixture, not any model's mutable real records.
    def setUp(self):
        fixtures.EvidenceTests.setUp(self)
        self.bind_identity()
        self.cfg = self.platform_config

    def save(self):
        workflow.write_yaml(self.platform / 'platform.yml', self.cfg)

    def receipt(self, stage, run_id='first'):
        self.save()
        record = self.record(stage)
        record['run_id'] = run_id
        if stage in workflow.ACCEPTANCE_SUBSTEPS:
            self.cfg['workflow']['acceptance']['records'][stage] = record
            self.cfg['workflow']['acceptance']['substeps'][stage] = 'passed'
        else:
            self.cfg['workflow'][stage].update(status='passed', evidence='evidence.md', verification=record)
        self.save()
        return record

    def bound_prerequisites(self):
        for stage in ('architecture', 'environment', 'adaptation', 'execution-mode', 'sanity'):
            self.receipt(stage)

    def test_rebinding_adaptation_does_not_resurrect_old_sanity(self):
        self.bound_prerequisites()
        self.assertEqual(workflow.check_dependencies(self.cfg, ['acceptance'], self.platform), [])
        self.assertEqual(workflow.check_acceptance_dependencies(self.cfg, ['accuracy'], self.platform), [])
        saved = copy.deepcopy(self.cfg['workflow']['acceptance']['records'])
        (self.platform / 'environment/plugin-change-review.md').write_text('new dirty implementation reviewed')
        self.receipt('adaptation', 'second-implementation')
        errors = workflow.check_acceptance_dependencies(self.cfg, ['accuracy'], self.platform)
        self.assertTrue(any('execution-mode' in e for e in errors), errors)
        self.assertTrue(any('sanity' in e for e in errors), errors)
        self.assertEqual(saved, self.cfg['workflow']['acceptance']['records'])

    def test_same_head_dirty_or_untracked_change_invalidates_downstream(self):
        self.bound_prerequisites()
        path = self.platform / 'environment/deployment-identity.yml'
        original = workflow.load_yaml(path)
        for field in ('tracked_diff_sha256', 'untracked_files_sha256'):
            value = copy.deepcopy(original)
            value['stack']['plugin'][field] = 'e' * 64
            workflow.write_yaml(path, value)
            errors = workflow.check_acceptance_dependencies(self.cfg, ['accuracy'], self.platform)
            self.assertTrue(errors, field)

    def test_narrative_state_notes_do_not_invalidate_receipts(self):
        self.bound_prerequisites()
        path = self.platform / 'environment/deployment-identity.yml'
        identity = workflow.load_yaml(path)
        identity['notes'] = 'explanatory note only'
        workflow.write_yaml(path, identity)
        self.cfg['notes'] = 'unrelated progress'
        self.save()
        self.assertEqual(workflow.check_acceptance_dependencies(self.cfg, ['accuracy'], self.platform), [])

    def test_cross_platform_evidence_rejected(self):
        other = self.platform.parent / 'nvidia'
        other.mkdir()
        file = other / 'evidence.md'
        file.write_text(self.evidence.read_text())
        record = self.record('sanity')
        record['evidence'] = '../nvidia/evidence.md'
        self.assertTrue(workflow.verification_errors(record, self.platform, 'sanity'))

    def test_platform_schema_rejects_invalid_or_incomplete_success(self):
        self.assertEqual(workflow.platform_schema_errors(self.cfg, 'ppu', {'PPU-01'}), [])
        for mutate in (
            lambda c: c.update(status='nonsense'),
            lambda c: c.update(status=[]),
            lambda c: c.update(status='optimized', validated_hosts=[]),
            lambda c: c['workflow']['acceptance'].pop('substeps'),
            lambda c: c['workflow']['acceptance'].pop('records'),
            lambda c: c.update(validated_hosts=['PPU-01', 'PPU-01']),
            lambda c: c.update(validated_hosts=['H100-205']),
            lambda c: c['workflow']['acceptance']['substeps'].update(sanity=[]),
            lambda c: (c.update(status='optimized'), c['workflow']['acceptance']['substeps'].update(sanity=[])),
        ):
            cfg = copy.deepcopy(self.cfg)
            mutate(cfg)
            self.assertTrue(workflow.platform_schema_errors(cfg, 'ppu', {'PPU-01'}), cfg)

    def ready_service(self):
        runtime_path = self.platform / 'environment/runtime-config.yml'
        runtime = workflow.load_yaml(runtime_path)
        runtime['target'] = {'hosts': ['PPU-01'], 'container_name': 'example'}
        workflow.write_yaml(runtime_path, runtime)
        self.bind_identity()
        now = datetime.now(timezone.utc)
        state = workflow.load_yaml(ROOT / 'templates/adaptation/service-state.yml')
        state.update(model='Example', platform='ppu', host='PPU-01', container_name='example')
        state['service'].update(status='ready', mode='graph', readiness_result='passed', pid=123, port=8000,
                                instance_id='example-start-1', deployment_fingerprint=deployment_fingerprint(self.platform),
                                command_record='environment/launch.md', started_at=(now - timedelta(minutes=5)).isoformat(),
                                readiness_checked_at=now.isoformat())
        workflow.write_yaml(self.platform / 'environment/service-state.yml', state)
        return state

    def test_service_actual_mode_identity_and_freshness(self):
        ready = self.ready_service()
        path = self.platform / 'environment/service-state.yml'
        self.assertEqual(service_state_errors(self.platform, require_ready=True, require_graph=True), [])
        for fields in ({'status': 'failed'}, {'mode': 'eager'}, {'readiness_result': 'failed'},
                       {'deployment_fingerprint': 'stale'}, {'pid': None},
                       {'readiness_checked_at': '2020-01-01T00:00:00+00:00'}):
            state = copy.deepcopy(ready)
            state['service'].update(fields)
            workflow.write_yaml(path, state)
            self.assertTrue(service_state_errors(self.platform, require_ready=True, require_graph=True), fields)

    def test_stopped_service_preserves_history_but_blocks_new_execution(self):
        state = self.ready_service()
        self.bound_prerequisites()
        state['service']['status'] = 'stopped'
        workflow.write_yaml(self.platform / 'environment/service-state.yml', state)
        self.assertEqual(workflow.check_acceptance_dependencies(self.cfg, ['accuracy'], self.platform), [])
        self.assertEqual(workflow.check_execution_readiness(self.cfg, ['summary'], self.platform), [])
        self.assertTrue(workflow.check_execution_readiness(self.cfg, ['accuracy'], self.platform))

    def test_new_instance_requires_revalidation(self):
        self.ready_service()
        self.bound_prerequisites()
        self.assertTrue(workflow.check_execution_readiness(self.cfg, ['accuracy'], self.platform))
        for record in self.cfg['workflow']['acceptance']['records'].values():
            record['service_instance_id'] = 'example-start-1'
        self.assertEqual(workflow.check_execution_readiness(self.cfg, ['accuracy'], self.platform), [])

    def test_combined_execution_mode_may_start_from_ready_eager(self):
        state = self.ready_service()
        state['service']['mode'] = 'eager'
        workflow.write_yaml(self.platform / 'environment/service-state.yml', state)
        self.assertEqual(workflow.check_execution_readiness(self.cfg, ['execution-mode', 'sanity'], self.platform), [])
        self.assertTrue(workflow.check_execution_readiness(self.cfg, ['sanity'], self.platform))

    def test_instance_identity_is_part_of_dependency_chain(self):
        self.bound_prerequisites()
        before = workflow.context_sha256(self.platform, 'accuracy', self.cfg)
        self.cfg['workflow']['acceptance']['records']['sanity']['service_instance_id'] = 'different-start'
        self.assertNotEqual(before, workflow.context_sha256(self.platform, 'accuracy', self.cfg))

    def test_installed_distribution_identity_tracks_actual_files(self):
        runtime_path = self.platform / 'environment/runtime-config.yml'
        runtime = workflow.load_yaml(runtime_path)
        runtime['stack']['vllm'] = {'path': '/opt/site-packages/vllm', 'revision': '0.24.0+cu129'}
        workflow.write_yaml(runtime_path, runtime)
        identity_path = self.platform / 'environment/deployment-identity.yml'
        identity = workflow.load_yaml(identity_path)
        identity['runtime_config_sha256'] = workflow.file_sha256(runtime_path)
        identity['stack']['vllm'] = {'source_kind': 'installed_distribution', 'package': 'vllm',
                                   'revision': '0.24.0+cu129', 'import_path': '/opt/site-packages/vllm',
                                   'installed_files_sha256': 'e' * 64}
        workflow.write_yaml(identity_path, identity)
        before = deployment_fingerprint(self.platform)
        identity['stack']['vllm']['installed_files_sha256'] = 'f' * 64
        workflow.write_yaml(identity_path, identity)
        self.assertNotEqual(before, deployment_fingerprint(self.platform))
        identity['stack']['vllm']['import_path'] = '/another/environment/vllm'
        workflow.write_yaml(identity_path, identity)
        with self.assertRaises(ValueError):
            deployment_fingerprint(self.platform)

    def test_evidence_info_uses_explicit_historical_instance_not_live_state(self):
        self.bound_prerequisites()
        # No service-state file at all: binding recorded history needs no running service.
        args = ['adapt-model', 'Example', '--repo-root', str(self.root), '--platform', 'ppu',
                '--steps', 'acceptance', '--evidence-info', 'sanity', '--evidence', 'evidence.md',
                '--run-id', 'historical', '--verified-on', '2020-01-01']
        with patch.object(sys, 'argv', args), self.assertRaises(workflow.WorkflowError):
            workflow.main()
        output = io.StringIO()
        with patch.object(sys, 'argv', args + ['--service-instance-id', 'actual-old-instance']), patch('sys.stdout', output):
            self.assertEqual(workflow.main(), 0)
        record = json.loads(output.getvalue())
        self.assertEqual(record['service_instance_id'], 'actual-old-instance')
        self.assertEqual(record['last_verified'], '2020-01-01')


if __name__ == '__main__':
    unittest.main()
