# Remote Operations Instructions

## Scope

- This repository manages every concrete host alias from the operator's SSH
  configuration through `inventory/hosts.yml`. Keep the `managed` group in sync
  when SSH aliases are added or removed.
- Use Ansible for repeatable or multi-host changes. Direct SSH is acceptable for
  focused, read-only diagnostics.
- When Codex invokes Ansible, set the working directory to the repository root
  and use the exact relative entry points `./scripts/ansible`,
  `./scripts/playbook`, `./scripts/connectivity-check`,
  `./scripts/accelerator-check`, `./scripts/health-check`, or
  `./scripts/inventory`. Project rules run the four hardened read-only wrappers
  outside the sandbox automatically and prompt for the two generic wrappers,
  because Ansible's local RPC requires a Unix socket. Do not bypass these rules
  with `.venv/bin/*`, `bash`/`sh` wrappers, absolute paths, or compound commands.
- Do not hardcode IP addresses, SSH users, bastion details, passwords, tokens,
  or private-key paths. SSH connection details belong in the operator's
  `~/.ssh/config`.

## Safety

- Treat status checks, log inspection, inventory listing, disk checks, process
  inspection, and version queries as read-only operations.
- Before changing a server, inspect the current state and identify the exact
  target hosts.
- A mutating playbook must be run against one host first. Verify that host before
  expanding to a group. Use `serial: 1` for changes across any hardware group.
- Use `--check --diff` when the involved modules support check mode.
- Never use broad destructive commands, disable SSH host-key checking, overwrite
  an unexpected file, or suppress a failed verification.
- Require explicit user confirmation before deleting data, replacing an existing
  configuration owned outside this repository, rebooting, or stopping a service
  outside the active model-adaptation scope. During an active adaptation, the
  agent may stop or restart an inference service or related process that it
  started for the current task or that the user explicitly assigned to the
  adaptation, without requesting confirmation each time. The adaptation
  container itself must remain running and must not be stopped, restarted, or
  removed. Resolve the exact service or process first, never affect shared or
  unrelated workloads, and record the reason, command, and verified result.
- Prefer idempotent Ansible modules over shell commands. If a command is needed,
  define `changed_when` and `failed_when` deliberately.

## Accelerator queries

- Never assume all hosts use NVIDIA tools. Use the platform group variables and
  `./scripts/accelerator-check`.
- NVIDIA: `nvidia-smi`.
- Huawei Ascend: `npu-smi info`.
- T-Head PPU: `ppu-smi`.
- MetaX: `mx-smi`.
- Hygon: `hy-smi`; use `hy-smi --showpids` for process details. Use `htop` only
  in an interactive SSH session.
- Moore Threads: `mthreads-gmi`.
- If the configured command is missing, report that condition. Do not silently
  fall back to another vendor's command.

## Model adaptation workspace

The adaptation workspace has two deliberately separate parts:

1. The **remote work directory** is the approved per-host execution area used by
   the adaptation containers and remote commands for runtime configuration,
   temporary diagnostics, runs, caches, and bug reproducers. It is not a source
   checkout or repository mirror.
2. The **local work directory** is this management repository. It contains
   curated model/platform records, reusable control tools, templates, and concise
   evidence references, not a mirror of remote runtime artifacts.

Local records must point to exact remote paths and revisions. Do not copy remote
raw artifacts into the local workspace or treat local records as authorization to
write remotely.

### Remote work directory

- Before any remote write, obtain the exact SSH alias and absolute `host_root`;
  for container work, also verify the absolute `container_root` and its mapping.
  Until then, perform read-only checks only. In `workspace.roots`, record one
  `{host_alias, host_root, container_root}` entry per `target.hosts` member.
  Mappings are container-specific, and configuration alone is not verification.
- Keep every new remote process artifact under the approved root, using these
  ordered names: `01-environment/` for collection and runtime configuration,
  `02-issues/` for one-off diagnosis, `03-acceptance/` for
  evaluation tools/configuration, `04-runs/` for run output, `05-tmp/` and
  `06-cache/` for temporary or implicit writes, and `07-bugs/` for minimal
  operator reproducers. Do not create a source-repository subdirectory or mirror
  under this work root. Product changes belong in the adaptation container's
  existing editable-installed Plugin source tree after its package metadata,
  import path, Git root, revision, and working-tree ownership are verified; do
  not copy or clone that tree into the remote work directory. Keep a reproducer
  in `07-bugs/` and run it through its
  verified container path; do not duplicate it under `/bug`. Only when a required
  tool or upstream workflow specifically needs `/bug` may the same `07-bugs/`
  directory be exposed there through an approved, verified mapping or an explicit
  outside-root exception. Verify the corresponding mapping for every participating
  container; pause if a tool cannot remain inside this boundary.
- Treat directories using the previous numbering as historical evidence. New
  writes and new run plans must use the current names above. Do not rename,
  merge, delete, or rewrite references to an existing remote directory until its
  exact host/container paths, active users, and evidence references have been
  checked and the user has explicitly authorized that migration.
- Before an adaptation can be marked complete, place one final executable model
  launch script at `<host_root>/start-model.sh` for every target host root, with
  the verified container path `<container_root>/start-model.sh`. It must launch
  the final accepted `graph` configuration, keep logs/results under `04-runs/`
  and caches under `06-cache/`, contain no secrets, and refuse to overwrite an
  unrelated running service. Keep the launcher minimal: remove diagnostic,
  profiling, tracing, dump, temporary-path, obsolete workaround, duplicated
  default, experimental tuning, and unrelated model/platform settings unless
  the accepted configuration demonstrably requires them. Every retained explicit
  environment variable and argument must have a documented correctness, safety,
  resource-placement, or reproducibility reason; pinning a default is acceptable
  only when that reason is recorded. Verify its syntax, exact arguments, revisions,
  device allocation, service readiness, and container mapping. Record the host
  and container paths, SHA-256, verification date, and result in the platform
  README and final acceptance summary; do not copy the script into the local
  model directory. The script must never stop, restart, or remove the adaptation
  container.
- Set an explicit `cwd`/`workdir` for every remote command and stop on a failed
  `cd`. Resolve symlinks and bind mounts. Existing external weights, datasets,
  dependencies, and source trees other than the verified editable Plugin source
  and the explicitly authorized FlagGems synchronization are read-only. Do not
  move or duplicate them, change mounts, or stop/restart the adaptation container
  to arrange the workspace. If the Plugin package is not editable-installed or
  its source identity cannot be verified, stop and report the blocker instead of
  creating a replacement checkout under the work root.
### Local work directory

- Keep this repository limited to verified model bring-up, platform validation,
  and inference optimization for an identified model and platform. Exclude
  unrelated administration, package installation, chat, exploratory output, and
  unverified conclusions. Commit or push only when explicitly requested.
- Create models with `./scripts/new-model <model-name>` without overwriting an
  existing directory. Use only platform names `nvidia`, `ppu`, `metax`, `ascend`,
  `mthreads`, and `hygon`.
- Under `models/<model>/<platform>/`, keep only `README.md`, `platform.yml`, and:
  `environment/` for Markdown environment/platform analysis only;
  `adaptation/` for a Markdown-only numbered issue ledger; and `acceptance/` for
  Markdown acceptance plans, result reports, summaries, and retrospectives only.
  Do not create subdirectories or store scripts, playbooks, JSON/YAML configuration,
  raw output, caches, or temporary files in any of these three local directories.
  Keep model-wide material in `architecture-and-inference.md` and `_shared/`;
  common test tools remain in repository `test/`.
- Keep `_shared/` readable and cross-platform: use only a Markdown index and a
  small number of consolidated Markdown analyses. Put raw upstream metadata,
  copied templates, one-off inspectors, JSON/YAML snapshots, and other collection
  artifacts in the approved remote root, not in the local model directory.
- `adaptation/` contains no scripts, playbooks, patches, source/operator code,
  copied tests, raw logs, runtime JSON/YAML, or command output. The editable
  Plugin source tree contains only required product code and maintainable focused
  tests. Put one-off
  process code in remote `02-issues/` or `05-tmp/`, outside plugin, vLLM, and FlagGems,
  and do not commit it. Promote reusable tools to repository `scripts/` only with
  user approval.
- Keep executable process artifacts in the approved remote root: environment
  collectors and runtime configuration in `01-environment/`, one-off diagnosis in
  `02-issues/` or `05-tmp/`, acceptance wrappers/configuration in `03-acceptance/`,
  and raw results in `04-runs/`. Local Markdown records summarize the repeatable
  command and retain exact hosts, remote paths, revisions, engine, image, arguments,
  inputs, date, purpose, and verified result. Preserve the minimum needed evidence
  before remote temporary cleanup.

### Status and completion

- Establish correctness and performance baselines before optimization; change
  one material variable at a time and retain the comparison.
- Before completion, update the platform `README.md` with outcomes, problems,
  causes, solutions, limits, and next steps, and synchronize it with
  `platform.yml`. Verify the root-level remote `start-model.sh` described above;
  file existence alone is not completion evidence. Require minimal inference for `functional`, and recorded
  correctness regression plus performance results for `optimized`.
- Never commit weights, secrets, complete logs, or bulky raw benchmarks.

## Plugin design and PR quality

- Treat plugin changes as maintainable contributions to a multi-model,
  multi-platform framework. Before editing, read the target Plugin source tree's
  design,
  contribution and test guidance, and follow
  [the plugin contribution policy](docs/plugin-contribution-policy.md).
- Explain ownership, existing extension points, interface contracts, alternatives
  and affected callers in the platform environment analysis or relevant numbered
  adaptation issue. Reuse the
  framework's dispatch and registration paths. Scope model semantics to model
  adapters and hardware constraints to vendor/capability paths; do not scatter
  model-name or machine-specific exceptions through shared execution code.
- Preserve existing behavior outside the intended scope. Verify applicable
  shared-model callers, guard miss paths, optional-dependency isolation, and
  eager/graph behavior. Declare unavailable hardware and untested scope honestly;
  do not infer multi-platform support from one successful model run.
- Before completing adaptation and when preparing a PR, review the actual diff
  and record the review in the relevant numbered issue and final acceptance summary. Record
  the confirmed PR base, current HEAD, dirty/untracked changes, inherited work,
  impact matrix, test evidence, workaround exit conditions and unresolved risks.
  Refresh the review after material changes; do not mark adaptation complete
  with unresolved design blockers. Design review and full acceptance are distinct.
- Keep changes cohesive and production-focused. Do not perform unrelated
  refactors, hide failures with broad fallbacks, or commit/push/create PRs merely
  to finish this review; Git and PR actions still require an explicit user request.

## Adaptation experience accumulation and reuse

- Before environment changes, implementation, or acceptance, search
  `docs/troubleshooting/`, relevant retrospectives, and similar model/platform
  issue records. Prior experience is a candidate hypothesis, never automatic
  proof or authorization.
- Match on the complete failure signature and context: symptom order, first
  failing rank/component, model structure, platform, revisions, dtype/shape,
  parallel topology, load, and `eager`/`graph` mode. A shared keyword alone is not
  a match.
- Record each new material problem in the current platform's numbered
  `adaptation/` issue ledger using `templates/adaptation/issue-record.md`. Keep it
  as `hypothesis` until a controlled comparison verifies it; change one material
  variable at a time, preserve before/after evidence, and classify each action as
  diagnostic, workaround, mitigation, or root-cause fix.
- Promote only reusable, verified experience to `docs/troubleshooting/`. A
  knowledge entry must state its signature, applicability and confidence,
  revisions, diagnostic sequence, safe action, stop/rollback conditions,
  verification, performance impact, `eager`/`graph` coverage, and source record.
  Keep secrets, weights, complete logs, and unsupported conclusions out. Audit
  promote/reject/supersede/pending decisions during retrospective.
- When reusing an entry, cite it from the current numbered issue, record the
  similarities and differences, and revalidate it on the current stack. Add the
  result and date; constrain or deprecate the entry when a counterexample appears.
- Known example: for the exact TP signature “`sample_tokens` exceeds 300 seconds,
  rank work sequences diverge, then EngineCore exits on RPC timeout,” follow
  `docs/troubleshooting/distributed-sample-tokens-timeout.md`. Increasing
  `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` is only a controlled diagnostic/mitigation
  when workers remain alive and make progress; stop and inspect the earliest
  failing rank for exceptions, OOM, collective divergence, or deadlock.

## Workflow invocation and phase isolation

- The user may select any phases by number or name: `architecture` (1),
  `environment` (2), `adaptation` (3), `acceptance` (4), and `retrospective` (5).
  Execute only those phases, always in 1-to-5 order. Unselected phases may be
  inspected as prerequisites but must not be executed or rewritten.
- Before a selected phase, run the corresponding `./scripts/adapt-model ...
  --check-only`. Phases 2-5 require exact host aliases. Stop and report the exact
  blocker when prerequisite identity, evidence, status, or freshness is missing
  or inconsistent; never repair it by silently rerunning another phase or merely
  refreshing hashes.
- Acceptance substeps may also be selected individually, but keep their order:
  `execution-mode` → `sanity` → `accuracy` → `performance` → `evidence` →
  `summary`. Execute no unselected substep, and never waive an incomplete earlier
  prerequisite.
- The current `adapt-model` implementation still contains legacy structured-file
  gates. Do not run it in creation mode for platform phases 2 through 5 and do not
  reintroduce its legacy YAML/process files into a compact platform directory.
  Invoke those phases through a natural-language Codex request and use
  `audit-workspace` for local layout checks until the gate is migrated. Step 1
  architecture initialization remains safe.
- Update `platform.yml` only after the selected work is actually verified and
  its evidence is current. Bind phase and acceptance receipts as defined in
  `docs/workflow-guide.md`; record and verify the exact Host set in the environment
  analysis. Formal accuracy requires a passing
  `acceptance-result.json`; formal performance requires the receipt exported by
  `test/perf_test/perf_acceptance.py`, not a Markdown/CSV success label.
- Use `./scripts/audit-workspace` for local structure and historical-state review.
  Its warnings require review and never prove remote success.

## Detailed workflow (required reading)

Before performing any selected architecture, environment, adaptation, acceptance, or
retrospective phase, read [the detailed workflow](docs/model-adaptation-workflow.md)
and apply the selected phases in order. The detailed rules are mandatory; moving
them out of this file does not weaken any safety or acceptance requirement.
See [the execution and evidence guide](docs/workflow-guide.md) for local commands.

## Validation and reporting

- Run `./scripts/inventory` after changing inventory or group variables.
- Run `./scripts/syntax-check` after changing inventory, variables, or playbooks.
- For multi-host work, report one result per host and distinguish unchanged,
  changed, failed, and unreachable hosts.
- Never claim success for a host that was not reached or not verified.
- Use `./scripts/connectivity-check` instead of relying on SSH exit code alone;
  the bastion can return exit code 0 while reporting that an asset was not found.

## Secrets

- Never commit secrets. Use SSH agent/keychain for SSH keys and Ansible Vault or
  an approved secret manager for other credentials.
- Mark secret-bearing Ansible tasks with `no_log: true`.
