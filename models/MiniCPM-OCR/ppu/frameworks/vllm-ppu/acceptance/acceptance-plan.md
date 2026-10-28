# 原生PPU基础验证计划

2026-10-27，PPU-01，experimental vllm-ppu，checkpoint为merge_rl_mergedp1_7140_hf5_4x。选择execution-mode、sanity、evidence、summary；不执行正式精度/性能或复盘阶段，不标完整正式验收或optimized。

执行比较在最终复验前固定最大误差0，比较对象为6类图像的生成token IDs及prompt token IDs，相同只读权重的Transformers模型作为独立参考。这不是logits逐元素一致性或正式数据集精度。故意保留的关闭放大小图只验证实现一致性，不能算OCR正确性通过。

正常前缀缓存开启；PPU4/TP1、32768上下文、8序列、16384批次token、显存0.55、图像4/视频1。FULL因GDN UNIFORM_BATCH能力限制失败，按序选择FULL_AND_PIECEWISE；记录实际捕获和回放，不用请求参数替代实际档位。

sanity显式选择仓库 `adaptation/accuracy` 的 `service-sanity`；Skill bundle SHA-256 `355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d`。5例为默认4x、16x、自适应小图、切片、多图，参考文本由Transformers生成并与图像已知文字交叉核对。manifest SHA-256 `061c3c0318bdc213ad6600ea76dba42bfa711079f8bb8744f63be5780fe816c6`；并发4、超时120秒。先验证原生manifest，再绑定当前服务进程和监听端口，执行精确文本比较；失败和超时保留。

原生计划和脚本在批准根03-acceptance，运行结果在04-runs；只用同一根级start-model.sh默认启动进行sanity。evidence审查全部实际源码diff、安装身份与未验证范围；summary核查脚本权限/语法/实参/就绪/缓存及容器内交付副本。新镜像验证保持pending。
