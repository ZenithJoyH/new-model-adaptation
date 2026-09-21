---
name: inference-performance-evaluation
description: Execute the explicitly selected performance operation with this model-adaptation project's framework profile, maintained native runner, and evidence contract.
---

# Model adaptation performance

This repository-local entrypoint has capability ID `adaptation/performance` and the
interface in [interface.json](interface.json). Its legacy directory name is not
an alias for the Hub package. Load this exact path; do not substitute a global
namesake or dynamically read a sibling checkout.

Read [the project contract](references/project-contract.md) and the selected
framework profile before running anything. The contract specifies methods,
concurrency, cache state, native commands, output paths and verification.

Require the caller to explicitly select one of: `single-scenario`, `full-suite`.
Return `incomplete` for missing or unsupported selection. Do not choose another
operation, broaden the selected stage, or invoke another Skill. Return missing
prerequisites and suggested next actions for the calling Agent to decide.

Before execution, record the exact Skill bundle fingerprint using
`python3 scripts/skill_bundle.py inspect --skill-dir <absolute-local-skill-directory> --capability-id adaptation/performance --selection <explicit-operation> --interface-version 1.0.0 --result-contract adaptation-native-performance/v1`
from the project root. Record the framework, model/platform/Hosts, current service
identity and frozen request/measurement configuration alongside it.

Use only the runner and native receipts supported by the selected framework.
For vllm-plugin-fl, follow the contract's dry-run/preflight, measured-run and
`adapt-model --check-only --verify-records` path. A public Hub result or a log line
cannot replace these native receipts. Torch-FL experimental device/operator/eager
checks follow their own profile and do not imply formal service acceptance.

When a long operation needs a recoverable control record, use
[the execution journal](../../docs/agent-execution.md). It wraps existing checks
and preserves context; it does not launch work or change workflow status. Its
supported completion gates are narrower than this Skill's complete mode list;
unsupported checks return `incomplete`.

Return `passed`, `failed`, or `incomplete` for the selected operation and exact
scope, with native evidence paths and hashes. A measurement or basic check is
not complete model adaptation.
