# Offline operations regression tests

Run `./scripts/bootstrap-control-node`, then `./scripts/syntax-check` from the
repository root. The latter includes the workflow/acceptance and operations
tests, shell syntax checks, public and model-specific playbook syntax checks,
and the workspace audit. Audit warnings remain outstanding evidence reviews;
they are not remote verification.

The unit tests use only temporary local files and do not use the operator's SSH
configuration or contact managed hosts. The GitHub workflow runs
`./scripts/syntax-check --offline` on an ordinary Linux runner. Offline mode
validates repository inventory structure and Ansible parsing but deliberately
does not compare it with the operator-only `~/.ssh/config`; the default local
command retains that comparison. Neither mode executes real-host playbooks or
substitutes for model acceptance.

`scripts/check_local_operations.py` detects shell scripts by their shebang and
Ansible playbooks by their top-level play structure. Runtime/model/vendor YAML
is not passed to `ansible-playbook`. Only `bash -n` and `--syntax-check` are used;
syntax success does not prove that deployed Python dependencies or runtime
paths are complete, which require separate bundle/contract smoke tests.
