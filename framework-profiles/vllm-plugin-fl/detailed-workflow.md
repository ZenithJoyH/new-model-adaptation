# vllm-plugin-fl implementation and acceptance

Applies only to this profile. Inherit the [common workflow](../../docs/model-adaptation-workflow.md); legacy direct records retain their paths.

3. **Perform the adaptation.** Combine the model architecture and inference-path
   analysis, the requested platform's environment analysis, and the
   adaptation-related reference files provided by the user. Carry out the work
   through the following substeps:

   1. **Define the plugin adaptation plan.** Use the architecture analysis,
      environment analysis, and user-provided references to map every model
      component, inference stage, key operator, parallelism requirement, and
      runtime dependency to the current plugin path and target platform
      capability. Include the gap list in the platform environment analysis or
      the relevant numbered adaptation issue; identify the required plugin
      changes, operator source, `eager` and `graph` impact, dependencies, risks,
      and planned verification for each item. This plan is preparation context,
      not an issue record.
      Read `docs/plugin-contribution-policy.md` and the target plugin checkout's
      current design/contribution guidance before choosing changes. Explain
      ownership, interface contracts, alternatives, shared callers, optional
      dependencies, guards, defaults and representative regression coverage.
   2. **Capture the baseline and enforce modification boundaries.** Inside the
      running adaptation container, record the repository path, revision, branch,
      and working-tree status for the plugin, vLLM, and FlagGems before editing.
      Verify that the installed Plugin resolves to the identified editable source
      tree, then make required product changes directly in that tree; do not make
      or use a second checkout under the remote work root. The vLLM source tree
      must remain read-only and unchanged throughout the
      adaptation. Do not stop,
      restart, or remove the adaptation container. Preserve before-and-after
      vLLM revision and status evidence. Store baseline and environment facts in
      `environment/environment-analysis.md`. If a dirty tree, revision
      mismatch, or modification-boundary violation becomes an adaptation issue,
      create a numbered Markdown issue record under `adaptation/`.
   3. **Synchronize FlagGems before operator integration.** Before checking or
      integrating any FlagGems operator, update the FlagGems repository inside
      the running adaptation container to the latest commit of its intended
      tracked branch. First verify that writing this checkout is authorized under
      the remote workspace prerequisite. Without authorization or a verified
      existing checkout, pause synchronization and report the blocker; do not move
      the existing tree or create a replacement checkout under the work root.
      Record the remote, branch, upstream, revision, and
      working-tree status before updating. Proceed only when the worktree is clean
      and the intended branch and upstream are unambiguous; fetch and use a
      fast-forward-only pull, never reset, force-update, or discard local changes.
      Record the resulting revision and synchronization command in the platform
      environment analysis or relevant numbered issue. If synchronization cannot
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
      adaptation stage, keep a dedicated issue directory under the approved
      remote root's `07-bugs/` and execute it through that directory's verified path
      below `container_root`. If the case already exists and is accessible there,
      do not copy, recreate, or synchronize it into container `/bug`. Use `/bug`
      only when a required tool or upstream reproduction workflow specifically
      requires that exact path. In that case, use a user-approved and verified
      mapping of the same `07-bugs/` directory to `/bug`, or an explicit outside-root
      exception; never maintain a second copy. If neither is available, pause the
      `/bug`-dependent operation and report the required approval; do not establish
      mounts or relocate files automatically. Do not create this directory at the
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
      the packaged test reproduces at the verified container path corresponding
      to `07-bugs/`; when `/bug` is genuinely required, verify the approved mapping
      or the exact location covered by the user's exception.
      Record the approved host-side storage path, container-side issue path,
      any `/bug` mapping or exception actually used, and reproduction command in the applicable
      numbered Markdown issue record under `adaptation/`. Do not stop or restart
      the adaptation container to create or test the reproducer, and do not place
      model weights, secrets, large logs, or unrelated adaptation artifacts in
      the reproducer directory.
   7. **Complete runtime configuration and integration.** Map parallelism, memory
      behavior, execution stages, model configuration, and launch arguments to
      the target platform. Add reproducible plugin-side configurations, wrappers,
      scripts, and optimization settings without changing vLLM source. Keep the
      only necessary production implementation and maintainable plugin regression
      tests in the plugin repository inside the running adaptation container.
      Keep one-off process code in the approved root's `02-issues/` or `05-tmp/`,
      outside all source repositories. Keep intermediate runtime configuration
      under the remote root's `01-environment/`. Do not call an intermediate
      launcher final. After acceptance identifies the final graph configuration,
      place its executable entry point at the remote root's `start-model.sh`.
      Build that final script from the smallest accepted launch command. Remove
      diagnostic/profiling/tracing/dump controls, temporary paths, obsolete
      workarounds, duplicated defaults, experimental tuning, and unrelated
      model/platform settings unless controlled acceptance proves they are still
      required. Reconstruct it as a production launcher instead of copying the
      last diagnostic, accuracy, or performance command; specifically exclude
      the performance-only `--no-enable-prefix-caching` argument. Prefer engine
      defaults whenever explicit pinning is unnecessary, and retain no argument
      solely because it appeared in an earlier run. Document the correctness, safety, resource-placement, or
      reproducibility reason for every retained environment variable and
      argument; explicitly pin a default only when the reason is recorded. Reference exact
      container paths, branches, revisions or commits, and verification commands from the relevant
      numbered issue record; do not copy these artifacts into `adaptation/`. Do
      not configure an unnecessarily
      small `--max-model-len` when starting the model service. First verify the
      model's actual maximum supported context length from its configuration and
      implementation. If that length is greater than 50000 tokens, use 50000 for
      the initial service configuration; if it is 50000 or fewer, use the model's
      full supported maximum. If the supported maximum cannot be verified, stop
      and resolve it rather than guessing. Do not silently reduce the value to
      conceal memory, graph-capture, or runtime problems. Record the evidence,
      computed value, final launch argument, and exact remote configuration path
      in `environment/environment-analysis.md`; when a context-length setting causes or
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
      repository within its authorized write scope; remote one-off process scripts
      and code remain in the approved root's `02-issues/` or `05-tmp/`, outside all
      source repositories. Remote configurations, raw logs, and other artifacts
      remain in the corresponding root subdirectories defined above. Reference
      each retained item by exact path,
      revision or commit when applicable, command, and result. Include service
      lifecycle actions, FlagGems evidence, and proof that
      vLLM remained unchanged in the applicable issue record before acceptance.
   11. **Review plugin design and the final diff.** Record the review in the
      relevant numbered issue and final acceptance summary, following
      `docs/plugin-contribution-policy.md`. Review the confirmed PR base, actual
      HEAD, dirty and untracked changes, inherited work, multi-model/platform
      impact, regression evidence and workaround exit criteria. Resolve design
      blockers before marking adaptation complete; after material changes,
      refresh the affected review. Do not infer untested platform support or
      full acceptance from the design review, or commit/push/create a PR without
      the user's explicit request.
4. **Accept the adaptation.** Complete all of the following acceptance work:

   1. **Execution-mode acceptance.** Run the model successfully in both `eager`
      mode and `graph` mode. This step verifies only that both execution modes
      can run successfully. After it passes, perform all remaining acceptance
      work—including the small-batch sanity check, formal accuracy evaluation,
      performance evaluation or profiling, and communication validation when
      applicable—using the accepted `graph`-mode service configuration. Do not
      require duplicate accuracy or performance acceptance in `eager` mode.
   2. **Ten-concurrency accuracy and performance sanity check.** Before the
      formal accuracy evaluation, send a small, fixed set of simple requests with
      request concurrency set to 10 against the accepted `graph`-mode service
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
      and then run the formal evaluation. The frozen configuration may contain
      one or more FlagEval/lm-eval tasks. Freeze an exact metric threshold and
      complete sample count for every task; for multiple tasks, use task-keyed
      sample counts and optional task-keyed dataset descriptors. GPQA is one
      supported configuration, not a required or exclusive dataset. Tasks that
      need different generation parameters or chat templates must use separate
      frozen configurations and runs. Formal full accuracy evaluation must
      use request concurrency of at least 32; the concurrency of 10 applies only
      to the preceding small-batch sanity check. Start at 32 or a higher verified
      safe concurrency and increase it as resources and service stability allow
      to minimize evaluation time. Do not sacrifice valid results, complete
      sample coverage, or service stability for speed. If concurrency 32 cannot
      run reliably, diagnose and resolve the blocker rather than silently running
      formal acceptance below 32. Record the configured and observed effective
      concurrency, tuning rationale, throughput, elapsed time, errors, and
      timeouts under `acceptance/`. Verify the expected sample count,
      process completion, final result and sample files, accuracy metrics,
      timeouts, and explicit pass criterion. Mark this formal accuracy substep
      passed or complete when the valid full-run result meets every metric
      threshold frozen before the run. The metric does not need to equal `1.0`:
      individually incorrect answers are allowed within the configured threshold
      and do not fail the formal test by themselves. Do not carry the preceding
      sanity check's per-question all-correct rule into formal accuracy. A final
      timeout response is an incorrect/failed sample: retain it in the complete
      sample set and metric denominator, and never drop it or hide it with retries.
      A limited number of timeout samples may coexist with a pass only when all
      frozen metrics still meet their thresholds. Missing or invalid samples,
      non-timeout request/execution errors, or any metric below its threshold
      still prevent a passing formal result.
   4. **Final performance evaluation.** Only after the formal accuracy evaluation
      in step 3 has completed and met its pass criterion, use `test/perf_test/`
      against the same accepted `graph`-mode configuration for final inference
      performance testing or profiling. Do not start the formal performance
      evaluation while full accuracy is incomplete or failing. Keep prefix
      caching enabled for sanity, accuracy, and every other non-performance run.
      Before any performance or profiling request, switch to a performance-only
      service launch profile and explicitly disable server-side prefix caching
      on the exact service instance under test by adding the exact
      service launch argument `--no-enable-prefix-caching`. Verify this argument
      in the effective launch configuration and startup evidence, and bind the
      exact argument and evidence reference into the formal performance receipt.
      The benchmark client does not configure the model service. Client-side
      `--random-prefix-len 0` only shapes the workload and is not evidence that
      the server cache is disabled. If the exact service argument or its effective
      disabled state is unverified, do not run or accept the performance result.
      Do not put this argument in the common graph profile, and restore the normal
      prefix-cache-enabled profile before any later non-performance test.
      Use `test/nccl_test/` for communication validation when relevant, also
      under the `graph`-mode acceptance configuration.
   5. **Acceptance evidence.** Record the exact test scripts, configuration,
      dataset or case set, service mode, container name and image, commands,
      environment, result locations, metrics, pass criteria, and outcomes under
      the platform's `acceptance/` directory. Explicitly identify `graph` as the
      execution mode used for all acceptance work after step 1. Keep new remote
      datasets/caches and raw outputs under the approved remote root's `06-cache/`
      and `04-runs/`; existing external datasets may be referenced read-only. Local
      records retain paths and concise evidence, not a full copy of remote outputs.
      If a common test asset
      needs model-specific
      changes, place a copy or wrapper in the approved remote `03-acceptance/` instead of silently
      changing the common baseline.
   6. **Final adaptation summary.** Create or update
      `models/<model-name>/<platform>/frameworks/vllm-plugin-fl/acceptance/adaptation-summary.md`. Summarize
      the scope, environment, reference files, implementation changes,
      reproducible procedure and configuration, correctness and performance
      verification, encountered problems and solutions, final status, unresolved
      limitations, and next steps. Before marking completion, verify that each
      approved target `host_root` contains executable `start-model.sh`, that its
      verified container path launches the final accepted graph configuration,
      and that it routes logs/results to `04-runs/` and caches to `06-cache/`
      without affecting an unrelated service or the adaptation container. Record
      both paths, SHA-256, syntax check, launch/readiness result, complete
      arguments, confirmation that performance-only and diagnostic flags are
      absent, the result of the minimal-parameter review and justification for
      every retained explicit setting, revisions, and verification date. Do not mark the adaptation
      complete until every acceptance item and this launcher verification have
      passed and the summary reflects the verified outcome.
