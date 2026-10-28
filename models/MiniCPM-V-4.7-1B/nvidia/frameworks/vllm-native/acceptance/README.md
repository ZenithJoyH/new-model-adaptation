# 适配验收索引

已完成的基本功能与 graph 验证、最终启动脚本和未完成的正式验收边界见
[功能验证摘要](functional-validation.md)。原始数据留在 Host
`/public/flagos/jinghao/MiniCPMV4.7-1B/native/04-runs/`。
参考处理器的单图 canvas 网格/位置对照见
[处理器对照](processor-comparison.md)。
用户要求的显式 `FULL_AND_PIECEWISE` 服务试验见
[混合图模式验证](full-and-piecewise-diagnostic.md)。
根级启动脚本的后续同步、备份与实际启动检查见
[根脚本混合图更新](root-launcher-hybrid-update.md)。
此前根脚本的参数精简与复测见
[启动脚本精简记录](launcher-simplification-20260930.md)。
用户指定的当前容器默认缓存/临时路径版本及复测见
[默认路径启动脚本](default-cache-launcher-20260930.md)。
用户随后自行调整的当前脚本及原样启动检查见
[用户脚本验证](user-launcher-validation-20260930.md)。
2026-10-03 对当前服务的 14 科、每科 50 题、32 并发实际评测见
[MMLU-Pro 子集测量](mmlu-pro-subset-c32-20261003.md)，保留严格和最终答案两个评分口径。

2026-10-10 对当前 8000 服务按最大支持长度评测 14 科、每科 50 题、32 并发，见
[MMLU-Pro 最大长度子集测量](mmlu-pro-subset-c32-20261010.md)。

2026-10-12 曾因范围理解错误启动 12032 题评测，用户纠正为每科前 50 题后已停止。
原始过程及停止证据保留在 [已停止的全量评测记录](mmlu-pro-full-c32-20261012.md)。

2026-10-12 按用户纠正后的范围完成 14 科各前 50 题，共 700 题、32 并发。当前规则
48.00%，最终答案规则 48.29%，见 [MMLU-Pro 前 50 题测量](mmlu-pro-subset-c32-20261012.md)。

执行模式与变输入基本测试有实测结果；项目定义的固定 GPQA 十并发 sanity manifest、
冻结准确率阈值、正式准确率与性能评测以及原生回执仍未完成。
