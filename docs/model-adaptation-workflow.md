# Model adaptation workflow

## Workspace split

Treat the adaptation workspace as two separate locations. The **remote work
directory** is each user-approved `host_root` and its verified container mapping;
it contains runtime configuration, diagnostics, runs, caches, evaluation
artifacts, and reproducers, not source checkouts. The **local work directory** is
this management repository; it
contains curated model/platform records, reusable tools, templates, and concise
references to remote evidence. Do not mirror raw remote artifacts locally, and do
not infer remote authorization from local file existence.

## Remote workspace prerequisite

This prerequisite applies before any remote write in any selected phase; it does
not authorize execution of an unselected phase. Obtain the user's exact SSH host
aliases and absolute host work roots, plus the corresponding absolute container
roots for container work. Record one `{host_alias, host_root, container_root}` entry
per host in `workspace.roots`, exactly covering `target.hosts`; roots may differ by
host. Each `container_root` describes the container selected by
`target.container_name`, not arbitrary containers on that host. Verify the actual
paths and that container's mapping to the approved host root. Separately confirm
the mapping to the same host root for every other participating container,
including evaluation containers. Until the required paths and authorization
are confirmed, perform only read-only verification: no remote directory creation,
deployment, source update, or command that writes remotely. These declarations
and local helper checks do not create directories or mounts and do not provide
OS-level write isolation.

Place all new remote process artifacts under that approved root using ordered
names: environment collection and runtime configuration in `01-environment/`,
issue-specific one-off scripts in `02-issues/`, acceptance
tools/configurations in `03-acceptance/`, per-run logs/results in `04-runs/`,
temporary files in `05-tmp/`, caches in `06-cache/`, and operator reproducers in
`07-bugs/`. Do not create a source-repository subdirectory or mirror in this
work root. Product changes are made directly in the adaptation container's
existing editable-installed Plugin source after verifying its package metadata,
import path, Git root, revision, and working-tree ownership. The final accepted
model launcher is the one deliberate root-level
artifact: `<host_root>/start-model.sh`, mapped and verified as
`<container_root>/start-model.sh`. Inside a container, use its verified corresponding
root. A reproducer already available at that container path must be run in place,
not copied to `/bug`. Configure implicit destinations such as framework/compiler caches, Python
bytecode, downloads, temporary files, and subprocess logs/results as well. Set an
explicit `cwd`/`workdir` for every remote command, and stop on a failed shell `cd`.
Changing directory alone is not a sandbox: check the actual backing paths through
symlinks/bind mounts, including destinations not yet created. Pause if a tool would
write outside the approved root without separate authorization.

Existing external weights, datasets, and system dependencies may be referenced
read-only. Other source trees remain read-only except for the verified editable
Plugin source and explicitly authorized synchronization of the existing
FlagGems checkout. If either source identity or permission cannot be verified,
pause; do not clone a replacement under the work root. Do not automatically move
or duplicate repositories/data, change mounts, or stop/restart the adaptation
container.

The current numbering applies to every new write and to run-plan schema 5.
Directories and evidence references using the previous numbering remain
historical facts; do not rename, merge, delete, or rewrite them until the exact
remote paths and users are verified and the user explicitly authorizes a
migration. Schema 4 run plans are not silently reinterpreted under the new
layout.

The local `models/` layout below remains the curated record and maintained-helper
layout. Keep remote raw artifacts in the approved remote root and reference their
exact paths and concise evidence locally; do not copy all raw work back. The
Container `/bug` is an optional compatibility path governed by step 3.6, not a
second storage location or permission to write outside this workspace.

## Phases

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
   making platform changes. Keep only Markdown analysis in that local
   `environment/` directory; keep collection helpers, runtime configuration, and
   raw collection outputs under the approved remote root's `01-environment/`.
   Record the target host aliases,
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
      changes, place a copy or wrapper in `acceptance/` instead of silently
      changing the common baseline.
   6. **Final adaptation summary.** Create or update
      `models/<model-name>/<platform>/acceptance/adaptation-summary.md`. Summarize
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
5. **Retrospect on the adaptation.** After acceptance, create or update
   `models/<model-name>/<platform>/acceptance/adaptation-retrospective.md` for
   each adapted platform. Review the complete work from architecture and
   inference-path analysis through environment analysis, implementation, and
   acceptance. Summarize the significant problems encountered, their symptoms,
   root causes, impact, discovery stage, attempted approaches, final solutions,
   verification evidence, and any unresolved consequences. Include relevant
   FlagGems operator reproductions under the approved root's `07-bugs/`, including
   the verified container path and any `/bug` compatibility mapping or explicit
   exception actually used under step 3.6, and
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
