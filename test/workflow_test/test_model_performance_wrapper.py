"""Offline Qwen wrapper/finalizer tests; benchmark subprocesses are synthetic."""

import contextlib
import copy
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
MODEL_TOOLS = ROOT / 'models/Qwen3.8-Flash-Next/ppu/acceptance'
PUBLIC_TOOLS = ROOT / 'test/perf_test'
sys.path.insert(0, str(MODEL_TOOLS))
import vllm_perf_qwen38 as wrapper
import finalize_performance as finalizer


def successful_process(command, **kwargs):
    def value(flag):
        return int(command[command.index(flag) + 1])
    count = value('--num-prompts')
    inputs = value('--random-input-len') * count
    outputs = value('--random-output-len') * count
    output = f'''Successful requests: {count}
Benchmark duration (s): 10.0
Total input tokens: {inputs}
Total generated tokens: {outputs}
Request throughput (req/s): {count / 10}
Output token throughput (tok/s): {outputs / 10}
Peak output token throughput (tok/s): {outputs / 8}
Total token throughput (tok/s): {(inputs + outputs) / 10}
Mean TTFT (ms): 10.0
Median TTFT (ms): 9.0
P99 TTFT (ms): 20.0
Mean TPOT (ms): 2.0
Median TPOT (ms): 1.9
P99 TPOT (ms): 3.0
Mean ITL (ms): 2.1
Median ITL (ms): 2.0
P99 ITL (ms): 3.1
'''
    return subprocess.CompletedProcess(command, 0, output, '')


class ModelWrapperTests(unittest.TestCase):
    def test_thin_wrapper_uses_shared_main_and_preserves_exit_code(self):
        main = Mock(return_value=1)
        with patch.object(wrapper, 'load_shared', return_value=SimpleNamespace(main=main)) as load:
            result = wrapper.main(['--tool-dir', '/verified/tools', '--tokenizer', '/models/qwen',
                                   '--max-model-len', '50000', '--output-dir', '/new-results'])
        self.assertEqual(result, 1)
        load.assert_called_once_with('/verified/tools', 'vllm_perf')
        args = main.call_args.args[0]
        self.assertEqual(args[args.index('--model') + 1], wrapper.MODEL)
        self.assertEqual(args[args.index('--port') + 1], '8038')
        self.assertEqual([args[i + 1] for i, arg in enumerate(args) if arg == '--case'],
                         [','.join(map(str, case)) for case in wrapper.DEFAULT_CASES])

    def test_explicit_cases_and_target_do_not_receive_duplicate_defaults(self):
        args = wrapper.benchmark_args(['--port=8040', '--case=1,1,1,1', '--model=diagnostic-model'])
        self.assertNotIn('--case', args)
        self.assertNotIn('--port', args)
        self.assertNotIn('--model', args)

    def test_output_root_must_be_explicit(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit), \
             patch.object(wrapper, 'load_shared') as load:
            wrapper.main(['--tokenizer', '/models/qwen', '--max-model-len', '50000'])
        load.assert_not_called()

    def test_public_argument_validation_still_rejects_missing_budget(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit), \
             patch.object(subprocess, 'run') as run:
            wrapper.main(['--tokenizer', '/models/qwen', '--output-dir', '/unused'])
        run.assert_not_called()

    def test_deployed_bundle_help_has_no_repository_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public = root / 'public'
            public.mkdir()
            for name in ['vllm_perf.py', 'perf_common.py']:
                shutil.copy2(PUBLIC_TOOLS / name, public / name)
            for name in ['vllm_perf_qwen38.py', 'finalize_performance.py']:
                shutil.copy2(MODEL_TOOLS / name, root / name)
                result = subprocess.run([sys.executable, '-B', str(root / name), '--tool-dir', str(public), '--help'],
                                        cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(list(root.rglob('benchmark-result.json'))), 0)


class ModelFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.silence = contextlib.redirect_stdout(io.StringIO())
        self.silence.__enter__()
        self.addCleanup(self.silence.__exit__, None, None, None)
        args = ['--tool-dir', str(PUBLIC_TOOLS), '--tokenizer', '/models/qwen',
                '--max-model-len', '50000', '--output-dir', str(self.root / 'benchmark')]
        with patch.object(subprocess, 'run', side_effect=successful_process):
            self.assertEqual(wrapper.main(args), 0)
        paths = list(self.root.rglob('benchmark-result.json'))
        self.assertEqual(len(paths), 1)
        self.report_path = paths[0]
        self.report = json.loads(self.report_path.read_text())
        request = self.report['request']
        self.evidence = {'schema_version': 1, 'kind': 'performance-service-evidence',
                         'benchmark_report_sha256': finalizer.digest(self.report_path),
                         'service': {key: request[key] for key in
                                     ['model', 'host', 'port', 'endpoint', 'tokenizer', 'max_model_len']},
                         'health_after': {'status': 200, 'observed_at': datetime.now(timezone.utc).isoformat()}}
        self.evidence['service'].update(mode='graph', instance_id='synthetic-instance-1',
                                        deployment_fingerprint='a' * 64)
        self.evidence_path = self.root / 'service-evidence.json'
        self.write_evidence()

    def write_evidence(self):
        self.evidence_path.write_text(json.dumps(self.evidence))

    def write_report(self):
        self.report_path.write_text(json.dumps(self.report))
        self.evidence['benchmark_report_sha256'] = finalizer.digest(self.report_path)
        self.write_evidence()

    def args(self):
        return ['--report', str(self.report_path), '--service-evidence', str(self.evidence_path),
                '--tool-dir', str(PUBLIC_TOOLS)]

    def check(self):
        return finalizer.review(self.report_path, self.evidence_path, str(PUBLIC_TOOLS))

    def test_default_review_is_read_only_and_explicit_output_is_exclusive(self):
        before = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(finalizer.main(self.args()), 0)
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})
        output = self.root / 'new-review.json'
        self.assertEqual(finalizer.main(self.args() + ['--output', str(output)]), 0)
        saved = output.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(finalizer.main(self.args() + ['--output', str(output)]), 2)
        self.assertEqual(output.read_bytes(), saved)

    def test_warmup_failure_cannot_be_hidden_by_run2_run3_success(self):
        self.report['cases'][0]['runs'][0]['returncode'] = 1
        self.write_report()
        with self.assertRaisesRegex(ValueError, 'benchmark contract failed'):
            self.check()

    def test_missing_run_nonfinite_metric_and_context_budget_are_rejected(self):
        original = copy.deepcopy(self.report)
        for mutate in [lambda r: r['cases'][0]['runs'].pop(0),
                       lambda r: r['cases'][0]['runs'][1]['metrics'].update(mean_ttft_ms=float('nan')),
                       lambda r: r['request'].update(max_model_len=100)]:
            self.report = copy.deepcopy(original)
            mutate(self.report)
            self.write_report()
            with self.assertRaisesRegex(ValueError, 'benchmark contract failed'):
                self.check()

    def test_changed_csv_and_stdout_are_rejected(self):
        for descriptor in [self.report['cases'][0]['csv'], self.report['cases'][0]['runs'][0]['stdout']]:
            path = self.report_path.parent / descriptor['path']
            before = path.read_bytes()
            path.write_bytes(before + b'\nchanged\n')
            with self.assertRaisesRegex(ValueError, 'benchmark contract failed'):
                self.check()
            path.write_bytes(before)

    def test_model_cases_and_run_selection_must_match_qwen_baseline(self):
        original = copy.deepcopy(self.report)
        for change in [{'model': 'another-model'}, {'engine': 'sglang'}, {'cases': [[1, 1, 1, 1]]},
                       {'runs': 2}, {'skip_first': 0}]:
            report = copy.deepcopy(original)
            report['request'].update(change)
            self.assertTrue(finalizer.context_errors(report, self.evidence, self.report_path))

    def test_profiled_run_does_not_replace_unprofiled_baseline(self):
        self.report['cases'][0]['runs'][1]['profiled'] = True
        self.assertTrue(finalizer.context_errors(self.report, self.evidence, self.report_path))

    def test_report_changed_during_validation_is_not_reviewed_under_new_hash(self):
        validator = wrapper.load_shared(str(PUBLIC_TOOLS), 'perf_common')
        original = validator.validate_report
        def changed(report, path):
            errors = original(report, path)
            path.write_bytes(path.read_bytes() + b'\n')
            return errors
        with patch.object(validator, 'validate_report', side_effect=changed), \
             patch.object(finalizer, 'load_shared', return_value=validator), self.assertRaises(ValueError):
            self.check()

    def test_graph_instance_health_and_request_binding_are_required(self):
        original = copy.deepcopy(self.evidence)
        for change in [{'mode': 'eager'}, {'instance_id': ''}, {'deployment_fingerprint': ''},
                       {'port': 1}, {'tokenizer': '/other'}, {'max_model_len': 1}]:
            self.evidence = copy.deepcopy(original)
            self.evidence['service'].update(change)
            self.write_evidence()
            with self.assertRaisesRegex(ValueError, 'service/run binding failed'):
                self.check()
        self.evidence = copy.deepcopy(original)
        self.evidence['health_after']['status'] = 503
        self.write_evidence()
        with self.assertRaisesRegex(ValueError, 'service/run binding failed'):
            self.check()

    def test_stale_future_and_unbound_observations_are_rejected(self):
        original = copy.deepcopy(self.evidence)
        for observed in [(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                         (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), '2026-09-01']:
            self.evidence = copy.deepcopy(original)
            self.evidence['health_after']['observed_at'] = observed
            self.write_evidence()
            with self.assertRaisesRegex(ValueError, 'service/run binding failed'):
                self.check()
        self.evidence = copy.deepcopy(original)
        self.evidence['benchmark_report_sha256'] = 'b' * 64
        self.write_evidence()
        with self.assertRaisesRegex(ValueError, 'service/run binding failed'):
            self.check()

    def test_failed_review_writes_no_output_and_legacy_summary_is_not_upgraded(self):
        self.report_path.write_text(json.dumps({'mode': 'graph', 'failed_cases': [], 'csv_files': []}))
        output = self.root / 'must-not-exist.json'
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(finalizer.main(self.args() + ['--output', str(output)]), 2)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
