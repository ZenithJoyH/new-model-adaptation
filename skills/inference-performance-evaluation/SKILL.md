---
name: inference-performance-evaluation
description: Route performance evaluation requests in this model-adaptation repository to the shared skills-hub capability and the selected framework's project contract.
---

# Project performance adapter

Read [the single project contract](references/project-contract.md) before executing.
This file is a project adapter, not a separate copy of the shared testing method.

Locate the actual installed `skills-hub/skills/inference-performance-evaluation/SKILL.md`
(prefer the sibling skills-hub checkout when available), read that Skill and its
required method references, and record the source revision. Do not create a
second copy or change the shared repository as part of a project-only request.
If unavailable, return incomplete with the missing dependency.

Use the operation supplied by the caller; the project contract maps legacy names.
Do not infer another operation or start unselected phases. The selected framework
must declare the requested capability. Torch-FL experimental device/operator/eager
checks use its own workflow; they are not vLLM/FlagEval formal service acceptance.

User requirements take precedence over stale shared defaults. For this project,
the contract defines concurrency, timeout handling, cache settings and supported
native receipts. If the selected shared implementation cannot express them or
its result schema is unsupported, report incomplete rather than silently swapping
runners or treating incompatible evidence as a pass.

Return passed/failed/incomplete for the selected operation only. A measurement
or basic check is not complete model adaptation.
