"""Read-only adapter to profile-specific adaptation evidence gates."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace


INTERFACES = {
    'adaptation/accuracy': ('1.0.0', 'adaptation-native-accuracy/v1'),
    'adaptation/performance': ('1.0.0', 'adaptation-native-performance/v1'),
}


def interface_requirements(capability_id):
    try:
        version, contract = INTERFACES[capability_id]
    except KeyError as exc:
        raise ValueError('unsupported project capability') from exc
    return {'interface_version': version, 'result_contract': contract}


def validate_check(check):
    required = {'kind', 'model', 'platform', 'framework', 'hosts', 'steps', 'verify_records', 'artifact_roots'}
    if not isinstance(check, dict) or check.get('kind') != 'framework' or not required <= set(check):
        raise ValueError('framework gate requires model/platform/framework/hosts/steps/verify_records/artifact_roots')
    if set(check) - required - {'acceptance_substeps'}:
        raise ValueError('unknown framework gate fields')
    if type(check['verify_records']) is not bool:
        raise ValueError('verify_records must be boolean')
    for key in ('model', 'platform', 'framework'):
        if not isinstance(check[key], str) or not check[key].strip(): raise ValueError(f'{key} required')
    for key in ('hosts', 'steps', 'acceptance_substeps'):
        values = check.get(key, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not v or ',' in v for v in values):
            raise ValueError(f'{key}: explicit string list required')
    if not check['steps']: raise ValueError('steps required')
    if not isinstance(check['artifact_roots'], dict): raise ValueError('artifact_roots must be a mapping')
    for host, path in check['artifact_roots'].items():
        if not isinstance(host, str) or '=' in host or not isinstance(path, str) or not Path(path).is_absolute():
            raise ValueError('artifact_roots require exact Host and absolute readable path')


def source_files(root):
    return (list((root / 'scripts').glob('*.py'))
        + list((root / 'framework-profiles').rglob('*.yml'))
        + list((root / 'framework-profiles').rglob('*.md'))
        + list((root / 'test/Accuracy_test').glob('*.py'))
        + list((root / 'test/perf_test').glob('*.py')) + [root / p for p in
        ('AGENTS.md', 'docs/skills-project-contract.md', 'docs/framework-evidence.md')])


def validate_plan(spec):
    interface_requirements(spec['capability_id'])
    expected = 'performance' if spec['capability_id'] == 'adaptation/performance' else 'accuracy'
    if expected == 'accuracy' and spec['selection'] not in ('formal-full', 'gate-check'):
        raise ValueError('journal accuracy adapter supports formal-full/gate-check only; sanity and hard-case need their own receipts')
    for c in spec['before'] + spec['after']:
        if c['steps'] != ['acceptance'] or c.get('acceptance_substeps') != [expected]:
            raise ValueError(f'this capability requires exactly acceptance/{expected}')
    if any(c['verify_records'] for c in spec['before']):
        raise ValueError('before gates check prerequisites; put completion verification in after')
    if not all(c['verify_records'] for c in spec['after']):
        raise ValueError('after gates must verify native completion records')
    def target(check):
        return {k: v for k, v in check.items() if k != 'verify_records'}
    if [target(c) for c in spec['before']] != [target(c) for c in spec['after']]:
        raise ValueError('before/after must address the exact same selected framework steps')
    scope = spec['scope']
    for c in spec['before']:
        for key in ('model', 'platform', 'framework', 'hosts'):
            if scope.get(key) != c[key]: raise ValueError(f'scope and native gate differ: {key}')


def run_check(root, check, scope, expected_run_id=None):
    validate_check(check)
    from framework_evidence import check_command
    args = SimpleNamespace(repo_root=root, model=check['model'], platform=check['platform'],
        framework=check['framework'], hosts=','.join(check['hosts']), steps=','.join(check['steps']),
        acceptance_substeps=','.join(check.get('acceptance_substeps', [])),
        artifact_root=[f'{host}={path}' for host, path in check['artifact_roots'].items()],
        check_only=True, verify_records=check['verify_records'], evidence_info=None)
    output = io.StringIO()
    with redirect_stdout(output): code = check_command(args)
    if check['verify_records'] and expected_run_id:
        from framework_evidence import record_for
        from framework_workspace import load_yaml
        directory = root / 'models' / check['model'] / check['platform'] / 'frameworks' / check['framework']
        config = load_yaml(directory / 'framework.yml')
        stages = check.get('acceptance_substeps') or check['steps']
        for stage in stages:
            if record_for(config, stage).get('run_id') != expected_run_id:
                raise ValueError(f'{stage}: native receipt run_id does not match this journal run')
    return {'kind': 'framework', 'status': 'passed' if code == 0 else 'incomplete',
            'verify_records': check['verify_records'], 'detail': output.getvalue()}


def output_files(root, spec):
    # The workflow record binds the original native receipts and their hashes.
    return [root / 'models' / c['model'] / c['platform'] / 'frameworks' / c['framework'] / 'framework.yml'
            for c in spec['after']]


def acceptance_binding(root, spec):
    """Freeze stable identity while allowing workflow records to be updated."""
    from framework_workspace import load_yaml
    values = []
    for check in spec['before']:
        path = root / 'models' / check['model'] / check['platform'] / 'frameworks' / check['framework'] / 'framework.yml'
        config = load_yaml(path)
        values.append({key: config.get(key) for key in
                       ('model', 'platform', 'framework', 'profile', 'profile_version',
                        'target', 'workspace', 'deployment', 'acceptance_plan')})
    return hashlib.sha256(json.dumps(values, sort_keys=True, ensure_ascii=False,
                        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_frozen_inputs(root, spec, context):
    """Ensure begin-time inputs encode the profile's already-frozen test plan."""
    from framework_evidence import canonical
    from framework_workspace import load_yaml
    for check in spec['before']:
        path = root / 'models' / check['model'] / check['platform'] / 'frameworks' / check['framework'] / 'framework.yml'
        config = load_yaml(path)
        stage = check['acceptance_substeps'][0]
        plan = config.get('acceptance_plan', {})
        if stage == 'accuracy':
            expected = plan.get('accuracy_config_sha256')
            if not expected or expected not in context.values():
                raise ValueError('frozen accuracy config is absent from context_files')
        elif stage == 'performance':
            expected = plan.get('performance_request_sha256')
            matched = False
            for filename in context:
                try:
                    value = json.loads(Path(filename).read_text(encoding='utf-8'))
                except (OSError, ValueError, TypeError):
                    continue
                request = value.get('request') if isinstance(value, dict) and 'request' in value else value
                if expected and canonical(request) == expected:
                    matched = True
                    break
            if not matched:
                raise ValueError('frozen performance request is absent from context_files')


def native_input_files(root, spec):
    """Resolve the config/runtime actually consumed by each verified native run."""
    from framework_evidence import Artifacts, record_for
    from framework_workspace import load_yaml
    result = []
    for check in spec['after']:
        directory = root / 'models' / check['model'] / check['platform'] / 'frameworks' / check['framework']
        config = load_yaml(directory / 'framework.yml')
        stage = check['acceptance_substeps'][0]
        key = 'config' if stage == 'accuracy' else 'runtime'
        for receipt_ref in record_for(config, stage).get('receipts', []):
            reader = Artifacts(config, receipt_ref['host_alias'], check['artifact_roots'])
            receipt = reader.json(receipt_ref)
            result.append(reader.file(receipt['native'][key]))
    return result
