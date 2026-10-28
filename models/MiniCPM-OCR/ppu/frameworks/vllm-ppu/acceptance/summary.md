# 原生PPU适配基础验证总结

2026-10-27，PPU-01 / `minicpm-ocr-ppu-native`，用户指定的原生0.23镜像及merge_rl_mergedp1_7140_hf5_4x权重。状态functional；experimental声明的基础验证通过，完整正式验收保持未完成，不标optimized。

容器持续运行，API为PPU-01的8014端口，OpenAI路径 `/v1/chat/completions`，模型名 `MiniCPM-OCR-PPU-native`。PPU4、TP1、32768上下文、8序列、16384批次token、显存0.55、图像4/视频1，FULL_AND_PIECEWISE，正常前缀缓存开启。其他既有服务未停止或重启。

共修改实际安装vLLM的11个Python文件：新增OCR配置、处理器和模型适配器，并接入标准惰性registry；隔离0.23的旧MiniCPMV processor包装。未修改权重、参考checkout、Torch、Transformers、SDK或原生内核。普通wheel无Git工作树，未伪造HEAD/PR base，未提交、推送或创建PR；全部diff与限定计划逐hunk核对，见问题001和 `04-runs/source-review.json`。

16项CPU回归通过。真实权重eager与graph各6类图像的prompt/生成token IDs与独立Transformers参考一致；图直接测得6次capture和48次replay。最终图服务文本/视频路径通过；原生service-sanity在绑定实例上5例4并发全部匹配，无错误或超时。FULL因GDN的UNIFORM_BATCH能力限制失败，已按顺序诊断和降一级，未把自动降档当作FULL通过。

Host及容器的根级启动入口均为 `/mnt/nfs/users/jinghao/MiniCPM-OCR/ppu-native/start-model.sh`，SHA-256 `fb250cb53139ef7cdc80f3310520ed0217463447ab853e5e222e000084572c2c`。根脚本实际启动了上述最终服务，语法/权限/实参/就绪和缓存已核验。它仅含必要服务设置及缓存开关，拒绝未知参数，不杀进程、不操作容器；未设置多余缓存目录环境变量。`--performance`只关闭前缀缓存，本轮不执行性能测试。

持久交付材料在批准根 `01-environment/delivery/`，包含相同启动脚本、配置、source.patch、依赖锁和恢复说明；容器内副本为 `/opt/minicpm-ocr-ppu-native/`，与持久材料逐文件哈希一致，不在绑定挂载内。已安装产品文件也在容器文件系统，正常启动不依赖PYTHONPATH或外部开发源码。权重保持已声明只读外部输入。镜像未打包，fresh-container image validation=pending。

限制：关闭放大的极小图在参考模型中同样识别退化；自由生成并非跨实现逐token一致；未验证其他平台、TP/PP、量化、满上下文/满8路容量、正式精度及性能目标。当前profile缺少正式accuracy/performance适配器，因此不签发整体验收。需要扩大范围时另行选择相应工作，不以局部验证推断。

本地审计仅发现仓库原有XingChen4失效链接和其他模型历史告警，本工作区无审计条目；它不替代远端原生门禁。精简记录和完整原始证据分离，早期失败保留，未迁移或清理他人目录。
