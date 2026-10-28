# 四并发小集合（2026-10-28）

同一最终根脚本SHA a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626，
默认prefix开启；图档位full-and-piecewise，双机TP8/PP2、BF16、65536上下文及所有基础参数不变。
服务实例glm53-pp-eefb511543be8f302ecd2b45，101提供API、102为headless参与节点。

原生`test/Accuracy_test/sanity.py`先离线检查，再显式--run。四并发、timeout3600，四条请求
及精确参考取自同源eager的reference-manifest，先冻结SHA，不从当前graph输出生成参考。
已完成的运行是`04-runs/glm-sanity-final-v14-20261028/`；sanity-result.json为passed，
四条均无错误，最终文本逐条为`**4**`、`**56**`、`**5**`、`Paris`，与独立参考完全相等。
completion tokens分别59、30、30、65，合计184，无空输出或512-token截断。

现场service-observation和两Host的pipeline-process-observation绑定同一run/challenge，
原生验证器确认101实际API监听进程及两机稳定进程身份/拓扑、1426对互逆跨机连接；
不将102描述为本地API，不为两Host重复执行四条请求。service-binding-check.json保留该证据。
客户端原生state为passed/rc0。独立performance-sanity.json保留实际总耗时及token计数：
此检查仅确认冻结小集合在timeout内正常完成，不是业务时延/吞吐达标或正式性能测量。

原生gate对逐Host回执、完整manifest、全部响应及服务绑定再次核验。该小集合不能代替
GPQA Diamond198全量的strict-match>=0.88，也不证明多模态、MTP或其他硬件通过。
