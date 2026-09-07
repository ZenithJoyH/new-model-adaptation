"""Model-specific score helpers cannot overwrite the shared formal receipt."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'models/GLM-5.3-Flash-BF16/ppu/acceptance/grade_gpqa.py'
spec = importlib.util.spec_from_file_location('glm_score_review', SCRIPT)
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)


class ModelScoreReviewTests(unittest.TestCase):
    def setUp(self):
        self.cfg = {'tasks': ['example'], 'expected_samples': 2, 'acceptance_metric': 'strict',
                    'acceptance_threshold': 0.88, 'eval_model': 'example-model', 'run_id': 'one-run'}
        self.result = {'results': {'example': {'strict': 1.0}}}
        self.samples = [{'doc_id': 0}, {'doc_id': 1}]

    def test_review_is_explicitly_nonformal(self):
        summary = grade.judge(self.cfg, self.result, self.samples)
        self.assertTrue(summary['passed'])
        self.assertEqual(summary['kind'], 'model-accuracy-review')
        self.assertFalse(summary['formal_acceptance'])

    def test_duplicate_rows_and_out_of_range_scores_fail(self):
        self.assertFalse(grade.judge(self.cfg, self.result, self.samples + self.samples[:1])['passed'])
        for score in (1.1, float('nan'), float('inf'), -0.1):
            self.result['results']['example']['strict'] = score
            with self.subTest(score=score):
                self.assertFalse(grade.judge(self.cfg, self.result, self.samples)['passed'])

    def test_formal_receipt_and_prior_review_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.cfg['output_root'] = str(root / 'outputs')
            results = root / 'outputs/example-model/one-run/example'
            results.mkdir(parents=True)
            (results / 'results_fixture.json').write_text(json.dumps(self.result))
            (results / 'samples_example_fixture.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in self.samples))
            config = root / 'config.json'
            config.write_text(json.dumps(self.cfg))
            formal = root / 'acceptance-result.json'
            formal.write_bytes(b'formal receipt owned by shared runner\n')
            with patch('sys.argv', [str(SCRIPT), str(config)]), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    grade.main()
                self.assertEqual(result.exception.code, 0)
                review = root / 'gpqa-score-review.json'
                before = review.read_bytes()
                with self.assertRaises(FileExistsError):
                    grade.main()
            self.assertEqual(review.read_bytes(), before)
            self.assertEqual(formal.read_bytes(), b'formal receipt owned by shared runner\n')


if __name__ == '__main__':
    unittest.main()
