import copy
import json
from pathlib import Path
import sys
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_gates as gates
import skill_bundle
import test_framework_workspace as fixture


class NativeAdapterTests(unittest.TestCase):
    def test_real_framework_prerequisites_and_completion_are_distinct(self):
        f = fixture.FrameworkGateTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        for stage in ('architecture', 'environment'): f.bind(stage)
        path = f.directory / 'framework.yml'
        path.write_text(yaml.safe_dump(f.cfg, sort_keys=False))
        check = dict(kind='framework', model='Example', platform='ppu', framework='torch-fl',
                     hosts=['PPU-01'], steps=['adaptation'], artifact_roots=f.mounts, verify_records=False)
        scope = {k: check[k] for k in ('model', 'platform', 'framework', 'hosts')}
        self.assertEqual(gates.run_check(f.root, check, scope)['status'], 'passed')
        check['verify_records'] = True
        with self.assertRaises(ValueError): gates.run_check(f.root, check, scope)
        f.bind('adaptation')
        path.write_text(yaml.safe_dump(f.cfg, sort_keys=False))
        self.assertEqual(gates.run_check(f.root, check, scope)['status'], 'passed')
        with self.assertRaisesRegex(ValueError, 'run_id'):
            gates.run_check(f.root, check, scope, expected_run_id='another-run')
        (f.remote / 'adaptation.txt').write_text('changed')
        with self.assertRaises(ValueError): gates.run_check(f.root, check, scope)

    def test_plan_cannot_complete_an_unrelated_step_or_host(self):
        before = dict(kind='framework', model='Example', platform='ppu', framework='vllm-plugin-fl',
                      hosts=['PPU-01'], steps=['acceptance'], acceptance_substeps=['performance'],
                      artifact_roots={'PPU-01': '/approved'}, verify_records=False)
        spec = dict(capability_id='adaptation/performance', selection='single-scenario',
                    scope={k: before[k] for k in ('model', 'platform', 'framework', 'hosts')},
                    before=[before], after=[dict(before, verify_records=True)])
        gates.validate_plan(spec)
        bad = copy.deepcopy(spec); bad['after'][0]['verify_records'] = False
        with self.assertRaises(ValueError): gates.validate_plan(bad)
        bad = copy.deepcopy(spec); bad['scope']['hosts'] = ['PPU-02']
        with self.assertRaises(ValueError): gates.validate_plan(bad)
        bad = copy.deepcopy(spec); bad['capability_id'] = 'adaptation/accuracy'; bad['selection'] = 'formal-full'
        with self.assertRaises(ValueError): gates.validate_plan(bad)

    def test_project_interface_version_and_contract_are_enforced(self):
        root = ROOT / 'skills/inference-accuracy-evaluation'
        bundle = skill_bundle.inspect_bundle(root)
        expected = gates.interface_requirements('adaptation/accuracy')
        skill_bundle.validate_selection(bundle, 'formal-full', 'adaptation/accuracy',
            expected_version=expected['interface_version'], expected_contract=expected['result_contract'])
        changed = copy.deepcopy(bundle)
        changed['interface']['interface_version'] = '999.0.0'
        with self.assertRaisesRegex(ValueError, 'interface version'):
            skill_bundle.validate_selection(changed, 'formal-full', 'adaptation/accuracy',
                expected_version=expected['interface_version'], expected_contract=expected['result_contract'])
        changed = copy.deepcopy(bundle)
        changed['interface']['result_contract'] = 'another/v999'
        with self.assertRaisesRegex(ValueError, 'result contract'):
            skill_bundle.validate_selection(changed, 'formal-full', 'adaptation/accuracy',
                expected_version=expected['interface_version'], expected_contract=expected['result_contract'])

    def test_native_validator_sources_are_frozen(self):
        paths = {str(path.relative_to(ROOT)) for path in gates.source_files(ROOT)}
        self.assertTrue({
            'test/Accuracy_test/llmrun.py',
            'test/Accuracy_test/acceptance_contract.py',
            'test/perf_test/perf_common.py',
            'test/perf_test/perf_acceptance.py',
        } <= paths)

    def test_begin_inputs_bind_frozen_request_and_stable_deployment(self):
        f = fixture.FrameworkGateTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        request = {'model': 'Example', 'cases': [[1024, 1024, 32, 64]]}
        manifest = f.remote / 'request.json'
        manifest.write_text(json.dumps(request))
        f.cfg['acceptance_plan']['performance_request_sha256'] = fixture.gate.canonical(request)
        path = f.directory / 'framework.yml'
        path.write_text(yaml.safe_dump(f.cfg, sort_keys=False))
        check = dict(kind='framework', model='Example', platform='ppu', framework='torch-fl',
                     hosts=['PPU-01'], steps=['acceptance'], acceptance_substeps=['performance'],
                     artifact_roots=f.mounts, verify_records=False)
        spec = {'before': [check]}
        context = {str(manifest): fixture.gate.digest(manifest)}
        gates.validate_frozen_inputs(f.root, spec, context)
        binding = gates.acceptance_binding(f.root, spec)
        f.cfg['workflow']['architecture']['status'] = 'in_progress'
        path.write_text(yaml.safe_dump(f.cfg, sort_keys=False))
        self.assertEqual(gates.acceptance_binding(f.root, spec), binding)
        f.cfg['deployment']['fingerprint'] = 'b' * 64
        path.write_text(yaml.safe_dump(f.cfg, sort_keys=False))
        self.assertNotEqual(gates.acceptance_binding(f.root, spec), binding)
        manifest.write_text(json.dumps({'model': 'other'}))
        with self.assertRaisesRegex(ValueError, 'performance request'):
            gates.validate_frozen_inputs(f.root, spec, {str(manifest): fixture.gate.digest(manifest)})
