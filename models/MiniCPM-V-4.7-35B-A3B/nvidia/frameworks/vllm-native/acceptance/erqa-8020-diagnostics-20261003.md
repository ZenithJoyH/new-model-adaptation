# ERQA 8020 服务对照诊断（非正式验收）

日期：2026-10-03。用户确认历史 `cpm35B-erqa_nv.json` 指向 `H100-149:8020`，
本轮核实当前 8020 是 `MinicpmV4.7-35B-native` 容器中的原生 vLLM，
Host API PID `3073088`，TP2，GPU 2/3，`FULL_AND_PIECEWISE`，前缀缓存开启。
工作根 Host/容器均为 `/public/flagos/jinghao/MiniCPMV4.7-35B/native`，
设备号:inode 同为 `45:242118947849`；适配容器和推理服务未停启。
历史 JSON 缺少请求时间和服务实例 ID，故不能证明历史与当前是同一个进程实例。

评测容器 `flageval-mmeval_v0.3.8` 内的 ERQA 数据位于
`/root/.cache/flagevalmm/datasets/ERQA/test/`。本轮由 Host 通过
`/proc/1981788/root/root/.cache/flagevalmm/datasets/ERQA/test/` 只读访问，
没有移动或复制图片。与 PPU-13 复测图片逐题按编号重排后，630 张 JPEG 的
名称/字节 SHA-256 清单聚合值同为
`1dd1354be4439731550ec0888e3eb08e7787471ae016abb475e2f6fb0ec204f4`。
400 题追加相同评测提示后的题干聚合 SHA-256 同为
`4d5ceb985fcb72acc429c257f5c1e696d8680ef72ed9b88665fc12d19c671360`。
实际 400 题 `usage.prompt_tokens` 聚合 SHA-256 在 NV/PPU 两端同为
`41a2886e4ead92e9124a5291c948dfa70a13169410fde957434ab405c06b1281`。

诊断脚本 `02-issues/erqa_nv8020_repeat_20261003.py` SHA-256
`c604ba701e5733038bc9b310bd3b8062041c3e282d9347ca4048a74390fcc200`。
`--run-dir /public/flagos/jinghao/MiniCPMV4.7-35B/native/04-runs/erqa-native-8020-defaults-c32-20261003`
配合 32 并发、`temperature=1,top_p=0.95,top_k=20,max_tokens=32768`，
不重试；结果 `result.json` SHA-256
`3b32b6ac4202fa39bb78a988979fe2a1f0913c00f71fe4177ca222ca4e7b3c4e`，
原始逐题响应在同目录 `results.jsonl`。112.3 秒收齐 400/400，0 HTTP/执行错误，
**195/400** 正确；19 题 HTTP 200、`finish_reason=stop`，但 `content` 无
可提取的最终 `Answer` 行，按错误计零。诊断脚本保存 `content` 和
`reasoning_content`，而当前原生 API 还可返回 `reasoning` 字段；
本轮未保存该字段，不能仅据这 19 题推断模型没有生成推理文字。
历史 NV 为 213/400，本轮最终选项与历史相同 323/400，历史独对 31 题、
本轮独对 13 题；这是一轮复现性诊断，不能替代正式 FlagEvalMM 回执。

贪心诊断脚本 `02-issues/erqa_nv8020_greedy_probe_20261003.py` SHA-256
`003b534fb18bb92c50c7558527039aa180e4f381f9b5a22c9ecec6cf1faabcac`，
固定 `temperature=0,max_tokens=4096`：

| 目录（`04-runs/` 下） | 请求 | 正确 | 无答案 | `result.json` SHA-256 |
| --- | --- | ---: | ---: | --- |
| `erqa-native-8020-45-greedy-c8-20261003` | 历史两端有胜负的 45 题，8 并发 | 19/45 | 4 | `06d0d6c66893dc756d28e838fda343049c4d6413805a0d69d79ceb147a5c9c11` |
| `erqa-native-8020-165-greedy-c20-20261003` | `ERQA_165` 同图同题重复 20 次，20 并发 | 19/20 | 0 | `8978821aa299ade3010e67935b156cf009c34531ac9c65da6c1310fac77aed9e` |

`ERQA_165` 与 PPU 请求的题干 SHA-256
`cc75f32197de7debb0dc0d2e41cb1a20d85cb724615cbf8ed32324e1f661b049`、
图片 SHA-256
`e58b080edb2d7a4f568383113fcf495051124f1a16f051ac6ea67003e23df7ff`、
590 个 prompt token 完全相同。NV 19 次选标准答案 A、1 次选 B；
PPU 当前图服务两轮分别只有 4/20 和 1/20 选 A，eager 为 0/20。
这是可重复的单题跨框架差异，不能由前段视觉注意力后端单独解释，
也不能从单题推断 400 题存在稳定的净分差。

两端服务使用不同框架路径：本服务的模型专用代码为原生 vLLM wheel
`minicpmv4_7.py`（历史 SHA-256 `91696f38a69091e45bd75fe1c35dd86ca32837c2827dd4d9251fda469ed2931f`）；
PPU 为 editable Plugin 模型适配器。索引标记的 459 个视觉/merger
张量分布在 `model-00001-of-00018.safetensors` 和
`model-00017-of-00018.safetensors`；两端两个完整 shard 的 SHA-256
分别同为 `4db68b027881abfc05c863778842f9695fe1bebe98debde8108dd65de64df277`
和 `8283b85a24a9b9190d819835d3813d2829ca715bf99f71c552b130a3bd61e0f5`。
其他权重 shard、实际视觉特征和首个数值分歧尚未逐值核对。
没有改动 H100 服务或产品源码。
