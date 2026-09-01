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
  root. Store environment analysis and collection artifacts in `environment/`;
  adaptation analysis, reference indexes, commands, configurations, patches,
  operator implementations, focused tests, and working notes in `adaptation/`;
  and accuracy, performance, communication-test configurations or wrappers,
  concise results, and final acceptance documents in `acceptance/`.
- Use `./scripts/new-model <model-name>` to create a new workspace from
  `models/_template`. Never overwrite an existing model directory.
- Keep model-wide tokenizer work, common patches, and consistency cases in
  `_shared`. Route vendor-specific files to the appropriate one of the three
  platform work directories above.
- Before executing a new remote adaptation command, save the repeatable version
  under the corresponding platform's `adaptation/` directory. Do not leave the
  only copy in chat or shell history.
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
      capability. Create a gap list under `adaptation/` that identifies the
      required plugin changes, operator source, `eager` and `graph` impact,
      dependencies, risks, and planned verification for each item.
   2. **Capture the baseline and enforce modification boundaries.** Inside the
      running adaptation container, record the repository path, revision, branch,
      and working-tree status for the plugin, vLLM, and FlagGems before editing.
      The agent may modify the plugin source directly, but the vLLM source tree
      must remain read-only and unchanged throughout the adaptation. Do not stop,
      restart, or remove the adaptation container. Preserve before-and-after
      vLLM revision and status evidence, and store the plugin baseline information
      under `adaptation/`.
   3. **Synchronize FlagGems before operator integration.** Before checking or
      integrating any FlagGems operator, update the FlagGems repository inside
      the running adaptation container to the latest commit of its intended
      tracked branch. Record the remote, branch, upstream, revision, and
      working-tree status before updating. Proceed only when the worktree is clean
      and the intended branch and upstream are unambiguous; fetch and use a
      fast-forward-only pull, never reset, force-update, or discard local changes.
      Record the resulting revision and synchronization command under
      `adaptation/`. If synchronization cannot complete, report the exact blocker
      and do not continue operator selection against a stale revision.
   4. **Integrate operators already available in FlagGems.** For each operator
      the plugin does not invoke or support, inspect the plugin's
      dispatch/backend design and the synchronized FlagGems revision. When
      FlagGems has a compatible implementation, follow the existing plugin architecture to
      add the required dispatch, backend, registration, or platform binding.
      Never bypass the plugin design with an ad hoc direct call. Add focused
      integration and numerical tests, and record the FlagGems symbol, revision,
      plugin entry point, supported constraints, and results under `adaptation/`.
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
      results, and limitations under `adaptation/` and in the final
      `acceptance/adaptation-summary.md`.
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
      exact container-side issue path and reproduction command in the platform's
      `adaptation/` record. Do not stop or restart the adaptation container to
      create or test the reproducer, and do not place model weights, secrets,
      large logs, or unrelated adaptation artifacts under `/bug`.
   7. **Complete runtime configuration and integration.** Map parallelism, memory
      behavior, execution stages, model configuration, and launch arguments to
      the target platform. Add reproducible plugin-side configurations, wrappers,
      scripts, and optimization settings without changing vLLM source. Store all
      resulting files under `adaptation/`.
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
   10. **Consolidate reproducible records.** Continuously record verified results,
      problems, causes, attempted fixes, final solutions, unresolved risks, and
      next steps. Save commands, configurations, focused tests, plugin diffs or
      patches, service lifecycle actions, FlagGems evidence, and proof that vLLM
      remained unchanged under `adaptation/` before entering acceptance.
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
      and then run the formal evaluation. Verify the expected sample count,
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
