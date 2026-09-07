# Offline operations regression tests

Run `./scripts/bootstrap-control-node`, then `./scripts/syntax-check` from the
repository root. The latter includes the workflow/acceptance and operations
tests, shell syntax checks, public and model-specific playbook syntax checks,
and the workspace audit. Audit warnings remain outstanding evidence reviews;
they are not remote verification.

The operations fixtures use a temporary inventory containing only synthetic
`OPS-A`/`OPS-B` hosts with `connection=local`. Download fixtures retain only the
actual input assertions and a debug sentinel; they never execute download or
remote diagnostic tasks. ModelScope fixtures mock pip's changed prediction and
use check mode with temporary CLI paths. They do not install packages, create
real CLI links, use the operator's SSH configuration, or contact managed hosts.

Ansible needs local process/IPC support even for these fixtures. A sandbox that
blocks its local RPC socket must report a test infrastructure failure; do not
interpret that failure as a passing negative test or skip verification silently.
The GitHub workflow runs the same entry point on an ordinary Linux runner. It
does not execute real-host playbooks or substitute for model acceptance.

`scripts/check_local_operations.py` detects shell scripts by their shebang and
Ansible playbooks by their top-level play structure. Runtime/model/vendor YAML
is not passed to `ansible-playbook`. Only `bash -n` and `--syntax-check` are used;
syntax success does not prove that deployed Python dependencies or runtime
paths are complete, which require separate bundle/contract smoke tests.
