---
name: inference-accuracy-evaluation
description: Orchestrate layered correctness checks and formal model-accuracy gates for LLM adaptation and end-to-end inference optimization. Use before accepting a performance baseline, after retained inference-affecting changes, for graph-mode C8 sanity, for a formal full accuracy run, or to revalidate an existing accuracy gate before formal performance; do not use as an unrelated generic benchmark suite.
---

# Inference Accuracy Evaluation

Select the smallest valid correctness depth, invoke the project's maintained
evaluation workflow, and bind the result to the exact inference service. This
Skill is an orchestrator; never copy or replace the project's evaluator.

The mode names, trigger semantics, three-state result, and report fields are a
cross-project interface shared with the related end-to-end inference-optimization
project. Read [the project contract](references/project-contract.md) before acting;
it defines the local runners, acceptance order, paths, and evidence schema.

## Select one mode

Choose one mode and record it with the change or experiment IDs it covers:

| Mode | Trigger | Supported conclusion |
|---|---|---|
| `baseline-sanity` | Before accepting a new adaptation/optimization service or its performance baseline | Service-level smoke and C8 correctness/performance sanity only |
| `minimal-regression` | After every retained inference-affecting change | Scoped regression for the changed semantic surface only |
| `formal-gate` | After a high-risk change, after a small batch of retained low-risk changes, or for a final candidate without an exact current gate | Formal full-dataset accuracy for the bound service and contract |
| `gate-check` | Immediately before formal performance or when existing accuracy evidence may be stale | Validity of existing formal evidence; no new accuracy traffic |

Low-risk batching changes only the frequency of `formal-gate`; it never removes
`minimal-regression`. Treat numerical semantics, dtype/quantization, attention or
KV cache, MoE routing, sampling, fusion, algorithms/backends, dispatch, parallel
topology, communication, graph/fallback coverage, or suspicious output as high
risk.

If the mode is not explicit, infer the smallest sufficient mode from the trigger
and state the selection and conclusion boundary before execution.

## Freeze identity and scope

Bind every result to the model/weights, tokenizer, platform, exact Host,
container, service instance, endpoint, engine, Plugin and FlagGems revisions,
launch configuration, execution mode, workload/configuration, and covered change
or experiment IDs. Resolve current runtime facts; similar paths or version labels
do not justify reusing historical evidence.

Record remote artifact paths and hashes according to the project contract. Keep
large, sensitive, or raw evidence remote. Refuse a formal claim when required
identity, configuration, sample, metric, or artifact evidence is missing.

## Baseline sanity and minimal regression

1. Identify the changed semantic surface and a trustworthy reference path or
   expected result.
2. Cover representative and boundary shapes, non-aligned and fallback paths,
   dtype/layout/device constraints, and empty or zero-token cases where relevant.
3. Cover `eager` and graph capture plus at least two replays when the affected
   serving path supports both. Acceptance after execution-mode bring-up uses the
   accepted graph service as defined by the project contract.
4. For request-level changes, run fixed smoke and C8 checks and inspect every
   answer, timeout, error, truncation, malformed output, abnormal repetition, and
   obvious latency/throughput/resource anomaly.
5. Return `passed`, `failed`, or `incomplete`. A scoped or sanity pass is never a
   formal model-accuracy pass.

On failure, stop promotion, preserve the evidence, diagnose or revert, and repeat
the required checks before adding another change.

## Formal gate

1. Require all earlier project-specific acceptance prerequisites and capture the
   current service identity before sending traffic.
2. Use only the project's canonical formal runner and evaluator environment.
3. Freeze the task/dataset provenance, full-sample contract, metric, threshold,
   generation settings, concurrency, timeout policy, and artifact locations.
4. Run the canonical preflight, then the full evaluation. Do not substitute a
   parallel/sharded runner unless the user explicitly selected that design and
   the project contract supports it.
5. Validate process completion, unique sample coverage, response health, metrics,
   thresholds, errors/timeouts/duplicates, effective configuration, service
   identity, and artifact hashes. A score alone is insufficient.
6. Issue only the project-native formal receipt. Keep the result `incomplete` if
   any required binding or artifact cannot be verified.

If a batch of changes fails, freeze the set and isolate the responsible change by
rollback or splitting. Do not loosen the dataset, metric, filters, threshold,
sample count, or evidence requirements instead of diagnosing the failure.

## Gate check and invalidation

`gate-check` is read-only. Validate the existing formal receipt and all bindings
against freshly observed service facts. Do not send evaluation traffic.

A restart that changes service identity, source or configuration change,
weights/tokenizer change, inference-affecting launch change, workload-contract
change, or mismatched artifact hash invalidates the previous gate. Select
`formal-gate` when the candidate lacks an exact current gate; do not silently run
it when the user requested only `gate-check`.

## Report

Return a compact record containing:

- mode and covered change/experiment IDs;
- model, platform, Host, container, service and source identities;
- frozen workload/configuration and checks performed;
- artifact and receipt paths with required hashes;
- `passed`, `failed`, or `incomplete`;
- conclusion boundary and limitations;
- next accuracy trigger and whether formal performance is allowed.

Use `incomplete` rather than upgrading diagnostic, sanity, partial, historical,
or unbound evidence into a formal acceptance claim.
