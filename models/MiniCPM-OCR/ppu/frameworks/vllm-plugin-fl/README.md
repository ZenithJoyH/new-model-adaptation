# MiniCPM-OCR / PPU / vllm-plugin-fl

2026-10-23，源码修复阶段仅在 `PPU-01` 的 `minicpm-ocr` 容器直接修复 FlagGems 大步幅
int32 索引地址乘法溢出，覆盖 `index` 读取及两个共享状态写回入口。
12 项 BF16 eager/graph 边界回归通过，含非连续索引和两次变输入 replay；
两个完整测试模块 quick/CPU-reference 模式分别 46/46、66/66 通过，无跳过，实际算子在 PPU 执行。
原单槽 7296 无保护区用例在修复后通过。

用户明确要求不重启模型服务；本轮没有启动或重启服务。未修改 vLLM、Plugin、
启动脚本或原始故障日志。该修复阶段未执行模型级推理；后续用户手动启动 9999 服务后，
另行授权的指定数据集测量结果见下文。正式阶段状态不标记通过。

详情、备份和证据见 [001：GDN 索引偏移修复](adaptation/001-gdn-index-int32-offset.md)。
Host/容器批准工作根均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR`。

读取侧修复及回归已提交 [FlagGems PR #7582](https://github.com/flagos-ai/FlagGems/pull/7582)，
关联 #6846，并说明与已有 #5882、#6413 的关系。提交时 CI 已启动，尚未合并。

用户指定的 OmniDocBench v1.6 评测已完成：9999 服务 1651/1651 页、30594 次 OCR 请求成功，
Overall **96.4217**（包内参考 96.4243）。有 2 页匹配超时回退，比参考多 1 页；
评分环境也有版本差异，详见[完整测量记录](acceptance/001-omnidocbench-9999.md)。
服务未停止或重启，未执行正式 framework 验收、性能验收及镜像验证。

2026-10-26，按用户给定 Portable v1.1 包完成独立性能测量：同容器 PPU 3 临时 8013 服务，
BF16、关闭前缀与多模态缓存，原有服务不变；交互/批量/加压吞吐中位数为
**7.21 / 10.42 / 13.36 页每分钟**，前两场景达到包内时限目标，加压场景未达 60 秒目标。
计时及预热合计 3626 次请求全部成功且无截断，32 页质量复核 Overall 97.6196。
临时服务已退出，详见[完整记录](acceptance/002-portable-v11-performance.md)；不标记正式验收通过。

同日使用更新的 report-2 包重新测量，最终按用户指令仅保留 interactive 和 batch：
吞吐中位数 **7.29 / 11.59 页每分钟**，各三轮均达到延迟目标；batch 吞吐仍有 11.5% 波动，
未满足稳定性要求。计时 1956 次请求均成功无截断，32 页质量子集 Overall 97.5245。
loaded 已中止，临时服务正常退出，原有服务不变；详见[最新两场景记录](acceptance/003-portable-v11-interactive-batch-latest.md)。

2026-10-27，已在 FlagOS 中接入实际 PPU 视觉 FA2 和语言 vendor.thead FA3，
PPU5/8015 正常服务保留，见[功能验证](acceptance/004-ppu-flash-attention.md)。
同包完整重测三场景中位数为 **7.13 / 9.86 / 10.72 页每分钟**，相对旧完整基线下降约
1.0% / 5.3% / 19.8%，没有消除与原生环境的差距。最终两轮均稳定，批量首轮、加压全部轮次未达时限目标；
4644 次请求成功且无截断，32 页质量 Overall 97.5632。临时 PPU6/8016 已退出，
现有服务不变，详见[切换后性能记录](acceptance/005-portable-v11-ppu-flash-performance.md)。
