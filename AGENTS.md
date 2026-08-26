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
  configuration owned outside this repository, rebooting, or stopping a service.
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
- Use `./scripts/new-model <model-name>` to create a new workspace from
  `models/_template`. Never overwrite an existing model directory.
- Keep model-wide tokenizer work, common patches, and consistency cases in
  `_shared`. Keep vendor-specific commands, configs, patches, and results inside
  that platform's directory.
- Before executing a new remote adaptation command, save the repeatable version
  in the corresponding model/platform directory. Do not leave the only copy in
  chat or shell history.
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

## Model adaptation analysis workflow

1. Before platform adaptation begins, create or update
   `models/<model-name>/architecture-and-inference.md`. Analyze the model's
   overall architecture and end-to-end inference path. Break down and enumerate
   the complete model structure, including the relevant configuration, major
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
2. For each adaptation platform explicitly requested by the user, create or
   update `models/<model-name>/<platform>/environment-analysis.md` before making
   platform changes. Record the target host aliases, accelerator model and
   topology, operating system or container environment, driver and runtime,
   inference framework and platform plugin versions, compiler or toolchain,
   available resources, verification commands, compatibility gaps, and the
   environment conclusions that affect the adaptation plan. Do not create
   environment analyses for platforms the user did not request.
3. Complete the end-to-end adaptation by combining the model architecture and
   inference-path analysis, the requested platform's environment analysis, and
   the adaptation-related reference files provided by the user. Use these inputs
   to determine the implementation plan, map model operations and parallelism to
   platform capabilities, resolve compatibility gaps, select configurations and
   optimization steps, and define correctness and performance verification.
   Feed verified results, encountered problems, causes, solutions, unresolved
   risks, and next steps back into the corresponding model and platform records
   throughout the adaptation.
   The adaptation must run successfully in both `eager` mode and `graph` mode.
   After starting the inference service, execute 10 GQQA test cases and verify
   every response against its expected answer. The adaptation is not complete
   unless both execution modes pass and all 10 responses are correct (10/10).
4. After the adaptation is complete, create or update
   `models/<model-name>/<platform>/adaptation-summary.md` for that model and
   platform. Summarize the adaptation scope, analyzed environment, reference
   files used, implementation changes, final reproducible procedure and
   configuration, correctness and performance verification, encountered
   problems and their solutions, final status, unresolved limitations, and next
   steps. Do not mark the adaptation complete until this summary reflects the
   verified outcome.

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
