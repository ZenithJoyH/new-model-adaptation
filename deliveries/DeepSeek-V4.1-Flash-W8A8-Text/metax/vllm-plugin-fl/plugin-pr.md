### PR Category
Core

### PR Type
New Features

### Description
Add text-only DeepSeek V4.1 support for vLLM 0.28 through the existing FlagOS model registry and dispatch architecture. The base Plugin cannot load this architecture or express its tokenizer, W8A8 checkpoint and cache-metadata contracts. The new path preserves the checkpoint's omitted head Q normalization and supports V2-runner TP8/PP2 FULL graphs on MetaX C550.

### Related Issues
No external issue or PR has been opened by this preparation. Operator-library dependencies must be published and pinned before this draft is ready to submit.

### Changes
- Add lazy configuration/model/tokenizer registration, text encoding, streaming weight loading and pipeline ownership. Reject unsupported vision, tool, speculative and context-parallel paths explicitly.
- Keep request/token/slot mapping, allocator-owned buffers and cache lifetime in the Plugin. Invoke numerical operations through existing dispatch and public FlagGems-vllm APIs.
- Add dynamic symmetric per-token W8A8 checkpoint integration for Linear/MoE, mixed-precision exclusions, parameter loading and the V4.1 `apply_q_norm=False` insert contract. Execution errors propagate without retrying another backend.
- Add independent loading, dispatch, metadata, numerical and changed-input graph tests. Parameterized FP16 graph cases use FP16 inputs and dtype-based tolerances. Real-checkpoint tests take `DEEPSEEK_V41_MODEL_PATH`; missing assets fail explicitly instead of silently skipping.
- Add a runnable standard-library client and the README support boundary. Process logs and one-off benchmark reports are outside Plugin README/docs.

### Testing
Environment: two hosts with eight 64-GiB MetaX C550 devices each; Python 3.12.11, PyTorch 2.10.0+metax3.8.2.2, FlagTree 0.7.0+metax, vLLM 0.28.0+empty at `2cf0a6915ce544dc493a0990f2ea38d81601128a`. Exact source bases and patch identities are in [review notes](review-notes.md).

- All eight applicable Plugin pre-commit hooks passed on the exact changed-source/package context with no formatter changes. This is a scoped check, not an all-repository CI claim.
- Previous identical executable runtime: TP8/PP2 full-model load, actual FULL capture/replay, representative text sanity and 15 async ON/OFF request pairs completed. A separate 64-sequence bounded check observed 64 running sequences and 148 completed requests with no request errors/OOM/preemption. Full accuracy at max_num_seqs=64 has not been rerun.
- Original max_num_seqs=16 GPQA: 171/198 strict exact match, with 12 length-truncated empty answers and 1 HTTP timeout counted incorrect at the user's explicit direction; 86.3636% meets the subsequently selected 86% minimum. This is a separate full-denominator summary, not an unchanged native acceptance report or a higher-precision comparison.
- Restored service: the same 64/FULL/TP8/PP2/async-on/prefix-on launcher completed startup and eight representative text requests with independent content review; actual argv/environment/effective settings match the previous64 service.
- Current targeted hardware regression: 13/13 passed on an isolated MetaX C550 GPU, including real FP16/BF16 capture and changed-input replay. New stream creation blocked when sharing a GPU with the active model service; prior failed attempts are preserved. Device isolation resolved the test execution condition, not the unestablished driver-internal cause.

Reproduce the targeted tests against the installed source, with the exact frozen checkpoint available and an isolated idle test device (stop the assigned model service first if it owns that device):

```bash
export DEEPSEEK_V41_MODEL_PATH=/path/to/DeepSeek-V4.1-Flash-W8A8-Text
export MACA_VISIBLE_DEVICES=0 CUDA_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m pytest \
  tests/functional_tests/ops/test_dynamic_w8a8_checkpoint.py::test_real_graph_replay_with_new_input \
  tests/functional_tests/models/test_deepseek_v41_attention_chain.py::test_live_owner_cache_public_chain_and_graph_new_inputs \
  tests/functional_tests/models/test_deepseek_v41_engram.py::test_hasher_actual_tokenizer_frozen_map_and_public_dispatch \
  -vv -o pythonpath= -o faulthandler_timeout=90
```

The 13 cases comprise 6 FP16/BF16 graph cases, 6 attention/cache integrations and 1 frozen-tokenizer/public-hasher integration. The external checkpoint's configuration and compressed-token-map fingerprints remain asserted. Other hardware, a clean build/install with published pinned dependencies, higher-precision model quality and full 64-sequence accuracy remain unverified. The 8 pre-existing MetaX standalone/MCCL changes are excluded; latest-target integration must account for their separate upstream fixes.

### Checklist
- [ ] All required CI/build/hardware and final delivery gates pass.
- [x] Add focused regression and integration tests without weakening numerical assertions.
- [x] Document actual support boundaries and a runnable example.
- [ ] Pin public operator-library dependencies and complete the required higher-precision quality comparison.
