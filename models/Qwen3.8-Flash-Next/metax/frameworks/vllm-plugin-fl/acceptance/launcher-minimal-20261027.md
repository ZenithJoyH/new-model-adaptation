# 2026-10-27 启动脚本精简

范围仅为mx-101 / qwen3.8-flash的根start-model.sh及容器内部交付副本、对应交付说明。
产品源码、模型、TP8、100K上下文和FULL_AND_PIECEWISE选择不变，不重复开展适配或正式精度/性能评测。
此前2026-10-25的GPQA与九场景性能保留为当时脚本/实例的历史结果，不改写旧回执或声称由新脚本执行。

现场已核实容器ID仍为06b36c1d70e22ca68adef42e521d76f9b597f3fc6e8c0a9a8738ef03e1b85289，
工作根/public-flash/jinghao/qwen3.8-flash在host/container同路径映射，control.mode=agent。
旧脚本两份一致，SHA256 cd9f4a4d2e56628597b636892e5834e6d64a9d9357c21f98184b9e51703d07b6；
仍运行旧任务服务PID3304826/start_ticks1123453698。

## 改动界限与验证计划

先验证已安装版本的默认值，再移除冗余平台/plugin/八卡选择、无必要的无缓冲设置、
HF_HOME/TORCHINDUCTOR_CACHE_DIR覆盖、cd/unset/嵌入式端口探测和日志重定向。
正常prefix启用及compile mode3只有默认值取证一致后才删除显式设置。
保留FGV接入、随机入口规避、内存SQLite和既有资源/模型语义参数。
按新共享契约添加唯一--performance分支，仅关闭prefix caching，拒绝其余参数，不透传任意参数。
日志、进程归属、就绪和输出对照由脚本外完成。

容器/、/root、/tmp当前statvfs可用空间为0，批准工作根约有15.78TB可用。
因此不将所有缓存变量一删了之：Triton默认/root/.triton/cache，FlagGems默认/root/.flaggems，
vLLM默认/root/.cache/vllm仍不适宜新增运行缓存，保留对应覆盖及TMPDIR。
PyTorch默认Inductor缓存跟随tempfile.gettempdir()，可在必要TMPDIR下使用默认路径。
不通过sourced helper/外层环境隐藏被移除的导出，不清理任何无关数据。

验证包括参数/默认配置预检、脚本语法和未知参数拒绝、真实normal启动及固定案例数值对照；
同字节脚本--performance分支只做shell展开及引擎配置预检，不启动性能实例或重跑端到端测量。
备份、包装脚本、原始日志与新回执均保存在远端批准根，镜像验证仍pending。
## 实际完成结果

根脚本`/public-flash/jinghao/qwen3.8-flash/start-model.sh`和容器内部副本
`/opt/qwen3.8-flash-delivery/start-model.sh`已更新且内容一致，SHA256均为
`66fa71fd3523354e5a1d0f8b9702bb3f6818dedb37e7f58b79812ad9cdbcc2db`。
导出环境变量从13项减为7项：删除GEMS_VENDOR、VLLM_PLUGINS、CUDA_VISIBLE_DEVICES、
HF_HOME、TORCHINDUCTOR_CACHE_DIR、PYTHONUNBUFFERED；这些变量没有转移到外层调用者或helper。
删除cd、unset PYTHONPATH、set -euo pipefail、嵌入式Python端口检查和脚本内日志重定向；
vLLM自身仍会拒绝监听端口冲突，脚本不会杀进程。删除compilation-config中冗余mode3键，
已安装版本实际仍解析为mode3。

独立预检证明自动识别为metax、8卡，正常模式prefix=true，性能模式prefix=false，
其余关键配置与原显式配置相同。正常--enable-prefix-caching不能删除：本模型的安装版本默认关闭prefix。
--performance仅改变该flag，不接受任意额外参数；--unexpected及--performance extra均退出2。
预检r1暴露prefix默认关闭；r2验证器错误地假定custom_ops不会自动展开，失败记录保留。
r3独立对照确认vLLM对原始/精简配置均追加相同activation custom_ops，并非脚本改变算子路径。

仍保留的7项导出及理由：

| 设置 | 必要性 |
| --- | --- |
| TMPDIR | 根文件系统普通可用空间为0；编译临时文件使用批准根05-tmp |
| TRITON_CACHE_DIR | 避免向默认/root/.triton/cache写入大量编译缓存，复用原已验证缓存 |
| FLAGGEMS_CACHE_DIR | 避免默认/root/.flaggems落入满盘文件系统，保留生成代码/配置缓存位置 |
| VLLM_CACHE_ROOT | 避免默认/root/.cache/vllm，保留原编译缓存位置 |
| VLLM_FL_FLAGOS_BLACKLIST_APPEND | 保持clone,randn,normal_已验证规避，不宣称底层随机问题已修复 |
| VLLM_FL_USE_FLAGGEMS_VLLM | 保持已验证FGV算子接入路径 |
| FLAGGEMS_DB_URL | 保留内存SQLite，避免先前已复现的NFS数据库等待 |

资源/模型参数保留TP8、100K上下文、max_num_seqs32、prefill6400、text-only、mamba align、
qwen3 parser、服务模型名和显式FULL_AND_PIECEWISE/custom_ops all，分别绑定原拓扑、容量、
模型语义与图模式选择，不将这些内容当作冗余默认删除。
默认目录及容器空间依据见[补充环境分析](../environment/launcher-defaults-20261027.md)。

已按准确owner停止旧服务，容器始终运行。新normal服务run_id为
launcher-minimal-normal-20261027，PID3373503/start_ticks1139280562，8000端口、100K上下文、
prefix启用。10例105生成token均与原100K eager参考一致，所有值有限，最大生成token logprob差
0.003827962094≤0.02。该验证不等同于全词表logits或全量GPQA重测。
新脚本、交付runtime配置/清单/恢复说明均已同步到容器内部，产品源码和编译二进制身份复核一致。

根脚本用法为`./start-model.sh`；将来进行性能测量时使用同一文件的`./start-model.sh --performance`。
日志由调用者重定向到批准根04-runs，脚本不再内嵌重定向。
本轮只实际启动normal服务，性能分支完成配置预检；全198题GPQA与九场景性能没有重跑，
原2026-10-25结果继续明确绑定旧脚本/实例，不刷新旧回执冒充新脚本验收。

所有相对路径均相对远端根`/public-flash/jinghao/qwen3.8-flash`：

| 证据 | 路径 | SHA256 |
| --- | --- | --- |
| 启动精简及回归回执 | 04-runs/launcher-minimal-normal-20261027/launcher-verification.json | f7702dc935efb4f1d5cb1006e874623246e2c432745a849e4ba40f4dc40e547c |
| 独立配置对照 | 04-runs/launcher-minimal-preflight-r3-20261027/result.json | 4621fe1d8c0b5e53d41152effd9a8cf255e02ddfe603b0d424fe72733201944c |
| 当前runtime | 01-environment/launcher-minimal-normal-20261027.json | 576906c827cb5417fdd69e1240ca17ae9245355463d093349715e34ec6005599 |
| 固定案例对照 | 04-runs/launcher-minimal-normal-20261027/eager-comparison.json | 0d8318cb4f1b9c44d153dfcc14c20d5788fb40a0def4a8020d45c6d07e08a4cc |
| 当前交付清单 | 03-acceptance/delivery-launcher-minimal-20261027/delivery-manifest.json | 7547574d05467390434744d232831744073124403027ee15110ee28d3ba5f476 |

旧脚本备份在04-runs/launcher-minimal-controller-20261027/previous-start-model.sh，
旧内部交付文件在同目录previous-internal/；原始回执未改写。
执行包装03-acceptance/apply-minimal-launcher-20261027.py的SHA256为
433f5a5e4164ee3e6fef32e283a7f097e92b1dc7b397853969ec6105bdad3d0e。
当前功能回归通过，仍不声明业务性能达标或镜像验证通过。
