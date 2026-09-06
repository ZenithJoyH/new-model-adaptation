# Remote Operations Instructions

## Scope

- This repository manages every concrete host alias from the operator's SSH
  configuration through `inventory/hosts.yml`. Keep the `managed` group in sync
  when SSH aliases are added or removed.
- Use Ansible for repeatable or multi-host changes. Direct SSH is acceptable for
  focused, read-only diagnostics.
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

- Treat this repository as a curated model-adaptation workspace, not as a
  general activity log. Modify or add adaptation files only when the current
  task actually concerns bringing up a new model, validating it on a hardware
  platform, or optimizing its inference.
- Do not record unrelated remote administration, temporary troubleshooting,
  ordinary package installation, chat content, exploratory commands, or
  unverified conclusions in this repository or under `models/`.
- Before writing an adaptation record, identify its exact model and platform.
  If the work has no clear model/platform scope, leave the adaptation files
  unchanged unless the user explicitly asks for a repository-level change.
- Do not commit or push changes merely because a task was completed. Commit or
  push only when the user explicitly requests it.
- Organize adaptation work under `models/<model-name>/<platform>/`. Platform
  directory names must match the inventory groups: `nvidia`, `ppu`, `metax`,
  `ascend`, `mthreads`, and `hygon`.
- When adaptation starts for a user-requested platform, create three work
  directories directly under its platform directory:
  `environment/`, `adaptation/`, and `acceptance/`. Keep only the platform-level
  `README.md` and `platform.yml` as the index and status metadata at the platform
  root. Store environment analysis, collection artifacts, the platform adaptation
  plan, structured runtime configuration, and service-state metadata in
  `environment/`. Treat `adaptation/` strictly as a concise, Markdown-only issue
  ledger: keep `README.md` as the issue index and use one numbered Markdown file
  per material problem to record its symptoms, diagnosis, attempted actions,
  root cause or current hypothesis, solution, verification, and remaining limits.
  Store accuracy, performance, communication-test configurations or wrappers,
  concise results, and final acceptance documents in `acceptance/`.
- Do not store standalone scripts, playbooks, source snapshots, patches, operator
  implementations, copied test suites, raw logs, JSON/YAML runtime artifacts, or
  temporary command output under a model platform's `adaptation/` directory.
  The plugin repository inside the running adaptation container is also not a
  general adaptation workspace. Add only code that is necessary to the plugin's
  shipped runtime behavior and focused, maintainable regression tests that belong
  in the plugin's normal test suite. Do not add one-off diagnostic probes,
  deployment or patch-application helpers, launch wrappers, log parsers, evidence
  collectors, experiment scripts, generated snapshots, or copied reference code
  to the plugin repository.
- Keep one-off process scripts and code in an explicitly named temporary work
  directory inside the running adaptation container but outside the plugin,
  vLLM, and FlagGems repositories. Do not commit them. Record the exact temporary
  path, command, purpose, and result in the relevant numbered issue, and retain
  the smallest necessary evidence before cleaning temporary files. Environment
  collection helpers belong in `environment/`; model-specific acceptance
  wrappers belong in `acceptance/`; reusable cross-model tooling may be promoted
  to the repository-level `scripts/` only after its generality is verified and
  the user requests or approves that shared change. Keep a FlagGems reproducer in
  the container-root `/bug` location required below. Common repository test tools
  remain under `test/`.
- Use `./scripts/new-model <model-name>` to create a new workspace from
  `models/_template`. Never overwrite an existing model directory.
- Keep model-wide tokenizer work, common patches, and consistency cases in
  `_shared`. Route vendor-specific files to the appropriate one of the three
  platform work directories above.
- Before executing a new remote command, record its repeatable form in the
  document that owns the operation: use `environment/` for collection, baseline,
  preparation, and planned adaptation commands; the relevant numbered
  `adaptation/*.md` issue record for diagnostic or corrective commands; and
  `acceptance/` for validation commands. Do not create a standalone command
  script in `adaptation/`, and do not leave chat or shell history as the only copy.
- Record exact host aliases, model revision, code revision, engine version,
  container image, launch arguments, test inputs, and verification date.
- Every model adaptation must produce or update the corresponding
  `models/<model-name>/<platform>/README.md` before the task is considered
  complete. Summarize the adaptation scope and outcome, every material problem
  encountered, its diagnosed cause, and the solution or workaround that was
  applied. Record unresolved problems and next steps explicitly; do not document
  only the successful final procedure.
- Establish a correctness and performance baseline before optimization. Change
  one material variable at a time and retain the baseline comparison.
- Keep `README.md` and `platform.yml` status synchronized. Do not mark a platform
  `functional` until a minimal inference has been verified, or `optimized` until
  correctness regression and performance results are recorded.
- Never commit model weights, secrets, complete logs, or bulky raw benchmark
  artifacts. Store only paths and small result summaries.

## Adaptation experience accumulation and reuse

- Treat verified adaptation experience as a maintained knowledge base, not as
  informal memory. Before environment changes, implementation, or acceptance,
  search `docs/troubleshooting/`, relevant prior platform retrospectives, and
  closely related model records for matching symptoms and constraints.
- Match an experience by the complete failure signature and context: symptom
  sequence, first failing rank or component, model structure, platform, software
  revisions, dtype and shapes, parallel topology, load, and `eager` or `graph`
  mode. A shared error keyword alone is not sufficient evidence that two failures
  have the same cause or solution.
- Record a new material problem in a numbered issue file under the current
  platform's `adaptation/`, and add it to `adaptation/README.md`. Label it as a
  hypothesis until a controlled experiment verifies it. Start new records from
  `templates/adaptation/issue-record.md`. Change one
  material variable at a time, retain the before-and-after evidence, and state
  whether the action is a diagnostic probe, workaround, mitigation, or root-cause
  fix.
- Promote an experience to `docs/troubleshooting/` once its trigger conditions,
  action, outcome, limits, revisions, and verification evidence are sufficient
  for safe reuse. A second model or platform confirmation strengthens confidence
  but is not required when the minimal reproducer and causal evidence are
  conclusive. Retrospectives must audit candidate experiences and identify which
  entries were promoted, rejected, superseded, or still need validation.
- When reusing an entry, cite it in the corresponding numbered adaptation issue,
  record the similarities and differences, and revalidate it on the current stack. Add
  new evidence and a revalidation date after success. Downgrade, constrain, or
  deprecate the entry when a counterexample is found; never silently preserve
  stale guidance.
- Knowledge entries must be concise and searchable. Include the failure
  signature, applicability, confidence, diagnostic sequence, safe action,
  stop/rollback conditions, verification, performance impact, `eager`/`graph`
  coverage, and source record. Do not include secrets, weights, complete logs, or
  unsupported conclusions.
- For a TP failure where a worker does not answer `sample_tokens` within 300
  seconds, rank communication work sequence numbers then diverge, and EngineCore
  exits on RPC timeout, increasing `VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS` is an
  allowed controlled diagnostic or mitigation only after preserving per-rank
  evidence. Verify that the installed runtime recognizes the variable, record
  the original and trial values, and restart only the scoped inference service
  if required. A longer timeout is appropriate when workers remain alive and
  make forward progress; it is not a fix for a rank exception, OOM, data-dependent
  branch divergence, collective-order mismatch, or deadlock. If progress stops or
  work sequence divergence remains, stop increasing the timeout and investigate
  the earliest divergent rank and collective instead.

## Workflow invocation and phase isolation

- The user may request any one or more workflow phases by number or name:
  `architecture` (1), `environment` (2), `adaptation` (3), `acceptance` (4), and
  `retrospective` (5). Execute only the selected phases and always order multiple
  selected phases from 1 through 5, regardless of the order in the request.
- Unselected prerequisite phases may be inspected for completeness, freshness,
  model identity, platform identity, and evidence, but must not be executed or
  rewritten automatically. If a required prerequisite is missing, stale, failed,
  or inconsistent, stop before the dependent phase and report the exact blocker.
- An acceptance request may select individual substeps: `execution-mode`,
  `sanity`, `accuracy`, `performance`, `evidence`, or `summary`. Do not run an
  unselected acceptance substep. Preserve the acceptance ordering constraints;
  selecting a later substep does not waive an incomplete prerequisite.
- Use `./scripts/adapt-model <model> [--platform <platform> --hosts <aliases>] --steps <steps>`
  to initialize only missing files for the selected phases,
  validate structured prerequisites and configuration, and generate a canonical
  Codex request. Steps 2 through 5 require exact host aliases either through
  `--hosts` or an existing adaptation config. Use `--check-only` when no files
  may be created. The helper does not run remote commands, mark phases passed,
  commit, or push.
- Update `platform.yml` phase or acceptance-substep status only after the named
  phase has actually reached that state and its evidence file has been updated.
  Never infer `passed` or `complete` from file existence alone.

## Model adaptation workflow

1. **Analyze the model architecture and inference path.** Before platform
   adaptation begins, create or update
   `models/<model-name>/architecture-and-inference.md`. Analyze the model's
   overall architecture and end-to-end inference path. This document must be
   written in Chinese, including its explanations, structure breakdown, operator
   inventory, conclusions, assumptions, and unresolved questions; code symbols,
   configuration field names, and established technical terms may remain in
   their original form. Break down and enumerate the complete model structure,
   including the relevant configuration, major
   components, layer organization, attention and MoE/routing behavior when
   applicable, tensor and data flow, parallelism requirements, execution stages,
   and implementation dependencies or compatibility risks. Also enumerate the
   key operators actually used by the model, grouped by component or execution
   stage, such as normalization, projection and matrix multiplication, positional
   encoding, attention and softmax, activation and MLP, routing and expert
   dispatch/combine, KV-cache operations, quantization/dequantization, sampling,
   and communication collectives when applicable. Derive operator claims from
   the model configuration or implementation rather than a generic architecture
   template, and clearly distinguish verified facts from assumptions and
   unresolved questions.
2. **Analyze the inference environment.** For each adaptation platform explicitly
   requested by the user, create or update
   `models/<model-name>/<platform>/environment/environment-analysis.md` before
   making platform changes. Keep supporting environment collection scripts and
   outputs in the same `environment/` directory. Record the target host aliases,
   accelerator model and topology, operating system or container environment,
   driver and runtime, inference framework and platform plugin versions,
   compiler or toolchain, available resources, verification commands,
   compatibility gaps, and the environment conclusions that affect the
   adaptation plan. Do not create environment analyses for platforms the user
   did not request.
3. **Perform the adaptation.** Combine the model architecture and inference-path
   analysis, the requested platform's environment analysis, and the
   adaptation-related reference files provided by the user. Carry out the work
   through the following substeps:

   1. **Define the plugin adaptation plan.** Use the architecture analysis,
      environment analysis, and user-provided references to map every model
      component, inference stage, key operator, parallelism requirement, and
      runtime dependency to the current plugin path and target platform
      capability. Create the gap list in
      `environment/platform-adaptation-plan.md`; identify the required plugin
      changes, operator source, `eager` and `graph` impact, dependencies, risks,
      and planned verification for each item. This plan is preparation context,
      not an issue record.
   2. **Capture the baseline and enforce modification boundaries.** Inside the
      running adaptation container, record the repository path, revision, branch,
      and working-tree status for the plugin, vLLM, and FlagGems before editing.
      The agent may modify the plugin source directly, but the vLLM source tree
      must remain read-only and unchanged throughout the adaptation. Do not stop,
      restart, or remove the adaptation container. Preserve before-and-after
      vLLM revision and status evidence. Store baseline and environment facts in
      `environment/environment-analysis.md` or
      `environment/platform-adaptation-plan.md`. If a dirty tree, revision
      mismatch, or modification-boundary violation becomes an adaptation issue,
      create a numbered Markdown issue record under `adaptation/`.
   3. **Synchronize FlagGems before operator integration.** Before checking or
      integrating any FlagGems operator, update the FlagGems repository inside
      the running adaptation container to the latest commit of its intended
      tracked branch. Record the remote, branch, upstream, revision, and
      working-tree status before updating. Proceed only when the worktree is clean
      and the intended branch and upstream are unambiguous; fetch and use a
      fast-forward-only pull, never reset, force-update, or discard local changes.
      Record the resulting revision and synchronization command in
      `environment/platform-adaptation-plan.md`. If synchronization cannot
      complete, report the exact blocker, create a numbered issue record under
      `adaptation/`, and do not continue operator selection against a stale
      revision.
   4. **Integrate operators already available in FlagGems.** For each operator
      the plugin does not invoke or support, inspect the plugin's
      dispatch/backend design and the synchronized FlagGems revision. When
      FlagGems has a compatible implementation, follow the existing plugin architecture to
      add the required dispatch, backend, registration, or platform binding.
      Never bypass the plugin design with an ad hoc direct call. Add focused
      integration and numerical tests. When this work resolves a compatibility
      gap or failure, record the FlagGems symbol, revision, plugin entry point,
      supported constraints, solution, and results in the corresponding numbered
      Markdown issue record under `adaptation/`.
   5. **Implement operators missing from FlagGems.** When the synchronized FlagGems
      revision has no compatible implementation, add a plugin-owned Triton
      operator and connect it through the same plugin dispatch framework. The
      Triton implementation must support `graph` capture/replay, not only `eager`
      execution. Avoid capture-time host synchronization, unsupported dynamic
      allocation, data-dependent host control flow, and unstable tensor shapes or
      addresses. Add numerical, dtype, shape, layout, device, boundary-condition,
      and execution-mode tests, including dedicated `eager` and `graph`
      capture/replay coverage. Record the checked FlagGems revision and search
      evidence, explicitly mark the operator as missing from FlagGems, and
      document the Triton location, supported constraints, plugin integration,
      results, and limitations in a numbered Markdown issue record under
      `adaptation/` and in the final `acceptance/adaptation-summary.md`.
   6. **Package reproducible FlagGems operator bugs.** Whenever a FlagGems
      operator raises an error or shows a numerical-accuracy problem during any
      adaptation stage, create `/bug` at the filesystem root of the running
      adaptation container created from the target adaptation image, and create
      a dedicated issue directory under it. Do not create this directory at the
      root of this management repository, the FlagGems repository, the plugin
      repository, or the vLLM repository. Provide a minimal, independently
      executable unit test that reproduces the exact operator failure for the
      operator developers inside the same adaptation image environment. Prefer
      testing the FlagGems operator directly without requiring the complete model
      service, vLLM, or the plugin; if the defect only appears through plugin
      dispatch, graph capture/replay, or another required integration path,
      include the smallest such path and a direct-operator comparison when
      possible. Pin the random seed and record the exact container image and
      container name, FlagGems revision, platform, device, software environment,
      operator arguments, dtype, shapes, strides/layout, launch mode, command,
      expected behavior, actual behavior, tolerances, and concise error or
      numerical-difference evidence. Cover `eager` and `graph` separately when
      execution mode affects the problem, include a trustworthy reference
      implementation or expected output for accuracy defects, and verify that
      the packaged test reproduces inside `/bug` on the affected host. Record the
      exact container-side issue path and reproduction command in the applicable
      numbered Markdown issue record under `adaptation/`. Do not stop or restart
      the adaptation container to create or test the reproducer, and do not place
      model weights, secrets,
      large logs, or unrelated adaptation artifacts under `/bug`.
   7. **Complete runtime configuration and integration.** Map parallelism, memory
      behavior, execution stages, model configuration, and launch arguments to
      the target platform. Add reproducible plugin-side configurations, wrappers,
      scripts, and optimization settings without changing vLLM source. Keep the
      only necessary production implementation and maintainable plugin regression
      tests in the plugin repository inside the running adaptation container.
      Keep one-off process code in the container-local temporary workspace
      outside all source repositories, as defined above. Store structured launch configuration in
      `environment/runtime-config.yml`, and reference exact container paths,
      branches, revisions or commits, and verification commands from the relevant
      numbered issue record; do not copy these artifacts into `adaptation/`. Do
      not configure an unnecessarily
      small `--max-model-len` when starting the model service. First verify the
      model's actual maximum supported context length from its configuration and
      implementation. If that length is greater than 50000 tokens, use 50000 for
      the initial service configuration; if it is 50000 or fewer, use the model's
      full supported maximum. If the supported maximum cannot be verified, stop
      and resolve it rather than guessing. Do not silently reduce the value to
      conceal memory, graph-capture, or runtime problems. Record the evidence,
      computed value, and final launch argument in
      `environment/runtime-config.yml`; when a context-length setting causes or
      resolves a problem, also capture that reasoning in its numbered issue
      record.
   8. **Validate incrementally.** Validate imports and registration first, then
      individual operators, component combinations, minimal model execution, and
      finally full service bring-up. After each change, run the smallest relevant
      regression set and cover both `eager` and `graph` behavior where applicable.
      Do not continue to a broader test while the narrower test is failing.
   9. **Control the adaptation service lifecycle.** Stop or restart only the
      current adaptation's inference service or related process when required for
      configuration changes, recovery, or verification. Never stop, restart, or
      remove the adaptation container itself. Confirm the exact service or process
      before acting and do not affect shared or unrelated services.
   10. **Consolidate reproducible issue records.** Maintain
      `adaptation/README.md` as the issue index and one numbered Markdown file per
      material problem. Each issue must capture symptoms, scope, evidence,
      diagnosis, controlled attempts, root cause or current hypothesis, solution
      or workaround, verification, limitations, and next steps. Commands and
      concise excerpts may be embedded in the issue Markdown. Necessary plugin
      implementation and maintainable regression tests remain in the plugin
      repository; one-off process scripts and code remain in the container-local
      temporary workspace outside all source repositories; configurations, raw logs, and other artifacts
      remain in their owning location. Reference each retained item by exact path,
      revision or commit when applicable, command, and result. Include service
      lifecycle actions, FlagGems evidence, and proof that
      vLLM remained unchanged in the applicable issue record before acceptance.
4. **Accept the adaptation.** Complete all of the following acceptance work:

   1. **Execution-mode acceptance.** Run the model successfully in both `eager`
      mode and `graph` mode. This step verifies only that both execution modes
      can run successfully. After it passes, perform all remaining acceptance
      work—including the small-batch sanity check, formal accuracy evaluation,
      performance evaluation or profiling, and communication validation when
      applicable—using the accepted `graph`-mode service configuration. Do not
      require duplicate accuracy or performance acceptance in `eager` mode.
   2. **Eight-concurrency accuracy and performance sanity check.** Before the
      formal accuracy evaluation, send a small, fixed set of simple requests with
      request concurrency set to 8 against the accepted `graph`-mode service
      configuration. Check every response against its expected result and record
      errors, timeouts, latency, throughput, accelerator utilization, and memory
      usage sufficient to spot an obvious performance regression. If any response
      is incorrect, return to adaptation and fix correctness first. If responses
      are correct but performance is clearly abnormal, diagnose and fix the
      performance problem before the full accuracy run. Repeat this sanity check
      after every fix; do not proceed until both correctness and the performance
      sanity check pass.
   3. **Formal full accuracy evaluation.** Run the evaluation on the target host
      against the accepted `graph`-mode service, inside a container based on
      `harbor.baai.ac.cn/flageval/flageval-llmeval:v1` or
      `harbor.baai.ac.cn/flageval/flageval-llmeval:arm64`, as appropriate for the
      target platform. Use `test/Accuracy_test/llmrun.py`; do not substitute
      another runner unless the user explicitly requests it. Prepare a
      model-specific `llm_config.json`, run `llmrun.py` with `--preflight-only`,
      and then run the formal evaluation. Formal full accuracy evaluation must
      use request concurrency of at least 32; the concurrency of 8 applies only
      to the preceding small-batch sanity check. Start at 32 or a higher verified
      safe concurrency and increase it as resources and service stability allow
      to minimize evaluation time. Do not sacrifice valid results, complete
      sample coverage, or service stability for speed. If concurrency 32 cannot
      run reliably, diagnose and resolve the blocker rather than silently running
      formal acceptance below 32. Record the configured and observed effective
      concurrency, tuning rationale, throughput, elapsed time, errors, and
      timeouts under `acceptance/`. Verify the expected sample count,
      process completion, final result and sample files, accuracy metrics,
      timeouts, and explicit pass criterion.
   4. **Final performance evaluation.** Only after the formal accuracy evaluation
      in step 3 has completed and met its pass criterion, use `test/perf_test/`
      against the same accepted `graph`-mode configuration for final inference
      performance testing or profiling. Do not start the formal performance
      evaluation while full accuracy is incomplete or failing.
      Use `test/nccl_test/` for communication validation when relevant, also
      under the `graph`-mode acceptance configuration.
   5. **Acceptance evidence.** Record the exact test scripts, configuration,
      dataset or case set, service mode, container name and image, commands,
      environment, result locations, metrics, pass criteria, and outcomes under
      the platform's `acceptance/` directory. Explicitly identify `graph` as the
      execution mode used for all acceptance work after step 1. Keep large
      datasets and raw outputs local or on remote storage. If a common test asset
      needs model-specific
      changes, place a copy or wrapper in `acceptance/` instead of silently
      changing the common baseline.
   6. **Final adaptation summary.** Create or update
      `models/<model-name>/<platform>/acceptance/adaptation-summary.md`. Summarize
      the scope, environment, reference files, implementation changes,
      reproducible procedure and configuration, correctness and performance
      verification, encountered problems and solutions, final status, unresolved
      limitations, and next steps. Do not mark the adaptation complete until
      every acceptance item has passed and the summary reflects the verified
      outcome.
5. **Retrospect on the adaptation.** After acceptance, create or update
   `models/<model-name>/<platform>/acceptance/adaptation-retrospective.md` for
   each adapted platform. Review the complete work from architecture and
   inference-path analysis through environment analysis, implementation, and
   acceptance. Summarize the significant problems encountered, their symptoms,
   root causes, impact, discovery stage, attempted approaches, final solutions,
   verification evidence, and any unresolved consequences. Include relevant
   FlagGems operator reproductions under the container's `/bug` directory and
   explain whether earlier analysis or narrower tests could have exposed each
   problem sooner. Identify practices and artifacts worth reusing, as well as
   repeated work, avoidable detours, missing checks, unclear records, tooling
   gaps, and weaknesses in correctness, performance, `eager`, or `graph`
   coverage. Explicitly decide whether the current adaptation workflow needs
   improvement. For every recommended improvement, state the supporting
   evidence, expected benefit, scope, priority, risks, and the concrete rule,
   script, template, test, or automation change proposed. Distinguish verified
   facts from retrospective judgment, and record improvements that are not yet
   implemented as follow-up items. Do not silently change shared repository
   rules, templates, or tooling solely from a retrospective; implement those
   changes only when the user requests or approves them. The overall adaptation
   workflow is not closed until this retrospective is complete and consistent
   with the final adaptation summary.

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
