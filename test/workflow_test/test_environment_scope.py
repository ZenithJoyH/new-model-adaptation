"""Synthetic metadata and scope checks; never read or change a remote host."""

import copy
import unittest

import test_evidence_and_acceptance as fixtures
from workflow_state import deployment_fingerprint, environment_target, model_identity

workflow = fixtures.workflow


class EnvironmentScopeTests(unittest.TestCase):
    setUp = fixtures.EvidenceTests.setUp
    bind_identity = fixtures.EvidenceTests.bind_identity
    record = fixtures.EvidenceTests.record
    def test_mismatched_model_metadata_cannot_get_a_new_fingerprint(self):
        self.bind_identity()
        path = self.platform.parent / 'model.yml'
        original = workflow.load_yaml(path)
        original['name'] = 'AnotherModel'
        workflow.write_yaml(path, original)
        with self.assertRaises(ValueError):
            model_identity(self.platform.parent)
        with self.assertRaises(ValueError):
            deployment_fingerprint(self.platform)
        with self.assertRaises(workflow.WorkflowError):
            workflow.context_sha256(self.platform, 'architecture')

    def test_declared_model_revision_may_be_an_alias(self):
        self.bind_identity()
        path = self.platform.parent / 'model.yml'
        original = workflow.load_yaml(path)
        original['source']['revision'] = 'main'
        workflow.write_yaml(path, original)
        self.assertTrue(deployment_fingerprint(self.platform))

    def test_environment_scope_rejects_missing_wrong_or_ambiguous_hosts(self):
        path = self.platform / 'environment/environment-target.yml'
        original = workflow.load_yaml(path)
        self.assertEqual(environment_target(self.platform), ['PPU-01'])
        for change in (
            lambda c: c.update(model='AnotherModel'),
            lambda c: c.update(platform='nvidia'),
            lambda c: c.update(schema_version=True),
            lambda c: c['target'].update(hosts=[]),
            lambda c: c['target'].update(hosts=['PPU-01', 'PPU-01']),
            lambda c: c['target'].update(hosts=['PPU-01:PPU-02']),
        ):
            changed = copy.deepcopy(original)
            change(changed)
            workflow.write_yaml(path, changed)
            with self.assertRaises(ValueError):
                environment_target(self.platform)
        path.unlink()
        with self.assertRaises(ValueError):
            environment_target(self.platform)

    def test_compact_environment_scope_comes_from_platform_state(self):
        target_path = self.platform / 'environment/environment-target.yml'
        target_path.unlink()
        config = self.platform_config
        config.update(
            record_layout='compact',
            target={
                'hosts': ['PPU-01'],
                'container_name': 'adaptation',
                'container_image': 'example:latest',
            },
            workspace={
                'roots': [{
                    'host_alias': 'PPU-01',
                    'host_root': '/operator/Example',
                    'container_root': '/work/Example',
                }]
            },
        )
        workflow.write_yaml(self.platform / 'platform.yml', config)
        self.assertEqual(environment_target(self.platform), ['PPU-01'])
        before = workflow.context_sha256(self.platform, 'environment', config)
        config['target']['hosts'] = ['PPU-02']
        workflow.write_yaml(self.platform / 'platform.yml', config)
        after = workflow.context_sha256(self.platform, 'environment', config)
        self.assertNotEqual(before, after)

    def _complete_environment(self):
        config = self.platform_config
        for stage in ('architecture', 'environment'):
            config['workflow'][stage].update(status='passed', evidence='evidence.md', verification=self.record(stage))
        workflow.write_yaml(self.platform / 'platform.yml', config)
        return config

    def test_changed_runtime_host_cannot_reuse_old_environment(self):
        config = self._complete_environment()
        self.assertEqual(workflow.check_dependencies(config, ['adaptation'], self.platform), [])
        runtime_path = self.platform / 'environment/runtime-config.yml'
        runtime = workflow.load_yaml(runtime_path)
        runtime['target']['hosts'] = ['PPU-02']
        workflow.write_yaml(runtime_path, runtime)
        errors = workflow.check_dependencies(config, ['adaptation'], self.platform)
        self.assertTrue(any('hosts' in error for error in errors), errors)

    def test_environment_digest_tracks_scope_not_inference_tuning(self):
        before = workflow.context_sha256(self.platform, 'environment')
        path = self.platform / 'environment/runtime-config.yml'
        runtime = workflow.load_yaml(path)
        runtime['service']['port'] = 8011
        workflow.write_yaml(path, runtime)
        self.assertEqual(before, workflow.context_sha256(self.platform, 'environment'))
        target_path = self.platform / 'environment/environment-target.yml'
        target = workflow.load_yaml(target_path)
        target['target']['hosts'] = ['PPU-02']
        workflow.write_yaml(target_path, target)
        self.assertNotEqual(before, workflow.context_sha256(self.platform, 'environment'))

    def test_explicit_scope_checked_before_runtime_exists(self):
        config = self._complete_environment()
        (self.platform / 'environment/runtime-config.yml').unlink()
        self.assertEqual(workflow.check_dependencies(config, ['adaptation'], self.platform, expected_hosts=['PPU-01']), [])
        self.assertTrue(workflow.check_dependencies(config, ['adaptation'], self.platform, expected_hosts=['PPU-02']))

    def test_audit_flags_legacy_structured_environment_artifacts(self):
        config = self._complete_environment()
        config['status'] = 'model_loading'
        config['workflow']['adaptation']['status'] = 'in_progress'
        workflow.write_yaml(self.platform / 'platform.yml', config)
        runtime_path = self.platform / 'environment/runtime-config.yml'
        runtime = workflow.load_yaml(runtime_path)
        runtime['target']['hosts'] = ['PPU-02']
        workflow.write_yaml(runtime_path, runtime)
        findings = fixtures.audit_workspace.audit(self.root)
        self.assertTrue(any(f['level'] == 'warning' and 'environment 仅允许 Markdown' in f['message'] for f in findings))


if __name__ == '__main__':
    unittest.main()
