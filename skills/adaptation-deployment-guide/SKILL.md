---
name: adaptation-deployment-guide
description: Package and publish an adapted model image, validate deployment from the published image, and maintain an English deployment guide. Use for requested image release or deployment, or independently for documentation-only handoff. Reuses the accepted start-model.sh and preserves the running adaptation source container.
---

# Model image release and deployment

Keep the existing Skill name for invocation compatibility. Select the operation
from the user's request; editing this Skill never executes a release. Use the
bundled [English template](assets/deployment-guide.md) for the final guide.

## Select scope and prerequisites

| Requested operation | Execute |
| --- | --- |
| Deployment guide only, or adaptation completion without a release request | Read existing records and write the guide; no remote commands, packaging, requests or publication. |
| Package and validate locally, without push | Prepare a release candidate and validate a fresh container; report a local candidate, not a published deployment. |
| Publish and deploy the adapted image | Review, package, validate locally, push to the specified registry, verify the published image and retain the requested formal service. |
| Deploy an existing published image | Verify its identity and prerequisites, then perform the four deployment steps; do not rebuild or republish it. |

Here, local candidate means the selected Docker host's image store, not the
operator's desktop. Documentation-only requests may produce a clearly labeled
draft from incomplete records without resolving remote prerequisites.

Honor narrower instructions such as publish-only, no push, or temporary validation
without a formal service. A full release request authorizes its ordinary steps
within the established targets; do not ask again at every step. Missing target,
registry/namespace, resource or cleanup authorization must be resolved before the
corresponding mutation. Reading this Skill or generating documentation is not
release authorization. Do not download weights, push Git or create PRs as part of
image publication.

Resolve model/weight identity, hardware, framework profile, exact source and target
SSH aliases, source container ID, approved host/container work roots and registry
reference from the request and verified records. Do not default to every inventory
host or guess a registry. Read [remote operations Skill](../remote-operations/SKILL.md)
and its [policy](../../docs/remote-operations.md) before remote actions. Use its
maintained execution entrypoints and verify mappings for every new container.
For recoverable long runs, also follow the [execution journal](../../docs/agent-execution.md).
Respect human takeover and the selected profile's writable components and acceptance
requirements. Unsupported/draft profiles do not become deployable through this
Skill; experimental results must retain their actual status.

Use existing environment/acceptance records and the accepted launcher as inputs.
Do not rerun unrelated adaptation phases or equate a deployment smoke test with
formal accuracy/performance acceptance. Do not update `framework.yml` or
`platform.yml` merely because packaging or document generation succeeded.

## Preserve the source container and launcher

- The adaptation source container must remain running: never stop, restart, pause,
  remove or clean it for packaging. Only the task-assigned inference service or
  processes may be stopped/restarted after verifying their identities and saving
  their configuration and evidence. Do not affect unrelated workloads.
- Create a separate release candidate for cleanup and packaging. Record each
  container's host, ID and role: source, release candidate, temporary validation,
  or formal service. Establish the exact task-created temporary cleanup scope;
  preserve formal and source containers. No global pruning, broad deletion or
  automatic cleanup of pre-existing data.
- Reuse the accepted minimal `start-model.sh`, including the remote root copy and
  a byte-identical image-internal delivery copy when the root is a bind mount.
  Normal startup and deployment checks keep prefix caching enabled; only a
  separately selected performance evaluation uses `--performance` to disable it.
- The launcher contains only necessary startup settings and the existing cache
  switch. No extra cache-directory overrides, probes, polling, installs, patching
  or cleanup. Do not move unnecessary settings into a wrapper. Readiness checks,
  logging and session management belong to the deployment procedure outside it.
  Follow the [shared launcher contract](../../docs/remote-operations.md#shared-service-launcher).
- Do not introduce a second `vllm serve` / SGLang command in the guide. Invoke the
  accepted script at its container-internal absolute path; record its SHA-256 and
  effective settings. Changes to script bytes, installed code, model, topology or
  graph mode require affected revalidation, not just a new hash. Never downgrade
  graph mode, shorten context or disable FlagGems to make packaging pass.

## 1. Review the runtime and prepare the candidate

Inspect source/target identity, devices, actual process argv, interpreter, loaded
modules, component versions/revisions or file hashes, container image, mounts,
entrypoint, ports and resource use. Recover current facts rather than replaying
historical commands. Use the selected framework's actual help/configuration;
vLLM flags or plugin variables must not be copied into SGLang or Torch-FL.

In the approved remote work root, prepare a compact inclusion review:
`path -> include/exclude -> reason -> hash/source`. Include the tested installed
components, required native libraries/compiler resources, launcher and runtime
configuration. Exclude weights, secrets, evaluation data/results, raw logs,
one-off probes, failed experiments, backups, repository metadata and incidental
dynamic caches. Classify by actual runtime dependencies, not filename patterns.
Keep required SDK headers, bitcode and linker symlink targets; distinguish frozen
static tuning resources from regenerable JIT caches.

Prepare the independent candidate from a verified base and the reviewed installed
artifacts/build inputs, preserving exact versions and vendor ABI. Freeze the selected
file/configuration manifest and verify before/after hashes while collecting inputs;
if another task is changing those inputs, resolve the inconsistency before packaging.
Do not upgrade
dependencies during packaging or create a parallel development checkout. Materialize
required editable-install targets inside the image or package them using the
component's supported build/install process; verify the actual interpreter imports
those image-contained files without `PYTHONPATH`/`sys.path` overlays. Do not delete
required source merely to remove an editable install. vLLM stays read-only for the
`vllm-plugin-fl` profile; necessary adaptation fixes return to its contribution
workflow and affected validation.

Inspect inherited image layers as well as the candidate changes and image config
for credentials and excluded content. Deleting a file in a later layer is not
sufficient removal from a published image; rebuild from a clean base if required.
Do not snapshot an unreviewed source container as a shortcut. If the independent
candidate cannot faithfully reproduce the runtime, report the blocker and preserve
the source instead of stopping it or publishing a partial environment.

## 2. Commit the candidate and validate locally

Choose a collision-free local reference and complete remote registry/namespace/
image:tag using the project's verified naming convention. Do not depend on a
personal Downloads script; use an available reviewed naming tool only if required
and record its version. Record component versions with the actual interpreter;
never infer them from environment directory names. Do not overwrite an existing
tag without explicit authorization.

After candidate cleanup and import/registration checks, use the runtime's verified
image build procedure or `docker commit <candidate-ID> <local-reference>`. Only the
release candidate may be the commit target. Docker commit normally pauses its
target and excludes mounted data; see [Docker's commit reference](https://docs.docker.com/reference/cli/docker/container/commit/).
It must not target the running adaptation source, even with pause disabled as a
shortcut. Record image ID, base identity, candidate ID, changes and launcher hashes.

Create a fresh temporary container from the candidate image with declared devices,
read-only weights and approved writable runtime paths. Use fresh dynamic caches,
not host development code or the source container's cache contents. Necessary
static tuning configuration must be included and identified in the review.
Verify imports, actual framework/plugin routing and the accepted script identity.
Start that script with normal prefix caching, then perform bounded readiness and
real generation checks. A health response alone is insufficient: check an expected
answer, nonempty output, finish reason/truncation, fatal logs and process survival.
Use modality-appropriate inputs and a small bounded repeat/concurrency check;
record the actual workload without claiming full accuracy or benchmark coverage.
Set loading deadlines from observed graph warmup time; no infinite waits/restarts.

Gather component activation evidence separately from installation metadata.
Distinguish enabled ATen overloads, observed FlagGems implementations and custom
framework dispatch. For blacklists, record verified reasons or mark inherited
reasons unverified. Diagnostic instrumentation is temporary and outside the final
launcher; if it changes execution, recheck the normal delivered configuration.

Local candidate success permits publication, not a claim of published-image
verification. On failure, preserve evidence, diagnose and make a bounded repair;
do not push failed candidates or endlessly restart. A repeated unchanged failure
or missing resource/permission is a blocker. For package-only requests, stop here
and write the actual local status; no usable remote Pull command may be invented.

## 3. Publish the exact validated image

Prepare the English guide as a draft before publication. Retag the validated local
image to the authorized complete remote reference if needed; verify equal image
IDs (`docker tag <validated-local-reference> <remote-reference>` when applicable).
Use `docker push <remote-reference>`, record registry digest and resolve/pull the published
image to verify identity for the target architecture. A multi-platform manifest
digest is not a local image ID; record their mapping rather than equating them.
Check the remote tag still resolves to the recorded digest. Publication failures
leave the local candidate/evidence intact and the guide explicitly unpublished.

## 4. Execute the guide's four deployment steps

First verify the target machine's declared hardware, driver/runtime, disk/memory,
permissions, registry access, weights/config/tokenizer hashes, mounts, devices,
ports and any inter-node topology. Source-machine success is not target-machine
validation. No hidden package installs, patches or undeclared mounts are allowed.

Execute the four operations using the draft guide's existing headings:
`Download FlagOS Image`, `Start the Container`, `Start the Server`, and
`Service Invocation / Invocation Script`. The weight-download section stays
between image download and container startup as reader instructions, not an
executed release step. Do not rename the template into a numbered four-step report.

1. **Pull — host:** run `docker pull <remote-reference>` and verify its digest
   and selected image identity. Pull and Create must refer to that same release.
2. **Create container — host:** create a fresh container with the verified runtime,
   devices, network and declared mounts. Existing weight paths must be checked and
   mounted read-only. Declare whether it is temporary or formal before creation.
   Use a verified detached lifetime, no automatic deletion for a formal container,
   and give an explicit enter-container command. Do not start a duplicate service
   implicitly through an unchecked image entrypoint.
3. **Start service — container:** invoke only the image-internal accepted
   `start-model.sh`. Describe the verified session-independent launch mechanism
   outside the script, with logging and bounded readiness checks as separate
   deployment commands. Do not edit the launcher to add those checks. The block
   must return control for the next request; shell/SSH exit must not kill service.
4. **Real generation — declared host or container:** run a complete request with
   the verified endpoint, served model name, timeout and generation parameters.
   Check the known answer, finish reason, logs and service survival. Disconnect
   the interactive session, reconnect and repeat a bounded request to verify the
   declared formal lifetime; do not promise reboot recovery unless also tested.

Use fresh containers and empty dynamic caches with only declared inputs. Reuse
valid evidence from the same image/configuration where appropriate, but local
candidate validation cannot substitute for this published-image test. Save the
executed guide snapshot/hash, exact commands, image reference/digest/ID, container
IDs, launcher hash, effective configuration, requests/results and timestamps in
approved remote `03-acceptance/` / `04-runs/` paths. A changed deployment command
requires repeating the affected four-step deployment in a fresh container; a
changed image requires candidate validation and a new tag before doing so.
Editorial updates or evidence links alone do not require restarting services.

Retain the verified formal container/service when requested. If testing used a
temporary container, release its assigned resources and repeat the same deployment
in the formal container before claiming formal service success. Stop/delete only
explicitly authorized task-created temporary containers by verified IDs; never
include the source or formal service. Keep evidence and rollback references. On
failure report published-but-unverified or deployment-failed honestly; no automatic
source-container restart or unrequested restoration of the old service.

## 5. Write the English guide and report status

Write `models/<model>/<platform>/frameworks/<framework>/acceptance/deployment-guide.md`;
legacy workspaces retain the platform-level path. Preserve human edits. Use the
bundled template, replacing all placeholders; unresolved commands become explicit
pending prose, not runnable guessed commands. Preserve the weight-download section
as instructions only, based on verified provenance/revision/license. Do not download
weights. Omit inapplicable service sections for Python-API-only profiles.

Preserve the supplied README format embodied in the template, based on
`MiniMax-M3-mthreads-FlagOS-README.md`: frontmatter, `Introduction` with
`Integrated Deployment` / `Consistency Validation`, `Evaluation Results` with
`Benchmark Result`, `User Guide` with the environment table and `Operation Steps`,
`Service Invocation` / `Invocation Script`, `Technical Overview`, `Contributing`,
and `License`. Preserve their order, heading levels and comparison-table style.
The bundled template is the maintained source; the original Downloads file is
not a runtime dependency. Keep release readiness and limitations as concise notes
in existing sections. Do not add top-level release-status, coverage, evidence or
cleanup reports, or move weight-download instructions out of Operation Steps.

Treat the reference as a formatting example, not runtime facts: do not inherit
its model identity, license, benchmark claims, host paths, `PYTHONPATH`, diagnostic
flags or raw service command. Start the Server still invokes the accepted minimal
launcher; readiness/session handling stays outside it. Set frontmatter license and
language from verified provenance and actual document languages; omit an unknown
license field and explain the missing evidence in License. Adapt component
subheadings to the actual framework (for example SGLang-FL), omit unused optional
component sections and unverified contribution links, and avoid invented baselines.
For unpublished/draft outputs, replace unavailable runnable blocks with pending
prose while retaining their section positions.

Keep user instructions and concise results in the guide. Detailed inclusion review,
failures and raw logs stay in remote evidence with concise local acceptance links,
not Plugin README/docs. Add one link to the workspace README where useful. Keep
accuracy/performance results bound to their measured code/image/configuration;
old adaptation results do not automatically validate a repackaged image. Missing
measurements are `Not measured` or `Pending verification`, never zero or pass.

Report documentation readiness, local candidate validation, publication identity,
published-image four-step verification and formal-service status separately.
Include exact retained/temporary container roles, cleanup results, source-container
state, target scope and unresolved limitations. Documentation-only mode uses
existing evidence and never runs these remote steps. Automatic adaptation handoff
uses that mode unless image release/deployment is already in the user's scope.
This Skill is not a native evidence producer, new acceptance gate or background job;
do not fabricate receipts or mark adaptation/optimized status from its smoke checks.
