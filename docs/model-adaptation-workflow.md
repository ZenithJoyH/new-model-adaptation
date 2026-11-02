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

Before a selected phase, apply the [guidance and gate policy](adaptation-policy.md#guidance-precedence-missing-documents-and-gates).
Verified missing reading material is recorded with an alternative basis; it does not by
itself stop authorized implementation. Unknown contracts/write boundaries block affected
edits; failed or unrun checks block the corresponding acceptance/delivery claim, while
permitted diagnosis continues. Explicit applicability overrides resolve only their stated
conflicts; retain all other hard requirements and the selected profile's phase order.

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

### MetaX multi-host communication preflight

For MetaX adaptations spanning two or more Hosts, use
[MetaX-MACA/mccl_tests](https://github.com/MetaX-MACA/mccl_tests) in phase 2 before
dependent multi-host model execution. This is an environment prerequisite shared
by applicable frameworks, not a new phase or a model performance acceptance run.
Single-host work is not required to run cross-host tests. If phase 2 is unselected,
inspect matching existing evidence; missing evidence does not authorize running
an unselected phase. Draft/read-only profile restrictions still apply.

1. **Confirm scope and runtime.** Verify the exact Hosts, allocated GPUs, approved
   roots and container mappings. Test inside the actual adaptation containers using
   the same MACA/MCCL libraries as model execution. Record SDK, driver, MPI and loaded
   MCCL versions/paths, test revision and binary path/hash, rank/GPU mapping, network
   interfaces and RDMA devices. Check rank launch connectivity and device visibility;
   preserve unrelated services and keep adaptation containers running. Do not install
   or upgrade the SDK, change SSH/network policy or broaden resource use implicitly.
   Every test rank, including those launched remotely by MPI, must execute inside
   its corresponding adaptation container. Starting `mpirun` inside one container
   does not prove remote ranks entered theirs. Record each Host's container ID,
   rank process/container membership, actual loaded libraries, GPU/RDMA device
   mappings and network mode. Use the mappings intended for model execution;
   do not switch to a separate test container or host libraries to obtain a pass.
   Host-side launch orchestration is allowed within scope, but host-only benchmarks
   are diagnostic evidence only and cannot pass this container preflight. If a
   remote rank runs on the host or its container identity cannot be verified,
   leave the preflight incomplete and fix the launch path before rerunning.
2. **Verify the launch command.** Inspect the pinned README, build and launch scripts
   before use. The reviewed upstream `cluster.sh` takes `"IP1:slots,IP2:slots"`, total
   process count and test name, unlike the README's older argument list. It defaults
   to an SDK samples binary path, fixed HCA names and a derived `/24` subnet. Resolve
   these from the actual environment, not by copying example IPs, NICs or defaults;
   verify the intended binary and libraries on every Host. Recheck newer revisions.
3. **Exercise the topology.** Progress from per-host multi-GPU checks to two Hosts
   with one GPU each, then multi-GPU/multi-host tests covering the planned rank groups.
   Run AllReduce and the operations required by the model's parallelism, such as
   AllGather/ReduceScatter for TP, Send/Recv for PP and All-to-All for EP. Scan small
   and large message sizes with correctness checking (`-c 1`), warmup and repeated
   iterations; record datatype, sizes, counts, latency, `algbw`, `busbw` and errors.
   Verify the actual transport/NIC path from runtime evidence; a completed MPI job
   alone does not establish RDMA use or a healthy intended path.
4. **Record the decision.** Require all selected checks to complete with correct
   results, no hangs/timeouts and the intended communication path. Diagnose obvious
   bandwidth/latency anomalies against link/topology facts or a comparable baseline;
   do not invent a universal bandwidth threshold or treat `busbw` as raw NIC throughput.
   Failed, unavailable or unresolved checks leave the affected environment prerequisite
   incomplete and block dependent multi-host execution; independent analysis and
   authorized diagnosis may continue. Reuse only verified matching evidence; changes
   to Hosts, topology, containers, communication libraries or network settings require
   affected checks to be rerun. Do not silently rewrite historical acceptance states.

Keep test setup/commands under the approved remote root's `01-environment/`, with
test source/build artifacts in a declared `05-tmp/` subdirectory and full outputs in
`04-runs/`; do not add them to Plugin/operator sources or local model directories.
In local `environment/environment-analysis.md`, record scope, commands, versions,
results, blockers and exact remote evidence paths/hashes. This preflight may run
before model accuracy and requires no model service, launcher or prefix-cache switch.
It does not prove framework TP/PP/EP integration or graph capture/replay; retain
the selected profile's later graph, accuracy and performance acceptance requirements.

## 3. Implementation

Follow the profile's concrete steps, combining model analysis, environment facts
and user references. Establish baselines; change one material variable at a time.
Use existing extension points; test incrementally, retain issue evidence and review
the final diff/ownership/affected callers. Put one-off code outside product trees.
vLLM Plugin and Torch-FL have separate implementation instructions.

Operator changes also follow the [operator development standard](operator-development-standard.md):
read task-relevant clauses and apply the user's clarified ownership: FlagGems
provides ATen operators only; vLLM operators (including non-ATen fused computations)
come from FlagGems-vllm. Then verify contracts, independent numerics, actual
dispatch and applicable graph/autotune behavior. Component benchmarks belong here
and follow the operator repository's admission criteria; they do not impose a
predefined end-to-end speed target. Bind this evidence to the existing source review.

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

Service sanity sends representative text requests and, for image-capable models,
image requests. Review each response for relevance, garbling, empty/repetitive output
and actual image understanding; do not require verbatim open-ended answers. Preserve
responses, timings and a result-bound review. Fix obvious performance problems before
formal accuracy. Freeze verified modalities, the architecture hash, served aliases and
per-Host startup identity in `acceptance_plan.service_contract` before sanity, following
the [service evidence contract](evidence-contract-v2.md#服务范围与共享启动绑定).
Test coverage cannot be reduced by changing only the request manifest.
Performance acceptance then requires complete valid measurements,
not a predefined speed target; explicit optimization targets remain binding. The first
measurement needs no prior baseline; comparisons and relative targets require one.

Formal metrics pass at frozen thresholds with complete valid coverage; individual
wrong answers and retained timeout-as-incorrect samples do not alone fail a valid
full run. Native result/sample verification is mandatory. A Markdown hash is not
a formal receipt. Performance cache behavior is framework-specific: disable it
with the declared mechanism if applicable; do not add vLLM flags to Python API tests.

For service profiles, prepare the minimal root-level `start-model.sh` before
sanity/formal acceptance and use the same script for accuracy and performance;
only the explicit performance switch disables prefix caching. Keep that tested
script for delivery. Each run binds its hash, observed process argv, necessary
environment and effective settings to the frozen service contract; changes other
than prefix caching require revalidation. Follow the [shared launcher contract](remote-operations.md#shared-service-launcher),
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
limitations and workflow improvements. Failed, blocked, partial and experimental
work may be reviewed independently without passing prior phases. The review binds
actual stage states/evidence and must be revalidated when they change. Completing
a retrospective never promotes acceptance or overall adaptation status. Promote only reusable verified
experience, citing revisions and applicable scope. Repository-wide changes still
require a relevant user request.

## Completion handoff: English deployment guide

After each adaptation completes its required acceptance and any selected
retrospective, the Agent must invoke
[adaptation-deployment-guide](../skills/adaptation-deployment-guide/SKILL.md)
before the final handoff. The Skill now also handles requested image release and
deployment; default completion handoff remains documentation-only unless those
operations are already in scope. This does not add a sixth adaptation phase or
permission to run unselected phases. Write English
`acceptance/deployment-guide.md` in the exact local framework workspace (or the
existing legacy platform workspace), using only the template bundled in that Skill.
The guide is user-facing; retain the internal adaptation summary separately.
Keep model-weight download instructions without performing downloads. Deployment,
startup, evaluation, packaging, release and license statements must reflect the
available verified evidence; unresolved facts stay explicitly pending.

The same Skill can be called independently for documentation-only work, local
packaging/validation, publication/deployment, or deployment of an existing image.
Documentation-only work reads existing records without remote actions or tests.
Release work follows the Skill's review, independent candidate, local validation,
publication and published-image four-step deployment sequence within the selected
scope. Preserve the running source container and accepted minimal `start-model.sh`;
keep session management/readiness outside the script. Record candidate, publication,
deployment and formal-service status separately. Release smoke checks do not
replace formal accuracy/performance or authorize workflow status changes.
Partial/experimental work can have an explicitly labeled draft, not a claim of
complete acceptance. A missing or draft guide leaves documentation handoff
incomplete without rewriting technical acceptance results. This is an Agent
invocation requirement, not a new native receipt, background job or executable hook.

## Evidence gates

See [framework evidence](framework-evidence.md) and [execution guide](workflow-guide.md).
Gate-check is read-only and never executes unselected phases. Audit checks local
records only; current remote identity and native artifacts must also be verified.
