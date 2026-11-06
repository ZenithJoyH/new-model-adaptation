"""Local layout and template-link checks; no model or remote state is changed."""

from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_workspace


class WorkspaceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = self.root / "models/Example"
        self.model.mkdir(parents=True)
        (self.model / "model.yml").write_text("name: Example\n")
        (self.model / "README.md").write_text("# Example\n")
        (self.model / "architecture-and-inference.md").write_text("# Architecture\n")
        (self.model / "_shared").mkdir()
        (self.model / "_shared/README.md").write_text("# Shared\n")

    def test_model_root_rejects_unowned_artifacts_and_unknown_platforms(self):
        self.assertEqual(audit_workspace.audit(self.root), [])
        for name in ("weights.bin", "once.py"):
            (self.model / name).write_text("test artifact\n")
        unknown = self.model / "unowned-platform"
        unknown.mkdir()
        (unknown / "raw.log").write_text("raw output\n")
        findings = audit_workspace.audit(self.root)
        self.assertEqual({item["path"] for item in findings}, {
            "models/Example/weights.bin", "models/Example/once.py",
            "models/Example/unowned-platform",
        })
        self.assertTrue(all(item["level"] == "error" for item in findings))

    def test_wrong_root_entry_types_report_errors_without_crashing(self):
        (self.model / "ppu").write_text("not a platform directory\n")
        (self.model / "README.md").unlink()
        (self.model / "README.md").mkdir()
        findings = audit_workspace.audit(self.root)
        self.assertEqual({item["path"] for item in findings}, {
            "models/Example/ppu", "models/Example/README.md",
        })
        self.assertTrue(all(item["level"] == "error" for item in findings))

    def test_template_links_are_audited_including_underscore_templates(self):
        for name in ("templates/adaptation/plan.md", "framework-profiles/_template/acceptance.md",
                     "models/_template/README.md"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[required guidance](missing.md)\n")
        findings = audit_workspace.audit(self.root)
        self.assertEqual({item["path"] for item in findings}, {
            "templates/adaptation/plan.md", "framework-profiles/_template/acceptance.md",
            "models/_template/README.md",
        })
        self.assertTrue(all("失效的本地 Markdown 链接" in item["message"] for item in findings))

    def test_template_placeholders_and_valid_links_remain_allowed(self):
        template = self.root / "templates/adaptation/plan.md"
        template.parent.mkdir(parents=True)
        template.write_text("[model](../../models/<model>/README.md)\n[guide](guide.md)\n")
        (template.parent / "guide.md").write_text("# Guide\n")
        self.assertEqual(audit_workspace.audit(self.root), [])


if __name__ == "__main__":
    unittest.main()
