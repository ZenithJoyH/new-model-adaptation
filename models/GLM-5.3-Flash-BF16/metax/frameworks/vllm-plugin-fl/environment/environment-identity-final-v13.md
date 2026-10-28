# 双机最终运行环境身份（2026-10-28）

范围：mx-101/mx-102的glm5.3-flash容器；批准host/container工作根同为
`/public-flash/jinghao/glm5.3-flash`。两容器保持运行，完整ID、同路径挂载、实际安装位置、
HEAD、版本与source-snapshot-final-v13逐机复核。基础环境及默认服务缓存见
environment-analysis.md；33个推理/测试文件与已验v13完全同源。此次仅增加Plugin README
支持条目和真实chat示例，共35个任务文件；两机源集合相等。

Plugin tracked diff SHA为 adb86acb793922e094956211567397c978470c6375ccbc7d50b594cbf94957ea；
原33文件SHA及FG/FGV/vLLM差异均保持v13。没有PYTHONPATH覆盖，产品只在已核实的
/opt/vllm-plugin-FL、/opt/FlagGems、/opt/FlagGems-vllm；Torch、vLLM、SDK只读。
Plugin/FG/FGV公共基线分别为4e23ae8f/3eab0949/ddce1d66；本任务尚未提交的补丁不等于
上游已发布版本，安装与恢复必须同时锁定这些基线和完整补丁文件哈希。

模型120分片642652070880 bytes及所有模型/tokenizer元数据哈希不变。实际16×C550 64GiB，
TP8/PP2、native multi-node mp、inbond1 Socket，RDMA未验证。同源eager六请求、四chat参考、
冷/热prefix比较通过；FULL因实际MLA/indexer仅支持UNIFORM_BATCH而自动转下一档，保留失败。
显式FULL_AND_PIECEWISE随后四请求与16rank capture/replay通过，最大误差
0.03231409937143326 < 冻结0.05；每个rank每请求新增2次replay，累计8次。

最终API候选通过同一个根级start-model.sh启动，SHA
a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626，默认prefix开启。
运行身份见04-runs/glm-api-graph-final-v13-20261028/<host>/owned-process-snapshot.json；
未带诊断反序列化开关。当前KV容量420810 tokens；4路×(最长GPQA输入2901+最多生成60000)
=251604，小于此容量及65536上下文。正式服务就绪、sanity、GPQA198和性能须独立验收。
两机各81项、编译产物四组合和独立新进程恢复等原始证据见014及010，不声称本轮重跑。

最终部署身份：01-environment/deployment-identity-final-v13-20261028.json，指纹
e80048ed4c32de8ddedf3fadc681082500b51b972f78028fa4d37c1df63138d2。冻结变化只对齐实际graph档位、启动脚本及两项非运行时交付文件，
没有修改推理数学、权重、拓扑或其他推理参数。历史环境v13文档及回执保持原样。
API候选启动不是正式精度通过。图诊断退出时的资源跟踪警告保留；视觉/视频、MTP、
其他硬件未验证，性能目标未冻结，不宣称optimized。适配镜像及新容器验证尚待完成。
