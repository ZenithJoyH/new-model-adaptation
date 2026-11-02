---
language:
- en
---

# Introduction

### Integrated Deployment

- This handoff covers the retained Qwen3.8-Flash-Next development container on **mx-103**, using the MetaX / vllm-plugin-fl profile.
- Latest state, 2026-11-01: the GPUs became available and the image-capable graph service is running. Text/image content checks, C4 sanity, two 61038-token requests and a thinking probe passed. Full ERQA400 is running; GPQA198 follows sequentially on the same instance. Final full-dataset scores are pending. See the [current accuracy record](accuracy-mx103-20261101.md).
- Container: `qwen3.8-flash` (`31022d2372f941b64ad4da9c7cde8d1be5aacbaff650857e49e8f4e6d1201d89`). Its retained lifetime process is `sleep infinity`; the current image-capable API process is container PID1704721 / host PID2121037. No unrelated workload was stopped.
- The installed Plugin was advanced to `origin/main` at `7094141e28a2680644fc41073aa9dfdfbf1f0044`, with seven files retaining the previous adaptation fixes and regressions. Existing vLLM, FlagGems, FlagGems-vllm and FlagTree installations were preserved.

### Consistency Validation

This is a documentation-only handoff for the retained development environment, updated on 2026-11-01. The current image service completed 11 mixed PIECEWISE and 7 FULL decode capture sizes, all seven text/image content checks, four concurrent sanity requests, and two 61038-token requests with correct answers. The actual KV capacity is 251005 tokens. Full ERQA400 and GPQA198 results remain pending; this is not full accuracy acceptance or a released-image validation. The migrated runtime passed file-identity checks, installed-module and Qwen registration checks, and 43 CPU/Meta regressions. A subsequent user-requested whole-model text regression passed on the updated Plugin: 11 mixed PIECEWISE and 7 FULL decode capture sizes completed, all 10 state cases / 105 generated tokens matched historical graph and eager references, and 24 repeated sanity requests passed with no errors or timeouts. Maximum token-logprob differences were 0.00330432 against the previous graph service and 0.00100329 against eager, below 0.02. That text-only graph instance subsequently exited for the requested ERQA image-service switch. A new GLM workload acquired the GPUs during the switch; the unready Qwen startup was stopped without touching the other workload. Those historical text-only results do not establish released-image validation, current full GPQA accuracy or current full performance acceptance. See the [current graph regression](graph-main-mx103-20261031.md).

The local migration base image is `local/qwen3.8-flash:mx103-env-20261031`, ID `sha256:4290d9410d7db87b5a16c96cb121a111897ad195d94852998ffae564e602f315`. It contains the filtered runtime before the Plugin update. Restored Git metadata, updated Plugin files, private proxy configuration and the `/tmp` directory restoration reside in the retained container's writable filesystem. Updated-image packaging, registry publication and published-image deployment validation were not selected. See the [migration and verification record](../environment/mx103-container-migration-20261031.md), verified on 2026-10-31.

# Evaluation Results

## Benchmark Result

| Metrics | Historical mx-101 graph run | Updated mx-103 development container |
| --- | --- | --- |
| GPQA Diamond strict match | 183/198, 92.42%, measured 2026-10-25 | Pending; scheduled after ERQA400 |
| ERQA accuracy, full400 | Not measured | Running; no final score |
| Current service checks | Historical text-only evidence remains separately bound | Seven text/image cases, C4 four requests and two long requests passed; full-dataset request integrity pending |

The historical accuracy threshold was 88%; its result remains bound to the original code and service instance. It does not qualify the updated Plugin or this host. See [historical accuracy](accuracy-gpqa-100k.md).

| Workload / input-output lengths | Concurrency | Metric | Historical mx-101 | Updated mx-103 |
| --- | --- | --- | --- | --- |
| 1024/128, 1024/1024, 8192/1024 | 1, 8, 32 | End-to-end throughput and latency | [Nine-case measurement](performance-graph-100k.md) | Not measured |

The historical measurements used TP8 BF16, a 100000-token context and FULL_AND_PIECEWISE. Normal/accuracy startup enabled prefix caching; performance disabled it through the same launcher. Those full measurements were not rerun or rebound. The subsequent normal-service latency diagnostic found warm medians of 0.470 / 0.543 / 0.480 seconds for three short arithmetic requests and 6.275 seconds for the 8730-token prefix request, within about 2% of the historical medians. These prefix-enabled measurements across different hosts and Plugin versions do not establish a causal speedup or P99. First-request delays are preserved in the current regression record.

# User Guide

Environment Setup

| Item | Version / verified identity |
| --- | --- |
| Target host | mx-103; Ubuntu 22.04.5 LTS |
| Docker | 29.1.3 |
| Container OS / user | Ubuntu 22.04.3 LTS / root |
| Accelerator exposure | 8 MetaX C550 devices, 65536 MiB each; `/dev/dri` and `/dev/mxcd` exposed |
| Host driver / host-reported MACA | 3.8.1 / 3.7.1.5 |
| Container SDK check | MACA 3.8.2; import compatibility check completed after restoring `/tmp` |
| Python | 3.12.11, `/opt/conda/bin/python` |
| PyTorch | 2.10.0+metax3.8.2.2 |
| vLLM | 0.24.1.dev0+gee0da84ab.d20261023.empty; source kept unchanged |
| vllm-plugin-FL | 0.3.0rc2.post1+g7094141e2.d20261031 plus the retained adaptation patch |
| FlagGems | 5.5.0.dev0+ge510c6bbe.d20261023 |
| FlagGems-vllm | 0.3.0.dev1; source HEAD c900357 plus preserved local fixes |
| FlagTree / Triton API | 0.7.0+metax / 3.6.0 |

The writable work root is `/public-flash/jinghao/qwen3.8-flash`, mapped to the same container path. The existing weight directory `/public-flash/models/Qwen3.8-Flash-Next` is mounted separately as read-only. Installed components live in the container filesystem under `/opt`, without host development-source mounts. Copy verification covered 93471 regular `/opt` files and 23215973007 bytes before the Plugin update.

The current shared root launcher is `/public-flash/jinghao/qwen3.8-flash/start-model.sh`; its container-internal delivery copy is `/opt/qwen3.8-flash-delivery/start-model.sh`. Their verified matching SHA-256 is `5c5bd7ce11d468e1606399d054c04fd32cd179bc13fea6b66d78f02d999216ab`. It uses TP8 BF16, a 100000-token context, FULL_AND_PIECEWISE, image16/video0, Mamba align and enabled prefix caching. A fixed 6442450944-byte KV budget replaces unstable cold/warm automatic estimates; prefill batch2048 leaves room for long-context temporary tensors. Default caches and the local database remain enabled; only the two existing necessary FlagOS environment exports remain.

The 0.93 / batch6400 trial passed basic image sanity but failed long prefill with OOM. The 0.91 / batch2048 automatic-budget trial failed startup capacity. These failures remain intact. A missing-stdin delivery-copy error was also repaired and both final copies rehashed. The final configuration passed startup and long-request checks, but full-dataset accuracy and fresh-image validation remain pending. See the [dated record](accuracy-mx103-20261101.md).

`/tmp` exists with mode 1777 and is the verified default temporary directory. Runtime caches use their library defaults. The caller and launcher do not set `PYTHONPATH`. During registration, installed TileLang adds its bundled TVM Python directory; the final origin check confirms it contains no alternate copies of the requested components.

## Operation Steps

### Download FlagOS Image

No registry image was pulled or published for this operation. The private local migration base has the image ID recorded above. A reproducible deployment command for an immutable image containing the updated Plugin remains pending. The original base image alone does not contain the subsequent container updates.

### Download Open-source Model Weights

Existing weights were reused without downloading or copying them. Their public distribution source, release revision and weight license have not been verified in this handoff. Obtain the authorized checkpoint and its provenance from the model owner before arranging another deployment; place it at the declared host path `/public-flash/models/Qwen3.8-Flash-Next` and mount that exact directory read-only at the same container path.

The verified `config.json` SHA-256 is `889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b`. This is a configuration identity check, not a fresh full-shard content verification. Weight-download instructions are for the reader; no download is executed by this workflow.

### Start the Container

The task-created development container is already running on mx-103. Its detached lifetime is provided by `sleep infinity`, independently of SSH. The exact executed creation command is retained in remote `04-runs/migrate-mx103-target-20261031/container-command.json`. Full reconstruction from an updated immutable image was not selected.

Execution: **mx-103**, Bash. Enter the retained container:

```bash
docker exec -it -w /public-flash/jinghao/qwen3.8-flash qwen3.8-flash bash
```

The interactive and login Bash shells load the requested proxy exports from `/root/.config/qwen3.8-flash/proxy.env`, mode 0600, with localhost bypass. Credentials were configured after image creation and are omitted from this guide and Git. A direct `docker exec` command that bypasses Bash does not automatically source this shell configuration.

Execution: **inside mx-103 / qwen3.8-flash**, Bash. Inspect the current code:

```bash
cd /opt/vllm-plugin-FL
git rev-parse HEAD
git status --short
```

Expected HEAD: `7094141e28a2680644fc41073aa9dfdfbf1f0044`. The retained adaptation changes remain visible in the working tree. Their complete original backup is preserved in WIP stash `d4816cd7adb7ad818efb934c5a289495e91ed09a` and remote task artifacts. No new branch commit, push or PR was created.

### Start the Server

The current development service is already running on mx-103, port8000, instance `full-accuracy-mx103-20261101-kv6g-b2048`. Full ERQA400 and subsequent GPQA198 share this exact instance and launcher. Do not launch a duplicate on the occupied port. The adaptation container remains running; no GPU polling schedule or automatic resource-acquisition task was created.

For a later manual restart in a verified free GPU window, use the identical internal launcher from inside the retained container, Bash:

```bash
cd /public-flash/jinghao/qwen3.8-flash
/opt/qwen3.8-flash-delivery/start-model.sh
```

This is the existing development runtime. A detached deployment command from a newly published immutable image is still pending; the updated container has not been packaged or published. The running evaluation controller already records output outside the minimal launcher, under `04-runs/full-accuracy-mx103-20261101-kv6g-b2048/`.

Normal use of the shared launcher keeps prefix caching enabled. Only a separately selected performance operation uses its `--performance` switch. The launcher was not edited to include installation, proxy credentials, polling or diagnostics.

## Service Invocation

### Invocation Script

The verified development endpoint is `http://127.0.0.1:8000/v1/chat/completions` on mx-103, served alias `Qwen3.8-Flash-Next`. The seven-case sanity manifest and immutable raw responses are retained under the current run. Real ERQA requests are passing through a byte-preserving task recorder at port18031 to this same endpoint; every native transport attempt is retained. Evaluation uses the normal prefix-enabled launcher. No final full-dataset score is available yet; the historical text regression cannot substitute for it. Avoid additional invocation traffic while the full accuracy clients are running.

# Technical Overview

## FlagGems

The existing ATen operator installation was copied and retained. Its source revision, dirty diff and untracked-file hashes were unchanged during the Plugin update. This operation did not measure model-level ATen replacement or operator hit counts.

## FlagGems-vllm

The vLLM-specific operator library, including the previously installed PLE/QSA fixes, was preserved. The CPU/Meta public-binding checks verify framework wiring; the subsequent whole-model text regression exercised the accelerator path without updating this library. Independent operator numerical tests were not rerun. This operation authored no numerical kernel and did not update either operator-library checkout.

## FlagTree

The installed FlagTree compiler and Triton runtime binaries were copied with the existing toolchain and SDK resources. FlagTree's incomplete source Git metadata is retained as observed; actual installed-file identities and versions are used instead of inventing a Git HEAD.

## vLLM and vllm-plugin-FL

vLLM remains read-only at `/opt/vllm`. The Plugin is installed in editable mode from `/opt/vllm-plugin-FL`, using the same interpreter and without dependency downloads or upgrades. Main advanced by ten upstream commits. Seven reviewed files retain the RoPE compilation boundary, heterogeneous Mamba buffer integration, MetaX compiled-artifact compatibility and corresponding tests.

The native pytest run selected 43 CPU/Meta checks: 43 passed, zero failed, zero errors and zero skipped; 28 GPU/CUDA cases were deliberately deselected. The later text-only whole-model regression completed; that service has since exited for image bring-up. Since 2026-11-01 the container also runs the new image-capable graph service; full accuracy is in progress. The first control wrapper used an incorrect literal capture-completion log check; its failure is preserved, and a separate continuation verified both complete capture progress records without changing or restarting the service.

## FlagEval Evaluation Framework

The GPQA result above belongs to the historical mx-101 evaluation. Task-specific LLMEval and MMEval containers have now been created for the follow-up full-accuracy request. GPQA Diamond 198-row data validation passed. ERQA native preprocessing and dataset/scoring imports passed for 400 questions and 630 images at revision `6bf393250b0981c3f6dd77eb58b6d6879038633f`. Only the new CPU MMEval container received a matching official CPU Torchvision wheel to correct its initial CPU-Torch/CUDA-Torchvision mismatch; the model container packages and all scoring sources were unchanged. Full ERQA400 requests started on 2026-11-01; GPQA198 follows sequentially, with one-shot offline native validation after both clients exit. Final scores are not available yet. Historical receipts were not relabeled for the new code or host.

# Contributing

The Plugin upstream is [flagos-ai/vllm-plugin-FL](https://github.com/flagos-ai/vllm-plugin-FL). Contributions should follow that repository's current development and testing guidance. This operation did not publish source changes.

# License

The Plugin declares Apache-2.0 in its project metadata. Model-weight provenance and licensing remain unverified here; no model-license frontmatter field is asserted. Other copied components retain their installed license files, which must be checked for any subsequent redistribution.
