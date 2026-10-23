"""Human handoff and v2 evidence regressions. All data and services are synthetic."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'test/Accuracy_test'), str(ROOT / 'test/perf_test')]
import framework_evidence as gate
import framework_workspace as workspace
import workspace_control as control
import evidence_contract as contract
import project_gates
import sanity
import delivery_manifest
from acceptance_contract import validate_formal_config
from test_evidence_and_acceptance import formal_config, llmrun
import test_framework_workspace as fixtures


class ModernFixture(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.FrameworkGateTests(); self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.cfg = self.f.cfg
        workspace.pin_profile(self.cfg, self.f.profile)
        self.f.cfg = self.cfg
        self.reader = gate.Artifacts(self.cfg, 'PPU-01', self.f.mounts)

    def ref(self, path):
        return {'path': str(path.relative_to(self.f.remote)), 'sha256': gate.digest(path)}

    def raw(self, name, value):
        path = self.f.remote / name
        path.write_text(json.dumps(value))
        return self.ref(path)

    def handoff(self):
        control.transition(self.f.directory, self.cfg, 'handoff', actor='operator',
                           note='检查环境；已有评测任务保持运行', root=self.f.root)

    def binding(self, run_id='accuracy-run'):
        identity = {'container_id':'c'*64, 'boot_id':'12345678-abcd-1234-abcd-123456789abc',
                    'start_ticks':123, 'cmdline_sha256':'d'*64}
        observation = {'run_id':run_id, 'host_alias':'PPU-01', 'status':'verified', 'pid':123,
                       'service_instance_id':'service-A', 'nonce':'a'*64, 'listening_port':8000,
                       'process_identity':identity}
        return {'service_instance_id':'service-A', 'host_alias':'PPU-01',
                'deployment_fingerprint':self.cfg['deployment']['fingerprint'],
                'endpoint':'http://127.0.0.1:8000/v1/chat/completions',
                'observation':self.raw('observation.json',observation), 'process_identity':identity}


class HumanControlTests(ModernFixture):
    def test_removing_optional_step_requires_declared_change_and_rechecks_summary(self):
        steps = self.cfg['workflow']['acceptance']['substeps']
        self.cfg['workflow']['acceptance']['substeps'] = {
            name: steps.get(name, 'not_started') for name in self.f.profile['acceptance']['steps']}
        for stage in ('architecture', 'environment', 'adaptation', 'device', 'operators',
                      'model-eager', 'wheel', 'summary'):
            self.f.bind(stage)
        self.handoff()
        del self.cfg['workflow']['acceptance']['substeps']['wheel']
        with self.assertRaisesRegex(ValueError, '不能声明 none'):
            control.transition(self.f.directory, self.cfg, 'resume', actor='agent', note='resume',
                               changes=['none'], root=self.f.root)
        proof = self.f.remote/'change.txt'; proof.write_text('Remove optional wheel from this scope')
        control.transition(self.f.directory, self.cfg, 'resume', actor='agent', note='调整验收范围',
                           changes=['plan'], evidence=str(proof), root=self.f.root)
        event = self.cfg['control']['history'][-1]
        self.assertEqual(event['revalidate'], ['summary', 'acceptance', 'retrospective'])
        self.assertEqual(event['removed_steps']['wheel']['status'], 'passed')
        self.assertNotIn('wheel', self.cfg['workflow']['acceptance']['records'])
        self.assertEqual(self.cfg['workflow']['acceptance']['substeps']['model-eager'], 'passed')

    def test_resume_rejects_removing_required_step(self):
        self.handoff()
        del self.cfg['workflow']['acceptance']['substeps']['operators']
        with self.assertRaisesRegex(ValueError, '必需验收子步骤'):
            control.transition(self.f.directory, self.cfg, 'resume', actor='agent', note='resume',
                               changes=['documentation'], root=self.f.root)
        self.assertEqual(self.cfg['control']['mode'], 'human')

    def test_optional_step_addition_rechecks_only_new_step_and_downstream(self):
        self.handoff()
        steps = self.cfg['workflow']['acceptance']['substeps']
        self.cfg['workflow']['acceptance']['substeps'] = {
            name: steps.get(name, 'not_started') for name in self.f.profile['acceptance']['steps']}
        proof = self.f.remote/'change.txt'; proof.write_text('Add wheel validation')
        control.transition(self.f.directory, self.cfg, 'resume', actor='agent', note='增加 wheel',
                           changes=['plan'], evidence=str(proof), root=self.f.root)
        self.assertEqual(self.cfg['control']['history'][-1]['revalidate'],
                         ['wheel', 'summary', 'acceptance', 'retrospective'])

    def test_resume_rejects_reordered_steps(self):
        self.handoff()
        steps = self.cfg['workflow']['acceptance']['substeps']
        self.cfg['workflow']['acceptance']['substeps'] = dict(reversed(list(steps.items())))
        with self.assertRaisesRegex(ValueError, '顺序必须按 profile'):
            control.transition(self.f.directory, self.cfg, 'resume', actor='agent', note='resume',
                               changes=['documentation'], root=self.f.root)

    def test_no_change_handoff_preserves_pass_and_blocks_agent(self):
        self.f.bind('architecture')
        original = copy.deepcopy(self.cfg['workflow'])
        self.handoff()
        with self.assertRaisesRegex(ValueError, '人工接管'):
            workspace.require_agent_control(self.cfg)
        control.transition(self.f.directory, self.cfg, 'resume', actor='agent', note='只读检查完成',
                           changes=['none'], root=self.f.root)
        self.assertEqual(self.cfg['workflow'], original)
        gate.verify_record(self.f.root,self.f.directory,self.cfg,self.f.profile,'architecture')
        workspace.require_agent_control(self.cfg)

    def test_environment_change_retires_downstream_and_preserves_architecture(self):
        for stage in ('architecture','environment','adaptation'):
            self.f.bind(stage)
        previous = copy.deepcopy(self.cfg['workflow']['environment']['verification'])
        self.handoff()
        control.transition(self.f.directory, self.cfg, 'resume', actor='agent', note='人工安装组件已记录',
                           changes=['code'], evidence=str(self.f.remote/'environment.txt'), root=self.f.root)
        self.assertEqual(self.cfg['workflow']['architecture']['status'],'passed')
        self.assertEqual(self.cfg['workflow']['environment']['status'],'not_started')
        event=self.cfg['control']['history'][-1]
        self.assertEqual(event['retired_records']['environment']['verification'],previous)
        self.assertEqual(self.cfg['status'],'blocked')

    def test_false_no_change_and_missing_proof_are_rejected(self):
        self.handoff()
        self.cfg['deployment']['fingerprint']='b'*64
        with self.assertRaisesRegex(ValueError,'不能声明 none'):
            control.transition(self.f.directory,self.cfg,'resume',actor='agent',note='resume',changes=['none'],root=self.f.root)
        with self.assertRaisesRegex(ValueError,'--evidence'):
            control.transition(self.f.directory,self.cfg,'resume',actor='agent',note='resume',changes=['code'],root=self.f.root)
        self.assertEqual(self.cfg['control']['mode'],'human')

    def test_performance_plan_edit_only_invalidates_performance_onward(self):
        profile = workspace.resolved_profile(self.f.root, 'vllm-plugin-fl')[1]
        self.cfg.update(framework='vllm-plugin-fl', profile='framework-profiles/vllm-plugin-fl/profile.yml')
        workspace.pin_profile(self.cfg, profile)
        self.cfg['workflow']['acceptance']['substeps'] = {
            name: 'not_started' for name in profile['acceptance']['steps']}
        self.handoff()
        self.cfg['acceptance_plan']['performance_targets']={'cases':[{'case':[1,1,1,1]}]}
        proof=self.f.remote/'change.txt'; proof.write_text('changed throughput target')
        control.transition(self.f.directory,self.cfg,'resume',actor='agent',note='新目标',changes=['plan'],
                           evidence=str(proof),root=self.f.root)
        self.assertEqual(self.cfg['control']['history'][-1]['revalidate'],['performance','evidence','summary','acceptance','retrospective'])

    def test_cli_roundtrip_and_upgrade_keeps_human_ownership(self):
        path=self.f.directory/'framework.yml'; path.write_text(yaml.safe_dump(self.cfg,sort_keys=False))
        base=[sys.executable,str(ROOT/'scripts/workspace_control.py')]
        tail=['Example','--repo-root',str(self.f.root),'--platform','ppu','--framework','torch-fl']
        for operation, extra in [('handoff',[]),('upgrade',[]),('resume',['--change','none'])]:
            result=subprocess.run([*base,operation,*tail,'--actor','operator','--note','controlled transition',*extra],
                                  capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['mode'],'agent' if operation=='resume' else 'human')
        cfg=workspace.load_yaml(path)
        self.assertEqual(len(cfg['control']['history']),3)
        self.assertIn('previous_contract',cfg['control']['history'][1])

    def test_legacy_upgrade_preserves_history_and_requires_revalidation(self):
        self.f.bind('architecture')
        for k in ('evidence_contract','profile_snapshot','profile_sha256'): self.cfg.pop(k)
        self.handoff()
        control.transition(self.f.directory,self.cfg,'upgrade',actor='operator',note='显式升级',root=self.f.root)
        self.assertEqual(self.cfg['evidence_contract'],2)
        self.assertEqual(self.cfg['workflow']['architecture']['status'],'not_started')
        self.assertEqual(self.cfg['control']['history'][-1]['retired_records']['architecture']['status'],'passed')

    def test_handoff_gates_journal_even_when_outputs_are_being_verified(self):
        self.handoff()
        (self.f.directory/'framework.yml').write_text(yaml.safe_dump(self.cfg))
        spec={'before':[{'kind':'framework','model':'Example','platform':'ppu','framework':'torch-fl'}]}
        with self.assertRaisesRegex(ValueError,'人工接管'):
            project_gates.require_agent_available(self.f.root,spec)

    def test_verified_human_result_is_adopted_without_rerunning_the_stage(self):
        self.f.bind('architecture')
        self.handoff()
        rec=self.f.bind('environment')
        path=self.f.remote/'environment.json'; report=json.loads(path.read_text())
        report['producer']={'kind':'human','name':'operator'}
        report['check_results']={'environment_identity':{'status':'passed','method':'review',
            'note':'人工核对容器与已安装组件','evidence':report['artifacts']}}
        path.write_text(json.dumps(report)); rec['receipts'][0]['sha256']=gate.digest(path)
        control.transition(self.f.directory,self.cfg,'resume',actor='agent',note='接纳人工环境验证',
                           changes=['evidence'],evidence=str(self.f.remote/'environment.txt'),
                           mounts=self.f.mounts,root=self.f.root)
        self.assertEqual(self.cfg['workflow']['environment']['status'],'passed')
        self.assertEqual(self.cfg['workflow']['environment']['verification']['run_id'],'environment-run')
        self.assertIn('environment',self.cfg['control']['history'][-1]['accepted_manual_results'])
        gate.verify_record(self.f.root,self.f.directory,self.cfg,self.f.profile,'environment',self.f.mounts)

    def test_relabelled_old_manual_result_is_not_adopted(self):
        for stage in ('architecture','environment'): self.f.bind(stage)
        self.handoff()
        control.transition(self.f.directory,self.cfg,'resume',actor='agent',note='环境有变更',
                           changes=['environment','evidence'],evidence=str(self.f.remote/'environment.txt'),
                           mounts=self.f.mounts,root=self.f.root)
        self.assertEqual(self.cfg['workflow']['environment']['status'],'not_started')
        self.assertIn('接管前',self.cfg['control']['history'][-1]['unaccepted_manual_results']['environment'])


class PinnedContractTests(ModernFixture):
    def test_pinned_contract_binds_acceptance_order(self):
        self.cfg['profile_snapshot']['acceptance']['steps'] = dict(
            reversed(list(self.cfg['profile_snapshot']['acceptance']['steps'].items())))
        with self.assertRaisesRegex(ValueError, 'pinned profile identity'):
            workspace.workspace_profile(self.f.root, self.cfg)

    def test_order_changes_non_architecture_context_but_editorial_fields_do_not(self):
        profile = copy.deepcopy(self.f.profile)
        before = gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'environment')
        architecture = gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'architecture')
        profile['display_name'] = 'Editorial change'
        profile['documents']['workflow'] = 'renamed.md'
        self.assertEqual(before, gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'environment'))
        profile['acceptance']['steps'] = dict(reversed(list(profile['acceptance']['steps'].items())))
        self.cfg['workflow']['acceptance']['substeps'] = {
            name: 'not_started' for name, spec in profile['acceptance']['steps'].items() if not spec.get('optional')}
        self.assertNotEqual(before, gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'environment'))
        self.assertEqual(architecture, gate.context_hash(self.f.root, self.f.directory, self.cfg, profile, 'architecture'))

    def test_old_v2_hash_is_preserved_until_explicit_upgrade(self):
        self.cfg.pop('profile_hash_version', None)
        self.cfg['profile_sha256'] = workspace.contract_digest(workspace.profile_contract(self.f.profile))
        self.f.bind('architecture')
        self.assertEqual(workspace.workspace_profile(self.f.root, self.cfg), self.f.profile)
        before = gate.context_hash(self.f.root, self.f.directory, self.cfg, self.f.profile, 'environment')
        self.handoff()
        control.transition(self.f.directory, self.cfg, 'upgrade', actor='operator',
                           note='显式固定验收顺序', root=self.f.root)
        self.assertEqual(self.cfg['profile_hash_version'], 2)
        self.assertNotEqual(before, gate.context_hash(self.f.root, self.f.directory,
                                                    self.cfg, self.f.profile, 'environment'))
        self.assertEqual(self.cfg['workflow']['architecture']['status'], 'passed')

    def test_current_profile_order_change_is_reported_by_audit(self):
        import audit_workspace
        path = self.f.root/self.cfg['profile']
        profile = workspace.load_yaml(path)
        profile['acceptance']['steps'] = dict(reversed(list(profile['acceptance']['steps'].items())))
        path.write_text(yaml.safe_dump(profile, sort_keys=False))
        (self.f.directory/'framework.yml').write_text(yaml.safe_dump(self.cfg, sort_keys=False))
        findings = audit_workspace.audit(self.f.root)
        self.assertTrue(any('profile 已更新' in item['message'] for item in findings), findings)

    def test_editorial_changes_do_not_invalidate_evidence(self):
        self.f.bind('architecture')
        path=self.f.root/self.cfg['profile']; doc=path.parent/'workflow.md'
        doc.write_text(doc.read_text()+'\n<!-- spelling correction -->\n')
        gate.verify_record(self.f.root,self.f.directory,self.cfg,self.f.profile,'architecture')

    def test_profile_update_does_not_silently_upgrade_current_workspace(self):
        self.f.bind('architecture')
        path=self.f.root/self.cfg['profile']; current=workspace.load_yaml(path)
        current['profile_version']+=1
        path.write_text(yaml.safe_dump(current))
        pinned=workspace.workspace_profile(self.f.root,self.cfg)
        self.assertEqual(pinned['profile_version'],self.cfg['profile_version'])
        self.assertEqual(gate.validate_workspace(self.f.root,self.f.directory,self.cfg,current),[])
        self.cfg['profile_snapshot']['execution_modes']['required'].append('other')
        with self.assertRaisesRegex(ValueError,'pinned profile'):
            workspace.workspace_profile(self.f.root,self.cfg)

    def test_performance_target_change_keeps_accuracy_context(self):
        profile=workspace.resolved_profile(self.f.root,'vllm-plugin-fl')[1]
        self.cfg['workflow']['acceptance']['substeps']={name:'not_started' for name,spec in profile['acceptance']['steps'].items() if not spec.get('optional')}
        before=gate.context_hash(self.f.root,self.f.directory,self.cfg,profile,'accuracy')
        self.cfg['acceptance_plan']['performance_targets']={'cases':[]}
        self.assertEqual(before,gate.context_hash(self.f.root,self.f.directory,self.cfg,profile,'accuracy'))
        self.cfg['deployment']['fingerprint']='b'*64
        self.assertNotEqual(before,gate.context_hash(self.f.root,self.f.directory,self.cfg,profile,'accuracy'))

    def test_accuracy_journal_does_not_freeze_later_performance_targets(self):
        path=self.f.directory/'framework.yml'
        spec={'before':[{'model':'Example','platform':'ppu','framework':'torch-fl','acceptance_substeps':['accuracy']}]}
        path.write_text(yaml.safe_dump(self.cfg))
        original=project_gates.acceptance_binding(self.f.root,spec)
        self.cfg['acceptance_plan']['performance_targets']={'cases':[]}
        path.write_text(yaml.safe_dump(self.cfg))
        self.assertEqual(original,project_gates.acceptance_binding(self.f.root,spec))
        self.cfg['acceptance_plan']['accuracy_config_sha256']='changed'
        path.write_text(yaml.safe_dump(self.cfg))
        self.assertNotEqual(original,project_gates.acceptance_binding(self.f.root,spec))

    def test_journal_sources_exclude_unrelated_profile_and_editorial_files(self):
        paths=project_gates.source_files(ROOT,{'before':[]})
        self.assertFalse(any(p.suffix=='.md' or 'framework-profiles' in p.parts for p in paths))
        self.assertIn(ROOT/'scripts/evidence_contract.py',paths)


class ObjectiveEvidenceTests(ModernFixture):
    def test_native_service_binding_cannot_be_relabelled_or_reused(self):
        binding=self.binding()
        report={'run_id':'accuracy-run','service_instance_id':'service-A'}
        contract.service_binding(self.reader,binding,report,self.cfg,'PPU-01')
        for changed in (dict(report,service_instance_id='service-B'),dict(report,run_id='other-run')):
            with self.assertRaises(ValueError): contract.service_binding(self.reader,binding,changed,self.cfg,'PPU-01')
        changed=copy.deepcopy(binding); changed['process_identity']['start_ticks']+=1
        with self.assertRaisesRegex(ValueError,'进程身份'):
            contract.service_binding(self.reader,changed,report,self.cfg,'PPU-01')
        changed=copy.deepcopy(binding); changed['endpoint']='http://another-host:8000/v1/chat/completions'
        with self.assertRaisesRegex(ValueError,'localhost'):
            contract.service_binding(self.reader,changed,report,self.cfg,'PPU-01')

    def test_execution_needs_measurements_and_frozen_tolerance(self):
        profile=workspace.resolved_profile(self.f.root,'vllm-plugin-fl')[1]
        output=self.raw('outputs.json',{'reference':[1],'actual':[1]})
        measurements={'kind':'execution_measurements','run_id':'run', 'runs':[
            {'mode':'eager','inference_count':1,'max_abs_error':0,'evidence':[output]},
            {'mode':'graph','inference_count':2,'max_abs_error':0,'evidence':[output],
             'effective_level':'full','capture_count':1,'replay_count':2}]}
        report={'run_id':'run','graph_level':'full','native':{'execution':self.raw('execution.json',measurements)}}
        self.cfg['acceptance_plan']['execution']={'max_abs_error':0.001}
        contract.execution(self.reader,report,self.cfg,profile)
        for field,value in [('replay_count',0),('effective_level','piecewise'),('max_abs_error',0.1)]:
            bad=copy.deepcopy(measurements); bad['runs'][1][field]=value
            report['native']['execution']=self.raw('bad.json',bad)
            with self.assertRaises(ValueError): contract.execution(self.reader,report,self.cfg,profile)

    def test_anonymous_boolean_receipt_rejected_human_review_supported(self):
        with self.assertRaises(ValueError): contract.producer({'checks':{'source_review':True}})
        proof=self.raw('review.json',{'changes':'reviewed'})
        report={'producer':{'kind':'human','name':'operator'}, 'check_results':{
            'source_review':{'status':'passed','method':'review','note':'核对产品 diff 与调用方','evidence':[proof]}}}
        contract.producer(report); contract.checks_evidence(self.reader,report,['source_review'])
        report['check_results']['source_review']['evidence']=[]
        with self.assertRaises(ValueError): contract.checks_evidence(self.reader,report,['source_review'])

    def test_performance_limits_and_coverage_are_enforced(self):
        case=[1024,128,4,16]
        source={'request':{'cases':[case]},'cases':[{'summary':{'P99 TTFT (ms)':50,'Output tok/s':100}}]}
        plan={'performance_targets':{'cases':[{'case':case,'limits':{'P99 TTFT (ms)':{'max':100},'Output tok/s':{'min':90}}}]}}
        contract.performance_targets(self.reader,source,plan)
        source['cases'][0]['summary']['P99 TTFT (ms)']*=1000
        with self.assertRaisesRegex(ValueError,'未达标'): contract.performance_targets(self.reader,source,plan)
        plan['performance_targets']['cases'][0]['case']=[1,1,1,1]
        with self.assertRaisesRegex(ValueError,'逐一覆盖'): contract.performance_targets(self.reader,source,plan)

    def test_ratio_targets_require_a_real_baseline(self):
        case=[1,1,1,1]; source={'request':{'cases':[case]},'cases':[{'summary':{'Req/s':10}}]}
        plan={'performance_targets':{'cases':[{'case':case,'limits':{'Req/s':{'min_ratio':1.1}}}]}}
        with self.assertRaisesRegex(ValueError,'baseline'): contract.performance_targets(self.reader,source,plan)

    def test_bad_targets_are_rejected_before_benchmark_execution(self):
        for limits in ({'Successful Requests':{'min':1}}, {'Req/s':{'min':float('nan')}},
                       {'Req/s':{'min':10,'max':1}}, {'Req/s':{'min_ratio':1.1}}):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                contract.validate_performance_plan({'performance_targets':{'cases':[{'case':[1,1,1,1],'limits':limits}]}})

    def test_native_performance_checks_service_targets_and_baseline_artifacts(self):
        import test_performance_evidence as perf_fixtures
        fixture=perf_fixtures.PerformanceEvidenceTests(); fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        ref=lambda p: {'path':str(p),'sha256':gate.digest(p)}
        cfg={'evidence_contract':2,'model':'Example','platform':'ppu',
             'workspace':{'roots':[{'host_alias':'PPU-01','host_root':str(fixture.root),'container_root':str(fixture.root.resolve())}]},
             'deployment':{'fingerprint':perf_fixtures.workflow.deployment_fingerprint(fixture.platform)},
             'acceptance_plan':{'performance_request_sha256':gate.canonical(fixture.report['request'])}}
        binding=self.binding(fixture.report['run_id'])
        observation=json.loads((self.f.remote/'observation.json').read_text())
        observation.update(service_instance_id=fixture.instance,listening_port=fixture.report['request']['port'])
        observation_path=fixture.root/'observation.json'; observation_path.write_text(json.dumps(observation))
        request=fixture.report['request']
        binding.update(service_instance_id=fixture.instance,deployment_fingerprint=cfg['deployment']['fingerprint'],
                       endpoint=f"http://{request['host']}:{request['port']}{request['endpoint']}",observation=ref(observation_path))
        runtime=workspace.load_yaml(fixture.runtime_path); runtime['service_binding']=binding
        fixture.runtime_path.write_text(yaml.safe_dump(runtime))
        # Re-export from the actual updated runtime; no mocked acceptance validators.
        fixture.compact_path.write_text(json.dumps(perf_fixtures.perf_acceptance.export_evidence(
            fixture.report_path,fixture.runtime_path,model='Example',platform='ppu',
            deployment_fingerprint=cfg['deployment']['fingerprint'],service_instance_id=fixture.instance)))
        cfg['acceptance_plan']['performance_targets']={'baseline':ref(fixture.report_path),
            'cases':[{'case':case,'limits':{'Req/s':{'min_ratio':1.0}}} for case in request['cases']]}
        reader=gate.Artifacts(cfg,'PPU-01',{'PPU-01':str(fixture.root)})
        native={'report':ref(fixture.compact_path),'runtime':ref(fixture.runtime_path)}
        envelope={'service_instance_id':fixture.instance,'run_id':fixture.report['run_id'],'scope':{'host_alias':'PPU-01'}}
        gate.native_performance(reader,native,envelope,cfg)
        cfg['acceptance_plan']['performance_targets']['cases'][0]['limits']['Req/s']['min_ratio']=1.1
        with self.assertRaisesRegex(ValueError,'未达标'): gate.native_performance(reader,native,envelope,cfg)
        cfg['acceptance_plan']['performance_targets']['cases'][0]['limits']['Req/s']['min_ratio']=1.0
        raw=fixture.report_path.parent/fixture.report['artifacts'][0]['path']; raw.write_text('changed')
        with self.assertRaisesRegex(ValueError,'完整性能产物'): gate.native_performance(reader,native,envelope,cfg)

    def test_delivery_manifest_requires_all_reproducible_files(self):
        files=[dict(self.raw(role+'.json',{'content':role}),role=role) for role in ('launcher','config','source','lock','restore')]
        manifest={'schema_version':1,'kind':'delivery_manifest','files':files,'image':{'validation':'pending'}}
        report={'launcher':files[0],'native':{'delivery':self.raw('delivery.json',manifest)}}
        contract.delivery(self.reader,report)
        manifest['files'].pop()
        report['native']['delivery']=self.raw('delivery.json',manifest)
        with self.assertRaisesRegex(ValueError,'五类'): contract.delivery(self.reader,report)

    def test_delivery_builder_rejects_missing_roles_and_escaping_files(self):
        names=[]
        for role in ('launcher','config','source','lock','restore'):
            (self.f.remote/role).write_text('fixture '+role)
            names.append(role+'='+role)
        manifest=delivery_manifest.build(self.f.remote,names)
        self.assertEqual(manifest['image']['validation'],'pending')
        with self.assertRaisesRegex(ValueError,'five'): delivery_manifest.build(self.f.remote,names[:-1])
        with self.assertRaisesRegex(ValueError,'relative'): delivery_manifest.build(self.f.remote,['source=../escape'])

    def test_v2_concurrency_is_explicit_and_legacy_minimum_is_retained(self):
        cfg=formal_config(); cfg['num_concurrent']=1
        self.assertTrue(validate_formal_config(cfg))
        cfg.update(formal_contract_version=2,concurrency_reason='容量验证支持单并发',service_binding=self.binding(),run_id='accuracy-run')
        self.assertEqual(validate_formal_config(cfg),[])
        cfg.pop('concurrency_reason')
        self.assertTrue(validate_formal_config(cfg))

    def test_accuracy_native_gate_checks_actual_service_binding(self):
        self.cfg['workspace']['roots'][0]['host_root']=str(self.f.remote)
        binding=self.binding(); cfg=formal_config()
        cfg.update(formal_contract_version=2,concurrency_reason='capacity fixture',service_binding=binding,run_id='accuracy-run',
                   num_concurrent=1,eval_model='accuracy-run',model_name='Example',base_url=binding['endpoint'])
        path=self.f.remote/'config.json'; path.write_text(json.dumps(cfg))
        run=self.f.remote/'accuracy-run'; run.mkdir()
        (run/'source_config.json').write_bytes(path.read_bytes())
        effective=llmrun.load_config(path); (run/'effective_config.json').write_text(json.dumps(effective))
        (run/'samples_example_1.jsonl').write_text('\n'.join(json.dumps({'doc_id':i,'resps':[['answer']]}) for i in range(2)))
        (run/'results_1.json').write_text(json.dumps({'results':{'example':{'acc':1.0}}}))
        llmrun.write_acceptance_report(effective,run,[],{'example':[{'output_dir':str(run),'returncode':0,'status':'passed','errors':[]}]},[])
        self.cfg['acceptance_plan']['accuracy_config_sha256']=gate.digest(path)
        native={'report':self.ref(run/'acceptance-result.json'),'config':self.ref(path)}
        report={'run_id':'accuracy-run','service_instance_id':'service-A','scope':{'host_alias':'PPU-01'}}
        reader=gate.Artifacts(self.cfg,'PPU-01',self.f.mounts)
        gate.native_accuracy(reader,native,report,self.cfg)
        report['service_instance_id']='service-B'
        with self.assertRaisesRegex(ValueError,'服务绑定不匹配'): gate.native_accuracy(reader,native,report,self.cfg)


class SanityTests(unittest.TestCase):
    def test_performance_run_id_is_fixed_before_requests_and_cannot_reuse_directory(self):
        import io
        import tempfile
        import perf_common
        from test_performance_hardening import BASE_ARGS, GOOD_OUTPUT
        with tempfile.TemporaryDirectory() as tmp:
            args=BASE_ARGS+['--output-dir',tmp,'--run-id','human-performance-001']
            with patch.object(perf_common.subprocess,'run',return_value=subprocess.CompletedProcess([],0,GOOD_OUTPUT,'')), \
                 patch('sys.stdout',io.StringIO()):
                self.assertEqual(perf_common.main(args),0)
                report=json.loads(next(Path(tmp).rglob('benchmark-result.json')).read_text())
                self.assertEqual(report['run_id'],'human-performance-001')
                with patch.object(perf_common.subprocess,'run') as run:
                    with self.assertRaises(FileExistsError): perf_common.main(args)
                    run.assert_not_called()

    def test_default_cli_is_offline_and_does_not_create_a_result(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            manifest={'schema_version':1,'kind':'sanity_manifest','model':'Example','concurrency':1,'timeout':1,
                      'cases':[{'id':'one','request':{'messages':[{'role':'user','content':'fixture'}]},'reference_text':'ok'}]}
            (root/'manifest.json').write_text(json.dumps(manifest))
            (root/'binding.json').write_text(json.dumps({'endpoint':'http://127.0.0.1:1/v1/chat/completions'}))
            result=subprocess.run([sys.executable,str(ROOT/'test/Accuracy_test/sanity.py'),
                '--manifest',str(root/'manifest.json'),'--service-binding',str(root/'binding.json'),
                '--run-id','dry-run','--output',str(root/'result.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'planned')
            self.assertFalse((root/'result.json').exists())

    def test_reference_comparison_preserves_errors_and_requires_full_coverage(self):
        manifest={'schema_version':1,'kind':'sanity_manifest','model':'Example','concurrency':1,'timeout':30,
                  'cases':[{'id':'text','request':{'messages':[{'role':'user','content':'fixture'}]},'reference_text':'reference'}]}
        result={'kind':'sanity_result','status':'passed','concurrency':1,'cases':[
            {'id':'text','response':{'choices':[{'message':{'content':'reference'}}]},'error':None}]}
        sanity.validate_result(manifest,result)
        result['cases'][0]['response']['choices'][0]['message']['content']='wrong'
        with self.assertRaisesRegex(ValueError,'reference mismatch'): sanity.validate_result(manifest,result)
        result['cases'][0]['error']='timeout'
        with self.assertRaisesRegex(ValueError,'request failed'): sanity.validate_result(manifest,result)
        result['cases'][0].update(error=None,response={'choices':[]})
        with self.assertRaisesRegex(ValueError,'invalid response'): sanity.validate_result(manifest,result)
        result['cases']=[]
        with self.assertRaisesRegex(ValueError,'coverage'): sanity.validate_result(manifest,result)


if __name__ == '__main__': unittest.main()
