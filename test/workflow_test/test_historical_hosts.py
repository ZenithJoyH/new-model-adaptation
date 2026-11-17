"""Retired host identities remain auditable without becoming execution targets."""
import copy
import subprocess
import sys
import unittest

import yaml

import test_framework_workspace as fixtures

workflow = fixtures.audit_workspace.workflow
audit_workspace = fixtures.audit_workspace
gate = fixtures.gate


class HistoricalHostAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.FrameworkGateTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root
        for stage in ('architecture', 'environment', 'adaptation', 'device',
                      'operators', 'model-eager', 'summary'):
            self.fixture.bind(stage)
        self.fixture.cfg['status'] = 'functional'
        self.fixture.cfg['workflow']['retrospective']['status'] = 'failed'
        self.config_path = self.fixture.directory / 'framework.yml'
        self.config_path.write_text(yaml.safe_dump(self.fixture.cfg, sort_keys=False))

        # A compact legacy record retains its own failed phase and old Host.
        self.legacy_path = self.root / 'models/Example/ppu/platform.yml'
        legacy = workflow.load_yaml(self.legacy_path)
        self.framework_only_platform = copy.deepcopy(legacy)
        legacy.update(record_layout='compact', status='blocked', validated_hosts=['PPU-01'],
                      target={'hosts': ['PPU-01'], 'container_name': 'test', 'container_image': 'test:local'},
                      workspace=copy.deepcopy(self.fixture.cfg['workspace']))
        legacy['workflow']['environment']['status'] = 'failed'
        self.legacy_path.write_text(yaml.safe_dump(legacy, sort_keys=False))

        (self.root / 'inventory/hosts.yml').write_text(yaml.safe_dump(
            {'all': {'children': {'managed': {'children': {
                'ppu': {'hosts': {'PPU-166': None}},
                'metax': {'hosts': {'mx-57': None}},
            }}}}}))
        self.catalog = {'schema_version': 1, 'platforms': {'ppu': ['PPU-01']}}
        self.save_catalog()

    def save_catalog(self):
        (self.root / 'inventory/historical-hosts.yml').write_text(yaml.safe_dump(self.catalog))

    def model_bytes(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in (self.root / 'models').rglob('*') if p.is_file()}

    def errors(self):
        return [f for f in audit_workspace.audit(self.root) if f['level'] == 'error']

    def framework_errors(self):
        # An invalid legacy record intentionally short-circuits its platform's
        # audit. Use the original framework-only registration to reach its gate.
        before = self.legacy_path.read_bytes()
        try:
            self.legacy_path.write_text(yaml.safe_dump(self.framework_only_platform))
            return self.errors()
        finally:
            self.legacy_path.write_bytes(before)

    def test_retired_records_audit_without_rewriting_results_or_evidence(self):
        before = self.model_bytes()
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.model_bytes(), before)
        self.assertEqual(workflow.load_yaml(self.config_path), self.fixture.cfg)
        self.assertEqual(workflow.load_yaml(self.legacy_path)['workflow']['environment']['status'], 'failed')

    def test_retired_alias_is_still_rejected_by_both_execution_entrypoints(self):
        self.assertEqual(workflow.inventory_platform_hosts(self.root, 'ppu'), {'PPU-166'})
        for framework_args in ([], ['--framework', 'torch-fl']):
            with self.subTest(framework_args=framework_args):
                result = subprocess.run([
                    sys.executable, '-B', str(fixtures.ROOT / 'scripts/adapt_model.py'),
                    '--repo-root', str(self.root), 'Example', '--platform', 'ppu',
                    '--hosts', 'PPU-01', '--steps', 'environment', '--check-only',
                    *framework_args,
                ], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('不属于', result.stdout + result.stderr)

    def test_unregistered_alias_and_wrong_platform_remain_errors(self):
        for platforms in ({}, {'metax': ['PPU-01']}):
            with self.subTest(platforms=platforms):
                self.catalog['platforms'] = platforms
                self.save_catalog()
                messages = [f['message'] for f in self.errors()]
                self.assertTrue(any('validated_hosts' in m for m in messages), messages)
                self.assertTrue(any('compact target.hosts' in m for m in messages), messages)
                self.assertIn('工作区 Host 不属于目标平台',
                              [f['message'] for f in self.framework_errors()])

    def test_missing_catalog_does_not_accept_retired_aliases(self):
        (self.root / 'inventory/historical-hosts.yml').unlink()
        self.assertTrue(any('工作区 Host 不属于目标平台' == f['message'] for f in self.framework_errors()))

    def test_historical_membership_does_not_bypass_receipt_integrity(self):
        f = self.fixture
        self.assertEqual(gate.validate_workspace(
            self.root, f.directory, f.cfg, f.profile, f.mounts, historical_hosts={'PPU-01'}), [])
        (f.remote / 'environment.txt').write_text('tampered result')
        errors = gate.validate_workspace(
            self.root, f.directory, f.cfg, f.profile, f.mounts, historical_hosts={'PPU-01'})
        self.assertTrue(errors)
        self.assertNotIn('工作区 Host 不属于目标平台', errors)

    def test_malformed_catalog_fails_closed(self):
        bad_catalogs = [
            {'schema_version': True, 'platforms': {}},
            {'schema_version': 2, 'platforms': {}},
            {'schema_version': 1, 'platforms': {'other': ['PPU-01']}},
            {'schema_version': 1, 'platforms': {'ppu': 'PPU-01'}},
            {'schema_version': 1, 'platforms': {'ppu': ['PPU-01', 'PPU-01']}},
            {'schema_version': 1, 'platforms': {'ppu': ['PPU-01'], 'metax': ['PPU-01']}},
            {'schema_version': 1, 'platforms': {'ppu': ['-option']}},
            {'schema_version': 1, 'platforms': {'ppu': ['PPU-01']}, 'ansible_host': 'example'},
        ]
        for catalog in bad_catalogs:
            with self.subTest(catalog=catalog):
                self.catalog = catalog
                self.save_catalog()
                errors = self.errors()
                self.assertTrue(errors)
                self.assertEqual({f['path'] for f in errors}, {'inventory/historical-hosts.yml'})


if __name__ == '__main__':
    unittest.main()
