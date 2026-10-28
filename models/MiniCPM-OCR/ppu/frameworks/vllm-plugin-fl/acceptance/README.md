# 适配验收索引

- [PPU 厂商 Flash Attention 功能验证](004-ppu-flash-attention.md)：PPU5/8015 新实例使用视觉 FA2、语言 FA3，57 项回归及 6 个 OCR 案例通过；原服务保留。
- [切换 PPU Flash Attention 后的完整性能测量](005-portable-v11-ppu-flash-performance.md)：PPU6 独立实例，三场景中位数 7.13/9.86/10.72 页每分钟，未观察到提速；最终两轮均稳定，批量首轮及加压全部轮次未达时限目标。4644 次请求全部成功无截断，32 页质量 Overall 97.5632，临时实例已退出。

记录当前 framework profile 的执行模式、小批量验证、正式精度、性能、证据汇总、最终启动
脚本和复盘。文件存在不代表已经执行或通过。

- [9999 服务的 OmniDocBench v1.6 数据集测量](001-omnidocbench-9999.md)：1651/1651 页、30594 次 OCR 请求成功，Overall 96.4217；保留 2 页匹配超时回退及评分环境差异，非 framework 正式验收回执。
- [Portable v1.1 整页性能测量](002-portable-v11-performance.md)：单卡 BF16，交互/批量/加压吞吐中位数 7.21/10.42/13.36 页每分钟；请求均成功，交互及批量达到目标，加压未达到 60 秒目标；32 页质量子集 Overall 97.6196。
- [Portable v1.1 report-2 最新 interactive/batch 测量](003-portable-v11-interactive-batch-latest.md)：吞吐中位数 7.29/11.59 页每分钟，各三轮均达到延迟目标；batch 最后两轮吞吐差异 11.5%，未达到稳定性要求。计时 1956 次请求全部成功无截断，32 页质量子集 Overall 97.5245；loaded 按用户指令中止并排除。
