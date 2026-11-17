### PR Category
Operator

### Type of Change
Bug Fix

### Description
The clone entry used a flattened Autograd fallthrough rule and a broad Autograd key. When FlagGems replacement was enabled, CPU clone/RNG-state preservation could enter the accelerator implementation. Express the fallthrough as the required singleton rule tuple and scope its key to the selected backend's Autograd dispatch key.

The device copy kernel is unchanged. Register clone metadata and add regressions for CPU Autograd/RNG preservation, actual accelerator kernel dispatch, Inductor RNG preservation, noncontiguous values and changed-input graph replay.

### Issue
No external issue has been opened by this preparation. This independently reviewable fix is also needed by the separate DeepSeek V4.1 bring-up; no model-name condition is added.

### Progress
- [ ] Required maintainer review completed.
- [ ] Final PR target revision and issue references confirmed.
- [x] Add targeted registration/dispatch regressions and preserve existing clone tests.

### Performance
The exact 3-file patch at base `e584bded1ddb0ea2a638653043ef0d48931119a3` previously passed 64 selected tests on each of the two MetaX C550 hosts, including CPU Autograd, actual device dispatch, Inductor and new-input graph checks. The patch is byte-identical in this preparation; no new device-kernel implementation is introduced.

Kernel/graph component thresholds passed in the recorded scope. Higher-level operator-mode measurements had substantial Python dispatch overhead; no claim of a universal speedup is made. Other accelerator hardware and full repository CI remain unverified. Applicable Python/YAML/operator metadata checks passed; there are no C++ changes, and an unavailable local clang-format execution is not presented as a C++ pass.
