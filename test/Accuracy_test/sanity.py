#!/usr/bin/env python3
"""Small text/image service checks with response review; offline by default."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.request


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_manifest(value):
    if (type(value.get('schema_version')) is not int or value['schema_version'] not in (1, 2)
            or value.get('kind') != 'sanity_manifest'):
        raise ValueError('expected sanity_manifest schema 1 or 2')
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
    modalities = value.get('modalities')
    if value['schema_version'] == 2 and modalities not in (['text'], ['text', 'image']):
        raise ValueError('declare model modalities as [text] or [text, image]')
    observed = set()
    for case in cases:
        if not isinstance(case.get('request'), dict) or not case['request'].get('messages'):
            raise ValueError('case requires an explicit chat request (text or multimodal)')
        if 'model' in case['request'] and case['request']['model'] != value['model']:
            raise ValueError('case model differs from manifest')
        if case['request'].get('stream'):
            raise ValueError('streaming is not supported by this small-set runner')
        if value['schema_version'] == 1:
            if not isinstance(case.get('reference_text'), str) or not case['reference_text'].strip():
                raise ValueError('each case needs a frozen reference_text from the reference implementation')
            continue
        if type(case['request'].get('n', 1)) is not int or case['request'].get('n', 1) != 1:
            raise ValueError('sanity requires one reviewed completion per request (n=1)')
        messages = case['request']['messages']
        if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
            raise ValueError('messages must be a list of chat messages')
        has_image = False
        has_user_text = False
        for message in messages:
            if message.get('role') not in ('system', 'user', 'assistant'):
                raise ValueError('unsupported sanity message role')
            content = message.get('content')
            if isinstance(content, str) and content.strip():
                has_user_text |= message['role'] == 'user'
            elif isinstance(content, list) and content:
                for part in content:
                    if not isinstance(part, dict):
                        raise ValueError('invalid multimodal content part')
                    if part.get('type') == 'text' and isinstance(part.get('text'), str) and part['text'].strip():
                        has_user_text |= message['role'] == 'user'
                    elif (part.get('type') == 'image_url' and message['role'] == 'user'
                          and isinstance(part.get('image_url'), dict)
                          and isinstance(part['image_url'].get('url'), str) and part['image_url']['url'].strip()):
                        has_image = True
                    else:
                        raise ValueError('unsupported or empty multimodal content part')
            else:
                raise ValueError('empty or invalid message content')
        if not has_user_text:
            raise ValueError('each case needs a user text instruction')
        modality = 'image' if has_image else 'text'
        if case.get('modality') != modality or modality not in modalities:
            raise ValueError('case modality does not match its actual request or model capabilities')
        observed.add(modality)
        if not isinstance(case.get('expected_behavior'), str) or not case['expected_behavior'].strip():
            raise ValueError('each case needs reviewable expected_behavior, not an exact reference answer')
    if value['schema_version'] == 2 and observed != set(modalities):
        raise ValueError('sanity must cover text and every declared model modality')
    return value


def validate_responses(manifest, report):
    validate_manifest(manifest)
    allowed = ('passed',) if manifest['schema_version'] == 1 else ('needs_review', 'passed')
    if report.get('kind') != 'sanity_result' or report.get('status') not in allowed:
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
        if manifest['schema_version'] == 1 and (
                not isinstance(content, str) or content.strip() != case['reference_text'].strip()):
            raise ValueError('reference mismatch: ' + case['id'])
        if manifest['schema_version'] == 2:
            if len(choices) != 1:
                raise ValueError('expected one reviewed completion: ' + case['id'])
            if not isinstance(content, str) or not content.strip():
                raise ValueError('empty or invalid output: ' + case['id'])
            if choices[0].get('finish_reason') != 'stop':
                raise ValueError('incomplete or abnormal response finish: ' + case['id'])
            elapsed = result.get('elapsed_seconds')
            if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
                raise ValueError('missing request timing: ' + case['id'])


def validate_result(manifest, report, review=None):
    validate_responses(manifest, report)
    if manifest['schema_version'] == 1:
        return
    # A successful HTTP response is not proof of relevance or image understanding.
    # Keep the original responses immutable; gate a separately attributed review.
    if (not isinstance(review, dict) or review.get('kind') != 'sanity_review'
            or review.get('schema_version') != 1):
        raise ValueError('text/image responses require a separate sanity_review')
    if (not report.get('run_id') or not report.get('manifest_sha256')
            or review.get('run_id') != report['run_id']
            or review.get('manifest_sha256') != report['manifest_sha256']):
        raise ValueError('sanity review run or manifest mismatch')
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        raise ValueError('identified reviewer required')
    records = review.get('cases')
    if (not isinstance(records, list) or not all(isinstance(r, dict) for r in records)
            or [r.get('id') for r in records] != [c['id'] for c in manifest['cases']]):
        raise ValueError('sanity review coverage is incomplete or duplicated')
    for case, result in zip(manifest['cases'], records):
        checks = ['output_health', 'relevance']
        if case['modality'] == 'image':
            checks.append('image_understanding')
        if any(result.get(key) is not True for key in checks):
            raise ValueError('sanity content review failed: ' + case['id'])
        if not isinstance(result.get('note'), str) or not result['note'].strip():
            raise ValueError('case-specific review rationale required: ' + case['id'])


def execute(manifest, binding):
    def request(case):
        started = time.perf_counter()
        try:
            payload = dict(case['request'], model=manifest['model'], stream=False)
            req = urllib.request.Request(binding['endpoint'], data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(req, timeout=manifest['timeout']) as response:
                body = json.load(response)
            return {'id': case['id'], 'response': body, 'error': None,
                    'elapsed_seconds': time.perf_counter() - started}
        except Exception as exc:
            return {'id': case['id'], 'response': {}, 'error': str(exc),
                    'elapsed_seconds': time.perf_counter() - started}
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
        report = {'schema_version': 1, 'kind': 'sanity_result',
                  'status': 'needs_review' if manifest['schema_version'] == 2 else 'passed', 'run_id': args.run_id,
                  'manifest_sha256': digest(args.manifest), 'service_binding': binding,
                  'concurrency': manifest['concurrency'], 'cases': execute(manifest, binding)}
        try:
            validate_responses(manifest, report)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            report.update(status='failed', error=str(exc))
        with args.output.open('x') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps({'status': report['status'], 'report': str(args.output)}))
        return 0 if report['status'] in ('passed', 'needs_review') else 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'incomplete', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
