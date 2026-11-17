### PR Category
Operator

### Type of Change
New Feature; Bug Fix

### Description
Provide the numerical APIs consumed by DeepSeek V4.1 without moving framework scheduling or cache ownership into the operator library. Add Engram hashing/lookup, delayed mHC, compression/indexer/candidate and checkpoint dequantization paths through public exports and existing backend registration. Preserve existing V4 behavior by default; V4.1 explicitly disables head Q normalization through the fused insert API.

### Issue
No external issue has been opened. This draft is a prerequisite for the separate Plugin model integration; published fixed dependency references are pending.

### Progress
- [ ] Required maintainer review completed.
- [ ] Related upstream issues and final target revision confirmed.
- [ ] Complete required target CI/hardware/build validation and public API delivery.

The patch contains 45 files, including operator metadata/exports, actual numerical implementations, tests, benchmark integration, test selection and limited backend tuning. It includes independently identified fixes for empty/tail shapes, exact INT8 rounding, sparse blocks and sink/LSE merging. Existing `apply_q_norm=True` callers retain their default contract. The dequantization metadata describes the actual fused BF16 materialization; no production PyTorch compute fallback is introduced.

### Performance
Validation is scoped to MetaX C550 and the exact bases in [review notes](review-notes.md). Independent integer/FP32/FP64 references, actual public dispatch and changed-input graph tests are distinct evidence. The final Qnorm path had 115 selected tests per host; Plugin integration had 36 selected tests per host on the unchanged executable implementation. Eight separate native-vLLM hardware comparisons were not selected and are not counted as passed.

The controlled 16-shape Qnorm comparison against the independently validated generic FGV schedule had minimum ratios 0.97468/0.97213 on the two MetaX hosts, above the unchanged 0.9 criterion. Earlier failed trials remain in the evidence. Engram's lookup benchmark used a 65,536-row resident working set; it does not establish full-checkpoint table bandwidth. No overall quantization speedup or NVIDIA hardware result is claimed.

All seven applicable configured source hooks passed using the same pinned versions/arguments through verified official upstream mirrors; the installed hook configuration was not changed. This metadata-only final cleanup does not change numerical kernels or tuning. NVIDIA default-backend/Ampere execution, full required CI/build and final public dependency publication remain pending. Optional tuning exemptions and unsupported shapes remain explicit in the source review; unsupported production computation raises rather than falling back to torch.
