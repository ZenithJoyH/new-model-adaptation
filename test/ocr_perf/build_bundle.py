#!/usr/bin/env python3
"""Freeze a small page workload from the already verified OCR reproduction inputs."""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import tarfile

from PIL import Image


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def extract(source, names):
    text = source.read_text()
    nodes = {n.name: n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
    lines = text.splitlines(keepends=True)
    return '\n'.join(''.join(lines[nodes[name].lineno-1:nodes[name].end_lineno]) for name in names)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache', required=True)
    p.add_argument('--results', required=True)
    p.add_argument('--trace', required=True)
    p.add_argument('--gt', required=True)
    p.add_argument('--evalkit', required=True)
    p.add_argument('--model-identity', required=True, help='Verified historical service identity JSON')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    cache, results, evalkit, out = map(Path, (args.cache, args.results, args.evalkit, args.output))
    out.mkdir(parents=True, exist_ok=False)
    for name in ('images', 'layouts', 'reference'):
        (out / name).mkdir()
    gt = json.loads(Path(args.gt).read_text())
    gt_by_id = {Path(g['page_info']['image_path']).stem: g for g in gt}
    source = evalkit / 'minicpmvocr'
    prompts = {}
    exec(compile((source / 'default_prompts.py').read_text(), 'frozen-prompts', 'exec'), prompts)
    prompt_map = prompts['DEFAULT_PROMPT_MAP']
    # These are verbatim evaluation functions, not model/component overrides.
    native_text = ((source / 'markdown_utils.py').read_text() +
                   '\nfrom typing import Dict, List\n' +
                   'INLINE_LATEX_RE = re.compile(r"\\\\\\((.+?)\\\\\\)")\n' +
                   extract(source / 'pipeline.py', ['_normalize_crop_text', '_normalize_and_dedupe_blocks']))
    (out / 'native_postprocess.py').write_text(native_text)
    spec = importlib.util.spec_from_file_location('native_for_build', out / 'native_postprocess.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    candidates, buckets = [], defaultdict(list)
    for path in sorted(results.glob('*.json')):
        result = json.loads(path.read_text())
        page_id = result['image_id']
        if page_id not in gt_by_id:
            continue
        blocks = [b for b in result['crop_blocks'] if b['status'] != 'skipped_no_vlm']
        if not blocks:
            continue
        lang = gt_by_id[page_id]['page_info']['page_attribute']['language']
        if lang not in ('english', 'simplified_chinese'):
            continue
        labels = {b['label'] for b in blocks}
        family = ('formula' if 'display_formula' in labels else 'text') + ('+table' if 'table' in labels else '')
        entry = {'id': page_id, 'language': lang, 'family': family,
                 'baseline_tokens': sum(b.get('output_token_count', 0) for b in blocks),
                 'baseline_requests': len(blocks)}
        candidates.append(entry)
        buckets[lang, family].append(entry)
    selected, interactive, batch = [], [], []
    selection_stats = {}
    for key in sorted(buckets):
        pool = sorted(buckets[key], key=lambda e: (e['baseline_tokens'], e['baseline_requests'], e['id']))
        if len(pool) < 4:
            raise ValueError(f'Stratum too small: {key}')
        selection_stats['/'.join(key)] = {'population': len(pool)}
        for index, quantile in enumerate((.125, .375, .625, .875)):
            entry = dict(pool[min(len(pool)-1, int(len(pool)*quantile))], selection_quantile=quantile)
            selected.append(entry)
            # Vary interactive load quantiles across strata rather than selecting only easy pages.
            if index == (len(selection_stats)-1) % 4:
                interactive.append(entry['id'])
            else:
                batch.append(entry['id'])
    assert len(selected) == 32 and len(interactive) == 8 and len(batch) == 24
    selected_ids = {s['id'] for s in selected}
    warmup = []
    for language in ('english', 'simplified_chinese'):
        pool = sorted((e for e in candidates if e['language'] == language and e['id'] not in selected_ids
                       and e['family'] == 'formula+table'), key=lambda e: (e['baseline_tokens'], e['id']))
        entry = dict(pool[len(pool)//2], selection_quantile=.5, warmup=True)
        warmup.append(entry['id'])
        selected.append(entry)
    # Encode exactly as the native client (PIL RGB -> PNG), then match actual historical requests.
    pages, wanted, image_parameters = [], set(), {}
    baseline_by_id = {}
    for entry in selected:
        page_id = entry['id']
        layout = json.loads((cache / 'layouts' / (page_id + '.json')).read_text())
        baseline = json.loads((results / (page_id + '.json')).read_text())
        baseline_by_id[page_id] = baseline
        # Sanitize legacy machine paths from layout metadata.
        layout.pop('source', None)
        save(out / 'layouts' / (page_id + '.json'), layout)
        (out / 'reference' / (page_id + '.md')).write_text(baseline['markdown'])
        blocks = []
        for index, block in enumerate(layout['blocks']):
            label = block['label']
            cfg = dict(prompt_map['default'], **prompt_map['element_prompts'].get(label, {}))
            item = {'id': index, 'label': label, 'order': block.get('order', 0), 'bbox': block.get('bbox'),
                    'skip': bool(block.get('skip_vlm') or cfg.get('skip'))}
            if not item['skip']:
                if cfg.get('resize_min_side') is not None:
                    raise ValueError('Builder must implement the frozen resize before selecting this config')
                with Image.open(cache / 'crops' / page_id / block['crop_filename']) as im:
                    image = im.convert('RGB')
                    buf = io.BytesIO()
                    image.save(buf, format='PNG')
                raw = buf.getvalue()
                digest = hashlib.sha256(raw).hexdigest()
                image_name = 'images/' + digest + '.png'
                (out / image_name).write_bytes(raw)
                wanted.add(digest)
                item.update(image=image_name, image_sha256=digest, prompt=cfg['prompt'],
                            output_format=cfg['output_format'], expected_max_tokens=cfg['max_new_tokens'],
                            source_crop=block['crop_filename'])
            blocks.append(item)
        pages.append(dict(entry, blocks=blocks))
    # Read original trace once; only retain the selected requests.
    for line in Path(args.trace).open():
        trace = json.loads(line)
        if len(trace.get('image_sha256', [])) != 1 or trace['image_sha256'][0] not in wanted:
            continue
        key = (trace['image_sha256'][0], tuple(trace['text_prompt']), trace['parameters']['max_tokens'])
        value = {'parameters': trace['parameters'], 'response': trace['response']}
        image_parameters[key] = value
    preflight = []
    for page in pages:
        reconstructed = []
        for block in page['blocks']:
            item = {k: block[k] for k in ('label', 'order', 'bbox')}
            if block['skip']:
                item.update(content='', status='skipped_no_vlm')
            else:
                key = (block['image_sha256'], (block['prompt'],), block.pop('expected_max_tokens'))
                trace = image_parameters[key]  # Fail closed on unmatched image/prompt/config.
                parameters = dict(trace['parameters'])
                parameters.pop('model')
                # vLLM 0.24 OpenAPI does not declare this historical field. Freeze the portable
                # protocol without it rather than claiming consistent no-repeat enforcement.
                parameters.pop('no_repeat_ngram_size', None)
                block['parameters'] = parameters
                choice = trace['response']['choices'][0]
                block['baseline_finish_reason'] = choice['finish_reason']
                block['reference_raw_text'] = choice['message']['content']
                block['reference_completion_tokens'] = trace['response']['usage']['completion_tokens']
                text = block['reference_raw_text']
                item.update(content=native.postprocess_content(text, block['output_format'], label=block['label']),
                            inline_formula_mixed=(block['label'] == 'inline_formula' and
                                                  native.has_mixed_inline_formula_content(text)))
            reconstructed.append(item)
        markdown = native.assemble_markdown(native._normalize_and_dedupe_blocks(reconstructed), prompt_map)
        same = markdown == baseline_by_id[page['id']]['markdown']
        preflight.append({'id': page['id'], 'native_markdown_identical': same})
        if not same:
            raise ValueError('Frozen postprocessor differs from native result: ' + page['id'])
    scenarios = [
        {'name': 'interactive', 'page_ids': interactive, 'page_concurrency': 1, 'region_concurrency': 4,
         'per_page_regions': 4, 'slo_seconds': 30},
        {'name': 'batch', 'page_ids': batch, 'page_concurrency': 4, 'region_concurrency': 16,
         'per_page_regions': 4, 'slo_seconds': 60},
        {'name': 'loaded', 'page_ids': batch, 'page_concurrency': 8, 'region_concurrency': 32,
         'per_page_regions': 4, 'slo_seconds': 60}]
    checkpoint = json.loads(Path(args.model_identity).read_text())['checkpoint_files']
    checkpoint_hash = hashlib.sha256(json.dumps(checkpoint, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    manifest = {'schema': 'minicpm-ocr-portable/v1.1', 'selection': '32 measured pages + 2 diagnostic pages',
                'selection_method': '2 languages x 4 formula/table strata x 4 token-load quantiles',
                'selection_stats': selection_stats, 'pages': pages, 'diagnostic_page_ids': warmup,
                'warmup_policy': 'one full scenario workload replay at the same concurrency before measurements',
                'scenarios': scenarios, 'rounds': 2, 'request_timeout_seconds': 300,
                'extra_round': 'scenario throughput ratio > 1.10, at most one additional round',
                'prompt_map': prompt_map,
                'latency_boundary': 'bounded page-worker admission to final Markdown file saved; closed-loop',
                'excluded': ['PDF render', 'layout detection', 'crop extraction', 'accuracy scoring', 'startup'],
                'cache_policy': {'prefix_caching': False, 'mm_processor_cache_gb': 0},
                'historical_parameter_exclusion': 'no_repeat_ngram_size is undeclared in vLLM 0.24 API',
                'source_sha256': {str(f.relative_to(evalkit)): sha(f) for f in
                                  (source / 'markdown_utils.py', source / 'pipeline.py', source / 'default_prompts.py')},
                'official_gt_sha256': sha(args.gt), 'preflight': preflight}
    manifest['checkpoint_files'] = checkpoint
    manifest['checkpoint_identity_sha256'] = checkpoint_hash
    save(out / 'manifest.json', manifest)
    save(out / 'ground_truth.json', [gt_by_id[p['id']] for p in pages if not p.get('warmup')])
    (out / 'SOURCE-NOTICE.txt').write_text(
        'Inputs: user-provided mergedp1_7140_hf5_eval_repro.tar.gz and official OmniDocBench annotations.\n'
        'Official annotations: https://huggingface.co/datasets/opendatalab/OmniDocBench\n'
        'Includes an unmodified subset of cached crops and verbatim evaluation functions.\n'
        'Reference Markdown is historical model output, not ground truth.\n'
        'Original dataset/code terms remain applicable. The supplied reproduction archive did not\n'
        'contain standalone LICENSE/NOTICE files; this package does not grant additional rights.\n')
    for name in ('bench.py', 'README.md', 'compare.py'):
        shutil.copyfile(Path(__file__).with_name(name), out / name)
    inventory = {str(f.relative_to(out)): sha(f) for f in sorted(out.rglob('*'))
                 if f.is_file() and '__pycache__' not in f.parts}
    save(out / 'checksums.json', inventory)
    with tarfile.open(str(out) + '.tar.gz', 'w:gz') as archive:
        for name in sorted(inventory) + ['checksums.json']:
            archive.add(out / name, arcname=out.name + '/' + name, recursive=False)
    print(json.dumps({'bundle': str(out), 'archive_sha256': sha(str(out) + '.tar.gz'),
                      'measured_pages': 32, 'warmup_pages': 2,
                      'measured_requests_two_rounds': sum(2*sum(sum(not b['skip'] for b in p['blocks'])
                         for p in pages if p['id'] in s['page_ids']) for s in scenarios),
                      'strata': selection_stats, 'native_postprocess_preflight_pages': len(preflight)}, indent=2))


if __name__ == '__main__':
    main()
