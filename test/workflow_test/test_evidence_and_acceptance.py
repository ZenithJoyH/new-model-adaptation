import copy
import importlib
import json
import sys
import tempfile
import unittest
import yaml
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'test/Accuracy_test')]
import adapt_model as workflow
import audit_workspace
import llmrun
from acceptance_contract import validate_formal_config, metric_errors


def formal_config():
    return {'formal_acceptance': True, 'service_mode': 'graph', 'num_concurrent': 32,
            'limit': 0, 'expected_samples': 2, 'allow_timeouts': True,
            'tasks': ['example'], 'acceptance_criteria': {'example': {'metric': 'acc', 'minimum': 0.9}}}


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        logger = patch.object(llmrun, 'log')
        logger.start()
        self.addCleanup(logger.stop)

    def test_formal_configuration_rejects_diagnostic_settings(self):
        self.assertEqual(validate_formal_config(formal_config(), require_formal=True), [])
        for field, bad in [('num_concurrent', 8), ('num_concurrent', True), ('limit', 1),
                           ('expected_samples', 0), ('allow_timeouts', False),
                           ('service_mode', 'eager'), ('formal_acceptance', False),
                           ('formal_acceptance', 'true'),
                           ('acceptance_criteria', {}), ('tasks', 'example')]:
            with self.subTest(field=field, value=bad):
                cfg = formal_config()
                cfg[field] = bad
                self.assertTrue(validate_formal_config(cfg, require_formal=True))

    def test_threshold_and_nonfinite_metric(self):
        for value in [0.89, float('nan'), float('inf'), True, None, 1.1]:
            self.assertTrue(metric_errors(formal_config(), 'example', {'acc': value}))
        self.assertEqual(metric_errors(formal_config(), 'example', {'acc': 0.9}), [])

    def test_generic_diagnostic_keeps_lower_concurrency(self):
        cfg = {'formal_acceptance': False, 'num_concurrent': 1}
        self.assertEqual(validate_formal_config(cfg), [])

    def test_formal_samples_reject_invalid_records_but_retain_timeouts(self):
        good = [{'doc_id': i, 'resps': [['answer']]} for i in range(2)]
        timed_out = [good[0], {'doc_id': 1, 'resps': [['<TIMEOUT>']]}]
        cases = [good[:1], [good[0], good[0]],
                 [good[0], {'resps': [['answer']]}],
                 [good[0], {'doc_id': 1, 'resps': [[None]]}],
                 [good[0], {'doc_id': 1, 'resps': [['answer']], 'error': 'HTTP 500'}]]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'samples_example_1.jsonl'
            for records in cases:
                path.write_text('\n'.join(json.dumps(r) for r in records))
                self.assertFalse(llmrun.validate_samples(formal_config(), 'example', Path(d)))
            for records in (timed_out, good):
                path.write_text('\n'.join(json.dumps(r) for r in records))
                self.assertTrue(llmrun.validate_samples(formal_config(), 'example', Path(d)))

    def test_successful_runner_exit_is_not_passing_accuracy(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)
            (path / 'results_1.json').write_text(json.dumps({'results': {'example': {'acc': 0.2}}}))
            with patch.object(llmrun, 'validate_samples', return_value=True) as samples:
                self.assertFalse(llmrun.report_result(formal_config(), 'example', path))
                samples.assert_not_called()

    def test_example_is_not_accidentally_runnable(self):
        with self.assertRaises(SystemExit):
            llmrun.load_config(ROOT / 'test/Accuracy_test/llm_config.json')

    def test_retry_cannot_reuse_older_result_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cfg = dict(formal_config(), eval_max_retries=1, retry_delay=0, progress_score_interval=0)
            seen = []
            def process(command, log, sidecar):
                out = Path(command[command.index('--output_path') + 1])
                seen.append(out)
                if len(seen) == 1:
                    (out / 'results_1.json').write_text(json.dumps({'results': {'example': {'acc': 1.0}}}))
                    (out / 'samples_example_1.jsonl').write_text('\n'.join(
                        json.dumps({'doc_id': i, 'resps': [['answer']]}) for i in range(2)))
                    return 1
                # The second attempt exits 0 without writing results; first-attempt files cannot rescue it.
                return 0
            with patch.object(llmrun, 'build_command', return_value=['lm_eval', '--output_path', 'unused']), \
                 patch.object(llmrun, 'run_streaming', side_effect=process), \
                 patch.object(llmrun, 'probe_service', return_value=(True, 'ok')), \
                 patch.object(llmrun.time, 'sleep'):
                self.assertFalse(llmrun.run_task(cfg, 'example', root))
                self.assertEqual([p.name for p in seen], ['attempt-1', 'attempt-2'])

    def test_formal_main_writes_passing_or_failed_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cfg = dict(formal_config(), model_name='Example', eval_model='test', base_url='http://localhost/v1/chat/completions',
                       output_root=str(root / 'outputs'), cache_root=str(root / 'cache'), source_config_sha256='hash')
            config = root / 'config.json'
            config.write_text(json.dumps(cfg))
            for outcome in (True, False):
                output = root / str(outcome)
                output.mkdir()
                with patch.object(sys, 'argv', ['llmrun.py', str(config)]), \
                     patch.object(llmrun, 'configure_environment'), \
                     patch.object(llmrun.shutil, 'which', return_value='/usr/bin/lm_eval'), \
                     patch.object(llmrun, 'verify_dataset'), patch.object(llmrun, 'wait_for_service'), \
                     patch.object(llmrun, 'create_run_dir', return_value=output), \
                     patch.object(llmrun, 'run_task', return_value=outcome):
                    if outcome:
                        llmrun.main()
                    else:
                        with self.assertRaises(SystemExit):
                            llmrun.main()
                report = json.loads((output / 'acceptance-result.json').read_text())
                self.assertEqual(report['status'], 'passed' if outcome else 'failed')
                self.assertEqual(report['source_config_sha256'], workflow.file_sha256(config))
                self.assertIsNone(report['observed_concurrency'])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.platform = self.root / 'models/Example/ppu'
        (self.platform / 'environment').mkdir(parents=True)
        (self.platform.parent / 'model.yml').write_text('name: Example\nsource: {revision: abc}\n')
        (self.platform.parent / 'architecture-and-inference.md').write_text('verified architecture')
        (self.platform / 'environment/environment-analysis.md').write_text('verified environment')
        (self.platform / 'environment/environment-target.yml').write_text(
            'schema_version: 1\nmodel: Example\nplatform: ppu\ntarget: {hosts: [PPU-01]}\n')
        (self.platform / 'environment/runtime-config.yml').write_text(
            'model: Example\nplatform: ppu\ntarget: {hosts: [PPU-01]}\nservice: {port: 8000}\n')
        (self.platform / 'environment/plugin-change-review.md').write_text('Reviewed example plugin change')
        self.evidence = self.platform / 'evidence.md'
        self.evidence.write_text('Controlled experiment result; successful')
        self.platform_config = workflow.load_yaml(ROOT / 'models/_template/ppu/platform.yml')
        workflow.write_yaml(self.platform / 'platform.yml', self.platform_config)

    def bind_identity(self):
        runtime = workflow.load_yaml(self.platform / 'environment/runtime-config.yml')
        runtime.setdefault('stack', {name: {'revision': 'a' * 40} for name in ('vllm', 'plugin', 'flaggems')})
        workflow.write_yaml(self.platform / 'environment/runtime-config.yml', runtime)
        identity = {'schema_version': 1, 'model': 'Example', 'platform': 'ppu',
                    'model_revision': 'actual-snapshot', 'container_image_digest': 'sha256:' + 'b' * 64,
                    'runtime_config_sha256': workflow.file_sha256(self.platform / 'environment/runtime-config.yml'),
                    'stack': {name: {'revision': component['revision'], 'tracked_diff_sha256': 'c' * 64,
                                      'untracked_files_sha256': 'd' * 64} for name, component in runtime['stack'].items()}}
        workflow.write_yaml(self.platform / 'environment/deployment-identity.yml', identity)

    def record(self, stage):
        self.bind_identity()
        return {'run_id': 'actual-run-1', 'last_verified': date.today().isoformat(),
                'evidence': 'evidence.md', 'evidence_sha256': workflow.file_sha256(self.evidence),
                'context_sha256': workflow.context_sha256(self.platform, stage)}

    def test_current_evidence_valid_and_edits_invalidate(self):
        record = self.record('sanity')
        self.assertEqual(workflow.verification_errors(record, self.platform, 'sanity'), [])
        self.evidence.write_text('Changed conclusion')
        self.assertTrue(workflow.verification_errors(record, self.platform, 'sanity'))

    def test_service_or_model_change_invalidates_receipt(self):
        for file in [self.platform.parent / 'model.yml', self.platform / 'environment/runtime-config.yml']:
            record = self.record('sanity')
            file.write_text(file.read_text() + '\n# revised input\n')
            self.assertTrue(workflow.verification_errors(record, self.platform, 'sanity'))

    def test_changed_or_missing_plugin_review_invalidates_adaptation(self):
        review = self.platform / 'environment/plugin-change-review.md'
        record = self.record('adaptation')
        self.assertEqual(workflow.verification_errors(record, self.platform, 'adaptation'), [])
        review.write_text('Design blockers identified in this revision')
        self.assertTrue(workflow.verification_errors(record, self.platform, 'adaptation'))
        review.rename(review.with_suffix('.saved'))
        self.assertTrue(workflow.verification_errors(record, self.platform, 'adaptation'))

    def test_accuracy_report_binding_and_failed_result(self):
        import yaml
        acceptance = self.platform / 'acceptance'
        acceptance.mkdir()
        config = acceptance / 'llm_config.json'
        config.write_text(json.dumps(formal_config()))
        runtime = self.platform / 'environment/runtime-config.yml'
        runtime.write_text(yaml.safe_dump({'acceptance': {'accuracy_config': str(config.relative_to(self.root))}}))
        report = {'kind': 'formal_accuracy', 'status': 'passed', 'service_mode': 'graph', 'failed_tasks': [],
                  'configured_concurrency': 32, 'source_config_sha256': workflow.file_sha256(config),
                  'run_id': 'actual-run-1', 'expected_samples': 2,
                  'criteria': formal_config()['acceptance_criteria'], 'allow_timeouts': True,
                  'timeout_policy': 'count_as_incorrect'}
        self.evidence.write_text(json.dumps(report))
        record = self.record('accuracy')
        self.assertEqual(workflow.verification_errors(record, self.platform, 'accuracy'), [])
        report['status'] = 'failed'
        self.evidence.write_text(json.dumps(report))
        # Even a freshly hashed failed report cannot become a passed prerequisite.
        self.assertTrue(workflow.verification_errors(self.record('accuracy'), self.platform, 'accuracy'))
        report['status'] = 'passed'
        self.evidence.write_text(json.dumps(report))
        record = self.record('accuracy')
        config.write_text(config.read_text() + '\n')
        self.assertTrue(workflow.verification_errors(record, self.platform, 'accuracy'))

    def test_evidence_cannot_escape_model(self):
        record = self.record('sanity')
        outside = self.root / 'unrelated.md'
        outside.write_text(self.evidence.read_text())
        record['evidence'] = '../../../unrelated.md'
        self.assertTrue(workflow.verification_errors(record, self.platform, 'sanity'))

    def test_transitive_phase_dependencies(self):
        phases = {s: {'status': 'not_started'} for s in workflow.STEP_ORDER}
        phases['adaptation'] = {'status': 'passed', 'evidence': 'evidence.md',
                                'verification': self.record('adaptation')}
        errors = workflow.check_dependencies({'workflow': phases}, ['acceptance'], self.platform)
        self.assertEqual(len(errors), 2)

    def test_stage_gate_reads_owned_formal_accuracy_config(self):
        import yaml
        template = workflow.load_yaml(ROOT / 'templates/adaptation/runtime-config.yml')
        template.update(model='Example', platform='ppu', configuration_status='ready')
        template['target'].update(hosts=['PPU-01'], container_name='model', container_image='image:tag')
        template['workspace'] = {'roots': [{'host_alias': 'PPU-01', 'host_root': '/operator/Example',
                                           'container_root': '/work/Example'}]}
        for component in template['stack'].values():
            component.update(path='/workspace/source', revision='abc')
        template['service'].update(model_path='/models/Example', served_model_name='Example', port=8000,
                                   tensor_parallel_size=2)
        template['service']['max_model_len'].update(model_supported=50000, initial=50000, evidence='config.json')
        template['acceptance'].update(graph_base_url='http://127.0.0.1:8000',
                                     accuracy_image='harbor.baai.ac.cn/flageval/flageval-llmeval:v1',
                                     accuracy_config='models/Example/ppu/acceptance/llm_config.json')
        (self.root / 'inventory').mkdir()
        (self.root / 'inventory/hosts.yml').write_text(yaml.safe_dump(
            {'all': {'children': {'managed': {'children': {'ppu': {'hosts': {'PPU-01': None}}}}}}}))
        accuracy = dict(formal_config(), model_name='Example', base_url='http://127.0.0.1:8000/v1/chat/completions')
        config = self.platform / 'acceptance/llm_config.json'
        config.parent.mkdir()
        config.write_text(json.dumps(accuracy))
        runtime = self.platform / 'environment/runtime-config.yml'
        runtime.write_text(yaml.safe_dump(template))
        def errors():
            return workflow.validate_adaptation_config(runtime, 'Example', 'ppu', self.root, ['accuracy'])
        self.assertEqual(errors(), [])
        accuracy['num_concurrent'] = 8
        config.write_text(json.dumps(accuracy))
        self.assertTrue(any('num_concurrent' in e for e in errors()))
        template['acceptance']['accuracy_config'] = 'test/Accuracy_test/llm_config.json'
        runtime.write_text(yaml.safe_dump(template))
        self.assertTrue(any('acceptance/' in e for e in errors()))

    def test_failed_execution_cannot_be_hidden_by_passed_sanity(self):
        statuses = {s: 'not_started' for s in workflow.ACCEPTANCE_SUBSTEP_ORDER}
        statuses.update({'execution-mode': 'failed', 'sanity': 'passed'})
        cfg = {'workflow': {'acceptance': {'substeps': statuses}}}
        self.assertTrue(workflow.check_acceptance_dependencies(cfg, ['accuracy']))

    def test_safe_token_arguments_and_real_credentials(self):
        workflow.reject_secret_keys({'max_num_batched_tokens': 4096, 'max_tokens': 100})
        for key in ['ssh_password', 'hf_token', '--api-key', 'ansible_host', 'identity-file']:
            # hf_token is a credential, distinct from token counts.
            self.assertTrue(workflow.sensitive_key(key), key)
        self.assertFalse(workflow.sensitive_key('--max-num-batched-tokens'))

    def test_audit_finds_non_markdown_and_broken_links(self):
        (self.platform / 'adaptation').mkdir()
        script = self.platform / 'adaptation/probe.py'
        script.write_text('print(1)')
        (self.platform / 'README.md').write_text('[missing](missing.md)')
        findings = audit_workspace.audit(self.root)
        self.assertTrue(any('probe.py' in f['path'] for f in findings))
        self.assertTrue(any('missing.md' in f['message'] for f in findings))


if __name__ == '__main__':
    unittest.main()
