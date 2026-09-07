"""Offline tests using self-created trusted SQLite/pickle fixtures only."""

import contextlib
import importlib.util
import io
from pathlib import Path
import pickle
import sqlite3
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "models/Hy4-preview/ppu/acceptance/prepare-gpqa-valid-cache-only.py"
spec = importlib.util.spec_from_file_location("hy4_cache_publication", SCRIPT)
cache = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cache)


class CachePublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source?#.sqlite"
        self.target = self.root / "filtered.sqlite"
        with sqlite3.connect(self.source) as connection:
            connection.execute("CREATE TABLE unnamed (key TEXT PRIMARY KEY, value BLOB)")
            connection.executemany("INSERT INTO unnamed VALUES (?, ?)",
                [("valid", pickle.dumps(("answer",))), ("none", pickle.dumps(None))])
        self.original = self.source.read_bytes()

    def invoke(self, *extra):
        argv = [str(SCRIPT), "--source", str(self.source), "--target", str(self.target),
                "--expected-total", "2", "--expected-invalid", "1", *extra]
        with patch("sys.argv", argv), contextlib.redirect_stdout(io.StringIO()):
            cache.main()

    def test_valid_cache_is_exclusively_published_and_source_unchanged(self):
        self.invoke()
        with sqlite3.connect(self.target) as connection:
            self.assertEqual(cache.classify(connection), (["valid"], []))
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(set(self.root.iterdir()), {self.source, self.target})

    def test_existing_target_and_dangling_symlink_are_not_replaced(self):
        self.target.write_bytes(b"other result")
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertEqual(self.target.read_bytes(), b"other result")
        self.target.unlink()
        self.target.symlink_to(self.root / "missing")
        with self.assertRaises(SystemExit):
            self.invoke()
        self.assertTrue(self.target.is_symlink())
        self.assertFalse((self.root / "missing").exists())

    def test_concurrent_publisher_cannot_be_overwritten(self):
        link = cache.os.link

        def another_writer_publishes_first(source, target):
            target.write_bytes(b"concurrent owner")
            return link(source, target)

        with patch.object(cache.os, "link", side_effect=another_writer_publishes_first), \
                self.assertRaises(FileExistsError):
            self.invoke()
        self.assertEqual(self.target.read_bytes(), b"concurrent owner")
        self.assertEqual(set(self.root.iterdir()), {self.source, self.target})

    def test_unavailable_atomic_publication_fails_without_result(self):
        with patch.object(cache.os, "link", side_effect=OSError("unsupported")), self.assertRaises(OSError):
            self.invoke()
        self.assertEqual(set(self.root.iterdir()), {self.source})
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_failed_validation_does_not_create_target(self):
        with self.assertRaises(SystemExit):
            self.invoke("--expected-invalid", "0")
        self.assertEqual(set(self.root.iterdir()), {self.source})

    def test_foreign_predictable_temporary_file_is_untouched(self):
        foreign = self.target.with_suffix(".sqlite.tmp")
        foreign.write_bytes(b"another owner")
        self.invoke()
        self.assertEqual(foreign.read_bytes(), b"another owner")
        self.assertEqual(set(self.root.iterdir()), {self.source, self.target, foreign})


if __name__ == "__main__":
    unittest.main()
