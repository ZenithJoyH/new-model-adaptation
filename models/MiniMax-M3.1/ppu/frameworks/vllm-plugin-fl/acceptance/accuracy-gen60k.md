# PPU-07 GPQA Diamond 60k 生成上限重测

2026-09-30，用户要求针对首轮 45,000 token 截断增大生成上限后重跑精度。原轮次完整 198 题 strict 163/198、35 题错误，其中 17 题触及生成上限；其冻结配置和失败回执保持原样，见[原精度记录](accuracy.md)。

本轮冻结新配置 `03-acceptance/gpqa-formal-gen60k-ctx65k-20260930/config.json`，SHA-256 `557afb70d94627d93adb725e48ff8fa0b65666cb04432f5f56c0375a47e12a1a`；运行 ID `m31-gpqa-diamond-c32-gen60k-ctx65k-20260930`。同一 GPQA Diamond Arrow SHA-256 `501f307f9e8bc34041af4120c8eb5a735f0ea29cd83c90167b913651071bb4c4`，198 题、32 并发、`temperature=0,top_p=1`、strict minimum 0.88、timeout 14,400 秒并计错；`max_gen_toks` 提至 **60,000**，其他评测语义不变。服务 `--max-model-len` 由 50,000 提至 **65,536**，满足上一轮最大提示 2,606 + 新输出 60,000。新旧服务容量不同，分数差异不能单独归因于输出上限。

Host `PPU-07`、容器 `minimaxM3.1` 和 `/mnt/nfs/users/jinghao/minimaxM3.1` 映射再次核实同 inode `41:29130276076`；评测容器 `flageval_llmeval-jinghao` 同映射。65k 部署身份 `01-environment/identity-ctx65k-20260930.json` SHA-256 `3fc9bccc17fec5f723f1111eb01e227f1c3a0f852c5daec1a523c01bb654a0e5`，fingerprint `f37fdc7e9b8677ab2a057b6c7df886fe556e7f941a034857dfd2ccca96643afd`；源码 revision 与 Plugin diff 保持上一轮一致。

按 profile 首先在 65k 请求 FULL，真实日志 `04-runs/graph-full-ctx65k-service-20260930.log` 再现 MiniMax sparse/indexer 后端 `UNIFORM_BATCH` 限制，自动降为 `FULL_DECODE_ONLY`，6/6 decode 图捕获、健康 200。随后仅停止该首试进程，显式 `FULL_DECODE_ONLY` 启动，日志 `04-runs/graph-decode-full-ctx65k-service-20260930.log` 显示 48/48 加载、6/6 捕获、prefix cache enabled、服务就绪；当前服务实例 `ppu07-m31-container1ac783da-api2291878-start345908995-cmd8ee48233f293f954`。真实聊天 200、变输入 replay 2/2 正确；固定简单题十并发预检 10/10、零请求错误，原生报告 `04-runs/service-sanity-ctx65k-20260930/report.json` SHA-256 `5eeb7869c61d665f3c1c6311f40754fee3e5b5bb4a2f757ec198afb9fd0c0824`。执行模式事实 `04-runs/execution-mode-ctx65k-20260930/mode-evidence.json` SHA-256 `36967e80b3a50fb71fa2f374f3fa38f0d4871b81a8fd971779931d7b36fd5714`；eager 证据来自相同源码在旧 50k 服务上的真实运行，未将其冒充 65k eager 实测。

项目 `adaptation/accuracy` 能力包 SHA-256 `5ba2c9b96040324baf067405c53ff48528ae463b2dcd06f0a062ce57ac3885ca`。评测前原生 `llmrun.py --preflight-only` 确认 198 样本、limit full、c32、HTTP 200；`03-acceptance/gpqa-formal-gen60k-ctx65k-20260930/run-identity.json` SHA-256 `118d5de534d911c6f2277b5d2e7a533f8e4c29b79ca29f1a5dbe98c4f2c8a981` 冻结服务、数据、配置和能力包。原生 runner 已启动，结果独立写入 `04-runs/m31-gpqa-diamond-c32-gen60k-ctx65k-20260930/`，缓存位于 `06-cache/m31-gpqa-diamond-c32-gen60k-ctx65k-20260930/`，不会重用 45k 响应。

同轮执行项目框架原生 `adapt-model --framework vllm-plugin-fl --steps acceptance --acceptance-substeps accuracy --check-only --artifact-root PPU-07=/mnt/nfs/users/jinghao/minimaxM3.1`，在评测容器的 `03-acceptance/gate-ctx65k-preaccuracy-20260930/` 精简工具包内返回 `Framework gate passed`、`mode=prerequisites-only`。该门禁验证新部署前置回执，不代替最终精度通过；完成后未对失败精度伪造 passed 回执。

## 完整结果与逐题对照

原生 runner 已结束，wrapper 退出码 **1**，正式回执 `04-runs/m31-gpqa-diamond-c32-gen60k-ctx65k-20260930/outputs/m31-gpqa-diamond-c32-gen60k-ctx65k-20260930/m31-gpqa-diamond-c32-gen60k-ctx65k-20260930/acceptance-result.json` SHA-256 `9b237898c69400917697132ebe31b4448d872c227f4528bca7004c0c1821c1c5`，状态 `failed`。原生结果 SHA-256 `af489aea4d8df88f5ce07f7020409b0d43dc23f46b083658f1657b5134c877df`；严格匹配 **164/198 = 0.8282828283**，低于冻结 minimum **0.88**，至少需 **175/198**，还差 11 题。两次 task attempt 均以进程码 0 完整完成，但因同一缓存回答的指标不足而均标 `result validation failed`；第二次只是重新评分，不是独立模型重试。正式分数未通过，不得标记 accuracy passed。

原生 source config 快照 SHA-256 `557afb70d94627d93adb725e48ff8fa0b65666cb04432f5f56c0375a47e12a1a`，与事先冻结配置一致；effective config SHA-256 `03fce2d5943856091b8b6d2f69e6c2ce92b2566745c9ca8413f8db70bafa5bfe`。回执仍为 198 样本、配置 32 并发、graph、timeout 计错、strict minimum 0.88；`errors=[]`。项目原生 `validate_samples` 对最终样本 SHA-256 `4b0cfe7271d454d27de30a8335885056e75f0c4e163a391e2ebbb247a9c412f6` 返回 `True`：198 个唯一 doc、396 条双过滤行，零 timeout。新旧每题的 doc/prompt/target 哈希逐一一致。校验与对照产物 `04-runs/m31-gpqa-diamond-c32-gen60k-ctx65k-20260930/comparison.json` SHA-256 `5f2ddf61fd6a8d45f140114a30ef321343ab32f06f0474e03b59507756e73315`。

相对 45k 的 163/198，新轮次 **10 题转对、9 题转错，净增 1 题**。转对 doc id：33、35、48、88、90、115、130、138、150、180；转错：10、15、17、29、32、42、81、89、129。旧轮次 17 道错误题触及 45k 上限，其中 5 道（48、88、90、115、180）这轮转对；新轮次仍有 10 题触及 60k 上限，其中 8 题错误。新轮次 34 道错误中 **26 道未触及 60k 上限**。因此截断影响了部分题，但扩大生成上限并未解决大部分失分，不能把低分全部归因于 45k 截断。新旧服务的 `max-model-len` 也从 50k 改为 65,536，不能把逐题转移严格归因于 `max_gen_toks` 单一变量；尚无证据将剩余错误归因为 Plugin、W8A8 或图模式实现缺陷。

当前 65k 显式 decode-full 服务评测后 `/health` 为 HTTP 200。正式性能、证据汇总及最终启动脚本受精度门禁阻止。旧 45k 与新 60k 失败回执、所有错误样本均保留，不降低阈值、不删题、不按逐题答案调参。
