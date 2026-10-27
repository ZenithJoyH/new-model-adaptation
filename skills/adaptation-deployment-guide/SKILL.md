---
name: adaptation-deployment-guide
description: Generate or refresh an English deployment guide from verified model adaptation records. Invoke after adaptation completes or when the user separately requests its deployment README. Includes weight-download instructions for readers, but does not download, deploy, evaluate or publish anything.
---

# Adaptation deployment guide

Produce a user-facing English Markdown guide, distinct from the internal
`adaptation-summary.md` issue/change record. Read the bundled
[assets/deployment-guide.md](assets/deployment-guide.md) template before writing.
Keep the template inside this Skill; do not depend on a Downloads file, a sibling
repository or a global namesake Skill.

## Scope and output

- Resolve the exact model, platform, framework profile and applicable Hosts from
  the request or completed adaptation. Ask if ambiguous; do not select a different
  workspace. Honor the repository's human-control boundary.
- Write `models/<model>/<platform>/frameworks/<framework>/acceptance/deployment-guide.md`.
  Existing legacy implicit workspaces use their platform-level
  `acceptance/deployment-guide.md`; do not migrate them. Refresh the same file,
  preserving human edits and reporting conflicting facts before replacing them.
- Automatic invocation belongs to adaptation completion handoff, after required
  acceptance and any selected retrospective. Standalone invocation reads existing
  evidence only; it never runs missing phases or marks adaptation complete.
- This is a local document-writing Skill, not an evaluation runner or journal
  gate. Do not change `framework.yml`/`platform.yml`, copy raw artifacts, install
  packages, pull images, download weights, start containers/services, send test
  requests, commit or publish. Commands in the guide are instructions for readers.

## Gather existing evidence

Read the workspace README, environment analysis, acceptance summary, verification
records and selected profile's acceptance contract. A status label alone is not
proof. Collect the following facts with their available verified source references:

- Exact model/weight identity, quantization, platform, devices/topology, OS,
  drivers/runtimes, component versions, supported capabilities and limitations.
- Image reference/digest and actual packaging and fresh-container validation
  status. An adaptation container is not proof of a released or validated image.
- Tested launcher container path, SHA-256, invocation, required devices/mounts,
  served model name, port and endpoint. Do not inherit privileged mode, host paths
  or network settings from a sample without evidence they are necessary here.
- Accuracy dataset/metric, threshold, score, sample coverage and date; performance
  workload, concurrency, cache state, units and results. Comparisons require an
  actual baseline under matching conditions. Missing data is `Not measured` or
  `Pending verification`, never a fabricated zero/pass.
- Confirmed weight distribution location/revision and license provenance. A
  renamed/quantized checkpoint is not automatically the public source checkpoint;
  do not infer its license, model ID or redistribution permission.

Missing evidence is a documentation limitation, not permission for remote checks
or testing. Ask for the missing source or a separately scoped check. A standalone
request may produce an explicitly labeled draft with unresolved items. Experimental
profiles must not be presented as formally accepted deployments: describe their
actual API workflow and mark service-only sections not applicable instead of
inventing vLLM commands.

## Compose and verify

1. Adapt the template in English. Keep the weight-download section as instructions
   only, using confirmed source/revision, destination and method. If unknown,
   state what the reader must obtain instead of emitting a guessed command.
   Never execute a documented download or installation command.
2. Document the verified container launch and accepted `start-model.sh`, not a
   second `vllm serve` command. Normal/accuracy startup enables prefix caching;
   the same script's `--performance` switch disables it where supported. Required
   files belong in the delivery image; explain explicitly agreed external weights
   and mounts. State pending image packaging/validation honestly.
3. Match curl/API examples to the known endpoint, model name, modality and auth
   requirements without exposing credentials. Mark examples not tested in the
   evidence as unverified. Do not send requests while writing the document.
4. Describe only stack components actually used. Do not copy marketing claims,
   benchmark numbers, contribution links or license declarations from a sample.
   Omit unsupported optional background sections; retain known limitations.
5. Replace every template placeholder. Use explicit English status notes for
   unresolved facts, not runnable placeholder commands. Check tables, units,
   links, path/mount consistency, launcher identity and accuracy/performance cache
   states. Keep concise evidence references, not secrets, SSH config or raw logs.
6. Save the guide and, where appropriate, add a minimal link in the workspace's
   existing README without rewriting unrelated content. Report its path,
   documentation readiness, missing evidence and that no download/deployment ran.
   Writing a guide cannot establish acceptance or image-validation success.
