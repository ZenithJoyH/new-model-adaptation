# 2026-10-27 移除四项缓存路径覆盖

范围为mx-101 / qwen3.8-flash的start-model.sh、容器内部副本和对应交付记录。
用户进一步要求尽量删除TMPDIR、TRITON_CACHE_DIR、FLAGGEMS_CACHE_DIR、VLLM_CACHE_ROOT。
不改变模型/产品源码、TP8、100K、图模式、推理参数和其他三项已验证必要设置。

进一步核实发现：虽然statvfs普通可用空间f_bavail=0，但容器服务UID为0，
实际root可用保留块约27GB；之前仅据普通可用空间保留四项覆盖过于保守。
/tmp、/root/.triton/cache、/root/.flaggems、/root/.cache/vllm均已通过匿名临时文件
1MiB写入和fsync测试。它们是容器内默认路径，不是指向host目录的软链接或新增挂载。
未清理、移动或替换既有缓存。旧NFS缓存大小查询超时，保留为不完整观察，不用其证明容量通过。

写入预检原始证据位于远端批准根03-acceptance/default-cache-write-preflight-20261027.json，
SHA256 493e9914a6e1c3969fd808146d38d43ae1507e15e5b0c7a7ea9a5a862dae04b6。
计划直接删除四项导出，不用其他变量、sourced helper、外层环境或目录迁移隐藏它们。
先做shell参数/环境对照，再实际normal启动及105token固定回归；性能分支只做配置预检。
验证完成前不刷新旧回执或宣称旧完整评测已由新脚本执行。

## 验证完成

四项导出已全部删除。根脚本和/opt/qwen3.8-flash-delivery/start-model.sh内容一致，
SHA256均为1550bacb0b7d219c283170fd6e3667b27b6c87d42bff01cb9bc51d045cbf6e91。
仅剩VLLM_FL_FLAGOS_BLACKLIST_APPEND、VLLM_FL_USE_FLAGGEMS_VLLM、FLAGGEMS_DB_URL三项正确性相关导出。
脚本与外层调用均没有四项缓存变量、XDG替代变量、软链接重定向或缓存迁移。
normal/performance两分支的模型命令与上一验证版本相同，仍只切换prefix缓存。

实际默认路径为/tmp、/root/.triton/cache、/root/.flaggems、/root/.cache/vllm；
Inductor默认/tmp/torchinductor_root，vLLM管理的AOT产物实际生成于/root/.cache/vllm/torch_compile_cache。
首次冷缓存加载、编译、mixed/decode图捕获、服务就绪及固定回归均通过。
完成时root保留空间仍为21617643520 bytes（约21.62GB），普通f_bavail仍为0；
没有通过清理或迁移其他数据获得空间。详细路径与依据见[默认路径实测](../environment/cache-defaults-verified-20261027.md)。

当前服务run_id为launcher-default-cache-normal-20261027，PID3433953/start_ticks1139790311，
8000端口、100K、TP8、FULL_AND_PIECEWISE、prefix开启。10例105生成token均匹配原100K eager参考，
所有数值有限，最大生成token logprob差0.001207549125≤0.02。
产品源码、模型输入及编译二进制身份保持原验证状态，未修改vLLM或其他组件源码。

根脚本和容器内部副本、runtime、交付清单及恢复说明均已同步，容器与正常服务保持运行。
全198题GPQA及九场景性能未重跑或改写；性能分支只做参数/配置预检，不声称实际性能测试通过。
镜像打包和新容器验证仍pending。

相对路径均位于远端批准根/public-flash/jinghao/qwen3.8-flash：

| 证据 | 路径 | SHA256 |
| --- | --- | --- |
| 实际启动与回归 | 04-runs/launcher-default-cache-normal-20261027/launcher-verification.json | 20699ef4833a3ac83f45675bb5407a63de2ca183c3129b9e668eb20790cfb366 |
| 默认路径/两分支预检 | 04-runs/launcher-default-cache-preflight-20261027/result.json | b4b1036197fd7df027f6248ed6d730ae88f2798a05ed3e30ace1ec3ac95d5c92 |
| 当前runtime | 01-environment/launcher-default-cache-normal-20261027.json | 12f9698ded86b0db64a727575c253975938bf1157f105aa8c89558ba615a30d3 |
| 固定案例对照 | 04-runs/launcher-default-cache-normal-20261027/eager-comparison.json | 19abf9578400ce2500175b889200922afb0c7b8635fe25a03469d500fedabab1 |
| 当前交付清单 | 03-acceptance/delivery-launcher-default-cache-20261027/delivery-manifest.json | a6f8b1aa346039dc771e360539b4696bf5eb814c623a6e008d00beff07a00af6 |

上一版脚本与内部文件分别备份于04-runs/launcher-default-cache-controller-20261027/previous-start-model.sh
及previous-internal/；其SHA66fa71fd及原回执作为历史保留。
本次执行包装03-acceptance/apply-default-cache-launcher-20261027.py的SHA256为
aaad9eceac0a7eccf3f601b93ad5f0cab9e3af907db22adca119090d0350693e。
