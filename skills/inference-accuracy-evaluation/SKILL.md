---
name: inference-accuracy-evaluation
description: Execute the explicitly selected accuracy operation with this model-adaptation project's framework profile, maintained native runner, and evidence contract.
---

# Model adaptation accuracy

This repository-local entrypoint has capability ID `adaptation/accuracy` and the
interface in [interface.json](interface.json). Its legacy directory name is not
an alias for the Hub package. Load this exact path; do not substitute a global
namesake or dynamically read a sibling checkout.

Read [the project contract](references/project-contract.md) and the selected
framework profile before running anything. The contract specifies methods,
concurrency, cache state, native commands, output paths and verification.

Require the caller to explicitly select one of: `service-sanity`, `hard-case`, `formal-full`, `score-existing-run`, `gate-check`.
Return `incomplete` for missing or unsupported selection. Do not choose another
operation, broaden the selected stage, or invoke another Skill. Return missing
prerequisites and suggested next actions for the calling Agent to decide.

Before execution, record the exact Skill bundle fingerprint using
`python3 scripts/skill_bundle.py inspect --skill-dir <absolute-local-skill-directory> --capability-id adaptation/accuracy --selection <explicit-operation> --interface-version 1.0.0 --result-contract adaptation-native-accuracy/v1`
from the project root. Record the framework, model/platform/Hosts, current service
identity and frozen request/measurement configuration alongside it.

Use only the runner and native receipts supported by the selected framework.
For vllm-plugin-fl, follow the contract's dry-run/preflight, measured-run and
`adapt-model --check-only --verify-records` path. A public Hub result or a log line
cannot replace these native receipts. Torch-FL experimental device/operator/eager
checks follow their own profile and do not imply formal service acceptance.

`score-existing-run` is limited to explicitly user-authorized recovery of the
original complete GPQA Diamond198 invocation whose native scorer rejected a
length-truncated null content or demonstrably normalized it to a timeout and
excluded it from the aggregate denominator. Use `test/Accuracy_test/recover_gpqa.py`; its
default is offline preflight, and `--run` creates a separate report. Preserve the
original terminal report and raw responses, including a native passed report with
an incorrect denominator. No inference requests, response-cache
edits, retries or dropped samples are permitted. A later explicit user threshold
change must be frozen separately in `threshold_override`; preserve the original
configuration and change only the authorized minimum. Unknown
nulls, incomplete provenance or changed data/parameters remain failures. The
framework gate validates the explicit recovery policy and every original score;
ordinary `formal-full` empty-response rejection is unchanged.

When a long operation needs a recoverable control record, use
[the execution journal](../../docs/agent-execution.md). It wraps existing checks
and preserves context; it does not launch work or change workflow status. Its
supported completion gates are narrower than this Skill's complete mode list;
unsupported checks return `incomplete`.

Return `passed`, `failed`, or `incomplete` for the selected operation and exact
scope, with native evidence paths and hashes. A measurement or basic check is
not complete model adaptation.
