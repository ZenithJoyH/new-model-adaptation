---
name: inference-performance-evaluation
description: Orchestrate baseline, targeted, checkpoint, and formal no-profiler performance measurements for LLM adaptation and end-to-end inference optimization. Use to establish a performance baseline, test one optimization candidate, recheck an affected scenario set, or validate a frozen final graph service after an exact accuracy gate; use profiling only as a separate diagnostic activity.
---

# Inference Performance Evaluation

Select the smallest valid performance test, use the project's maintained
toolchain, and bind the result to the exact service, workload, scenario, and
change. This Skill is an orchestrator; never create another benchmark runner.

The mode names, trigger semantics, three-state result, and report fields are a
cross-project interface shared with the related end-to-end inference-optimization
project. Read [the project contract](references/project-contract.md) before acting;
it defines the local runners, acceptance order, paths, and evidence schema.

## Select one mode

| Mode | Trigger | Minimum scope | Supported conclusion |
|---|---|---|---|
| `baseline` | A correct new service/scenario has no comparable baseline | Freeze and measure the acceptance set or named scenario set | Baseline facts for measured scenarios only |
| `targeted` | Testing one optimization hypothesis | Directly affected scenarios plus a cheap adjacent/fallback/stage sentinel when spillover is possible | Local result for listed scenarios only |
| `checkpoint` | Several changes are retained, the hotspot moves, or a shared mechanism changes | Every affected scenario under one frozen contract | Stage result for the affected set |
| `formal` | The final candidate is frozen and has an exact current accuracy gate | Pre-frozen final acceptance set on the accepted graph service | Formal performance for the contracted scope only |

If the mode is not explicit, infer the smallest sufficient mode. State the mode,
scenario set, omitted scope, and conclusion boundary before execution.

## Freeze the measurement contract

Before traffic, record:

- mode, change/experiment IDs, scenario IDs, target/sentinel roles, and omitted
  acceptance scenarios;
- model/tokenizer, platform, Host, hardware/topology, container, service instance,
  engine, Plugin/FlagGems revisions, graph mode, launch configuration, client and
  endpoint identity;
- input/output lengths, EOS/sampling, concurrency or arrival pattern, request
  count, seed, timeout, warmup, repetitions, metrics, guards, thresholds/SLO, and
  stop conditions;
- unique remote run directory and required evidence paths/hashes.

Use a matching baseline for reduced requests, repetitions, or scenarios. Never
compare a reduced candidate with an incompatible historical summary. Record
prefix-cache and other cache state as workload variables; only force a value when
the project contract or an explicit experiment requires it.

## Execute and validate

1. Confirm correctness prerequisites and current service identity. Inspect the
   dry-run command before sending requests.
2. Invoke only the project-maintained entry for the engine and purpose, with a
   unique run ID and no overwrite of existing evidence.
3. Validate request and success counts, token counts, context budget, warmup,
   repetitions, finite metrics, native result schema, current service/client
   identity, and artifact hashes.
4. For comparisons, evaluate only pre-frozen primary metrics, guards, SLOs, and
   variability. Change one material variable at a time when attributing impact.
5. Return `passed`, `failed`, or `incomplete`; never cherry-pick rounds, scenarios,
   or metrics.

Keep the result `incomplete` when the client is the bottleneck, identity or cache
state is unproven, workloads differ, artifacts are partial, warmup is unstable,
repetitions are insufficient, or drift prevents attribution.

Profiling is diagnostic and separate. Do not mix profiler-on timings into
baseline, candidate, checkpoint, or formal no-profiler conclusions. After
profiling, return to `targeted` or `checkpoint` to verify end-to-end impact.

## Formal performance

1. Invoke `inference-accuracy-evaluation` in `gate-check` mode against the frozen
   candidate and fresh service facts. If it does not pass, do not send or claim
   formal performance traffic. Request `formal-gate` only when allowed by the
   user's selected scope.
2. Run the pre-frozen final scenario set on the same accepted graph configuration
   through the project's canonical performance entry.
3. Validate complete raw artifacts, then export and validate the project-native
   formal performance receipt.
4. Limit the conclusion to the contracted model, platform, Host/topology, service
   configuration, client, and scenario set. Capacity or endurance claims require
   their own sustained-load contract.

## Report

Return a compact record containing:

- mode, change/experiment IDs, scenario IDs and target/sentinel roles;
- service/source identities and frozen measurement contract;
- plan/contract evidence and artifact/receipt paths with required hashes;
- `passed`, `failed`, or `incomplete`;
- primary and guard metrics, comparisons when valid, and omitted/invalid evidence;
- conclusion boundary, limitations, and next performance trigger.

Diagnostic timing, raw CSV, a Markdown pass label, or a historical report is not
a formal performance receipt.
