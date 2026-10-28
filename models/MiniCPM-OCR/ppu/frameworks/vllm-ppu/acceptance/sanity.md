# 原生service-sanity：5/5通过

2026-10-27，PPU-01，最终根脚本默认启动的 FULL_AND_PIECEWISE 服务，PPU4/TP1、端口8014，前缀缓存开启。实例 `ocr-native-579999791`，容器内API PID39469。仓库observer已核验容器ID、boot ID、启动tick、命令SHA和8014监听socket，未用人工填写身份代替现场检查。

显式操作service-sanity；冻结5例、并发4、超时120秒，manifest与Skill bundle见验收计划。先通过环境/适配/执行模式 v2 门禁及原生preflight，再使用仓库 `test/Accuracy_test/sanity.py --run` 生成新结果。

5例全部HTTP成功、无错误或超时，与独立参考完整文本逐一匹配：默认4x、16x、切片、多图为 `HELLO OCR\nTEST 01`；自适应小图为 `HELLO OCR TEST 01`。这是已冻结小集合的一致性检查，不是正式数据集评测。

原始回执：`04-runs/sanity-native-20261027-final/sanity-result.json`，SHA-256 `cb4ce1e9d8cab606dd813c8264647d3b0a47425829945b420d9c94dfa7568879`。同目录保留observer的challenge、service-observation、preflight和runner输出。服务绑定在 `03-acceptance/service-binding.json`，manifest为 `03-acceptance/sanity-manifest.json`。

极小图关闭放大的已知识别退化未被隐藏为通过案例，单独保留于执行模式和问题001。正式精度、性能及镜像验收未执行。
