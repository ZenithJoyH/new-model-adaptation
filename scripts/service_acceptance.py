"""Frozen service scope and cross-stage launcher checks for service profiles.

Historical plans without this extension keep their original contract. New service
workspaces and schema-2 sanity require it. Runtime settings still need an attributed
review of the service's effective configuration; hashes alone do not prove semantics.
"""
import hashlib
import re

from evidence_contract import require, service_binding

CACHE_ON = '--enable-prefix-caching'
CACHE_OFF = '--no-enable-prefix-caching'


def normalized_argv(argv):
    require(isinstance(argv, list) and argv and all(isinstance(a, str) and a and '\0' not in a for a in argv),
            'service argv 必须是非空字符串列表')
    switches = [a for a in argv if a.split('=', 1)[0] in {CACHE_ON, CACHE_OFF}]
    require(len(switches) <= 1 and all(a in {CACHE_ON, CACHE_OFF} for a in switches),
            'prefix caching 开关重复、冲突或格式不明确')
    return [a for a in argv if a not in {CACHE_ON, CACHE_OFF}]


def validate_plan(cfg, architecture_sha256=None):
    plan = cfg.get('acceptance_plan', {}).get('service_contract')
    require(isinstance(plan, dict) and type(plan.get('schema_version')) is int and plan['schema_version'] == 1,
            '先冻结 acceptance_plan.service_contract schema_version=1')
    sha = plan.get('architecture_sha256')
    require(isinstance(sha, str) and re.fullmatch(r'[0-9a-f]{64}', sha), 'service_contract 缺少结构分析 SHA-256')
    if architecture_sha256 is not None:
        require(sha == architecture_sha256, 'service_contract 模型结构分析已变化，需复核能力')
    require(plan.get('required_modalities') in (['text'], ['text', 'image']), '冻结实际 required_modalities: text 或 text,image')
    hosts = plan.get('hosts')
    require(isinstance(hosts, dict) and set(hosts) == set(cfg['target']['hosts']), 'service_contract 必须覆盖准确 Host 集合')
    for value in hosts.values():
        require(isinstance(value, dict), 'service_contract Host 必须为映射')
        normalized_argv(value.get('argv'))
        require(CACHE_OFF not in value['argv'], '冻结普通启动 argv，不能关闭 prefix caching')
        env = value.get('environment')
        require(isinstance(env, dict) and all(isinstance(k, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', k)
                and isinstance(v, str) for k, v in env.items()), '冻结必要 environment（可为空），不得含凭据')
        config = value.get('effective_config')
        require(isinstance(config, dict) and config.get('prefix_caching_enabled') is True,
                '冻结开启缓存的完整有效推理配置 effective_config')
        names = config.get('served_model_names')
        require(isinstance(names, list) and names and all(isinstance(n, str) and n.strip() for n in names)
                and len(set(names)) == len(names), '冻结真实 served_model_names（允许别名）')
        # The remaining settings include graph, dtype, TP/PP, context and other
        # effective inference defaults, not ephemeral PID/run/port observations.
        require(isinstance(config.get('settings'), dict) and config['settings'], '缺少 effective_config.settings')
        from framework_evidence import reference
        reference(value.get('launcher'))
    return plan


def validate_served_model(cfg, host, model):
    plan = validate_plan(cfg)
    require(host in plan['hosts'] and model in plan['hosts'][host]['effective_config']['served_model_names'],
            '请求 model 不属于冻结的实际服务模型/别名')


def validate_sanity_scope(cfg, host, manifest):
    plan = validate_plan(cfg)
    validate_served_model(cfg, host, manifest.get('model'))
    version = manifest.get('schema_version')
    require(version in (1, 2), '不支持的 sanity manifest schema')
    observed = set()
    for case in manifest.get('cases', []):
        messages = case.get('request', {}).get('messages', [])
        image = any(isinstance(message, dict) and message.get('role') == 'user'
                    and isinstance(message.get('content'), list)
                    and any(isinstance(part, dict) and part.get('type') == 'image_url'
                            and isinstance(part.get('image_url'), dict)
                            and isinstance(part['image_url'].get('url'), str) and part['image_url']['url'].strip()
                            for part in message['content']) for message in messages)
        observed.add('image' if image else 'text')
    require(observed == set(plan['required_modalities']), 'sanity 模态覆盖与已核实模型能力不一致')
    if version == 2:
        require(manifest.get('modalities') == plan['required_modalities'],
                'sanity 模态覆盖与已核实模型能力不一致')


def validate_launch(reader, report, cfg, host, stage, native_binding=None):
    plan = validate_plan(cfg)
    frozen = plan['hosts'][host]
    launch = reader.json(report['native']['service_launch'])
    require(launch.get('kind') == 'service_launch' and launch.get('schema_version') == 1
            and launch.get('run_id') == report['run_id'], 'service_launch 不属于本轮 run')
    binding = launch.get('service_binding')
    service_binding(reader, binding, report, cfg, host)
    if native_binding is not None:
        require(binding == native_binding, '启动证据与原生评测服务绑定不一致')
    if binding.get('distributed') is not None:
        participant = next(p for p in binding['distributed']['participants'] if p['host_alias'] == host)
        observed = reader.json(participant['observation'])
    else:
        observed = reader.json(binding['observation'])
    argv = observed.get('argv')
    actual = normalized_argv(argv)
    require(hashlib.sha256(b'\0'.join(a.encode() for a in argv) + b'\0').hexdigest()
            == observed['process_identity']['cmdline_sha256'], '观察 argv 与实际进程命令哈希不一致')
    require(actual == normalized_argv(frozen['argv']), '启动 argv 除前缀缓存外发生变化，需重新验收')
    performance = stage == 'performance'
    require((CACHE_OFF in argv) == performance, '只有性能启动可且必须使用 --no-enable-prefix-caching')
    require(observed.get('launch_environment') == frozen['environment'], '必要环境变量与冻结启动配置不一致')
    path = reader.file(launch['launcher'])
    require(path == reader.root / 'start-model.sh' and path.stat().st_mode & 0o111,
            '共享启动脚本必须位于工作根且可执行')
    require(reader.file(frozen['launcher']) == path and launch['launcher']['sha256'] == frozen['launcher']['sha256'],
            '启动脚本与冻结共享脚本不一致')
    if stage == 'summary':
        require(reader.file(report['launcher']) == path and report['launcher']['sha256'] == frozen['launcher']['sha256'],
                '交付脚本与评测共享脚本不一致')
    config = launch.get('effective_config')
    require(isinstance(config, dict) and config.get('prefix_caching_enabled') is (not performance),
            '实际 prefix caching 状态不符合本轮用途')
    normalized = dict(config, prefix_caching_enabled=True)
    require(normalized == frozen['effective_config'], '有效推理配置除前缀缓存外发生变化，需重新验收')
    review = launch.get('configuration_review', {})
    require(isinstance(review.get('reviewer'), str) and review['reviewer'].strip()
            and isinstance(review.get('note'), str) and review['note'].strip(), '有效配置需要署名现场审阅')
    evidence = review.get('evidence')
    require(isinstance(evidence, list) and evidence, '缺少服务有效配置原始证据')
    for ref in evidence:
        reader.file(ref)
