# 适配计划与缺口表

材料导航：[环境索引](README.md) · [Plugin 设计审查准备](plugin-change-review.md)。
当前完整 PR diff 尚未按新标准审查；模型实现、共享 runner 和平台 workaround 分别列出影响。

目标：PPU-01 / qwen3.8-flash，BF16 Qwen3.8-Flash-Next，基线与边界见environment和architecture文档。
保留原dirty GLM插件，在新目录克隆support-qwen3.8-flash@2b2fe95并editable安装；不修改vLLM，不重启容器。

| 缺口 | 实现来源/接入 | eager/graph影响与风险 | 验证 |
|---|---|---|---|
| 配置与模型缺失 | 候选patches/qwen3_8_flash_next、models/qwen3_8_flash_next；插件register_model | config aliases、typed subconfig及v0.24 ABI | config/registry与weight loader测试 |
| QSA分页与压缩语义 | 候选plugin dispatch/backends/triton/qwen38 | 固定topk宽度、尾块、KV实际stride；需对最新FlagGems重新检索，不能引用旧缺失结论 | QSA reference/cache/graph变输入用例 |
| PLE哈希、embedding与卷积state | 模型PLE和dispatch state gather/scatter | integer溢出/EOS边界、TP overlap、graph请求行重用 | PLE reference/state IO、runner ngram |
| GDN packed decode | 专用子类resolve_op，不替换vLLM函数 | FP32 beta、唯一state行、非连续布局 | 独立FP32 oracle、eager/graph |
| 公共slot metadata | 候选ModelRunnerFL/common_slot_mapping | 缓存重绑、padding和调度后metadata刷新 | changed-input graph测试 |
| 通用RMSNorm/GEMM/SiLU/MoE/RoPE/conv | 已有插件dispatch，FlagGems更新后核对 | 旧PPU blacklists不能无证据迁移 | dispatch回归与组件组合 |
| 四分支residual | 候选common/hyperconnection | 与GLM mHC不同公式，不混用 | FP32参考及整模正确性 |
| 服务资源 | PPU8–15、TP8、PP1、8038、maxlen50000 | 先核验设备/端口，保留相同参数eager→graph | imports→ops→components→minimal model→service |
| 验收 | graph固定配置c8 sanity→c32完整198 GPQA→性能/相关通信→总结 | formal accuracy未通过不可跑final performance | 保留完整结果路径、错误/超时及明确标准 |
| 视觉/MTP等 | 候选分支未验收，不伪装通过 | 首轮language-model-only；扩展范围需独立验证 | 标为未验证 |

FlagGems若不clean、分支不明确或FF同步失败，停止算子选择并报告精确阻塞；遇FlagGems错误时在工作根 `08-bugs/` 打包最小复现，并通过容器对应路径原地执行，已有用例不再复制到 `/bug`。每次只改一个实质变量，窄回归失败不扩大测试。
