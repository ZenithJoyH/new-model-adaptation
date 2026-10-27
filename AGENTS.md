# Model Adaptation Instructions

This repository supports model bring-up and inference optimization for an exact
model, hardware platform and framework profile. English instructions are for
agents; [AGENTS.zh-CN.md](AGENTS.zh-CN.md) is the human-readable Chinese version.

## Scope and boundaries

- Execute only the work requested by the user. Local documentation, code review
  and repository maintenance do not imply remote execution or a new adaptation.
  Inventory membership is not authorization to operate every listed host.
- Keep model records limited to verified adaptation work. Preserve unrelated
  changes; do not add chat, unrelated administration, raw logs, caches or one-off
  scripts to model directories. Commit, push or create PRs only when requested.
- Before remote writes, establish the exact hosts and approved absolute work
  roots; verify each container mapping. Product changes belong only in the
  selected profile's verified writable source tree. Undeclared sources remain
  read-only; `vllm-plugin-fl` keeps vLLM read-only.
- Modify the verified container-installed FlagOS components directly, including
  ordinary package installations and editable sources; never select another copy
  or version through `PYTHONPATH`. Follow the profile's writable component list.
- Keep code changes PR-ready and scoped to a verified adaptation need. Before
  editing, bound the affected components/files/symbols and tests; justify additions
  and deletions, exclude unrelated refactors, and review each final diff hunk.
  For Plugin, FlagGems and FlagGems-vllm under `vllm-plugin-fl`, apply the
  [contribution policy](docs/plugin-contribution-policy.md) to every changed component.
- Final service launchers contain only necessary startup commands/settings.
  Omit unnecessary cache-directory environment overrides. Prepare the minimal
  `start-model.sh` before service acceptance and reuse the same script for sanity,
  accuracy, performance and delivery; only performance switches prefix caching
  off, while normal/accuracy startup keeps it on. Follow the
  [shared launcher contract](docs/remote-operations.md#shared-service-launcher).
  Required code, configuration and scripts must survive image packaging at
  container paths; a host bind mount is not evidence of inclusion in the image.
- The adaptation container must remain running. Only the current task's assigned
  inference service/processes may be stopped or restarted within adaptation.
  Deletion, replacement of externally owned configuration, host reboot and
  stopping unrelated services require explicit user confirmation.
- Keep connection details in the operator's SSH configuration. Do not commit
  secrets, weights, complete logs or bulky benchmark artifacts. Preserve command
  approvals and host-key verification; never bypass execution restrictions.
- Report only verified results for the exact scope. Missing, stale or inaccessible
  evidence cannot support a pass. Preserve failures and untested limitations.
- Respect `framework.yml control.mode`. Record human takeover and stop subsequent
  Agent mutations for that workspace. Inspect existing processes before resuming,
  retain human changes and accept their evidence through the same validators.
  Follow [human collaboration](docs/human-collaboration.md).

## Required reading by task

Read the applicable entry before acting. Linked policies are mandatory within
their scope; moving them out of this file does not relax their requirements.
Load unrelated workflows only if the user expands the task.

| Requested work | Required entry |
| --- | --- |
| Local documentation, code review or control-tool maintenance | Relevant files and their tests/contracts; use the rows below only if their scope applies. |
| Adaptation completion handoff or a standalone deployment guide | [Deployment guide Skill](skills/adaptation-deployment-guide/SKILL.md) and its bundled English template. |
| Remote checks/changes, or inventory, group variables, Ansible entrypoint or playbook maintenance | [Remote operations Skill](skills/remote-operations/SKILL.md), then its linked policy. |
| Any selected model-adaptation phase | [Adaptation policy](docs/adaptation-policy.md), selected profile's workflow/acceptance documents, then [detailed workflow](docs/model-adaptation-workflow.md). |
| Adaptation involving remote work | Also read the remote operations Skill before the first remote action. |
| Accuracy/performance evaluation | Also read [project contract](docs/skills-project-contract.md) and its repository-local Skill; select an explicit operation. |
| Recoverable long-running execution | Also read [execution journal](docs/agent-execution.md). |
| Framework implementation or PR review | Also read the target source guidance; for `vllm-plugin-fl`, [plugin contribution policy](docs/plugin-contribution-policy.md). |

The remote Skill is a repository-local entry read by path. A natural-language
request naming the hosts and intended operation is sufficient; no global Skill
installation is required. A local-only task does not activate remote checks.

## Adaptation essentials

- Select phases by number or name: architecture (1), environment (2), adaptation
  (3), acceptance (4), retrospective (5). Run only selected phases, in that order.
  Inspect unselected prerequisites without executing or rewriting them.
- Select the framework profile before framework-specific work; phases 2–5 also
  require exact host aliases. Draft/incomplete profiles allow architecture and
  read-only discovery only. Experimental profiles allow declared validation but
  cannot complete formal acceptance or reach `optimized`.
- Use each profile's own implementation and acceptance steps. Do not apply vLLM
  service gates to Torch-FL Python API work. Profiles cannot weaken shared rules.
- Keep architecture and inference-chain analyses in Chinese. Local environment,
  adaptation and acceptance directories contain concise Markdown records only;
  executable process artifacts and native evidence stay in approved remote roots.
  Full layout, evidence, experience-reuse and completion rules are in the policies.
- For vLLM profiles, try `full` → `full-and-piecewise` → `decode-full` → `piecewise`.
  Descend one level only after documented diagnosis/remediation and an unresolved
  blocker at each preceding level. Optimize measured performance, not mode names;
  bind later acceptance and the launcher to the final verified per-host choice.
  Accuracy, performance, final launcher and summary requirements still apply;
  one successful check does not establish complete adaptation.
- Verify work before updating `framework.yml` (or legacy `platform.yml`).
  Use `./scripts/audit-workspace` for local layout checks; its warnings do not
  prove remote success. Read the adaptation policy before using legacy gates.
- After each completed adaptation, invoke the repository-local
  [deployment guide Skill](skills/adaptation-deployment-guide/SKILL.md) to write
  English `acceptance/deployment-guide.md` in its local framework workspace.
  It is also independently callable; keep its template inside the Skill.
  Retain weight-download instructions for readers without executing downloads.
  This handoff document does not replace acceptance evidence or run unselected phases.
- New workspaces pin the [v2 evidence contract](docs/evidence-contract-v2.md).
  Upgrade existing contracts explicitly and preserve historical results.
  `optimized` requires frozen performance targets as well as valid measurements.
