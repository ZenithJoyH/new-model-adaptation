"""Offline integration fixtures for the prescribed evaluator and deployment."""

import copy
import json
import pickle
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ACCURACY = ROOT / 'test/Accuracy_test'
sys.path.insert(0, str(ACCURACY))
import llmrun
import llmrun_parallel as parallel
import score_progress as scorer


def formal_config():
    return {'formal_acceptance': True, 'service_mode': 'graph', 'num_concurrent': 32,
            'limit': 0, 'expected_samples': 2, 'allow_timeouts': True,
            'tasks': ['example'],
            'acceptance_criteria': {'example': {'metric': 'exact_match,strict-match', 'minimum': 0.9}}}


def dual_filter_rows():
    # The FlagEval v1 schema observed in the model records: each document has
    # separate strict/flexible rows sharing the original input and response.
    return [{'doc_id': i, 'filter': f, 'doc': {'question': f'question-{i}'},
             'arguments': {'gen_args_0': {'arg_0': [f'prompt-{i}'], 'arg_1': {'temperature': 0}}},
             'target': 'A', 'resps': [['The answer is A.']], 'filtered_resps': ['A'],
             'doc_hash': f'doc-{i}', 'prompt_hash': f'prompt-{i}', 'target_hash': 'target-A',
             'exact_match': 1.0}
            for i in range(2) for f in ['strict-match', 'flexible-extract']]


class SamplesAndCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        logger = patch.object(llmrun, 'log')
        logger.start()
        self.addCleanup(logger.stop)

    def validate(self, rows, cfg=None):
        (self.root / 'samples_example_1.jsonl').write_text('\n'.join(json.dumps(row) for row in rows))
        return llmrun.validate_samples(cfg or formal_config(), 'example', self.root)

    def test_valid_dual_filter_and_legacy_document_schemas(self):
        self.assertTrue(self.validate(dual_filter_rows()))
        self.assertTrue(self.validate([{'doc_id': i, 'resps': [['answer']]} for i in range(2)]))

    def test_formal_timeout_samples_are_retained_as_incorrect(self):
        rows = dual_filter_rows()
        for row in rows:
            if row['doc_id'] == 0:
                row['resps'] = [['<TIMEOUT>']]
                row['filtered_resps'] = ['<TIMEOUT>']
                row['exact_match'] = 0.0
        cfg = formal_config()
        cfg['acceptance_criteria']['example']['minimum'] = 0.5
        self.assertTrue(self.validate(rows, cfg))
        self.assertEqual(llmrun.metric_errors(cfg, 'example', {'exact_match,strict-match': 0.5}), [])
        self.assertTrue(llmrun.metric_errors(cfg, 'example', {'exact_match,strict-match': 0.49}))

    def test_same_filter_duplicates_are_not_deduplicated(self):
        rows = dual_filter_rows()
        rows.append(copy.deepcopy(rows[0]))
        self.assertFalse(self.validate(rows))

    def test_incomplete_or_mixed_filter_coverage_fails(self):
        self.assertFalse(self.validate(dual_filter_rows()[:-1]))
        rows = dual_filter_rows()
        del rows[0]['filter']
        self.assertFalse(self.validate(rows))
        rows = [row for row in dual_filter_rows() if row['filter'] == 'flexible-extract']
        self.assertFalse(self.validate(rows))

    def test_cross_filter_inputs_responses_and_hashes_must_agree(self):
        for field in ['doc', 'arguments', 'target', 'resps', 'doc_hash', 'prompt_hash', 'target_hash']:
            with self.subTest(field=field):
                rows = dual_filter_rows()
                rows[1][field] = [['different response']] if field == 'resps' else 'different'
                self.assertFalse(self.validate(rows))

    def test_cross_filter_rows_without_input_identity_fail(self):
        rows = dual_filter_rows()
        for row in rows:
            del row['arguments']
            del row['prompt_hash']
        self.assertFalse(self.validate(rows))

    def test_bad_ids_unknown_multi_filter_and_failed_response_fail(self):
        for field, value in [('doc_id', ''), ('doc_id', True), ('filter', ''),
                             ('filter', 'unverified-filter'), ('resps', [['']]),
                             ('resps', [['<TIMEOUT>']]), ('error', 'HTTP 500')]:
            with self.subTest(field=field, value=value):
                rows = dual_filter_rows()
                rows[0][field] = value
                self.assertFalse(self.validate(rows))

    def test_nonfinite_input_identity_is_rejected_without_crashing(self):
        rows = dual_filter_rows()
        rows[0]['arguments'] = {'temperature': float('nan')}
        self.assertFalse(self.validate(rows))

    def test_cache_identity_binds_model_config_and_is_stable_within_run(self):
        cfg = {'eval_model': 'label', 'model_name': 'model-A', 'base_url': 'http://localhost/v1/chat/completions',
               'cache_root': str(self.root / 'cache'), 'num_concurrent': 32, 'timeout': 10,
               'api_max_retries': 0, 'model_type': 'openai-chat-completions', 'limit': 0}
        directory = self.root / 'outputs' / 'run-1' / 'example'
        def cache(config):
            cmd = llmrun.build_command(config, 'example', directory)
            return cmd[cmd.index('--use_cache') + 1]
        self.assertEqual(cache(cfg), cache(cfg))
        for change in [{'model_name': 'model-B'}, {'gen_kwargs': 'temperature=1'}, {'service_revision': 'new'}]:
            self.assertNotEqual(cache(cfg), cache({**cfg, **change}))

    def test_new_invocations_never_resume_an_old_cache(self):
        cfg = {'eval_model': 'label', 'run_id': 'same-human-label', 'output_root': str(self.root / 'one')}
        llmrun.create_run_dir(cfg)
        first = cfg['run_nonce']
        other = {**cfg, 'output_root': str(self.root / 'two')}
        llmrun.create_run_dir(other)
        self.assertNotEqual(first, other['run_nonce'])
        self.assertNotEqual(llmrun.cache_identity(cfg, 'example'), llmrun.cache_identity(other, 'example'))


class ParallelIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = {'eval_model': 'model', 'task': 'example', 'run_id': 'run-one',
                    'output_root': str(self.root / 'outputs'), 'cache_root': str(self.root / 'cache'),
                    'api_list': 'model:http://localhost/v1/chat/completions',
                    'services': [('model', 'http://localhost/v1/chat/completions')],
                    'data_parallel_size': 2, 'shards': [0], 'merge_only': False,
                    'limit': 0, 'expected_samples': 2, 'allow_timeouts': True,
                    'num_concurrent': 32, 'timeout': 10, 'api_max_retries': 0,
                    'eval_max_retries': 1, 'retry_delay': 0, 'progress_interval': 0,
                    'progress_score_interval': 0}
        for module in (parallel, llmrun):
            logger = patch.object(module, 'log')
            logger.start()
            self.addCleanup(logger.stop)

    def shard(self, shard, doc_id=None):
        directory = parallel.output_base(self.cfg) / f'shard-{shard}' / 'attempt-1' / 'model'
        directory.mkdir(parents=True)
        (directory / 'results_1.json').write_text(json.dumps({'results': {'example': {'acc': 1.0}}}))
        (directory / 'samples_example_1.jsonl').write_text(json.dumps(
            {'doc_id': shard if doc_id is None else doc_id, 'resps': [['answer']]}))
        parallel.write_shard_receipt(self.cfg, shard, directory)
        return directory

    def test_run_ids_have_separate_output_roots(self):
        self.assertNotEqual(parallel.output_base(self.cfg), parallel.output_base({**self.cfg, 'run_id': 'run-two'}))

    def test_manifest_is_immutable_but_allows_other_shard_selection(self):
        parallel.initialize_run(self.cfg)
        path = parallel.output_base(self.cfg) / 'effective_config.json'
        before = path.read_bytes()
        parallel.initialize_run({**self.cfg, 'shards': [1]})
        self.assertEqual(path.read_bytes(), before)
        with self.assertRaises(SystemExit):
            parallel.initialize_run({**self.cfg, 'num_concurrent': 64})

    def test_unmanifested_history_and_missing_merge_run_fail_closed(self):
        parallel.output_base(self.cfg).mkdir(parents=True)
        with self.assertRaises(SystemExit):
            parallel.initialize_run(self.cfg)
        with self.assertRaises(SystemExit):
            parallel.initialize_run({**self.cfg, 'merge_only': True, 'run_id': 'missing'})

    def test_merge_only_requires_explicit_id_and_formal_parallel_is_rejected(self):
        config = self.root / 'parallel.json'
        for change in [{'merge_only': True, 'run_id': 'auto'}, {'formal_acceptance': True}]:
            config.write_text(json.dumps({**self.cfg, **change}))
            with self.assertRaises(SystemExit):
                parallel.load_config(config)

    def test_merge_uses_receipts_and_ignores_unlisted_old_files(self):
        parallel.initialize_run(self.cfg)
        dirs = [self.shard(i) for i in range(2)]
        old = parallel.output_base(self.cfg) / 'old-run'
        old.mkdir()
        (old / 'results_old.json').write_text('{}')
        with patch.object(parallel, 'run_streaming', return_value=0) as run:
            self.assertTrue(parallel.merge_results(self.cfg))
            merged_dirs = run.call_args.args[0][2].split(',')
            self.assertEqual(merged_dirs, [str(path.resolve()) for path in dirs])
        # Current merge wrote no result: old result files cannot rescue it.
        self.assertFalse(parallel.report_merged_result(self.cfg))

    def test_missing_tampered_and_overlapping_shards_reject_merge(self):
        parallel.initialize_run(self.cfg)
        first = self.shard(0)
        with patch.object(parallel, 'run_streaming') as run:
            self.assertFalse(parallel.merge_results(self.cfg))
            run.assert_not_called()
        second = self.shard(1, doc_id=0)
        self.assertFalse(parallel.merge_results(self.cfg))
        (second / 'samples_example_1.jsonl').write_text(json.dumps({'doc_id': 1, 'resps': [['answer']]}))
        self.assertFalse(parallel.merge_results(self.cfg))

    def test_retry_cannot_reuse_previous_attempt_results(self):
        parallel.initialize_run(self.cfg)
        attempts = []
        def process(command, *args):
            out = Path(command[command.index('--output_path') + 1])
            attempts.append(out)
            if len(attempts) == 1:
                (out / 'results_1.json').write_text(json.dumps({'results': {'example': {'acc': 1.0}}}))
                (out / 'samples_example_1.jsonl').write_text(json.dumps({'doc_id': 0, 'resps': [['answer']]}))
                return 1
            return 0
        with patch.object(parallel, 'run_streaming', side_effect=process), \
             patch.object(parallel, 'probe_service', return_value=(True, 'ok')):
            self.assertFalse(parallel.run_shard(self.cfg, 0, 'model', 'http://localhost/v1/chat/completions'))
        self.assertEqual([path.name for path in attempts], ['attempt-1', 'attempt-2'])
        self.assertFalse((parallel.output_base(self.cfg) / 'shard-0/shard-result.json').exists())

    def test_existing_shard_directory_is_never_overwritten(self):
        parallel.initialize_run(self.cfg)
        self.shard(0)
        with self.assertRaises(FileExistsError), patch.object(parallel, 'run_streaming') as run:
            parallel.run_shard(self.cfg, 0, 'model', 'http://localhost/v1/chat/completions')
        run.assert_not_called()


class ProgressSchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'responses.db'

    def scores(self, keys, answer_map):
        with sqlite3.connect(self.db) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS unnamed (key TEXT PRIMARY KEY, value BLOB)')
            for key in keys:
                conn.execute('INSERT INTO unnamed VALUES (?, ?)', (key, pickle.dumps('The answer is A.')))
        return scorer.read_scores(self.db, answer_map)

    def test_verified_top_k_encodings_match_without_changing_requests(self):
        kwargs = scorer.generation_kwargs('top_k=-1')
        before = copy.deepcopy(kwargs)
        keys = scorer.cache_keys('prompt', kwargs)
        self.assertEqual(len(keys), 2)
        self.assertEqual(kwargs, before)
        info = {'doc_id': 0, 'target': 'A', 'choices': ['one', 'two']}
        stats = self.scores([keys[1]], {key: info for key in keys})
        self.assertEqual(stats['matched'], 1)
        self.assertEqual(stats['strict'], 1)
        self.assertNotIn('UNAVAILABLE', scorer.format_score(stats, 1))

    def test_unknown_cache_keys_are_unavailable_not_zero_accuracy(self):
        stats = self.scores(['unknown'], {})
        message = scorer.format_score(stats, 198)
        self.assertIn('UNAVAILABLE', message)
        self.assertNotIn('0.00%', message)

    def test_two_encodings_for_one_doc_are_not_double_counted(self):
        keys = scorer.cache_keys('prompt', {'top_k': -1})
        info = {'doc_id': 0, 'target': 'A', 'choices': ['one', 'two']}
        stats = self.scores(keys, {key: info for key in keys})
        self.assertEqual(stats['matched'], 1)
        self.assertEqual(stats['duplicate_docs'], 1)
        self.assertIn('UNAVAILABLE', scorer.format_score(stats, 1))

    def test_no_responses_is_pending_and_unknown_schema_rejected(self):
        self.assertIn('PENDING', scorer.format_score(scorer.read_scores(self.db, {}), 198))
        with self.assertRaises(ValueError):
            scorer.build_answer_map({'task': 'gpqa_diamond_generative_cot', 'progress_score_cache_schema': 'unknown'})


if __name__ == '__main__':
    unittest.main()
