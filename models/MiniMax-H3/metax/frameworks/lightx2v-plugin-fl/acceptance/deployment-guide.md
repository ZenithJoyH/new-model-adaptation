---
language:
- en
---

# Introduction

### Integrated Deployment

- Experimental MiniMax-H3 text-to-audio/video on one MetaX host, mx-57, using eight MXC550 devices and LightX2V Plugin-FL.
- This is a documentation-only draft for the existing `minimaxH3` container. No release image, registry reference or digest has been validated.
- The native asynchronous HTTP task service remains running on port 8000; metrics use 8001. The accepted container launcher is recorded below. Do not start a duplicate service.

### Consistency Validation

On 2026-11-16, two sequential HTTP generations completed in the original container, retaining the same eight worker identities and one initialization per rank. Queue rejection, schema rejection, status and media download worked. Representative frames showed the requested red ball and white tabletop. Audio listening and strict quality assessment were not performed.

Documentation is a draft; candidate-image validation, publication and published-image deployment are not performed. The retained experimental service has HTTP functional evidence, but profile acceptance remains incomplete: raw generation tensors, Torch allocator highwater, request-specific native/cache/device dispatch and runtime policy restoration were not observed. See the [acceptance record](README.md). No formal accuracy, performance or complete adaptation pass is claimed.

# Evaluation Results

## Benchmark Result

| Metrics | Native baseline | MetaX FlagOS HTTP |
| --- | --- | --- |
| Formal accuracy | Not measured | Not measured |
| HTTP functional samples | Not compared | 2 completed; profile checks incomplete |

| Workload / input-output lengths | Concurrency | Metric | Native baseline | FlagOS |
| --- | --- | --- | --- | --- |
| 544×960,124 frames,29 steps | 1 | Controlled performance | Not measured | Not measured |

Service-reported task durations were 61.23 s and 52.61 s; these are diagnostic observations, not benchmark results. Code/configuration were fixed to DiT TP4 × SP2, text TP8, BF16 mixed precision and resident weights. Graph/compile, quantization and optional fusion were not enabled. Prefix caching in the service-profile sense is not applicable; do not add a performance switch to this launcher.

# User Guide

Environment Setup

| Item | Version |
| --- | --- |
| Docker / operating system | Exact release versions not recorded in this handoff |
| Accelerator / device count | 8×MetaX MXC550, one host |
| Driver / runtime | Existing MetaX MACA/MCCL stack; exact release strings not recorded here |
| Python | /opt/conda/bin/python, 3.12.11 |
| PyTorch / FlagTree | Existing MetaX PyTorch 2.10 / FlagTree 0.7 stack; no upgrade |
| LightX2V | c58c16d607c49bf6021fecc6238ed177752d7e87 source snapshot |
| lightx2v-plugin-FL | 2cf49116b12383122db0d1247b484d24ba4409c3 plus bounded H3 server integration |
| FlagGems / FlagOmni | Existing FlagGems 5.5.0dev; FlagOmni431a7e6fcb9251fd7b44cdcb665839f4771b425f |

The source container ID is `99cd2bd857e567440a9f73d50752e486b591b7a046e4388490bf7e502e7be3d8`, using host networking. Weights are at `/public-flash/models/MiniMax-H3`. The user directory and evidence root are RW `/public-flash` mounts; their presence does not prove inclusion in an image. No new-container device/mount recipe is validated.

The installed runtime uses `/opt/LightX2V`, `/opt/lightx2v-plugin-FL` and the existing vendor stack without PYTHONPATH overrides. The default runtime data directory `/opt/LightX2V/save_results/server_cache` is approved for this service; it requires no cache environment override. Tasks are kept in memory and do not require a Redis daemon. Preserve the existing dependency stack; the redis-client 8.1.0 versus declared 6.4.0 mismatch remains recorded for the unused path.

## Operation Steps

### Download FlagOS Image

Published image and verified digest: **unpublished / not verified**. No pull command is supplied. This guide does not authorize packaging, publishing or replacing the running source container.

### Download Open-source Model Weights

The authorized local checkpoint path is `/public-flash/models/MiniMax-H3`. A verified download URL, exact upstream revision, payload manifest and checkpoint license were not captured for this handoff. Obtain these from the checkpoint owner before reproducing it; no download command or repository revision is guessed. These are reader prerequisites, not an executed download step.

The current source container accesses the existing `/public-flash` mount. A future release must explicitly declare a read-only weight mount with the same verified checkpoint identity; current writable bind visibility is not image-inclusion evidence.

### Start the Container

The original adaptation container is already running and must be preserved. Fresh-container deployment has not been validated, so no `docker run`, entrypoint or device recipe is supplied. The user enters their existing `minimaxH3` container using their established access method; the launcher contains no Docker command.

### Start the Server

Execution: inside the existing mx-57 `minimaxH3` container, Bash. The service is already retained; **do not run this command while it is running**. After a separately authorized task-owned stop/restart and fresh resource/port checks, reuse only this accepted launcher:

```bash
/public-flash/jinghao/minimaxH3-dependencies-20261116/start-model.sh
```

Launcher SHA256: `1b3e37ea9247cb10a5ecb5686b80f8c27e519ceae59649a97ea0c59be0b12aea`. `/public-flash/jinghao/minimaxH3/start-model.sh` is a convenience symlink to the same file. The original offline `run.sh` is preserved. The 8-line launcher invokes the dedicated installed H3 module with eight ranks and native HTTP options, without diagnostics, installs, cache overrides or monitoring.

Configuration: `/public-flash/jinghao/minimaxH3/config.json`; SHA256 `5121fc6e3841c56d2391905f03f53d0914a32265a7a86ad9affa00ecf76a9c93`. Effective settings are t2av, 544×960, 124 frames, 29 steps, 24 fps, TP4/SP2/text TP8,queue1 and full residency. The default startup does not enable new fusions/graph/compile/offload.

The original detached controller retained the service after validation: container PID 32222/startticks 104418197, rank PIDs 32304–32311. Logs and evidence remain under `/public-flash/jinghao/minimaxH3-dependencies-20261116/04-runs/HTTP-001`. Reboot recovery, fresh-image lifetime and arbitrary rank-failure recovery are not verified.

Readiness is checked outside the launcher. Execution: mx-57 host or its host-network container, Bash:

```bash
curl --fail --max-time 10 http://127.0.0.1:8000/health
```

A health response alone is not generation acceptance. Verify service identity and task completion; external LAN reachability/firewall behavior is not established by the local endpoint checks.

## Service Invocation

### Invocation Script

Execution: mx-57 host or its host-network container, Bash. Submit exactly one task at a time to the retained service; choose a new relative output basename for each new request:

```bash
curl --fail --max-time 30 -H 'Content-Type: application/json' \
  -d '{"task":"t2av","prompt":"A red ball slowly rolls across a white tabletop, static camera, soft lighting, gentle ambient sound.","seed":42,"size":[544,960],"num_frames":124,"save_result_path":"reader-request-1.mp4"}' \
  http://127.0.0.1:8000/v1/tasks/video/
```

The response contains `task_id`. Poll the returned identifier and download after status becomes completed. For example, these commands inspect/download the already verified first task without starting another generation:

```bash
curl --fail --max-time 10 \
  http://127.0.0.1:8000/v1/tasks/MN7Y-02NM-ZWP5-EIUY-MJ73/status
curl --fail --max-time 60 \
  http://127.0.0.1:8000/v1/tasks/MN7Y-02NM-ZWP5-EIUY-MJ73/result \
  -o http001-verified-request-1.mp4
```

Task records are in memory and may disappear after a restart. Use `task=t2av` explicitly; omitted task or `t2v` is not this H3 contract. Relative `save_result_path` writes under native `server_cache/outputs` and supports the result endpoint. Do not send startup-only fields such as steps/fps/dtype in this request. Queue capacity 1 includes processing and pending; submission while busy returns 503, unknown request fields return 422.

Verified task IDs: `MN7Y-02NM-ZWP5-EIUY-MJ73` and `T6K7-WWGB-O1XJ-LDP7-ME1K`. Both produced124-frame960×544 video at 24 fps and 32 kHz stereo audio with 165600 samples. The main reviewer inspected representative original frames, finding the red ball moving right over the tabletop without the old 64×64 artifacts. Audio listening, full-video review and raw-tensor numerical acceptance remain unverified. This handoff did not issue another request or test a session reconnect/reboot.

# Technical Overview

Qwen3-VL conditioning feeds the joint audio/video DiT, followed by separate video/audio VAEs. Native LightX2V handles the memory task queue, distributed request broadcast and resident runner. The explicit Plugin server subclass applies H3OperatorPolicy around each rank's actual run_request thread. It does not globally replace the native server or change the existing CLI.

## FlagGems

The configuration selects FlagGems RMS and Flash attention through the existing Plugin dispatch policy. Historical FULL-001 recorded real native dispatch for the same offline model shape. Current HTTP-specific per-step native/cache/device-window proof is missing; historical counts do not fill that gap.

## FlagTree

The existing MetaX FlagTree/Triton compiler stack is retained. No compiler/runtime upgrade was performed for the HTTP integration.

## LightX2V and lightx2v-plugin-FL

LightX2V remains read-only. The bounded Plugin entry uses the public runner registry with idempotence and foreign-owner checks. CPU scope tests use real Policy with isolated host doubles; they are not an 8-rank GPU proof. Profile functional acceptance remains incomplete.

## **FlagCX**

The accepted launcher disables Plugin FlagCX routing with its existing required setting. It does not introduce a different communication stack from the verified single-host configuration.

## **FlagEval Evaluation Framework**

Not used. No formal video accuracy or performance adapter was executed. HTTP functional samples are not a substitute for those evaluations.

# Contributing

Changes should follow this workspace's pinned experimental profile and repository contribution rules. No new support channel, pull request or publication is created by this guide.

# License

Checkpoint license/provenance and a release-wide software license inventory remain pending verification. No license identifier is asserted in the frontmatter; do not infer weight redistribution rights from this documentation draft.
