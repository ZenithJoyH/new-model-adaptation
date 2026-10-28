# 2026-10-24 整模精度、性能测量与交付计划

2026-10-25更新：用户明确取消eager端到端性能测试，当前只执行graph九场景，
每场景1次预热及2次正式测量，共27轮。已完成的eager部分结果保留，不再补测或作完整性能比。
原有eager/graph数值一致性验证及精度标准不变。下文双模式性能安排保留为原计划历史。

范围：mx-101 / qwen3.8-flash / BF16文本TP8 / vllm-plugin-fl v7；代码保持已验证安装身份。
用户已选择GPQA Diamond全量198题、exact_match,strict-match≥0.88；超时按错保留，
不得删除缺失/错误样本或事后改阈值。性能采用1024/128、1024/1024、8192/1024三种
输入/输出长度，每种并发1/8/32，测同机同源码eager与graph；只报告，不设达标线，
不据此声明性能达标或optimized。原生有效测量和业务目标通过明确分开。

历史PPU记录显示60000生成上限仍有题目截断，不能以缩短生成加快全量评测；
本轮计划max-model-len100000、max_gen_toks96000，采样遵循本模型generation_config：
temperature1、top_p0.95、top_k20，思考模式开启。当前50K配置GPU KV记录164556token
只是参考，先实测新配置容量；初步选客户端并发8，在短/长混合负载确认后冻结正式配置。
GDN限制仍采用显式FULL_AND_PIECEWISE，不扩展其它主机，不变更vLLM源码。

先完成当前source_review原生绑定和新运行语义下environment/eager/graph，冻结0.02数值阈值；
再执行模式gate→冻结有eager参考的sanity manifest及并发8实际测量→完整精度。
正式精度通过后才切换性能专用服务（显式--no-enable-prefix-caching），同参数测量eager/
graph九场景，每场景1次warmup、2次无profiler测量，保留全部成功请求/token/指标校验。
性能后恢复普通prefix-enabled的graph服务。性能无目标判定是用户明确要求，不填写虚假目标。

评测使用指定FlagEval v1新建任务容器qwen38-mx101-eval-20261024，host network，
唯一host bind为已批准根同路径；响应SQLite通过批准根06-cache/flageval-responses内
tmpfs存储，避免NFS锁。GPU不分配给评测容器。不操作其它现有容器。
执行与结果使用批准根01-environment/03-acceptance/04-runs/05-tmp/06-cache，
本地仅保留Markdown及framework.yml；最终脚本在根start-model.sh并放置容器内部交付副本。
镜像打包未获请求，不创建镜像或声称新镜像验证通过；无提交、推送或PR创建。

## 已固定的正式输入

100K eager/graph三类技术验证与并发8小集已通过；两种模式均采用clone,randn,normal_排除。
qwen3 parser、xhigh thinking及并发8已固定，GPQA配置位于远端
03-acceptance/gpqa-full198-c8-100k-20261024-config.json，SHA256
`dbb90ef5c53c985e70919735cece94f4921a4977063d94e03958e6230896e58e`。
完整198题输入长度经实际模板核算为230–2933，生成预算合计最大98933≤100000；
只使用gpqa-token-budget-validated-20261024.json，早期误将BatchEncoding字段数当长度的产物
已标注invalid且保留，未用于准入。

FlagEval实际镜像digest为sha256:1396e5d63553530425db81ebf9a724aa98dc2e11aaf2e677c908f991a9cb7ce3；
数据集fingerprint 2ea5394e17e3ee1b。accuracy formal-full bundle为
355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d，performance full-suite为
3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff。

性能无业务目标，保留benchmark完整性校验与紧凑测量回执，但不伪造v2 performance_targets，
不把有效测量写成framework performance passed或optimized。此为用户明确选择。

## 长推理容量边界

实际100K eager启动报告KV849403token/满长请求8.49x，graph为167702token/1.68x；
不能将eager容量复用于graph。客户端并发8是经短长前缀探针选择的并发，不保证8题同时达到
96000生成预算。长推理过程中持续记录实际运行数、KV占用、抢占及错误；本轮配置不在中途
改变，最终保留所有超时/错误。服务支持的max_num_seqs32也不等于32路满上下文容量。

## C2重新冻结

首次C8完整尝试因长推理KV压力中断，全部部分结果与失败/中断证据保留，未计精度成绩。当前独立C2完整198题配置SHA256为6d831a4d81837c44d89cebf620c846102e5a8d675290e35851b87d2be6e65b64；原门槛、采样和生成预算不变，缓存命中0。双61038token容量先行通过，详见[011](../adaptation/011-gpqa-long-reasoning-capacity.md)。此前C8计划/配置保留为历史。
