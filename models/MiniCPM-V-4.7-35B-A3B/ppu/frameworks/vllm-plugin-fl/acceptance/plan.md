# PPU-13 正式验收计划草案（未冻结、未执行）

2026-09-30 用户要求先暂停精度评测，并先创建使用 `FULL_AND_PIECEWISE` 的
根级启动脚本；实际脚本与试运行见[单独记录](launcher-20260930.md)。此更改
不是原计划中 `decode-full` 正式执行模式回执，也未冻结精度/性能配置。
用户随后要求删去非必要设置，当时脚本与重启复验见
[精简版记录](launcher-minimal-20260930.md)；上述单独记录保留首版历史。
用户再次编辑的根级脚本实际启动失败，详情见
[006 问题](../adaptation/006-user-launcher-graph-oom.md)；上述精简版现只作为
已验证恢复配置，不再代表当前根级文件。
当前根级脚本经七个图尺寸限制及多模态参数删减后重新验证，详见
[2026-10-01 参数删减记录](launcher-mm-flags-20261001.md)；正式验收仍未开始。

日期：2026-09-29。唯一目标为 `PPU-13`，容器 `minicpmV4.7-35B`；批准工作根
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，模型权重
`/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`。当前部署指纹
`e66b5c293bb60296c932b1e3291282867a6d66c70d7be42e37411f7e31f09a37`。
环境、适配阶段原生回执已在目标 Host 通过读取远端产物的门禁。此文档只列待冻结
的验收输入；不是任一步骤的通过记录。

1. **执行模式**：沿用已核实的 eager 及 graph 服务证据。graph 启动请求 `FULL`，
   GDN 在两个 rank 明确降至 `FULL_DECODE_ONLY`，decode 图捕获 4/4；正式记录
   图级别为 `decode-full`，附完整 fallback 签名、限制和退出条件。两模式的
   EngineCore 生效值均为 `enable_prefix_caching=True`。
2. **固定小批量**：10 道固定科学单选题，10 并发，逐题正确及输出健康检查；
   manifest 和一次性运行器已准备，待执行模式通过后放入远端 `03-acceptance/`。
3. **正式精度**：建议 FlagEval 容器中的 `gpqa_diamond_generative_cot` 完整
   198 题，`limit=0`，并发 32，metric `exact_match,strict-match`，
   `allow_timeouts=true`。最低分阈值、生成参数和冻结配置须在执行模式验收前确定；
   当前没有足以替用户指定最低分的官方 4.7 35B-A3B 同条件基准。
4. **正式性能**：建议一个可复验的短输入场景：输入 128 token、输出 32 token、
   并发 1、20 请求，3 轮（首轮预热），不启用 profiler。具体场景范围须在
   执行模式验收前确定；运行时只对同一已验收 graph 配置的性能专用实例加入
   `--no-enable-prefix-caching`，核对 EngineCore 生效值为 `False`，精度后的
   其他服务与部署参数保持一致。性能完成后恢复普通缓存开启服务。
5. **证据、总结与复盘**：逐步核验原生回执和远端哈希。用户指定的根级
   `start-model.sh` 已提前创建，须先完成此次独立运行验证；正式总结仍需
   核对脚本是否符合最终通过的图级别与普通前缀缓存配置，再更新状态与复盘。

`framework.yml` 的 `acceptance_plan` 目前为空，所有验收子步骤为
`not_started`。只有精度阈值和性能场景确定、实际配置规范哈希冻结后才能
开始执行模式正式回执。性能场景和精度请求不可从当前诊断耗时推断通过。
