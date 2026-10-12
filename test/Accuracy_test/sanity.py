#!/usr/bin/env python3
"""Explicit, small reference-comparison requests; default is offline validation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import urllib.request


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_manifest(value):
    if value.get('schema_version') != 1 or value.get('kind') != 'sanity_manifest':
        raise ValueError('expected sanity_manifest v1')
    if not isinstance(value.get('model'), str) or not value['model'].strip():
        raise ValueError('explicit served model required')
    if type(value.get('concurrency')) is not int or value['concurrency'] < 1:
        raise ValueError('explicit positive concurrency required')
    if type(value.get('timeout')) not in (float, int) or not math.isfinite(value['timeout']) or value['timeout'] <= 0:
        raise ValueError('positive timeout required')
    cases = value.get('cases')
    if not isinstance(cases, list) or not cases or any(not isinstance(c, dict) for c in cases):
        raise ValueError('nonempty case list required')
    ids = [c.get('id') for c in cases]
    if not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('unique case IDs required')
    for case in cases:
        if not isinstance(case.get('request'), dict) or not case['request'].get('messages'):
            raise ValueError('case requires an explicit chat request (text or multimodal)')
        if 'model' in case['request'] and case['request']['model'] != value['model']:
            raise ValueError('case model differs from manifest')
        if case['request'].get('stream'):
            raise ValueError('streaming is not supported by this small-set runner')
        if not isinstance(case.get('reference_text'), str) or not case['reference_text'].strip():
            raise ValueError('each case needs a frozen reference_text from the reference implementation')
    return value


def validate_result(manifest, report):
    validate_manifest(manifest)
    if report.get('kind') != 'sanity_result' or report.get('status') != 'passed':
        raise ValueError('sanity run did not pass')
    records = report.get('cases', [])
    if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
        raise ValueError('invalid sanity cases')
    if [r.get('id') for r in records] != [c['id'] for c in manifest['cases']]:
        raise ValueError('sanity coverage is incomplete or duplicated')
    if report.get('concurrency') != manifest['concurrency']:
        raise ValueError('sanity concurrency differs from the frozen plan')
    for case, result in zip(manifest['cases'], records):
        if result.get('error') is not None:
            raise ValueError('sanity request failed: ' + case['id'])
        response = result.get('response')
        choices = response.get('choices') if isinstance(response, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError('invalid response choices: ' + case['id'])
        message = choices[0].get('message')
        content = message.get('content') if isinstance(message, dict) else None
        if not isinstance(content, str) or content.strip() != case['reference_text'].strip():
            raise ValueError('reference mismatch: ' + case['id'])


def execute(manifest, binding):
    def request(case):
        try:
            payload = dict(case['request'], model=manifest['model'], stream=False)
            req = urllib.request.Request(binding['endpoint'], data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=manifest['timeout']) as response:
                body = json.load(response)
            return {'id': case['id'], 'response': body, 'error': None}
        except Exception as exc:
            return {'id': case['id'], 'response': {}, 'error': str(exc)}
    with ThreadPoolExecutor(max_workers=manifest['concurrency']) as pool:
        return list(pool.map(request, manifest['cases']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--service-binding', type=Path, required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--output', type=Path)
    p.add_argument('--run', action='store_true', help='explicitly send the frozen requests')
    args = p.parse_args()
    try:
        manifest = validate_manifest(json.loads(args.manifest.read_text()))
        binding = json.loads(args.service_binding.read_text())
        from urllib.parse import urlsplit
        endpoint = urlsplit(binding.get('endpoint', ''))
        if (endpoint.scheme not in ('http', 'https') or not endpoint.hostname or endpoint.username
                or endpoint.password or endpoint.query or endpoint.fragment):
            raise ValueError('credential-free endpoint required')
        if not args.run:
            print(json.dumps({'status': 'planned', 'cases': len(manifest['cases']), 'concurrency': manifest['concurrency']}))
            return 0
        if not args.output or not args.output.is_absolute() or args.output.exists():
            raise ValueError('new absolute --output required; existing results are never overwritten')
        report = {'schema_version': 1, 'kind': 'sanity_result', 'status': 'passed', 'run_id': args.run_id,
                  'manifest_sha256': digest(args.manifest), 'service_binding': binding,
                  'concurrency': manifest['concurrency'], 'cases': execute(manifest, binding)}
        try:
            validate_result(manifest, report)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            report.update(status='failed', error=str(exc))
        with args.output.open('x') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps({'status': report['status'], 'report': str(args.output)}))
        return 0 if report['status'] == 'passed' else 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'incomplete', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
