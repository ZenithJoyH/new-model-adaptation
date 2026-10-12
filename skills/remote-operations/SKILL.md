---
name: remote-operations
description: Perform a user-requested check or change on specified model-adaptation hosts, or maintain this repository's inventory and Ansible entrypoints. Read this repository-local entry by path when the task requires remote operations; local-only model analysis and documentation do not require remote execution.
---

# Model adaptation remote operations

This entry uses the current repository's inventory and maintained commands.
Before acting, read [the remote operations policy](../../docs/remote-operations.md).
For adaptation, also follow the selected framework and
[adaptation policy](../../docs/adaptation-policy.md). Reading a policy grants no
additional access or permission.

1. Resolve the requested operation and exact inventory aliases. List inventory
   locally when target discovery is requested. Check only the selected hosts;
   do not expand to `managed` merely because more hosts exist.
2. For diagnostics, choose the narrowest existing command from the table below.
   Use a `--limit` for remote checks unless the user requests the whole inventory.
   Check connectivity with the maintained wrapper; the bastion can return status
   zero even when it did not reach a host. Focused read-only SSH is allowed by
   the policy, with an explicit remote working directory.
3. For a requested change, inspect current state first. Verify approved work roots,
   container mappings and profile source ownership where applicable. Use Ansible
   for repeatable/multi-host changes, check mode when supported, and one host first.
   Verify before expanding, with `serial: 1` across a hardware group. Generic
   entrypoints retain per-command approval; existing authorization still defines
   the permitted scope.
4. Report each host as unchanged, changed, failed or unreachable, with the relevant
   verification. Stop repeated failing attempts to inspect the cause. Missing
   authorization, an unverified root or an unrelated workload is a scope blocker,
   not permission to broaden the operation.

Run commands from the repository root, using the exact relative entrypoints:

| Operation | Entry |
| --- | --- |
| Local host list | `./scripts/inventory` |
| Selected host connectivity | `./scripts/connectivity-check --limit <Host>` |
| Selected host health | `./scripts/health-check --limit <Host>` |
| Selected host accelerator status | `./scripts/accelerator-check --limit <Host>` |
| Explicitly requested repeatable change | `./scripts/playbook <reviewed-playbook> --limit <Host>` |
| Explicitly requested operation without a suitable dedicated entry | `./scripts/ansible <Host> <reviewed-module-and-arguments>` |

After inventory/group-variable changes, run `./scripts/inventory`. After changes
to inventory, variables or playbooks, run `./scripts/syntax-check`.
For offline repository validation, their `--repository-only` and `--offline`
modes avoid dependence on the operator's full local inventory/model records.

This Skill is an instruction entry, not a native accuracy/performance evidence
producer. It has no `interface.json` or journal capability; do not pass it to
`skill_bundle.py` or treat a host check as adaptation acceptance.
