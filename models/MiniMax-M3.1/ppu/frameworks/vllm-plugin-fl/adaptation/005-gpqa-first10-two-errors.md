# 005：GPQA Diamond 前十题两题未通过

## 元数据与签名

- 状态：`hypothesis`；2026-09-30 首次出现及验证；`PPU-07`，容器 `minimaxM3.1`，TP16 PPU，`decode-full` 图服务与正常 prefix cache。
- 模型：`/mnt/cpfs/models/MiniMax-M3.1-preview-private-W8A8-FlagOS-20260929`；Plugin HEAD `cafe6363c8c3de5ba4693b91643089c17b3ab87c` 加本任务未提交 diff；FlagGems `6b49cff993956bff8cef495abd84f2acb6a63df6`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389` 未修改。
- 签名：固定 Diamond `doc_id=0..9`、c10、greedy、45,000 token 上限，样本齐全、零 timeout/请求错误、strict 8/10；第 8 题在生成上限截断并提取 B（目标 C），第 9 题完整回答 A（目标 D）。runner 退出 0 不等于逐题全对。
- 证据：`/mnt/nfs/users/jinghao/minimaxM3.1/04-runs/m31-gpqa-first10-c10-gen45k-20260930/sanity-verification.json` SHA-256 `9a7a1b9ab5f03f2f8e95bb2cd7f0d58c06ce8ea546ed7a79795d69acfda024ad`，含原生结果/样本哈希。冻结 manifest/config SHA-256 分别为 `3f3ecc9ff72d071faebdd4000bf56fb63290081e4f2f0f5f02361d459fb8fbdd`、`15d8449eaeffa31af77db81b546ed1edecb1d1fa08ce8611bfa8f58a3ebc9732`。

## 已有经验匹配与诊断

MiniMax-M3/PPU 旧记录 `adaptation/002-gpqa-first10-doc8-long-generation.md` 同为 GPQA 第 8 题触及生成上限；但旧模型、权重、服务配置与上限不同，旧输出 D/30,000，本模型输出 B/45,000，当前还有第 9 题语义答错，故只作为候选假设，不认定相同根因。当前第 8 题题干要求判定 C3h 分子，模型在截断前仍比较选项，未给最终可靠答案；第 9 题问同成分 5 倍地球质量行星密度，模型最终选了明确给出 5.5 g/cm³ 的另一个选项。数据集给出的依据是重力压缩令同成分的更高质量行星密度增大。暂无证据显示 Plugin W8A8 实现数值错误、图 replay 错误或 FlagGems 缺陷；单卡聚焦数值及服务简单题均通过，但不能据此排除长生成精度问题。

## 受控尝试与结论

| 轮次 | 变量 | 结果 | 解释 |
| --- | --- | --- | --- |
| 0 | Diamond 原始前十题，冻结配置 | strict 8/10，ID 8/9 错；10/10 样本完整 | 失败证据保留，不能标为 sanity 通过 |
| 1 | 独立、事先冻结的简单科学题作为 profile 服务预检 | c10 逐题 10/10 正确；细节见验收 sanity | 只验证服务小批量路径，不改写 Diamond 失败或正式 198 题 |

根因未验证；当前将第 8 题过长推理、第 9 题知识/推理选择视为模型质量假设。没有修改 Plugin、FlagGems 或 vLLM 来“修复”这两个答案，也没有删题、重试单题或改变正式精度阈值。正式配置 `03-acceptance/gpqa-formal-20260930/config.json` 已在执行模式回执前冻结，要求 Diamond 198 完整样本、strict ≥0.88。

## 全量精度失败后的更新

2026-09-30，同一 `decode-full` 服务上按冻结配置运行 GPQA Diamond 全量 198 题。原生结果在 `/mnt/nfs/users/jinghao/minimaxM3.1/04-runs/m31-gpqa-diamond-c32-gen45k-20260930/`，正式 `acceptance-result.json` SHA-256 `c58de852caf96e0c264b03d426284b020af8fc31bbd2bc8ff5f19ed24ef0ee4f`，状态 `failed`，runner 退出码 1。原生校验器确认 198 个唯一 doc、396 条双过滤行、零 timeout、样本合同有效；strict 163/198 = 0.8232323232，低于预先冻结的 0.88。runner 的第二次任务尝试只复用同一 198 条缓存响应，分数不变，不构成独立采样复测。

35 道错误中有 17 道生成恰好触及 45,000 token 上限；全体 21 道触及上限，其中 4 道仍被严格过滤计对。错误覆盖化学 18、物理 11、生物 6；既有前十题 ID 8/9 均在错误集中。长推理与答案选择错误共存，尚不能归因于 W8A8/图模式数值偏差。已核实的 MiniMax-M3 旧基线使用 `temperature=1,top_p=0.95,top_k=20,max_gen_toks=30000` 得 177/198，但模型、服务和采样均不同，只提供候选诊断方向。

同日完成受控温度诊断：`02-issues/005-gpqa-temp1-20260930/` 中的 source config SHA-256 `0ef47d4c07832c741eb88d8605a3eb9241bb794f45a54f0bb4d6269b2905cbd4`，独立运行路径 `04-runs/m31-gpqa-first10-temp1-c10-gen45k-20260930/`、缓存 `06-cache/m31-gpqa-first10-temp1-c10-gen45k-20260930/`。与原十题 source config 逐项比较，除隔离运行标识、输出、缓存外，仅 `gen_kwargs` 从 `temperature=0` 改为 `1`；仍为 `top_p=1,max_gen_toks=45000`、c10、相同服务。十道题的 doc、prompt、target 哈希逐一一致，20 条双过滤样本、10 个唯一 doc、零 timeout。结果文件 SHA-256 `72b6bd6588a2f6b87d4f6944d30dd2d414754ebf09933e76968797ce8415e89f`，样本 SHA-256 `9b00d40f0685178c932444782322c44823f8ebb6d0174cf4964243319d000df0`；原生 strict 分数从 8/10 降为 **3/10**。ID 8 不再触及上限（1,456 token）但仍回答 B 而目标是 C；ID 9 仍回答 A 而目标是 D；ID 5/6/7 的输出未提取出有效选项且包含长段混乱多语文本。这个对照不支持将 `temperature=1,top_p=1` 直接用于本模型的正式配置。

再以 `temperature=1,top_p=1` 为基线，只增加 `top_k=20`（另隔离 run id、输出和缓存）进行固定十题第二轮诊断。配置在 `02-issues/005-gpqa-temp1-topk20-20260930/config.json`，SHA-256 `758f14f33ce0253a805559650022a798d5aa47655464a12e23e4dfdefeb4dc08`；项目原生 preflight 通过。运行 `04-runs/m31-gpqa-first10-temp1-topk20-c10-gen45k-20260930/` 的 results SHA-256 `eabf98335024539864785cb4356582aacb3beba36feeb869472fed80e4d9e33e`、samples SHA-256 `7fe242d7032273ac2098b17f2d8660f80b49c9552bcfb347b75cc2e51c22356c`。与上一轮十题逐项比较，doc、prompt、target 哈希全同；20 行、10 个唯一 doc、零 timeout，runner 退出 0，服务事后 `/health` 200。strict 回升为 **8/10**，但错误转为 ID 3（目标 B，回答 A）及 ID 8（目标 C，回答 D，生成 42,076 token）；原先 ID 9 改为答对。该轮没有消除超长推理和第 8 题失分，且十题与原 greedy 同分，因此没有证据支撑替换已冻结的正式 198 题配置。继续按题集调参容易对已看过的样本过拟合；停止此轮参数探索，保留全部失败样本。十题结果不能断言全量采样最优值，也不能证明 W8A8、图 replay 或 FlagGems 是精度差距的根因。原正式精度失败仍保持原始回执和阈值，知识库处理状态 `needs-validation`，不提升为跨模型经验；目前没有足够证据扩大产品代码范围。

## 60k 生成上限全量重测

2026-09-30 按用户要求新建冻结配置 `03-acceptance/gpqa-formal-gen60k-ctx65k-20260930/config.json` SHA-256 `557afb70d94627d93adb725e48ff8fa0b65666cb04432f5f56c0375a47e12a1a`，`max_gen_toks=60000`，服务上下文从 50,000 提至 65,536；继续使用相同模型、源码、TP16、decode-full、greedy、198 题、c32、strict minimum 0.88、timeout 计错。新服务 FULL 首试仍因同两个 MiniMax backend 自动降级，显式 decode-full 与十题简单预检通过。新服务容量变化是此比较的伴随变量，不能声称只调整了输出上限。旧正式轮次完全保留。

运行 `04-runs/m31-gpqa-diamond-c32-gen60k-ctx65k-20260930/` 的原生回执 SHA-256 `9b237898c69400917697132ebe31b4448d872c227f4528bca7004c0c1821c1c5`，`failed`，strict **164/198 = 0.8282828283**；原生样本校验通过，198 个唯一 doc、396 条过滤行、零 timeout/请求错误。逐题比较 `comparison.json` SHA-256 `5f2ddf61fd6a8d45f140114a30ef321343ab32f06f0474e03b59507756e73315`：doc/prompt/target 哈希全同，10 题转对、9 题转错，净增 1；原先 17 道 45k 触顶错误中 5 道转对，新轮次 10 道触及 60k 上限，其中 8 道错；新轮次 34 道错误里 26 道未触顶。**结论：上限截断影响部分样本，但不是整个 0.88 差距的充分解释**；扩大上限仍差 11 道正确题。保留模型知识/推理、输出提取、长序列数值路径等假设，尚未通过单变量实验确证具体根因；本问题继续保持 `hypothesis`，不将分数失败包装为代码修复或知识库通则。详见[60k 验收记录](../acceptance/accuracy-gen60k.md)。

## MiniMax-M3 采样参数 198 题对照

2026-09-30 用户指定 `temperature=1,top_p=0.95,top_k=20`。与同服务 60k greedy 基线相比，仅把这组三个采样参数共同改动；`max_gen_toks=60000`、同一 65k decode-full 服务、198 题、c32、seed 42、timeout 策略和 strict 0.88 阈值均不变。新冻结配置 SHA-256 `599d80928196834804ac3badc7f493b170f85ecad51b5dd894508f03a58d2a01`，运行 `04-runs/m31-gpqa-diamond-c32-temp1-p095-k20-gen60k-ctx65k-20260930/` 的原生回执 SHA-256 `df5591ac4a78f7a740ea728f5d0be4b84711fc3555fd1d49b095743fcd12c31e`，`failed`；198 个唯一 doc、396 条双过滤样本、零 timeout/请求错误，项目原生样本校验通过。strict **167/198 = 0.8434343434**，比 greedy 的 164/198 净增 3，距 0.88 仍差 8 道正确题。

逐题对照 `comparison.json` SHA-256 `b53de2b5c8c66a29d9cde7e6ce1ef79eee80ecfc012af86fd43f7210a6ebf329`：doc/prompt/target 哈希全同，17 题转对、14 题转错；新轮次 2 道触及 60k 上限且均答错，31 道错误中 29 道未触顶。该受控对照能评价**整组**采样变化在当前服务和这次随机运行上的分数，不能拆分温度、top-p、top-k 各自作用；单次随机结果也不证明 84.34% 是稳定期望分数。旧 MiniMax-M3 的 30k/50k、c64、不同模型和服务结果不直接可比。现有证据仍不足以将失分定位到 Plugin、W8A8、图模式或 FlagGems 的实现问题；保留 `hypothesis`，不按已见题目逐题调参或降低验收门槛。完整结果见[采样参数验收记录](../acceptance/accuracy-sampling.md)。
