# Model Adaptation Instructions

This repository supports model bring-up and inference optimization for an exact
model, hardware platform and framework profile. English instructions are for
agents; [AGENTS.zh-CN.md](AGENTS.zh-CN.md) is the human-readable Chinese version.

## Agent entry and roles

- Codex and dsh are peer client entry points: the client currently in use is the
  controller on the current machine. Both share this file, profiles,
  repository-local Skills and native validators. Follow
  [the entry guide](docs/agent-entrypoints.md); client-specific discovery, tools
  and permission settings do not replace project contracts. Either client can
  serve as the controller independently.
- A direct user task starts as `coordinator` (the main agent) unless explicitly
  assigned a bounded worker task. A dispatched task declares `worker` (the
  executor/subagent), its coordinator and task binding. Record the role in the
  current task explanation or existing plan/issue; do not infer it from whether
  the client is Codex or dsh, and do not add a required business-state schema.
- The coordinator plans, delegates, coordinates resources, reviews evidence and
  accepts results. The delegation and main-agent direct-action limits below
  apply to this role. A worker directly performs the assigned analysis,
  implementation or checks within the original authorization and explicit task
  boundaries; it does not reapply the coordinator's duty to delegate or its
  direct-action exceptions to that assigned execution. Workers must not
  recursively delegate, expand scope, promote themselves to coordinator, commit
  or push, or declare overall adaptation acceptance. Missing scope or capability
  is reported to the coordinator before affected work proceeds.
- Both roles obey every applicable safety, permission, human-control, source and
  evidence requirement. Worker delivery is subject to coordinator review and the
  same native validators; role assignment does not grant new authorization.
- Dispatch through the current controller client's verified built-in subagent
  capability. Verify permissions and paths against the assignment. If no
  permitted subagent can perform the work, record the gap, stop affected
  execution and replan. The coordinator may continue only within its explicit
  direct-action exceptions.

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
  This defines the permitted source location, not permission for the main agent
  to take over implementation; follow the delegation requirements below.
- Keep code changes PR-ready and scoped to a verified adaptation need. Before
  editing, bound the affected components/files/symbols and tests; justify additions
  and deletions, exclude unrelated refactors, and review each final diff hunk.
  For Plugin, FlagGems and FlagGems-vllm under `vllm-plugin-fl`, apply the
  [contribution policy](docs/plugin-contribution-policy.md) to every changed component.
- For `vllm-plugin-FL` and `sglang-plugin-FL` work, follow the supplied
  [inference plugin development standard v1](docs/inference-plugin-development-v1.md)
  throughout adaptation and PR preparation. Read its overview and task-indexed
  clauses before edits; all applicable MUST clauses are binding, and departures
  from SHOULD clauses need rationale and verification. New numerical kernels
  belong in the appropriate operator library, not the Plugin; preserve the A3
  distinction for framework metadata. Prepare changes for PR delivery without
  broadening source permissions or automatically committing/publishing them.
- Operator work in FlagGems, FlagGems-vllm or FlagGems-sglang also follows the
  supplied [operator development standard](docs/operator-development-standard.md).
  Read its overview and task-indexed clauses; applicable MUST clauses bind operator
  implementation, dispatch, independent numerical/graph tests, benchmarks and PR
  review. Cite `plugin:<clause>` or `operator:<clause>` to distinguish the standards.
  Use the existing source review, not a new stage. This does not authorize another
  framework/component or patches to installed third-party dependencies.
- Follow the user's clarified ownership for future adaptation: FlagGems provides
  ATen operators only; vLLM operators, including non-ATen fused computations used
  by vLLM, belong in FlagGems-vllm. This overrides broader FlagGems ownership in
  the supplied standards; their other applicable requirements remain binding.
  FlagGems ATen operators use automatic replacement; verify activation, actual
  dispatch and correctness rather than adding a Plugin adapter per ATen operator.
  Test FlagGems numerical behavior through `flag_gems.<op>` and test automatic
  replacement/dispatch separately. Inspect FlagGems-vllm for each
  vLLM-specific operator, compare its contract, and integrate compatible public
  APIs through the existing Plugin architecture. Missing implementations belong
  in the appropriate operator library. The supplied PR development standard remains binding.
- Resolve guidance using explicit user/project applicability overrides, then applicable
  development standards and the target revision's engineering conventions; historical
  examples do not override them. Unchanged hard requirements remain binding.
- If referenced guidance is verified absent, record the revision/search and alternative
  basis, then continue authorized work whose contracts are established; do not repeatedly
  seek approval for the same gap or claim to have read missing material. Follow
  [missing-guidance handling](docs/adaptation-policy.md#guidance-precedence-missing-documents-and-gates).
- Separate development prerequisites from delivery gates: uncertain semantics or write
  boundaries block affected edits; failed/unrun checks block the corresponding pass/readiness
  claim, not authorized diagnosis and repair. Keep dependent acceptance incomplete.
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

## Subagent delegation

This section governs coordinator dispatch and direct actions. Workers perform
their bounded assignments under [Agent entry and roles](#agent-entry-and-roles)
and retain all shared boundaries and acceptance requirements.

- Except for the explicit direct-action exceptions below, independently
  deliverable execution MUST be split into bounded subtasks and delegated.
  This includes architecture/inference-chain and environment analysis, source
  and log/trace analysis, diagnosis, code and experiment-script/configuration
  changes, environment preparation, service launch/adjustment, operator trials,
  correctness/graph checks, profiling, accuracy/performance runs and statistics.
  Delegate local-only execution locally. For authorized remote work, the worker
  uses the approved project remote-operation entries within the assigned hosts,
  work roots and containers. Do not create remote work to satisfy delegation.
  These duties do not authorize
  unselected phases, hosts, components or deployment operations.
- The main agent owns overall planning, dependencies, worker coordination,
  integration decisions, priorities, resource coordination, observation, evidence
  review, keep/revert decisions, final acceptance and user communication. Do not
  hand the entire adaptation to one executor without intermediate review.
- Before each selected phase or bounded work unit, record its executor, inputs,
  expected outputs, dependencies/resources, budget and acceptance criteria in the
  existing phase plan or numbered issue. Assign and dispatch delegable work
  before executing it; do not complete it first and delegate only afterward.
  Give each worker the task/issue or experiment ID, verified state, relevant
  rules/Skills, exact model/platform/profile/phase, authorized hosts, containers,
  installed import paths, working roots and files/symbols, read/write limits,
  success/stop conditions, total budget and expected evidence. Workers must not
  expand scope, recursively delegate, commit or push.
- Check [existing receipts and in-flight
  work](docs/agent-execution.md#优先复用有效回执) before dispatch or launch.
  Within the same selected phase and authorization/write boundary, bundle related
  judgment-based steps for one worker, with explicit gates, stop conditions and
  evidence. Split for an independent review, a different approval/write boundary,
  a blocked dependency, or useful isolated parallel work. Within an open work
  unit, keep the same worker when its context is still useful and continuation
  is safe. Send only changed inputs and outstanding work.
- Use the smallest context that carries the verified task contract. For a
  self-contained Codex dispatch, explicitly use `fork_turns: "none"` when the
  available tool supports it. Follow the [client entry guide](docs/agent-entrypoints.md#委派上下文)
  when history is essential or inheritance controls differ.
- Close the worker turn at delivery or a stop condition. Give each new phase or
  work unit its own bounded dispatch when delegation is needed. Follow the
  [worker handoff rules](docs/agent-execution.md#执行者收尾与交接) for targeted
  corrections, blocked work and ownership of work still running.
- Grant read-only or bounded-write permissions to match the selected subtask
  and preserve command approvals. Container work must run in the assigned
  container and its verified installed components. Container evidence must
  come from that container.
- Main-agent direct actions are limited to these explicit exceptions, always
  within existing permissions, source boundaries and human-control rules:

  1. Read project rules, task context and existing delivery summaries for
     planning, contract definition and decisions.
  2. Perform the minimum read-only checks needed for dispatch, recovery or
     resource coordination: connection, identity, permissions, paths, executor
     entry, processes and resource ownership. Broad source searches, full-log
     scans, trace parsing and batch statistics remain delegated work.
  3. Save and dispatch task/control commands, observe progress, collect outputs
     and coordinate resources. Do not embed main-agent-written product code or
     experiment scripts in dispatch commands as a substitute for delegation.
  4. Inspect actual diffs and targeted execution-path/original-evidence samples,
     verify bindings/receipts, and invoke existing native validators that do
     not start a new workload. Delegate deeper analysis, repairs and reruns;
     acceptance review is not permission to redo the execution.
  5. Maintain local project rules, documentation and records, and run existing
     document checks for those changes. This excludes implementing product
     code, experiment scripts or evaluation/control tools under maintenance.
  6. Perform urgent pause/precisely targeted stop or other necessary emergency
     control within existing authorization; retain container/service protection
     and human-takeover requirements.
  7. Perform a single auxiliary action serving the duties above, requiring no
     deep analysis, product-source/experiment-configuration change or device
     experiment. Small task size alone is not an exception; batch small worker
     tasks and never split continuous execution into small actions to evade delegation.
- Record each direct action's exception category, reason and scope in the
  existing task/phase/issue record; a local rules-maintenance task may use its
  current task explanation. At phase end summarize worker deliveries, unfinished
  work, direct-action exceptions and main-agent acceptance results, retaining
  failures and evidence gaps. Do not create a second business ledger or new
  required YAML schema. There is no mechanical call-count/workload ratio, and
  no work is repeated to improve a delegation metric. Exception recording adds
  no approval step and never replaces approvals already required by policy.
- Run independent subtasks in parallel where host, resource and write constraints
  permit. Assign clear write ownership and serialize conflicting or dependent
  changes. The main agent reviews returned results and diffs and accepts completion
  only when the required checks and evidence support it.
- For [interrupted work](docs/agent-execution.md#执行中断与接续), report the known
  cause and distinguish transport loss, controller timeout, worker failure and a
  failed workload/test.
  A disconnected SSH client or expired local wait does not prove remote exit.
  Inspect the original process identity, task children, session, partial changes
  and artifacts before any replacement. Unknown state or live writers block a
  new executor. Collect completed results before rerunning work.
- For long remote tasks, use an independent controller within the approved work
  root and persist inputs, events and bounded checkpoints. Use one status observer
  per run, favor native events or existing status tools, and follow
  [the observation rules](docs/agent-execution.md#按事件观察) for checkpoints,
  stall/failure and user decisions. Keep any user-requested update cadence.
  Freeze soft observation and total task budgets before launch. A soft deadline
  with verified progress permits continued observation within the total budget;
  it does not trigger an automatic kill. Resume an existing session only after
  its execution has stopped, its checkpoint and unchanged binding are verified,
  and that installation's resume support is established. Retry a transient failure
  only with verified absence of side effects and no live execution. Allow at most
  two recovery attempts; stop mechanical retries after the same error twice.
- All attempts and reassignment share the frozen total budget. Replan when it is
  exhausted. After reconciling partial effects and confirming old execution and
  child writers have stopped, transfer only verified state and remaining work to
  a suitable built-in subagent. Missing capabilities, configuration or permissions
  require resolving the gap or replanning. Preserve failed tests and accuracy
  results and use the same native acceptance validators. The coordinator remains
  subject to the direct-action exceptions above.
- All client and executor choices obey the same task scope, source permissions,
  human control and evidence requirements. Use only authorized hosts and work roots;
  delegation does not authorize remote work for a local-only task or bypass
  command approvals.
- Apply this division at the next safe work-unit boundary for ongoing tasks.
  Check live processes, partial changes, resources and valid evidence first;
  reuse running/completed checks rather than restarting them just to change
  executor. Human pause/takeover takes precedence. Carry these scoped rules
  into an independent worktree's own AGENTS without overwriting unrelated changes.

## Required reading by task

Read the applicable entry before acting. Linked policies are mandatory within
their scope; moving them out of this file does not relax their requirements.
Load unrelated workflows only if the user expands the task.

| Requested work | Required entry |
| --- | --- |
| Local documentation, code review or control-tool maintenance | Relevant files and their tests/contracts; use the rows below only if their scope applies. |
| Running commands through Codex or dsh, or checking client capabilities | [Client entry guide](docs/agent-entrypoints.md); then the rows below that match the operation. |
| Image release/deployment, adaptation completion handoff or a standalone deployment guide | [Image release and deployment Skill](skills/adaptation-deployment-guide/SKILL.md) and its bundled English template; select the requested operation before executing. |
| Remote checks/changes, or inventory, group variables, Ansible entrypoint or playbook maintenance | [Remote operations Skill](skills/remote-operations/SKILL.md), then its linked policy. |
| Any selected model-adaptation phase | [Adaptation policy](docs/adaptation-policy.md), selected profile's workflow/acceptance documents, then [detailed workflow](docs/model-adaptation-workflow.md). |
| Adaptation involving remote work | Also read the remote operations Skill before the first remote action. |
| Accuracy/performance evaluation | Also read [project contract](docs/skills-project-contract.md) and its repository-local Skill; select an explicit operation. |
| Recoverable long-running execution | Also read [execution journal](docs/agent-execution.md). |
| Operator implementation, integration, testing, tuning or PR review | [Operator development standard](docs/operator-development-standard.md), its task-indexed clauses and target repository guidance; also apply the selected profile and Plugin standard for cross-component changes. |
| Framework implementation or PR review | Also read the target source guidance; for vLLM/SGLang plugins, [development standard v1](docs/inference-plugin-development-v1.md); for `vllm-plugin-fl`, also [plugin contribution policy](docs/plugin-contribution-policy.md). |

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
- For MetaX multi-host adaptation, first verify cross-host communication with
  `MetaX-MACA/mccl_tests` during environment analysis, before dependent multi-host
  model execution. Follow the [MetaX communication preflight](docs/model-adaptation-workflow.md#metax-multi-host-communication-preflight).
  Every test rank must run inside its Host's actual adaptation container using
  the model's communication stack and device/network mappings; host-only results
  cannot satisfy this prerequisite.
  Retain exact-scope evidence; failed or missing checks block dependent execution,
  not independent analysis. This does not authorize unselected phases or hosts.
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
  [image release and deployment Skill](skills/adaptation-deployment-guide/SKILL.md) to write
  English `acceptance/deployment-guide.md` in its local framework workspace.
  Default completion handoff is documentation-only unless image release/deployment
  is already requested. The same Skill also supports explicitly scoped packaging,
  publication and published-image deployment verification. Preserve the running
  adaptation source container and reuse the accepted minimal `start-model.sh`.
  It is independently callable; keep its template inside the Skill.
  Retain weight-download instructions for readers without executing downloads.
  This handoff document does not replace acceptance evidence or run unselected phases.
- New workspaces pin the [v2 evidence contract](docs/evidence-contract-v2.md).
  Upgrade existing contracts explicitly and preserve historical results.
  Complete adaptation requires valid performance measurements and full acceptance,
  not a predefined speed target. Explicit user-requested optimization targets remain
  binding when configured; never remove them to turn a failed run into a pass.
- Service sanity uses representative text requests; image-capable models also need
  image requests. Review relevance, output health and actual image understanding,
  plus obvious performance problems. Do not require verbatim reference answers for
  open-ended generation. Keep raw responses and an attributed, result-bound review;
  successful HTTP responses alone do not establish sanity acceptance.
- For service profiles, freeze verified model modalities, architecture SHA-256 and
  each Host's served aliases, shared launcher and effective startup configuration in
  `acceptance_plan.service_contract` before sanity. Bind sanity, accuracy, performance
  and delivery to it; only performance changes prefix caching. Follow the
  [service evidence contract](docs/evidence-contract-v2.md#服务范围与共享启动绑定).
  First performance measurements need no prior baseline; comparisons/relative targets do.
- A retrospective may review failed, blocked or partial work without passing prior
  phases. Bind the review to actual stage states/evidence; it never promotes acceptance
  or overall adaptation status. Revalidate the review when its referenced state changes.
