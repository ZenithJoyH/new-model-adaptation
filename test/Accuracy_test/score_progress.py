#!/usr/bin/env python3
"""Report interim GPQA scores from an lm-eval SQLite response cache."""

import argparse
import hashlib
import json
import pickletools
import random
import re
import sqlite3
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional


STRICT_PATTERN = re.compile(
    r"answer is[\s*]*[\(\[]?([ABCDEFGHIJ])[\)\]]?[\s*]*[.\s]"
)
PRIMARY_FLEXIBLE_PATTERN = re.compile(r"(\([A-Z]\))")
CACHE_SCHEMA = "flageval-gpqa-v1-top-k-numeric"


def log(message: str, output_file: Optional[Path] = None) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [SCORE] {message}"
    print(line, flush=True)
    if output_file is not None:
        with output_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def parse_scalar(value: str):
    value = value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() == "none":
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def generation_kwargs(config_value: str) -> Dict:
    # Preserve the task YAML's insertion order because lm-eval includes the
    # serialized dict in its cache key.
    kwargs = {
        "until": ["</s>"],
        "temperature": 0.0,
        "do_sample": False,
        "max_gen_toks": 18000,
    }
    for item in filter(None, (part.strip() for part in config_value.split(","))):
        if "=" not in item:
            raise ValueError(f"Invalid gen_kwargs item: {item!r}")
        key, value = item.split("=", 1)
        kwargs[key.strip()] = parse_scalar(value)
    return kwargs


def preprocess(text: Optional[str]) -> str:
    if text is None:
        return " "
    text = text.strip().replace(" [title]", ". ")
    text = re.sub(r"\[.*?\]", "", text)
    return text.replace("  ", " ")


def build_prompt(question: str, choices: List[str]) -> str:
    choices_text = "\n".join(
        f"({chr(65 + index)}) {choice}" for index, choice in enumerate(choices)
    )
    return (
        "Given the following question and four candidate answers (A, B, C and D), "
        "choose the best answer.\n\n"
        f"Question: {question}\nChoices:\n{choices_text}\n\n"
        "- For simple problems:\nDirectly provide the answer with minimal explanation.\n\n"
        "- For complex problems:\nUse this step-by-step format:\n"
        "## Step 1: [Concise description]\n[Brief explanation]\n"
        "## Step 2: [Concise description]\n[Brief explanation]\n\n"
        "Regardless of the approach, always conclude with:\n"
        "The best answer is [the_answer_letter].\n"
        "where the [the_answer_letter] is one of A, B, C or D.\n\n"
        "Let's think step by step."
    )


def build_answer_map(cfg: Dict) -> Dict[str, Dict]:
    task = cfg.get("task") or (cfg.get("tasks") or [""])[0]
    if task != "gpqa_diamond_generative_cot":
        raise ValueError(f"Interim scoring currently supports gpqa_diamond_generative_cot, not {task!r}")
    if cfg.get("progress_score_cache_schema", CACHE_SCHEMA) != CACHE_SCHEMA:
        raise ValueError("Unsupported progress-score cache schema; verify the pinned evaluator before adding an adapter")
    from datasets import load_dataset

    dataset = load_dataset(
        cfg.get("dataset_path", "Idavidrein/gpqa"),
        cfg.get("dataset_name", "gpqa_diamond"),
        split=cfg.get("dataset_split", "train"),
        cache_dir=cfg.get("hf_datasets_cache", "/root/.cache/huggingface/datasets"),
    )
    gen_kwargs = generation_kwargs(cfg.get("gen_kwargs", ""))
    answer_map: Dict[str, Dict] = {}
    limit = int(cfg.get("limit", 0))
    docs = dataset if limit <= 0 else dataset.select(range(min(limit, len(dataset))))
    for doc_id, doc in enumerate(docs):
        correct = preprocess(doc["Correct Answer"])
        choices = [
            preprocess(doc["Incorrect Answer 1"]),
            preprocess(doc["Incorrect Answer 2"]),
            preprocess(doc["Incorrect Answer 3"]),
            correct,
        ]
        seed = int(hashlib.md5(doc["Question"].encode()).hexdigest(), 16) % (2**32)
        random.Random(seed).shuffle(choices)
        target = chr(65 + choices.index(correct))
        prompt = build_prompt(doc["Question"], choices)
        chat = json.dumps([{"role": "user", "content": prompt}], ensure_ascii=False)
        for key in cache_keys(chat, gen_kwargs):
            answer_map[key] = {"doc_id": doc_id, "target": target, "choices": choices}
    return answer_map


def cache_keys(chat: str, gen_kwargs: Dict) -> List[str]:
    """Two verified FlagEval encodings, not a general numeric coercion.

    The pinned GPQA evaluator has emitted top_k=-1 as both int and float.
    Probe exact keys for these encodings without changing requests or the DB.
    Unrecognized task/prompt/serialization changes remain visibly unsupported.
    """
    variants = [gen_kwargs]
    if type(gen_kwargs.get("top_k")) in (int, float) and gen_kwargs["top_k"] == -1:
        variants = [dict(gen_kwargs, top_k=-1), dict(gen_kwargs, top_k=-1.0)]
    return list(dict.fromkeys(hashlib.sha256(json.dumps(
        ["generate_until", [chat], value]).encode("utf-8")).hexdigest() for value in variants))


def safe_pickle_string(blob: bytes) -> Optional[str]:
    """Extract a cached string without executing pickle opcodes."""
    strings_found = []
    try:
        for opcode, argument, _position in pickletools.genops(blob):
            if opcode.name in {"SHORT_BINUNICODE", "BINUNICODE", "UNICODE", "STRING"}:
                strings_found.append(str(argument))
    except Exception:
        return None
    return strings_found[0] if len(strings_found) == 1 else None


def normalize_exact(value: str) -> str:
    value = value.lower()
    return "".join(char for char in value if not unicodedata.category(char).startswith("P"))


def strict_extract(response: str) -> str:
    matches = STRICT_PATTERN.findall(response)
    return matches[-1].strip() if matches else "[invalid]"


def flexible_extract(response: str, choices: List[str]) -> str:
    matches = PRIMARY_FLEXIBLE_PATTERN.findall(response)
    if matches:
        return matches[-1].strip()

    def clean(value: str) -> str:
        value = value.lower()
        return "".join(char for char in value if not unicodedata.category(char).startswith("P"))

    cleaned_response = clean(response)
    choice_to_alpha = {}
    choice_patterns = []
    for index, choice in enumerate(choices):
        cleaned_choice = clean(choice.strip())
        if cleaned_choice:
            choice_patterns.append(re.escape(cleaned_choice))
            choice_to_alpha[cleaned_choice] = f"({chr(65 + index)})"
    if choice_patterns:
        choice_matches = re.compile("|".join(choice_patterns)).findall(cleaned_response)
        if choice_matches:
            return choice_to_alpha[choice_matches[-1]]
    bare = re.findall(r":[\s]*([A-D])", response)
    return f"({bare[-1]})" if bare else "[invalid]"


def read_scores(cache_db: Path, answer_map: Dict[str, Dict]) -> Dict[str, float]:
    result = {"completed": 0, "matched": 0, "timeouts": 0, "strict": 0, "flexible": 0,
              "unmatched": 0, "duplicate_docs": 0}
    if not cache_db.is_file():
        return result
    try:
        connection = sqlite3.connect(f"file:{cache_db}?mode=ro", uri=True, timeout=5)
        try:
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute('SELECT key, value FROM "unnamed"').fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        result["unavailable"] = f"cache read failed: {type(exc).__name__}"
        return result
    result["completed"] = len(rows)
    seen_docs = set()
    for key, blob in rows:
        info = answer_map.get(key)
        if info is None:
            result["unmatched"] += 1
            continue
        response = safe_pickle_string(blob)
        if response is None:
            result["unmatched"] += 1
            continue
        if info["doc_id"] in seen_docs:
            result["duplicate_docs"] += 1
            continue
        seen_docs.add(info["doc_id"])
        result["matched"] += 1
        if response == "<TIMEOUT>":
            result["timeouts"] += 1
        target = info["target"]
        if normalize_exact(strict_extract(response)) == normalize_exact(target):
            result["strict"] += 1
        if normalize_exact(flexible_extract(response, info["choices"])) == normalize_exact(target):
            result["flexible"] += 1
    return result


def format_score(stats: Dict[str, float], total: int) -> str:
    matched = int(stats["matched"])
    if stats.get("unavailable") or stats.get("unmatched") or stats.get("duplicate_docs"):
        return (f"UNAVAILABLE: cache/schema mismatch or unreadable cache; completed={stats['completed']}, "
                f"matched={matched}, unmatched={stats.get('unmatched', 0)}, "
                f"duplicate_docs={stats.get('duplicate_docs', 0)}; "
                f"detail={stats.get('unavailable', 'verify the pinned evaluator/request schema')}. "
                "This is not an accuracy score; use final lm-eval artifacts.")
    if not matched:
        return f"PENDING: completed={int(stats['completed'])}/{total}, matched=0; no scored responses yet"
    strict_pct = 100.0 * stats["strict"] / matched if matched else 0.0
    flexible_pct = 100.0 * stats["flexible"] / matched if matched else 0.0
    return (
        f"completed={int(stats['completed'])}/{total}, matched={matched}, "
        f"timeouts={int(stats['timeouts'])}, "
        f"strict={int(stats['strict'])}/{matched} ({strict_pct:.2f}%), "
        f"flexible={int(stats['flexible'])}/{matched} ({flexible_pct:.2f}%)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--cache-db", required=True)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    output_file = Path(args.output) if args.output else None
    try:
        answer_map = build_answer_map(cfg)
    except Exception as exc:
        log(f"UNAVAILABLE: cannot initialize progress-score schema ({type(exc).__name__}: {exc}); not an accuracy score", output_file)
        raise SystemExit(2) from exc
    total = len({info["doc_id"] for info in answer_map.values()})
    last_bucket = -1
    while True:
        stats = read_scores(Path(args.cache_db), answer_map)
        bucket = int(stats["completed"]) // max(1, args.interval)
        if args.once or bucket > last_bucket:
            log(format_score(stats, total), output_file)
            last_bucket = bucket
        if args.once:
            if stats.get("unavailable") or stats.get("unmatched") or stats.get("duplicate_docs"):
                raise SystemExit(2)
            return
        if args.pid and not Path(f"/proc/{args.pid}").exists():
            stats = read_scores(Path(args.cache_db), answer_map)
            log("final: " + format_score(stats, total), output_file)
            return
        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    main()
