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
  configuration owned outside this repository, rebooting, stopping a service,
  or starting a large download on more than one host.
- Prefer idempotent Ansible modules over shell commands. If a command is needed,
  define `changed_when` and `failed_when` deliberately.

## Model downloads

- Require one explicit target in `modelscope_hosts`, a model ID, and an absolute
  destination path. Validate a new host before adding it to that group.
- Check free disk space before starting. Do not lower the configured threshold
  without explaining why.
- Start long downloads asynchronously and return the Ansible job ID. Use the
  async-status playbook to monitor them.
- A completed command is not enough: verify expected model metadata and report
  the final directory size.

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
- Keep model-wide downloads, tokenizer work, common patches, and consistency
  cases in `_shared`. Keep vendor-specific commands, configs, patches, and
  results inside that platform's directory.
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
