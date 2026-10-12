# Remote operations policy

These rules are required by [AGENTS.md](../AGENTS.md) before remote operations or
changes to inventory, group variables, Ansible entrypoints or playbooks. Code
paths are relative to the repository root. Workspace and launcher requirements
apply to tasks involving those resources; this document does not grant access.

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

## Remote work directory

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
  installation/source declared writable by the selected framework profile after
  verifying the service interpreter, package metadata, actual import path and
  ownership. Record Git revision/diff when available, otherwise package version
  and before/after installed-file hashes. Modify the actual container-installed
  component directly; an editable install is not required. Never select a second
  checkout/version via `PYTHONPATH`, `sys.path` or an equivalent import override.
  For `vllm-plugin-fl`, Plugin, FlagGems and installed FlagGems-vllm may receive
  necessary product fixes; vLLM stays read-only. Preserve existing changes and
  follow the profile's separate synchronization procedure. Do not
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
  the profile's final accepted primary execution mode and per-Host graph level
  selected through its evidenced stepwise fallback and performance review,
  keep logs/results under `04-runs/`
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
- Keep only the interpreter/shebang, necessary service command and indispensable
  environment/path setup in the final launcher. Move package installation,
  source updates, patch application, cleanup, diagnostic probes, evaluation,
  polling and report generation out of it. Perform readiness and evidence checks
  during acceptance, not on every launch. A necessary service-conflict guard
  may remain minimal; never add automatic process killing.
- For image delivery, required launchers, configs, templates, modified components
  and runtime libraries must reside in the container filesystem included in the
  image. Use container paths in commands, never host paths. Resolve symlinks,
  editable-install targets and mounts: bind mounts and volumes are not included
  by an ordinary container image commit. If the work root is mounted, retain the
  root-level launcher as evidence and place the verified delivery copy and its
  necessary dependencies at a recorded container-internal delivery path before
  handoff; verify matching contents and recheck the delivery command.
  This is a required delivery artifact, not an alternate development checkout.
  External weights/tokenizers or other deliberately external inputs require an
  explicitly agreed deployment mount and container path; do not silently rely
  on the adaptation host's directories or copy weights without authorization.
  Logs/caches must use container-writable `04-runs/` and `06-cache/` paths.
  Verify imports and launch/readiness without `PYTHONPATH` or incidental host
  development mounts. Record required-file paths, mount/image ownership, hashes
  and installed-component identities. When image packaging is requested, test a
  fresh container from that image with only declared deployment mounts and record
  the image identity; until then report image validation as pending. Do not stop,
  restart or remove the active adaptation container to perform these checks.
- Set an explicit `cwd`/`workdir` for every remote command and stop on a failed
  `cd`. Resolve symlinks and bind mounts. Existing external weights, datasets,
  dependencies, and source trees other than profile-declared installed writable
  components and explicitly authorized synchronization/delivery files are read-only. Do not
  move or duplicate them, change mounts, or stop/restart the adaptation container
  to arrange the workspace. If the selected profile's required writable component
  cannot be identified as the actual installed component or its required build
  source cannot be verified,
  stop and report the blocker instead of creating a replacement checkout under
  the work root.

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
