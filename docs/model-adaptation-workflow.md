# Common model adaptation workflow

The five phases organize records; they do not impose one framework's implementation
or tests on another framework. Read the selected profile's workflow and acceptance
documents. Its ordered `acceptance.steps`, supported platforms, writable components
and execution modes determine the actual procedure.

- `draft`: architecture and read-only discovery only.
- `experimental`: implementation and the explicitly declared validation substeps
  are allowed within the approved task; complete formal acceptance is unavailable.
- `active`: the defined complete acceptance contract is available.
- Profile status describes process capability, never proof that a model/platform passed.

## Workspace and source boundaries

Use one approved remote root per exact model/platform/framework/Host. Verify
`host_root`, `container_root`, container identity and actual mapping before writes;
verify every evaluation-container mapping separately. Set explicit workdir and
stop on failed cd. Resolve symlinks and implicit writes. Use `01-environment/`,
`02-issues/`, `03-acceptance/`, `04-runs/`, `05-tmp/`, `06-cache/`,
`07-bugs/`; never mirror source repositories or raw remote data locally.
Product changes belong only in verified profile-declared source trees. Preserve
unrelated work. The adaptation container must remain running. Only current-task
services/processes may be restarted after their identities are resolved.
Existing external dependencies, weights and datasets are read-only; source sync
requires its existing authorization. Existing remote paths must not be migrated
without checking users/evidence and the user's migration authorization.
A reproducer in `07-bugs/` runs in place; `/bug` may only expose that same approved
directory when an upstream tool actually requires it.

Local explicit records are `models/<model>/<platform>/frameworks/<framework>/`.
Keep environment analysis, numbered issue records, acceptance reports and
retrospectives in Markdown. Runtime files and full test artifacts remain remote.

## 1. Architecture

Write `architecture-and-inference.md` at model level in Chinese. Cover overall
structure, configuration, tensor/data flow, inference stages, parallelism and
key operators grounded in the actual implementation. Distinguish evidence,
assumptions and unresolved questions. Framework-specific execution paths belong
in the selected framework's records.

## 2. Environment

Analyze only the requested platforms/Hosts. Record hardware, topology, container,
drivers, toolchain, package/import/source identities, revisions, available resources,
root mappings and compatibility gaps. Search prior verified troubleshooting
experience before changes; revalidate its applicability.

## 3. Implementation

Follow the profile's concrete steps, combining model analysis, environment facts
and user references. Establish baselines; change one material variable at a time.
Use existing extension points; test incrementally, retain issue evidence and review
the final diff/ownership/affected callers. Put one-off code outside product trees.
vLLM Plugin and Torch-FL have separate implementation instructions.

## 4. Acceptance

Execute only the selected profile's declared substeps, in declared order, after
verified prerequisites. Optional steps are explicitly added to the workspace's
ordered substep map before execution. Never invent a missing runner or interpret
unavailable capability as a pass.

Formal metrics pass at frozen thresholds with complete valid coverage; individual
wrong answers and retained timeout-as-incorrect samples do not alone fail a valid
full run. Native result/sample verification is mandatory. A Markdown hash is not
a formal receipt. Performance cache behavior is framework-specific: disable it
with the declared mechanism if applicable; do not add vLLM flags to Python API tests.

For active complete service adaptations, verify each root-level `start-model.sh`
against the final accepted primary mode, runtime identity, executable permissions,
syntax, actual readiness, minimal required settings, normal cache behavior and
root mappings. Logs/results stay in `04-runs/`, caches in `06-cache/`. Reference
its exact paths, SHA-256 and verification date locally. Never stop the container.
Experimental Torch-FL bring-up can pass its individual checks and reach
`functional`; it cannot claim full accuracy, performance, `optimized` or complete
formal acceptance.

## 5. Retrospective

Review the selected work, verified problems/solutions, unsuccessful attempts,
limitations and workflow improvements. Experimental work may be reviewed without
pretending formal acceptance has completed. Promote only reusable verified
experience, citing revisions and applicable scope. Repository-wide changes still
require a relevant user request.

## Evidence gates

See [framework evidence](framework-evidence.md) and [execution guide](workflow-guide.md).
Gate-check is read-only and never executes unselected phases. Audit checks local
records only; current remote identity and native artifacts must also be verified.
