#!/usr/bin/env python3
"""Score an authorized complete GPQA invocation offline; never issue model requests."""
from pathlib import Path
import argparse
import hashlib
import json
import os

from gpqa_recovery_contract import (COUNT, TASK, LocalArtifacts, digest,
                                    recovery_inputs, require)
from llmrun import (configure_environment, create_run_dir, load_config,
                    write_acceptance_report)
from acceptance_contract import metric_errors, validate_formal_config


def reference(path):
    return {"path": str(path), "sha256": digest(path)}


def native_scores(data):
    """Use the installed original task's actual filters and metric functions."""
    from lm_eval.api.instance import Instance
    from lm_eval.tasks import get_task_dict

    source_files = dict(data["generation"]["source_files"])
    source_files.update(data["targets"]["source_files"])
    for name, sha in source_files.items():
        require(digest(name) == sha, "Installed evaluator source changed: " + name)
    task = get_task_dict([TASK])[TASK]
    docs = list(task.eval_docs)
    require(len(docs) == COUNT, "Native task no longer contains 198 documents")
    require(task.get_config("filter_list") == data["targets"]["filter_list"], "Native filter configuration changed")
    require(task.get_config("metric_list") == data["targets"]["metric_list"], "Native metric configuration changed")
    instances = []
    for row, doc, audited in zip(data["rows"], docs, data["targets"]["items"]):
        prompt = json.loads(row["arguments"][0])[0]["content"]
        require(task.doc_to_text(doc) == prompt and task.doc_to_target(doc) == row["target"], "Native prompt/target changed")
        require(hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == audited["doc_sha256"], "Native document changed")
        raw = row["raw_resps"][0][0]
        instances.append(Instance(request_type="generate_until", doc=doc,
                                  arguments=tuple(row["arguments"]), idx=0,
                                  metadata=(TASK, row["doc_id"], 1),
                                  resps=["" if raw is None else raw]))
    for ensemble in task._filters:
        ensemble.apply(instances)
    metrics = {}
    for row, instance, doc in zip(data["rows"], instances, docs):
        row["filtered_resps"] = dict(instance.filtered_resps)
        require(instance.filtered_resps["strict-match"] == row["strict_answer"], "Original native strict extraction disagrees")
        for name, filtered in instance.filtered_resps.items():
            score = task.process_results(doc, [filtered])["exact_match"]
            require(score in (0, 1), "Unexpected native exact-match result")
            if name == "strict-match":
                require(score == row["exact_match,strict-match"], "Native selected metric disagrees")
            metrics.setdefault("exact_match," + name, []).append(score)
    return {name: sum(values) / COUNT for name, values in metrics.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--run", action="store_true", help="emit a new offline recovery report after verifying the original terminal invocation")
    args = parser.parse_args()
    path = Path(args.config).resolve(strict=True)
    raw = json.loads(path.read_text())
    require(not validate_formal_config(raw, require_formal=True), "Invalid formal configuration")
    reader = LocalArtifacts(args.artifact_root)
    data = recovery_inputs(raw, reader)
    cfg = load_config(path)
    configure_environment(cfg)
    os.environ["HF_EVALUATE_OFFLINE"] = "1"
    values = native_scores(data)
    if not args.run:
        print(json.dumps({"status": "ready", "operation": "score-existing-run", "requests_sent": 0,
                          "samples": COUNT, "truncated_empty_content": data["proof"]["truncated_empty_content"]}))
        return
    directory = create_run_dir(cfg)
    attempt = directory / TASK / "attempt-1"
    attempt.mkdir(parents=True, exist_ok=False)
    samples = attempt / ("samples_" + TASK + "_recovered.jsonl")
    with samples.open("x") as stream:
        for row in data["rows"]:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    result = attempt / "results_gpqa_recovered.json"
    with result.open("x") as stream:
        json.dump({"results": {TASK: values}, "n-samples": {TASK: {"original": COUNT, "effective": COUNT}},
                   "operation": "score-existing-run", "inference_run_id": data["source"]["run_id"],
                   "requests_sent": 0}, stream, indent=2)
    proof = dict(data["proof"])
    proof.update(contract_sha256=digest(Path(__file__).with_name("gpqa_recovery_contract.py")),
                 producer_sha256=digest(__file__), native_evaluator_source_hashes=data["targets"]["source_files"])
    proof_path = directory / "recovery-proof.json"
    with proof_path.open("x") as stream:
        json.dump(proof, stream, indent=2)
    errors = metric_errors(raw, TASK, values)
    attempts = {TASK: [{"attempt": 1, "output_dir": str(attempt), "returncode": 0,
                        "status": "failed" if errors else "passed", "errors": errors,
                        "operation": "score-existing-run", "requests_sent": 0,
                        "recovery_proof": reference(proof_path)}]}
    passed = write_acceptance_report(cfg, directory, [TASK] if errors else [], attempts, [])
    print(json.dumps({"status": "passed" if passed else "failed", "operation": "score-existing-run",
                      "requests_sent": 0, "report": str(directory / "acceptance-result.json"),
                      "strict_correct": proof["strict_correct"], "samples": COUNT}))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
