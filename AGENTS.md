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

Every adaptation has three identity dimensions: **model**, **hardware platform**,
and **framework profile**. Select an active or experimental profile from `framework-profiles/`
before any framework-specific environment change, implementation, or acceptance.
Existing records directly under `models/<model>/<platform>/` are legacy records
with the implicit `vllm-plugin-fl` profile; do not bulk-migrate them. A framework
with a draft/incomplete profile is limited to architecture analysis and
read-only environment discovery. Experimental profiles allow their declared implementation
and validation steps, but cannot pass complete formal acceptance or reach optimized. A profile may tighten, but never weaken, the
repository safety and evidence rules.

The adaptation workspace has two deliberately separate parts:

1. The **remote work directory** is the approved per-host execution area for one
   exact model/platform/framework-profile work item, used by
   the adaptation containers and remote commands for runtime configuration,
   temporary diagnostics, runs, caches, and bug reproducers. It is not a source
   checkout or repository mirror.
2. The **local work directory** is this management repository. It contains
   curated model/platform/framework records, reusable control tools, templates, and concise
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
- Keep every new remote process artifact under the framework-specific approved root, using these
  ordered names: `01-environment/` for collection and runtime configuration,
  `02-issues/` for one-off diagnosis, `03-acceptance/` for
  evaluation tools/configuration, `04-runs/` for run output, `05-tmp/` and
  `06-cache/` for temporary or implicit writes, and `07-bugs/` for minimal
  operator reproducers. Do not create a source-repository subdirectory or mirror
  under this work root. Product changes belong only in the component and source
  tree declared writable by the selected framework profile after its package
  metadata, import path, Git root, revision, and working-tree ownership are
  verified; undeclared components remain read-only. For `vllm-plugin-fl`, the
  writable product tree is the existing editable-installed Plugin, vLLM stays
  read-only, and FlagGems synchronization remains separately authorized. Do not
  copy or clone source trees into the remote work directory. Keep a reproducer
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
- Before an active-profile service adaptation can be marked complete, place one final executable model
  launch script at `<host_root>/start-model.sh` for every framework-specific target host root, with
  the verified container path `<container_root>/start-model.sh`. It must launch
  the profile's final accepted primary execution mode (`graph` for
  `vllm-plugin-fl`), keep logs/results under `04-runs/`
  and caches under `06-cache/`, contain no secrets, and refuse to overwrite an
  unrelated running service. Keep the launcher minimal: remove diagnostic,
  profiling, tracing, dump, temporary-path, obsolete workaround, duplicated
  default, experimental tuning, and unrelated model/platform settings unless
  the accepted configuration demonstrably requires them. Rebuild it from the
  smallest accepted production command instead of copying the last diagnostic,
  accuracy, or performance command. In particular, do not carry the
  profile's performance-only cache-disable mechanism into the final launcher;
  for `vllm-plugin-fl`, this includes `--no-enable-prefix-caching`.
  Prefer engine defaults over explicit flags when behavior and reproducibility
  do not depend on pinning them; do not add convenience flags merely because they
  appeared in an earlier run. Every retained explicit
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
  dependencies, and source trees other than the profile-declared writable source
  and explicitly authorized synchronization are read-only. Do not
  move or duplicate them, change mounts, or stop/restart the adaptation container
  to arrange the workspace. If the selected profile's required writable component
  is not in the declared editable/source form or its identity cannot be verified,
  stop and report the blocker instead of creating a replacement checkout under
  the work root.
### Local work directory

- Keep this repository limited to verified model bring-up, platform validation,
  and inference optimization for an identified model and platform. Exclude
  unrelated administration, package installation, chat, exploratory output, and
  unverified conclusions. Commit or push only when explicitly requested.
- Create models with `./scripts/new-model <model-name>` without overwriting an
  existing directory. Use only platform names `nvidia`, `ppu`, `metax`, `ascend`,
  `mthreads`, and `hygon`. Create an explicit framework workspace with
  `./scripts/new-framework <model> <platform> <framework-id>`; never hand-copy a
  profile or reuse another framework's status.
- Under `models/<model>/<platform>/`, keep only `README.md`, `platform.yml`, the
  optional `frameworks/` hierarchy, and legacy direct records. New work belongs at
  `models/<model>/<platform>/frameworks/<framework-id>/`, which contains only
  `README.md`, `framework.yml`, and:
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
  profile-declared product source contains only required product code and
  maintainable focused tests. Put one-off process code in remote `02-issues/` or
  `05-tmp/`, outside all product, framework, and kernel source trees,
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
- Mark the formal accuracy substep passed or complete when a valid full-run
  accuracy receipt shows that every metric frozen in the run configuration meets
  its configured minimum threshold. A score below `1.0`, and therefore some
  individually incorrect answers, does not fail the formal accuracy test by
  itself. Per-question all-correct checking belongs only to the small-batch
  sanity check. A final timeout response is retained as a failed/incorrect sample
  and contributes zero correctness credit; it must never be dropped from the
  denominator or hidden by retries. A limited number of such timeout samples may
  coexist with a passing formal run only when sample coverage remains complete
  and every frozen metric still meets its threshold. Missing or invalid samples,
  non-timeout request/execution errors, stale evidence, or a metric below its
  threshold remain failures or incomplete evidence as defined by the project
  accuracy contract.
- Before completion, update the framework workspace `README.md` with outcomes,
  problems, causes, solutions, limits, and next steps, and synchronize it with
  `framework.yml`. For legacy implicit records, continue to use the platform
  `README.md` and `platform.yml`. Verify the root-level remote `start-model.sh` described above;
  file existence alone is not completion evidence. Require minimal inference for `functional`, and recorded
  correctness regression plus performance results for `optimized`.
- Never commit weights, secrets, complete logs, or bulky raw benchmarks.

## Framework implementation and PR quality

- Treat changes as maintainable contributions to a multi-model, multi-platform
  framework. Before editing, read the selected profile, its workflow and
  acceptance documents, and the target source tree's design, contribution and
  test guidance. For `vllm-plugin-fl`, also follow
  [the plugin contribution policy](docs/plugin-contribution-policy.md).
- Explain ownership, existing extension points, interface contracts, alternatives
  and affected callers in the platform environment analysis or relevant numbered
  adaptation issue. Reuse the
  framework's dispatch and registration paths. Scope model semantics to model
  adapters and hardware constraints to vendor/capability paths; do not scatter
  model-name or machine-specific exceptions through shared execution code.
- Preserve existing behavior outside the intended scope. Verify applicable
  shared-model callers, guard miss paths, optional-dependency isolation, and all
  execution modes required by the selected profile (`eager`/`graph` for
  `vllm-plugin-fl`). Declare unavailable hardware and untested scope honestly;
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

- Use the shared `inference-accuracy-evaluation` and
  `inference-performance-evaluation` Skills for accuracy and performance work.
  Their Skill bundles own the test levels/modes, concrete execution method,
  concurrency and warmup rules, metric calculations, evidence validation,
  three-state decisions, and report fields. Do not duplicate or redefine those
  methods in this AGENTS file.
- Read `docs/skills-project-contract.md` to map the shared methods to this
  repository's canonical runners, containers, paths and native receipts. The
  contract is an adapter only: project rules and the user's selected execution
  boundary may narrow execution, but neither the contract nor this file may
  silently replace or weaken the Skill method.
- For frameworks that provide prefix caching, it remains enabled for architecture, environment, adaptation,
  execution-mode, sanity, accuracy, and all other non-performance work. This
  project adds one mandatory performance-only precondition: prefix caching must
  be explicitly disabled on the exact service instance under test before any
  performance or profiling run starts. Use a performance-specific service launch
  profile; do not add the disable mechanism to the normal service profile. Use
  the exact mechanism declared by the selected framework profile, verify that it
  is present in the effective launch configuration and startup evidence, and bind that evidence into the formal
  performance receipt. A zero random-prefix length in the client workload
  is not proof that server-side prefix caching is disabled. For `vllm-plugin-fl`,
  the required argument remains exactly `--no-enable-prefix-caching`. If the
  profile mechanism and its effective disabled state cannot be verified, do not run or
  pass the performance substep. Restore the normal prefix-cache-enabled service
  profile before any subsequent non-performance test.

- The user may select any phases by number or name: `architecture` (1),
  `environment` (2), `adaptation` (3), `acceptance` (4), and `retrospective` (5).
  Execute only those phases, always in 1-to-5 order. Unselected phases may be
  inspected as prerequisites but must not be executed or rewritten.
- Phases 2-5 require an explicit active/experimental framework profile and exact host aliases. For a
  new framework workspace, create it with `./scripts/new-framework` and validate
  the local layout with `./scripts/audit-workspace`. Legacy direct platform
  records continue to use their existing checks. Stop and report the exact
  blocker when prerequisite identity, evidence, status, or freshness is missing
  or inconsistent; never repair it by silently rerunning another phase or merely
  refreshing hashes.
- Acceptance substeps come from the selected profile's ordered `acceptance.steps`.
  vllm-plugin-fl uses execution-mode → sanity → accuracy → performance → evidence → summary;
  Torch-FL uses device → operators → model-eager → optional wheel → summary.
  Execute only selected steps, never waive earlier prerequisites, and never require
  vLLM service tests from a Torch-FL Python API adaptation.
- Use `adapt-model --framework <id> --check-only` for explicit workspaces, adding
  `--verify-records` to verify selected completed work. Read `docs/framework-evidence.md`;
  native evidence remains remote and must be accessible through a verified artifact root.
  Missing native evidence is incomplete, not a Markdown-based pass.
- The legacy `adapt-model` implementation without `--framework` still contains structured-file
  gates. Do not run it in creation mode for platform phases 2 through 5 and do not
  reintroduce its legacy YAML/process files into a compact platform directory.
  Invoke those phases through a natural-language Codex request and use
  `audit-workspace` for local layout checks until the gate is migrated. Step 1
  architecture initialization remains safe.
- Update the selected framework's `framework.yml` only after the work is actually
  verified; legacy direct records continue to update `platform.yml`. Bind
  phase and acceptance receipts through
  `docs/skills-project-contract.md` and `docs/workflow-guide.md`; record and
  verify the exact Host set in the environment analysis. Native receipt names,
  validation commands and invalidation rules belong in the project contract,
  not in this AGENTS file.
- Use `./scripts/audit-workspace` for local structure and historical-state review.
  Its warnings require review and never prove remote success.

## Detailed workflow (required reading)

Before performing any selected architecture, environment, adaptation, acceptance, or
retrospective phase, read the selected profile's workflow and acceptance documents,
then read [the detailed workflow](docs/model-adaptation-workflow.md) and apply the
selected phases in order. The detailed rules are mandatory; moving
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
