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
Product changes belong in verified profile-declared installed components/source
trees. Modify the container's actual FlagOS installation directly, without
`PYTHONPATH` or other import overrides selecting a different version. Record
package/import identity and Git diff or installed-file hashes. Preserve
unrelated work. The adaptation container must remain running. Only current-task
services/processes may be restarted after their identities are resolved.
External dependencies outside that writable scope, weights and datasets are read-only; source sync
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

When a profile declares a graph preference, attempt each level in order. The
current vLLM profiles use this project-defined sequence (not a guaranteed speed ranking):

| Record value | vLLM mode | Coverage |
| --- | --- | --- |
| `full` | `FULL` | Full graphs for prefill/mixed and compatible decode batches. |
| `full-and-piecewise` | `FULL_AND_PIECEWISE` | Full decode and piecewise prefill/mixed graphs. |
| `decode-full` | `FULL_DECODE_ONLY` | Full decode graphs; prefill/mixed outside graphs. |
| `piecewise` | `PIECEWISE` | Piecewise graphs with unsupported operations outside graphs. |

Mode semantics follow [vLLM's graph documentation](https://docs.vllm.ai/en/latest/design/cuda_graphs/);
verify the installed revision's names, backend and compilation requirements.
Other frameworks declare their own supported sequence; do not invent vLLM modes
for Torch-FL. Before descending one level, diagnose and attempt to fix the current
level, then record the exact configuration, reproducible failure, remedies,
unresolved blocker, limitations, evidence and conditions for retrying. A proven
unsupported mode may be documented with version/backend evidence instead of
repeated futile launches, but still needs an entry in the fallback chain.

The goal is reliable performance. Record comparable throughput, TTFT/inter-token
latency and memory for runnable candidates using the same workload, topology,
context length and cache state. Higher graph coverage is not proof of higher
speed; performance blockers also require controlled evidence and optimization
attempts, not assumptions. Keep the accuracy-before-formal-performance gate.
Inspect effective startup configuration and capture/replay evidence: automatic
backend fallback is not success at the requested higher mode. `piecewise` may
pass once every preceding level has a documented blocker. If all graph modes
fail, eager/NONE is diagnostic only; leave graph acceptance incomplete.
Bind all later receipts and the launcher to the final verified per-Host mode.
Changing it invalidates affected receipts and requires revalidation, including
accuracy before final performance; never silently downgrade a running service.

Formal metrics pass at frozen thresholds with complete valid coverage; individual
wrong answers and retained timeout-as-incorrect samples do not alone fail a valid
full run. Native result/sample verification is mandatory. A Markdown hash is not
a formal receipt. Performance cache behavior is framework-specific: disable it
with the declared mechanism if applicable; do not add vLLM flags to Python API tests.

For service profiles, prepare the minimal root-level `start-model.sh` before
sanity/formal acceptance and use the same script for accuracy and performance;
only the explicit performance switch disables prefix caching. Keep that tested
script for delivery. Follow the [shared launcher contract](remote-operations.md#shared-service-launcher),
including removal of unnecessary cache-path overrides and recording verified
default locations. Do not introduce service launchers for Python-API-only profiles.
For active complete service adaptations, verify each root-level `start-model.sh`
against the final accepted primary mode, runtime identity, executable permissions,
syntax, actual readiness, minimal required settings, normal cache behavior and
root mappings. Logs/results stay in `04-runs/`, evaluation caches in `06-cache/`;
service runtime defaults follow the shared launcher contract. Reference
its exact paths, SHA-256 and verification date locally. Never stop the container.
Keep only necessary startup commands/settings in the launcher. Follow the
[image-delivery rules](remote-operations.md): required files must survive in the
image at container paths, with no incidental host mounts or import overrides.
Perform diagnostics/readiness checks separately; record actual image validation
only when packaging and fresh-container testing have been performed.
Experimental Torch-FL bring-up can pass its individual checks and reach
`functional`; it cannot claim full accuracy, performance, `optimized` or complete
formal acceptance.

## 5. Retrospective

Review the selected work, verified problems/solutions, unsuccessful attempts,
limitations and workflow improvements. Experimental work may be reviewed without
pretending formal acceptance has completed. Promote only reusable verified
experience, citing revisions and applicable scope. Repository-wide changes still
require a relevant user request.

## Completion handoff: English deployment guide

After each adaptation completes its required acceptance and any selected
retrospective, the Agent must invoke
[adaptation-deployment-guide](../skills/adaptation-deployment-guide/SKILL.md)
before the final handoff. This is a document task within completion, not a sixth
phase or permission to run unselected phases. Write English
`acceptance/deployment-guide.md` in the exact local framework workspace (or the
existing legacy platform workspace), using only the template bundled in that Skill.
The guide is user-facing; retain the internal adaptation summary separately.
Keep model-weight download instructions without performing downloads. Deployment,
startup, evaluation, packaging, release and license statements must reflect the
available verified evidence; unresolved facts stay explicitly pending.

The same Skill can be called independently to generate or refresh this document
from existing records. It must not change workflow status or rerun missing tests.
Partial/experimental work can have an explicitly labeled draft, not a claim of
complete acceptance. A missing or draft guide leaves documentation handoff
incomplete without rewriting technical acceptance results. This is an Agent
invocation requirement, not a new native receipt, background job or executable hook.

## Evidence gates

See [framework evidence](framework-evidence.md) and [execution guide](workflow-guide.md).
Gate-check is read-only and never executes unselected phases. Audit checks local
records only; current remote identity and native artifacts must also be verified.
