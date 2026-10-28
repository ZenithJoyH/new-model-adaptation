# 100K并发参考小集验收

mx-101 / qwen3.8-flash，显式FULL_AND_PIECEWISE、前缀缓存开启，部署7d11fb14。

原生sanity.py执行固定8题、并发8，包括3个短问和5个8730token前缀状态用例，全部逐题与同源码100K eager参考文本一致。结果完整保留请求与响应，无请求异常。此处并发8表示客户端请求上限，不等同8路同时运行。

正式服务身份经宿主机challenge、容器ID、boot_id、PID启动tick、cmdline SHA及实际8000监听归属验证。相同服务长前缀容量与正式xhigh采样探针通过；日志未出现OOM/非法地址/EngineCore退出。资源与响应健康只用于sanity，不据此推断正式吞吐或性能达标。
