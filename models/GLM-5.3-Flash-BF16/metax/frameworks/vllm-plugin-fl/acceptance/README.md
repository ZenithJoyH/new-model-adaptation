# 适配验收计划与状态

范围为mx-101/mx-102的vllm-plugin-fl v7、证据契约v2。阶段3源码审查、
[execution-mode](execution-mode-final-v14.md)及[四并发sanity](sanity-final-v14.md)的原生gate
均已通过；当前GPQA Diamond198正式运行中，尚无全量精度结论。性能和镜像验证待完成。

执行模式验收在运行前冻结 `max_abs_error=0.05`：固定确定性请求的生成token和文本必须一致，
图模式与eager比较对应token的自然对数概率最大绝对误差不超过0.05；不同输入至少两次实际
replay，另核实有效图档位和capture。该阈值不替代GPQA strict-match最低0.88。正式GPQA生成
参数计划temperature1.0/top_p0.95/max_gen_toks60000，最长实际输入2901、上下文65536；
实际KV容量420810 tokens；4路×(最长输入2901+最多生成60000)=251604，均不超过65536。
最终并发冻结为4，原生FlagEval容器按完整198题执行，超时计错误，API/eval重试均为0。
只执行一轮共享的整模型评测，不把两Host的回执误计为396题。

服务小集合与正式验收使用批准根的同一 `start-model.sh`，普通启动保持prefix开启，
只有 `--performance` 关闭prefix。最终为显式full-and-piecewise，FULL的原生能力阻塞和
逐级回退证据保留。根脚本SHA为a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626，
101实际API与102 headless进程/通信连接均有本轮现场取证。当前基线镜像未包含全部适配修改。

精度原生工具使用独立冻结的`03-acceptance/native-tools-pipeline-v1-20261028`，归档SHA
c9caa6c10a830d8f5092b76dd337ff1cf252e66b0dd14402e8c64e4d52ff06cd；
原51文件bundle及历史回执不改写，性能runner保持原冻结字节。
GPQA配置`03-acceptance/gpqa-final-v14.json`已冻结到framework计划；运行
`04-runs/glm-gpqa-final-v14-20261028/`有预检和journal，实际native结果目录为
`04-runs/accuracy-results/glm53-metax-final-v14/glm-gpqa-final-v14-20261028/`。
随附中间计分助手未识别v2数据集描述符，错误保留；不改变正在运行的runner/配置，
只读进度监视另见[016](../adaptation/016-gpqa-progress-display.md)。中间数字不作为正式通过证据。
