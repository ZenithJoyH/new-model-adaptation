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

   - **Adapt the plugin from the model analysis.** Implement all model and
     platform support within the plugin, its owned operators, dispatch layers,
     bindings, configuration, or wrappers. Modifying the upstream vLLM source
     code is prohibited throughout the adaptation. For every required operator
     that the plugin does not invoke or support, inspect the plugin's
     dispatch/backend design and verify whether the pinned FlagGems revision has
     a compatible implementation. If FlagGems contains the operator, follow the
     existing plugin architecture to add the required dispatch, backend,
     registration, or platform binding; never bypass the plugin design with an
     ad hoc direct call. If FlagGems has no compatible implementation, add a
     plugin-owned Triton operator and connect it through the same plugin dispatch
     framework. The Triton implementation must support `graph` capture/replay,
     not only `eager` execution. Follow the target graph runtime constraints by
     avoiding capture-time host synchronization, unsupported dynamic allocation,
     data-dependent host control flow, and unstable tensor shapes or addresses.
     Add applicable numerical, dtype, shape, layout, device, and execution-mode
     tests, including dedicated `eager` and `graph` capture/replay coverage.
     Record the checked FlagGems revision and search evidence, explicitly mark
     the operator as missing from FlagGems, and document the Triton location,
     supported constraints, plugin integration, test results, and remaining
     limitations under the platform's `adaptation/` directory and in the final
     `acceptance/adaptation-summary.md`.
   - **Complete configuration and integration.** Map model operators,
     parallelism, memory behavior, and execution stages to platform capabilities;
     resolve compatibility gaps and select reproducible runtime configurations
     and optimization steps without modifying vLLM source code. Store the
     resulting scripts, configurations, patches, implementations, and focused
     test files under the platform's `adaptation/` directory.
   - **Verify incrementally and keep records current.** Test focused components
     before full service bring-up. Continuously write verified results, problems,
     causes, solutions, unresolved risks, and next steps to the corresponding
     model record and the platform's `adaptation/` directory.
   - **Control the adaptation service lifecycle.** Stop or restart only the
     current adaptation's inference service or related process when required for
     configuration changes, recovery, or verification. Never stop, restart, or
     remove the adaptation container itself. Confirm the exact service or process
     before acting, do not affect shared or unrelated services, and record each
     stop or restart and its outcome under `adaptation/`.
4. **Accept the adaptation.** Complete all of the following acceptance work:

   1. Run the model successfully in both `eager` mode and `graph` mode.
   2. Run the formal accuracy evaluation on the target host inside a container
      based on `harbor.baai.ac.cn/flageval/flageval-llmeval:v1` or
      `harbor.baai.ac.cn/flageval/flageval-llmeval:arm64`, as appropriate for the
      target platform. Use `test/Accuracy_test/llmrun.py`; do not substitute
      another runner unless the user explicitly requests it. Prepare a
      model-specific `llm_config.json`, run `llmrun.py` with `--preflight-only`,
      and then run the formal evaluation. Verify the expected sample count,
      process completion, final result and sample files, accuracy metrics,
      timeouts, and explicit pass criterion.
   3. Only after the accuracy evaluation in step 2 has completed and met its pass
      criterion, use `test/perf_test/` for final inference performance testing or
      profiling. Do not start performance testing while accuracy is incomplete or
      failing. Use `test/nccl_test/` for communication validation when relevant.
   4. Record the exact test scripts, configuration, dataset or case set, service
      mode, container name and image, commands, environment, result locations,
      metrics, pass criteria, and outcomes under the platform's `acceptance/`
      directory. Keep large datasets and raw outputs local or on remote storage.
      If a common test asset needs model-specific changes, place a copy or wrapper
      in `acceptance/` instead of silently changing the common baseline.
   5. Create or update
      `models/<model-name>/<platform>/acceptance/adaptation-summary.md`. Summarize
      the scope, environment, reference files, implementation changes,
      reproducible procedure and configuration, correctness and performance
      verification, encountered problems and solutions, final status, unresolved
      limitations, and next steps. Do not mark the adaptation complete until
      every acceptance item has passed and the summary reflects the verified
      outcome.

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
