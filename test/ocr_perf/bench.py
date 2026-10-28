#!/usr/bin/env python3
"""Portable, closed-loop page OCR benchmark. Never starts/stops a model server."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import threading
import time
import urllib.error
import urllib.request


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def percentile(values, percent):
    """Nearest rank: retain this definition across platforms."""
    return sorted(values)[max(0, math.ceil(len(values) * percent / 100) - 1)] if values else None


def load_bundle(root):
    root = Path(root).resolve()
    inventory = json.loads((root / 'checksums.json').read_text())
    actual = {str(p.relative_to(root)) for p in root.rglob('*')
              if p.is_file() and p.name != 'checksums.json' and '__pycache__' not in p.parts}
    if actual != set(inventory):
        raise ValueError('Bundle file set changed')
    for name, expected in inventory.items():
        p = (root / name).resolve()
        if not p.is_relative_to(root) or sha(p) != expected:
            raise ValueError('Bundle checksum mismatch: ' + name)
    manifest = json.loads((root / 'manifest.json').read_text())
    if manifest['schema'] != 'minicpm-ocr-portable/v1.1':
        raise ValueError('Unsupported benchmark schema')
    spec = importlib.util.spec_from_file_location('frozen_ocr_postprocess', root / 'native_postprocess.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    return root, manifest, native, sha(root / 'checksums.json')


class Client:
    def __init__(self, endpoint, model, timeout):
        if not endpoint.startswith(('http://', 'https://')):
            raise ValueError('HTTP(S) endpoint required')
        self.endpoint = endpoint.rstrip('/')
        self.model, self.timeout = model, timeout
        self.local = threading.local()

    def request(self, path, payload=None):
        # Do not route image data via ambient HTTP proxies. No automatic retries.
        if not hasattr(self.local, 'opener'):
            self.local.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        headers = {'Content-Type': 'application/json'}
        key = os.environ.get('OCR_BENCH_API_KEY')
        if key:
            headers['Authorization'] = 'Bearer ' + key
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        with self.local.opener.open(urllib.request.Request(self.endpoint + path, data=data, headers=headers),
                                    timeout=self.timeout) as response:
            return json.loads(response.read())


def health_check(client):
    models = client.request('/v1/models')
    if client.model not in {m['id'] for m in models['data']}:
        raise ValueError('Requested served model not present')
    return models


def run_round(root, manifest, native, client, scenario, output, round_index):
    output.mkdir(parents=True, exist_ok=False)
    (output / 'pages').mkdir()
    records, pages = [], []
    lock = threading.Lock()
    semaphore = threading.BoundedSemaphore(scenario['region_concurrency'])
    page_map = {p['id']: p for p in manifest['pages']}

    def crop(page_id, block):
        started = time.perf_counter()
        result = {'page_id': page_id, 'block_id': block['id'], 'label': block['label'],
                  'status': 'failed', 'finish_reason': None}
        try:
            with semaphore:
                acquired = time.perf_counter()
                image = base64.b64encode((root / block['image']).read_bytes()).decode()
                payload = dict(block['parameters'], model=client.model,
                               messages=[{'role': 'user', 'content': [
                                   {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + image}},
                                   {'type': 'text', 'text': block['prompt']}]}])
                http_started = time.perf_counter()
                response = client.request('/v1/chat/completions', payload)
                http_ended = time.perf_counter()
                choice = response['choices'][0]
                text = choice['message']['content']
                if not isinstance(text, str):
                    raise ValueError('Non-string OCR result')
                usage = response.get('usage') or {}
                tokens = usage.get('completion_tokens')
                # Token throughput must not silently omit missing usage.
                if type(tokens) is not int or tokens < 0:
                    raise ValueError('Missing/invalid completion_tokens')
                result.update(status='ok' if text.strip() else 'empty', text=text,
                              finish_reason=choice['finish_reason'], completion_tokens=tokens,
                              prompt_tokens=usage.get('prompt_tokens'), response=response,
                              queue_seconds=acquired-started, http_seconds=http_ended-http_started)
        except Exception as exc:
            result['error'] = f'{type(exc).__name__}: {exc}'
            if isinstance(exc, urllib.error.HTTPError):
                result['http_status'] = exc.code
                result['error_body'] = exc.read().decode(errors='replace')[:4000]
        result['duration_seconds'] = time.perf_counter() - started
        with lock:
            records.append(result)
            with (output / 'requests.jsonl').open('a') as f:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
        return result

    def page(page_id):
        started = time.perf_counter()  # admission to the bounded page worker
        entry = page_map[page_id]
        active = [b for b in entry['blocks'] if not b.get('skip')]
        with ThreadPoolExecutor(max_workers=scenario['per_page_regions']) as pool:
            outputs = list(pool.map(lambda b: crop(page_id, b), active))
        by_id = {r['block_id']: r for r in outputs}
        blocks = []
        for block in entry['blocks']:
            item = {k: block[k] for k in ('label', 'order', 'bbox')}
            if block.get('skip'):
                item.update(content='', raw_content='', status='skipped_no_vlm')
            else:
                response = by_id[block['id']]
                text = response.get('text', '')
                item.update(raw_content=text, status=response['status'],
                            content=native.postprocess_content(text, block['output_format'], label=block['label']),
                            inline_formula_mixed=(block['label'] == 'inline_formula' and
                                                  native.has_mixed_inline_formula_content(text)))
            blocks.append(item)
        markdown = native.assemble_markdown(native._normalize_and_dedupe_blocks(blocks), manifest['prompt_map'])
        (output / 'pages' / (page_id + '.md')).write_text(markdown)
        result = {'page_id': page_id, 'requests': len(outputs),
                  'successful': all(r['status'] == 'ok' and r['finish_reason'] == 'stop' for r in outputs)
                                and bool(markdown.strip()),
                  'failed_requests': sum(r['status'] != 'ok' for r in outputs),
                  'truncated_requests': sum(r['finish_reason'] == 'length' for r in outputs),
                  'markdown_chars': len(markdown), 'duration_seconds': time.perf_counter() - started}
        with lock:
            pages.append(result)
            with (output / 'pages.jsonl').open('a') as f:
                f.write(json.dumps(result, ensure_ascii=False) + '\n')
            save(output / 'progress.json', {'completed_pages': len(pages), 'planned_pages': len(scenario['page_ids'])})
        return result

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=scenario['page_concurrency']) as pool:
        list(pool.map(page, scenario['page_ids']))
    elapsed = time.perf_counter() - started
    successful = [p for p in pages if p['successful']]
    latency = [p['duration_seconds'] for p in pages]  # never drop failed pages
    summary = {'scenario': scenario['name'], 'round': round_index, 'elapsed_seconds': elapsed,
               'planned_pages': len(scenario['page_ids']), 'completed_pages': len(pages),
               'successful_pages': len(successful), 'successful_pages_per_minute': 60*len(successful)/elapsed,
               'page_latency_p50_seconds': percentile(latency, 50),
               'page_latency_p90_seconds': percentile(latency, 90),
               'slo_seconds': scenario['slo_seconds'],
               'slo_success_fraction': sum(p['successful'] and p['duration_seconds'] <= scenario['slo_seconds']
                                           for p in pages)/len(scenario['page_ids']),
               'requests': len(records), 'failed_requests': sum(r['status'] != 'ok' for r in records),
               'truncated_requests': sum(r['finish_reason'] == 'length' for r in records),
               'successful_requests_per_second': sum(r['status'] == 'ok' for r in records)/elapsed,
               'output_tokens_per_second': sum(r.get('completion_tokens', 0) for r in records)/elapsed}
    expected = sum(sum(not b.get('skip', False) for b in page_map[p]['blocks']) for p in scenario['page_ids'])
    summary['integrity_ok'] = len(records) == expected and len(pages) == len(scenario['page_ids'])
    summary['operational_pass'] = (summary['integrity_ok'] and len(successful) == len(pages)
                                   and summary['slo_success_fraction'] >= .9)
    save(output / 'pages.json', pages)
    save(output / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def execute(args):
    root, manifest, native, bundle_hash = load_bundle(args.bundle)
    if args.dry_run:
        print(json.dumps({'bundle_sha256': bundle_hash, 'pages': len(manifest['pages']),
                          'scenarios': manifest['scenarios']}, ensure_ascii=False, indent=2))
        return 0
    if not args.service_evidence:
        raise ValueError('--service-evidence required: verify effective server cache settings first')
    evidence = json.loads(Path(args.service_evidence).read_text())
    if (evidence.get('endpoint') != args.endpoint.rstrip('/') or evidence.get('prefix_caching') is not False
            or evidence.get('mm_processor_cache_gb') != 0 or not evidence.get('verification')):
        raise ValueError('Service evidence must bind endpoint and verified disabled caches')
    if evidence.get('checkpoint_identity_sha256') != manifest['checkpoint_identity_sha256']:
        raise ValueError('Checkpoint file identity differs from frozen workload')
    if evidence.get('dtype') != 'bfloat16' or evidence.get('gpu_count') != 1:
        raise ValueError('v1 comparison requires bfloat16 and one accelerator; use a separately versioned track otherwise')
    output = Path(args.output).resolve()
    if output.is_relative_to(root):
        raise ValueError('Results must be outside the immutable bundle')
    output.mkdir(parents=True, exist_ok=False)
    client = Client(args.endpoint, args.model, manifest['request_timeout_seconds'])
    models = health_check(client)
    save(output / 'run.json', {'schema': 'minicpm-ocr-portable-result/v1', 'started_epoch': time.time(),
                             'label': args.label, 'endpoint': args.endpoint, 'model': args.model,
                             'bundle_sha256': bundle_hash, 'runner_sha256': sha(__file__),
                             'python': platform.python_version(), 'client_platform': platform.platform(),
                             'server_models': models, 'service_evidence': evidence})
    summaries = []
    for scenario in manifest['scenarios']:
        # Full workload replay covers image/sequence shapes at this exact concurrency.
        # Prefix/MM caches remain disabled; only compilation/operator warmup is allowed.
        warmup = dict(scenario)
        w = run_round(root, manifest, native, client, warmup, output / (scenario['name'] + '-warmup'), 0)
        if w['failed_requests'] or w['truncated_requests']:
            raise RuntimeError('Warmup failed; no measured rounds for this scenario')
        measured = []
        for index in (1, 2):
            measured.append(run_round(root, manifest, native, client, scenario,
                                      output / f"{scenario['name']}-r{index}", index))
        rates = [s['successful_pages_per_minute'] for s in measured]
        if min(rates) <= 0 or max(rates)/min(rates) > 1.1:
            measured.append(run_round(root, manifest, native, client, scenario,
                                      output / f"{scenario['name']}-r3", 3))
        summaries.extend(measured)
        save(output / 'partial-summary.json', summaries)
    stability = {}
    for scenario in manifest['scenarios']:
        rows = [r for r in summaries if r['scenario'] == scenario['name']][-2:]
        rates = [r['successful_pages_per_minute'] for r in rows]
        stability[scenario['name']] = min(rates) > 0 and max(rates)/min(rates) <= 1.1
    report = {'schema': 'minicpm-ocr-portable-result/v1', 'bundle_sha256': bundle_hash,
              'scope': 'application microbenchmark; not formal framework acceptance',
              'rounds': summaries, 'all_integrity_ok': all(s['integrity_ok'] for s in summaries),
              'all_operational_pass': all(s['operational_pass'] for s in summaries),
              'steady_state_stable': stability, 'all_steady_state_stable': all(stability.values()),
              'quality_status': 'pending central scoring; operational_pass does not mean accuracy pass',
              'finished_epoch': time.time()}
    save(output / 'benchmark-result.json', report)
    health_check(client)
    return 0 if report['all_integrity_ok'] else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--endpoint', default='http://127.0.0.1:8013')
    parser.add_argument('--model', default='MiniCPM-OCR-FlagOS')
    parser.add_argument('--output')
    parser.add_argument('--label', default='unspecified')
    parser.add_argument('--service-evidence')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not args.dry_run and not args.output:
        parser.error('--output required for measured execution')
    return execute(args)


if __name__ == '__main__':
    raise SystemExit(main())
