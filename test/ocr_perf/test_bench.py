"""Integration checks with a fake HTTP OCR service; no GPU required."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ocr_bench', Path(__file__).with_name('bench.py'))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class Handler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.calls.append(request)
        mode = request['messages'][0]['content'][1]['text']
        if mode == 'error':
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b'server overloaded')
            return
        data = {'choices': [{'message': {'content': '' if mode == 'empty' else 'recognized'},
                             'finish_reason': 'length' if mode == 'truncate' else 'stop'}],
                'usage': {'completion_tokens': 3, 'prompt_tokens': 20}}
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_failures_truncations_and_empty_pages_remain_in_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'crop.png').write_bytes(b'fake PNG consumed only by fake server')
            Handler.calls = []
            pages = [{'id': str(i), 'blocks': [{'id': 0, 'label': 'text', 'order': 0, 'bbox': [0, 0, 1, 1],
                      'parameters': {'max_tokens': 20}, 'image': 'crop.png', 'prompt': mode,
                      'output_format': 'text'}]} for i, mode in enumerate(('ok', 'truncate', 'empty', 'error'))]
            native = types.SimpleNamespace(postprocess_content=lambda text, fmt, label: text,
                                           has_mixed_inline_formula_content=lambda text: False,
                                           _normalize_and_dedupe_blocks=lambda blocks: blocks,
                                           assemble_markdown=lambda blocks, cfg: '\n'.join(b['content'] for b in blocks))
            scenario = {'name': 'test', 'page_ids': ['0', '1', '2', '3'], 'page_concurrency': 2,
                        'region_concurrency': 2, 'per_page_regions': 4, 'slo_seconds': 30}
            client = bench.Client(f'http://127.0.0.1:{self.server.server_port}', 'same-model', 5)
            result = bench.run_round(root, {'pages': pages, 'prompt_map': {}}, native, client,
                                     scenario, root / 'result', 1)
            self.assertEqual(len(Handler.calls), 4)  # no implicit retry for 503
            self.assertEqual(result['planned_pages'], 4)
            self.assertEqual(result['successful_pages'], 1)
            self.assertEqual(result['failed_requests'], 2)
            self.assertEqual(result['truncated_requests'], 1)
            self.assertEqual(result['slo_success_fraction'], .25)
            self.assertTrue(result['integrity_ok'])
            self.assertFalse(result['operational_pass'])
            self.assertEqual(len((root / 'result/requests.jsonl').read_text().splitlines()), 4)
            self.assertEqual(len(list((root / 'result/pages').glob('*.md'))), 4)
            self.assertTrue(all(p['model'] == 'same-model' for p in Handler.calls))
            self.assertTrue(all(p['max_tokens'] == 20 for p in Handler.calls))

    def test_corrupt_bundle_rejected_before_import_or_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'manifest.json').write_text('{}')
            bench.save(root / 'checksums.json', {'manifest.json': 'incorrect'})
            with self.assertRaisesRegex(ValueError, 'checksum'):
                bench.load_bundle(root)

    def test_full_shape_workload_is_warmed_before_measured_rounds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            evidence = root / 'evidence.json'
            bench.save(evidence, {'endpoint': 'http://127.0.0.1:1', 'prefix_caching': False,
                                 'mm_processor_cache_gb': 0, 'verification': 'fake verified fixture',
                                 'checkpoint_identity_sha256': 'same', 'dtype': 'bfloat16', 'gpu_count': 1})
            scenario = {'name': 'interactive', 'page_ids': ['shape-a', 'shape-b'], 'page_concurrency': 1,
                        'region_concurrency': 4, 'per_page_regions': 4, 'slo_seconds': 30}
            manifest = {'scenarios': [scenario], 'request_timeout_seconds': 1,
                        'checkpoint_identity_sha256': 'same', 'diagnostic_page_ids': ['unrelated-shape']}
            calls = []

            def fake_round(bundle, config, native, client, selected, output, round_index):
                calls.append((round_index, list(selected['page_ids'])))
                return {'scenario': selected['name'], 'round': round_index, 'failed_requests': 0,
                        'truncated_requests': 0, 'successful_pages_per_minute': 10,
                        'integrity_ok': True, 'operational_pass': True}

            args = types.SimpleNamespace(bundle=str(root/'bundle'), dry_run=False,
                                         endpoint='http://127.0.0.1:1', model='fake', label='test',
                                         service_evidence=str(evidence), output=str(root/'results'))
            with patch.object(bench, 'load_bundle', return_value=(root/'bundle', manifest, None, 'hash')), \
                 patch.object(bench, 'health_check', return_value={}), \
                 patch.object(bench, 'run_round', side_effect=fake_round):
                self.assertEqual(bench.execute(args), 0)
            self.assertEqual(calls, [(0, ['shape-a', 'shape-b']), (1, ['shape-a', 'shape-b']),
                                     (2, ['shape-a', 'shape-b'])])


if __name__ == '__main__':
    unittest.main()
