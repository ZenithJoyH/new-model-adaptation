# Model adaptation policy

Read these rules, required by [AGENTS.md](../AGENTS.md), before any adaptation
phase. Code paths are relative to the repository root. Read the
[remote operations policy](remote-operations.md) for remote write boundaries,
workspace numbering and final launch-script requirements before remote work or
final launcher verification.

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
  copied tests, raw logs, runtime JSON/YAML, or command output. The installed
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

### Contract versions, handoff and reproducible delivery

New workspaces pin a profile snapshot under [evidence contract v2](evidence-contract-v2.md).
Changes to prose or the current profile file do not silently upgrade an existing workspace.
Use explicit `workspace-control upgrade` while under human control; retain old receipts
and revalidate affected stages. Legacy phase 2–5 creation is disabled; read-only
legacy checks remain available.

[Human collaboration](human-collaboration.md) applies at every phase. Handoff records
ownership, identity and current processes without stopping them. On return, verify the
change description and original evidence, adopt valid new human receipts using the same
validators, and invalidate only affected stages and their dependencies.

A small, sanitized reproducible delivery may be versioned separately under
`deliveries/<model>/<platform>/<framework>/`: launcher, configuration, source patch or
source reference, dependency lock and restoration instructions. This exception does
not permit weights, credentials, raw logs, results or process scratch files in the
repository. Record file hashes and actual image validation state. A pending image
check is not a packaging pass. Commit/push still requires a user request.

### Status and completion

- Establish correctness and performance baselines before optimization; change
  one material variable at a time and retain the comparison.
- Follow the selected profile's graph preference one level at a time. vLLM
  profiles use `full` → `full-and-piecewise` → `decode-full` → `piecewise`.
  Record each higher level's exact configuration, reproducible problem, diagnosis,
  attempted remedies, unresolved blocker, evidence and conditions for retrying.
  Never skip directly to a convenient lower mode. Apply the performance and
  effective-runtime checks in the [common workflow](model-adaptation-workflow.md).
  Piecewise graphs may pass after the full fallback chain is evidenced; eager-only
  remains diagnostic and cannot satisfy graph acceptance. Bind later acceptance
  and the launcher to the final verified mode for each Host.
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
  `README.md` and `platform.yml`. Verify the root-level remote `start-model.sh` required by the remote operations policy;
  file existence alone is not completion evidence. Require minimal inference for `functional`, and recorded
  correctness regression plus performance results for `optimized`.
- Never commit weights, secrets, complete logs, or bulky raw benchmarks.

After technical completion, the Agent invokes the
[deployment guide Skill](../skills/adaptation-deployment-guide/SKILL.md) for the
English local `acceptance/deployment-guide.md` before handoff. Its bundled template
includes weight-download instructions only; do not execute them. Follow the
[completion handoff](model-adaptation-workflow.md#completion-handoff-english-deployment-guide)
for independent invocation, draft handling and phase isolation.

## Framework implementation and PR quality

- For vLLM/SGLang plugins, the supplied
  [development standard v1](inference-plugin-development-v1.md) applies throughout
  planning, implementation, testing and PR preparation. Read the overview, then
  all task-indexed applicable clauses; record clause IDs, evidence, unmet MUSTs
  and justified SHOULD deviations in the existing plan/review. New numerical
  implementations belong to FlagGems or the framework-specific operator library
  via public APIs; framework metadata remains framework-owned under A3. This
  supersedes older guidance to add missing numerical Triton kernels in Plugin.
  It does not authorize a new component, unsupported profile or remote operation.
- Treat changes as maintainable contributions to a multi-model, multi-platform
  framework. Before editing, read the selected profile, its workflow and
  acceptance documents, and the target source tree's design, contribution and
  test guidance. For `vllm-plugin-fl`, also follow
  [the plugin contribution policy](plugin-contribution-policy.md).
- Before editing, record a bounded change list in the existing plan or issue:
  verified need, owning component, files/symbols, additions/modifications/deletions,
  baseline and regression tests. Apply this to every changed component, including
  Plugin, FlagGems and FlagGems-vllm where declared writable. Justify deletions with
  caller/registration/compatibility evidence, not absence from the current model.
  Avoid unrelated cleanup, whole-layer rewrites and duplicate cross-component
  workarounds. Review incremental diffs against the plan; justify scope growth
  before editing and seek authorization for work beyond the task's boundary.
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
  Check each component's diff hunk against the bounded plan, including additions
  and deletions; unexplained changes or known regressions block source review.
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

- Use the repository-local accuracy/performance entrypoints with capability IDs
  `adaptation/accuracy` and `adaptation/performance`. Require an explicit operation;
  same-named Hub/global Skills are not interchangeable native evidence producers.
- Read `docs/skills-project-contract.md` for the project-owned methods and native
  runners. Do not dynamically load a mutable sibling Hub checkout. Any migration
  must explicitly compare the bundle interface and evidence contract.
- For recoverable long-running steps, follow `docs/agent-execution.md`: freeze
  Skill/input identity, run native pre/post checks, and inspect the existing run
  before retrying. The journal does not grant remote permissions or replace the
  framework workflow records; the calling Agent decides next actions.
- For frameworks that provide prefix caching, it remains enabled for architecture, environment, adaptation,
  execution-mode, sanity, accuracy, and all other non-performance work. This
  project adds one mandatory performance-only precondition: prefix caching must
  be explicitly disabled on the exact service instance under test before any
  performance or profiling run starts. Use the same minimal `start-model.sh`
  used for accuracy, selecting only its explicit performance switch; do not add
  the disable mechanism to the normal invocation. Follow the
  [shared launcher contract](remote-operations.md#shared-service-launcher). Use
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
  not duplicated in this policy.
- Use `./scripts/audit-workspace` for local structure and historical-state review.
  Its warnings require review and never prove remote success.

## Detailed workflow (required reading)

Before performing any selected architecture, environment, adaptation, acceptance, or
retrospective phase, read the selected profile's workflow and acceptance documents,
then read [the detailed workflow](model-adaptation-workflow.md) and apply the
selected phases in order. The detailed rules are mandatory; moving
them out of this file does not weaken any safety or acceptance requirement.
See [the execution and evidence guide](workflow-guide.md) for local commands.
