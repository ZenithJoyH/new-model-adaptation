"""Remote root declarations are validated locally; no remote filesystem access."""

import copy
import io
import shutil
import sys
import unittest
from unittest.mock import patch

import test_evidence_and_acceptance as fixtures

workflow = fixtures.workflow


def config():
    return {'target': {'hosts': ['PPU-01', 'PPU-02'], 'container_name': 'model-container'},
            'workspace': {'roots': [
                {'host_alias': 'PPU-01', 'host_root': '/operator/first', 'container_root': '/work/first'},
                {'host_alias': 'PPU-02', 'host_root': '/another/disk/task', 'container_root': '/work/second'}]}}


class RemoteWorkspaceTests(unittest.TestCase):
    def test_each_host_may_have_different_explicit_paths_without_local_resolution(self):
        with patch.object(workflow.Path, 'resolve', side_effect=AssertionError('must not resolve remote paths locally')):
            self.assertEqual(workflow.workspace_errors(config()), [])

    def test_missing_malformed_unknown_duplicate_or_incomplete_scope_fails(self):
        mutations = (
            lambda c: c.pop('workspace'), lambda c: c.update(workspace=[]),
            lambda c: c['workspace'].update(roots=[]), lambda c: c['workspace'].update(roots={}),
            lambda c: c['workspace']['roots'].append(copy.deepcopy(c['workspace']['roots'][0])),
            lambda c: c['workspace']['roots'].pop(),
            lambda c: c['workspace']['roots'][0].update(host_alias='PPU-OTHER'),
            lambda c: c['workspace']['roots'][0].update(host_alias=[]),
            lambda c: c['workspace']['roots'][0].update(unexpected='value'),
            lambda c: c['workspace']['roots'][0].pop('container_root'),
            lambda c: c['target'].update(hosts=[{}]),
            lambda c: c['target'].update(container_name=''),
            lambda c: c['target'].update(container_name='model-container\nextra prompt line'),
            lambda c: c['target'].update(container_name=' model-container'),
            lambda c: c['target'].update(container_name='model-container\x7f'),
        )
        for mutation in mutations:
            value = config()
            mutation(value)
            with self.subTest(value=value):
                self.assertTrue(workflow.workspace_errors(value))

    def test_matching_host_scope_still_rejects_option_or_dot_alias(self):
        for alias in ('-PPU-01', '.', '..', '.PPU-01'):
            value = config()
            value['target']['hosts'][0] = alias
            value['workspace']['roots'][0]['host_alias'] = alias
            with self.subTest(alias=alias):
                self.assertTrue(any('.host_alias 必须' in error for error in workflow.workspace_errors(value)))

    def test_paths_are_canonical_posix_not_local_or_interpolated(self):
        invalid = ('', '/', '//server/path', '/work/../other', '/work/./task', '/work//task',
                   '/work/task/', 'relative/path', '~/task', '/work/$USER', '/work/<task>',
                   ' /work/task', '/work/task\n', '/work/\x00task', 'C:\\work', None, 3, [])
        for field in ('host_root', 'container_root'):
            for path in invalid:
                value = config()
                value['workspace']['roots'][0][field] = path
                with self.subTest(field=field, path=path):
                    self.assertTrue(workflow.workspace_errors(value))
        value = config()
        value['workspace']['roots'][0]['host_root'] = '/operator/my task'
        self.assertEqual(workflow.workspace_errors(value), [])


class RemoteWorkspaceCliTests(unittest.TestCase):
    setUp = fixtures.EvidenceTests.setUp

    def prepare(self):
        shutil.copytree(fixtures.ROOT / 'templates', self.root / 'templates')
        shutil.copytree(fixtures.ROOT / 'models/_template', self.root / 'models/_template')
        (self.root / 'inventory').mkdir()
        workflow.write_yaml(self.root / 'inventory/hosts.yml',
                            {'all': {'children': {'managed': {'children': {'ppu': {'hosts': {'PPU-01': None}}}}}}})
        return ['adapt-model', 'Example', '--repo-root', str(self.root), '--platform', 'ppu',
                '--hosts', 'PPU-01', '--steps', 'environment']

    def test_environment_prompt_shows_roots_without_creating_remote_directories(self):
        argv = self.prepare()
        runtime_path = self.platform / 'environment/runtime-config.yml'
        runtime = workflow.load_yaml(runtime_path)
        runtime['target']['container_name'] = 'model-container'
        runtime['workspace'] = {'roots': [config()['workspace']['roots'][0]]}
        workflow.write_yaml(runtime_path, runtime)
        before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        output = io.StringIO()
        with patch.object(sys, 'argv', argv), patch('sys.stdout', output):
            self.assertEqual(workflow.main(), 0)
        self.assertIn('PPU-01: host_root=/operator/first', output.getvalue())
        self.assertIn('container=model-container; container_root=/work/first', output.getvalue())
        self.assertIn('不是 chroot', output.getvalue())
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

    def test_environment_without_runtime_reports_stop_write_and_does_not_backfill(self):
        argv = self.prepare()
        runtime = self.platform / 'environment/runtime-config.yml'
        runtime.unlink()
        status_before = (self.platform / 'platform.yml').read_bytes()
        output = io.StringIO()
        with patch.object(sys, 'argv', argv), patch('sys.stdout', output):
            self.assertEqual(workflow.main(), 0)
        self.assertIn('停止远端新增/写入', output.getvalue())
        self.assertFalse(runtime.exists())
        self.assertEqual(status_before, (self.platform / 'platform.yml').read_bytes())
        checked_output = io.StringIO()
        with patch.object(sys, 'argv', [*argv, '--check-only']), patch('sys.stdout', checked_output):
            self.assertEqual(workflow.main(), 0)
        self.assertIn('不自动授权远端写入', checked_output.getvalue())
        self.assertFalse(runtime.exists())
        self.assertEqual(status_before, (self.platform / 'platform.yml').read_bytes())

    def test_config_gate_rejects_missing_workspace_without_state_changes(self):
        path = self.platform / 'environment/runtime-config.yml'
        runtime = workflow.load_yaml(fixtures.ROOT / 'templates/adaptation/runtime-config.yml')
        runtime.update(model='Example', platform='ppu', configuration_status='ready')
        runtime['target'].update(hosts=['PPU-01'], container_name='model', container_image='test-image')
        for item in runtime['stack'].values():
            item.update(path='/existing/external/checkout', revision='revision')
        runtime['service'].update(model_path='/existing/weights', served_model_name='Example', port=8000,
                                  tensor_parallel_size=1)
        runtime['service']['max_model_len'].update(model_supported=100, initial=100, evidence='model config')
        runtime.pop('workspace', None)
        workflow.write_yaml(path, runtime)
        original = path.read_bytes()
        errors = workflow.validate_adaptation_config(path, 'Example', 'ppu')
        self.assertTrue(any('workspace' in error for error in errors), errors)
        self.assertEqual(path.read_bytes(), original)
        runtime['workspace'] = {'roots': [config()['workspace']['roots'][0]]}
        workflow.write_yaml(path, runtime)
        self.assertEqual(workflow.validate_adaptation_config(path, 'Example', 'ppu'), [])

    def test_read_only_identity_and_evidence_tools_do_not_require_or_backfill_workspace(self):
        argv = self.prepare()
        fixtures.EvidenceTests.bind_identity(self)
        before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        for flags in (['--deployment-info'],
                      ['--evidence-info', 'architecture', '--evidence', 'evidence.md', '--run-id', 'historical']):
            with patch.object(sys, 'argv', argv + flags), patch('sys.stdout', io.StringIO()), \
                 patch.object(workflow, 'workspace_errors', side_effect=AssertionError('read-only identity tool must not require workspace')):
                self.assertEqual(workflow.main(), 0)
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()})


if __name__ == '__main__':
    unittest.main()
