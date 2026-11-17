---
language:
- en
---

# Introduction

### Integrated Deployment

- DeepSeek-V4.1-Flash-W8A8-Text on two MetaX C550 hosts, eight devices per host, using vllm-plugin-fl and the specified vLLM 0.28 base image.
- The current candidate supports text generation, reasoning, TP8/PP2, FULL CUDA graphs and asynchronous scheduling. The configured context budget is 50,000 tokens; the checkpoint's advertised longer context is not validated here. Images, tool calling, speculative decoding, expert parallelism and context parallelism are outside this profile.
- An adapted inference image has **not been packaged or published**. The base image alone does not contain this adaptation. The running development containers contain the installed changes and the internal launcher `/opt/deepseek-v41-runtime/start-model.sh`.

### Consistency Validation

As of November 5, 2026, the candidate has completed eight concurrent text sanity cases with independent response review. Fifteen matched request pairs completed correctly with PP2 and asynchronous scheduling both enabled and disabled, including streaming and chunked prefill. Three same-weight eager/FULL comparisons produced identical generated token IDs; the maximum absolute difference in their generated-token log probabilities was 1.4305046533991117e-6. These checks do not establish a higher-precision quality baseline or exhaustive scheduling coverage.

The current service now uses `max_num_seqs=64`. Its separate bounded check observed 64 engine sequences running concurrently, completed eight reviewed native sanity cases plus 140 diagnostic requests, and observed no request errors, HTTP timeouts, OOM or preemption. Sixty-four capacity requests deliberately ran to their 512-token cap with nonempty content. Full GPQA accuracy has not been rerun under this configuration. See the [64-sequence evidence and limits](max-num-seqs64.md).

PR preparation corrected five test/documentation files without changing executable numerical logic. Thirteen isolated MetaX graph/integration cases passed, including actual FP16/BF16 replay. The service was then restored using the identical 64-sequence launcher and base configuration; eight fresh text cases and independent content review passed. The current instance is `v41-pr-cleanup-restored-v1-20261105`, with logs and immutable identity under `04-runs/pr-cleanup-service-restored-v1-20261105/`. The earlier service identities remain historical. New stream creation blocked during shared-GPU tests; isolation resolved the execution condition, while the driver-internal cause remains unresolved. These PR candidates are not submitted or release-ready; fixed public dependencies, higher-precision quality comparison and final build/CI remain pending.

This document is a draft handoff. The first full GSM8K attempt was stopped after 742 responses: the original literal `Q:` generation stop cut off reasoning and produced 14 empty final answers. That invalid run is preserved. A new complete 1,319-item run removes only this conflicting stop; all original prompts, targets, filters, scorers and the 0.95 minimum remain unchanged. At the user’s explicit cutoff, 1,318 cached answers were preserved and the sole unanswered item was counted incorrect. The separate cutoff summary is 1,171/1,319 (88.7794%), below the unchanged 95% minimum; it is not an unmodified complete native-run result. Formal performance is not measured. Public fixed cross-repository dependencies, higher-precision model-quality comparison and final source review remain pending. Local release-candidate validation, publication and published-image deployment verification have not been performed. The existing two adaptation containers and their candidate service remain running. See the [cutoff score record](accuracy-cutoff-summary.md), [acceptance record](README.md) and [evaluation plan](evaluation-plan.md).

# Evaluation Results

## Benchmark Result

| Metrics | Higher-precision baseline | MetaX FlagOS candidate |
| --- | --- | --- |
| GSM8K, exact_match / flexible-extract | Not measured | 1,171/1,319 = 88.7794%; one unanswered item counted incorrect at the user’s cutoff; below 0.95 |
| GPQA Diamond, exact_match / strict-match | Not measured | 171/198 = 86.3636%; all 13 anomalous answers counted incorrect; meets the subsequently user-selected 0.86 minimum; measured with max_num_seqs=16 |
| Text service sanity | Not measured | 8/8 reviewed cases; observed peak of 8 running requests |

The native FlagEval image uses lm-eval 0.4.8. The full task retains the original prompts and scorers, zero-shot reasoning, temperature 0, top-p 1, reasoning effort high, seed 20261104 and a 32,768-token generation budget. It uses concurrency 8, one API attempt per request, no task retries and prefix caching enabled. A separate eight-item tooling pilot scored 7/8; its formatting-related miss remains a scored error. It is not the full-task result.

| Workload / input-output lengths | Concurrency | Metric | Higher-precision baseline | MetaX FlagOS candidate |
| --- | --- | --- | --- | --- |
| Fixed performance scenario | Pending verification | TTFT, TPOT/ITL, throughput and memory | Not measured | Not measured |

Results apply to the installed candidate sources in the running base-image containers, BF16 activations, dynamic W8A8 INT8 linear/MoE operations, FP8 MLA cache, FULL graphs and TP8/PP2. They do not validate a repackaged image. Accuracy uses prefix caching enabled; the same launcher's `--performance` branch only disables prefix caching for performance measurements.

# User Guide

Environment Setup

| Item | Version |
| --- | --- |
| Docker Version | Server 29.1.3 on both hosts |
| Operating System | Ubuntu 22.04.5 LTS; kernel 5.15.0-119-generic on both hosts |
| Accelerator / device count | 2 hosts × 8 MetaX C550, 64 GiB per device |
| Driver / device runtime | Host driver 3.8.1; image MACA 3.8.2 |
| Python / PyTorch | Python 3.12.11; PyTorch 2.10.0+metax3.8.2.2 |
| vLLM | 0.28.0+empty; read-only source revision 2cf0a6915ce544dc493a0990f2ea38d81601128a |
| vllm-plugin-fl | Base revision 37f2127367cfbc24349a1f28cb37c4c629b9ed6c plus reviewed candidate changes; final review pending |
| FlagGems | Base revision e584bded1ddb0ea2a638653043ef0d48931119a3 plus clone registration fix |
| FlagGems-vllm | Base revision f108ba81bf6799ccfe48c86f77cbb3ce117c4179 plus candidate operator changes |
| FlagTree / Triton | FlagTree 0.7.0+metax; Triton 3.6 |

The verified targets are mx-102 and mx-103. Their approved shared work root is `/public-flash/jinghao/deepseekV4.1`. Weights are mounted read-only at `/public-flash/models/DeepSeek-V4.1-Flash-W8A8-Text`. The candidate uses host networking/IPC, `/dev/mxcd`, `/dev/dri`, `/dev/infiniband` and unlimited memlock. Its coordinator API is `http://192.168.2.102:8000/v1`; inter-node coordination uses port 29621. Both nodes require the verified four active RoCE HCAs and the same communication stack. Container-based 16-rank MCCL collectives and PP edge communication passed before dependent model execution.

Required internal runtime files include the launcher and `/opt/deepseek-v41-runtime/libbnxt_re-rdmav34.so`. The latter is the explicitly authorized, process-private provider compatibility copy; host and system libraries were not replaced. Its SHA-256 is `e2694779e895e2682e113dea8d8d5a50b92af7bad4ec617216541cf87ef9fae1`. Neither file is supplied by a published adapted image yet.

## Operation Steps

### Download FlagOS Image

Adapted-image pull instructions are pending publication and digest verification. The specified development base is `harbor.baai.ac.cn/flagos-inner-models-release/metax-for-vllm-plugin-fl-0.28`, with observed local image ID `sha256:34dfb5c72b60cf0a7c2c1ff0d73c24cc8bc4314b3b0deb36c51306000d85b6f1`. Pulling it does not install the candidate changes. No release pull command is provided until an adapted image is validated and published.

### Download Open-source Model Weights

An independently verified public download source, checkpoint revision and weight license for this exact Text checkpoint have not been established. Obtain those details before downloading; do not substitute the similarly named W8A8-BF16 checkpoint as a full-precision baseline. These download instructions are for the reader; this workflow has not downloaded weights.

The approved existing host source and read-only container destination are both `/public-flash/models/DeepSeek-V4.1-Flash-W8A8-Text`. The verified config SHA-256 is `5d716883e320def43c473bde82030f13f3b806c4411437975e94b3a29de3c0e7`; the safetensors index SHA-256 is `3ca46c734ab2a61daf0821d34cb48f3902f5e81769d5c8faf8c85b620f93b644`. These are metadata checks, not a hash of all weight payloads.

### Start the Container

Fresh release-container creation is pending a validated adapted image. The current task uses the already running `deepseek-v41-text-plugin028-20261103` container on each host. Its identity and mappings are recorded in the [environment analysis](../environment/environment-analysis.md). Keep both adaptation containers running. No guessed release `docker run` command is supplied.

### Start the Server

The verified current internal launcher is `/opt/deepseek-v41-runtime/start-model.sh`, SHA-256 `364d18c989f8ce0e5e1406e714eb79cd8586af95487512b6c39aaf9845f9bce9`. The shared root copy has identical bytes. The current candidate service is already running on both nodes; do not launch duplicates during evaluation.

Release startup, detached lifetime and bounded readiness commands will be frozen after fresh-image validation. The existing candidate was started through the shared launcher with per-host `VLLM_HOST_IP`, headless rank 1 on mx-103 and coordinator rank 0 on mx-102. Logging and process observation remain outside the script. Current candidate logs are in the approved root's `04-runs/seq64-v1-20261105/` directory; prior max_num_seqs=16 logs remain in `04-runs/final-service-v22-20261105/`.

Effective settings are TP8/PP2, FULL graphs, asynchronous scheduling enabled, context 50000, batch-token budget 1024, at most 64 sequences, 512 MiB explicit KV-cache allocation, logical block size 64 and the exact served alias below. This limit does not reserve 64 maximum-length contexts. Normal startup keeps prefix caching enabled. Only a separately selected performance evaluation uses the same launcher with `--performance`.

## Service Invocation

### Invocation Script

Execution: a host shell on mx-103, against the existing candidate container and coordinator. This installed standard-library client was run successfully in both ordinary and thinking modes. Its default request asks for 17 × 23, temperature 0 and a 1,024-token budget.

```bash
docker exec deepseek-v41-text-plugin028-20261103 \
  python /opt/vllm-plugin-FL/examples/deepseek_v41_client.py \
  --base-url http://192.168.2.102:8000/v1 \
  --model DeepSeek-V4.1-Flash-W8A8-Text --thinking
```

The verified response was 391 with finish reason `stop`, including a separate reasoning field in thinking mode. Evidence is retained in `03-acceptance/example-v35-20261105/` under the approved root. This existing-service check does not prove fresh published-image deployment or its reconnect lifetime; those validations remain pending.

# Technical Overview

The Plugin adds V4.1 text configuration/tokenization, weight loading, PP model orchestration and allocator-owned cache metadata. Numerical operations use the existing Plugin dispatch architecture and public operator-library entry points. The installed vLLM source remains unchanged.

## FlagGems

FlagGems provides ATen operators through automatic replacement. The adaptation fixes clone Autograd registration, with separate direct numerical, actual device dispatch, layout and graph tests on both hosts. A separate Plugin adapter was not added for each ATen operator.

## FlagTree

The installed FlagTree/Triton toolchain compiles the numerical kernels. Kernel and real graph-replay tests use this exact MetaX stack; no other accelerator platform is claimed validated.

## vllm-plugin-fl and FlagGems-vllm

The Plugin owns framework contracts and scheduling metadata. FlagGems-vllm owns V4.1-specific numerical work, including Engram, delayed mHC, compression, indexer/candidate operations, quantization and attention. V4.1 omits per-head Q RMSNorm after Q projection; its fused operator explicitly uses `apply_q_norm=False`, preserving the existing default for other callers.

## **FlagEval Evaluation Framework**

A separate CPU-only FlagEval tool container runs the native lm-eval task and unchanged original scoring filters against the coordinator's OpenAI-compatible API. The full-task configuration, source fingerprints, immutable service binding, responses and final reports are retained in the approved remote evidence directories. The GPQA score above is a separate, user-authorized full-denominator summary; the original aggregate excluded 13 anomalies and remains preserved. Complete formal receipts and accuracy at max_num_seqs=64 remain pending.

# Contributing

Final review and public fixed dependency delivery are pending. Candidate patches are retained for review; no Git commit, push or PR publication has been performed for this task. Follow the repository's Plugin and operator contribution standards before publishing changes.

# License

Candidate source files retain their Apache-2.0 notices and upstream attribution. The license and public redistribution provenance of the exact model weights have not been independently verified; this guide makes no weight redistribution claim. An adapted image has not been published.
