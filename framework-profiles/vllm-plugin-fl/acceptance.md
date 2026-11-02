# vLLM + vllm-plugin-FL 验收要求

新服务工作区在 sanity 前冻结 `acceptance_plan.service_contract`；模态与服务别名必须
匹配结构分析和实际服务，精度/性能/交付共用已冻结脚本和配置，只有性能关闭缓存。
完整字段与升级规则见[服务证据契约](../../docs/evidence-contract-v2.md#服务范围与共享启动绑定)。

- 最小推理分别在 eager 和 graph 跑通。graph 按
  `full` → `full-and-piecewise` → `decode-full` → `piecewise` 逐级尝试。
  每次回退都要提供上一档的配置、定位、修复尝试、未解决阻塞及证据，不能跳级。
- `piecewise` 可以在完整逐级阻塞证据下验收；仅 eager/NONE 不能通过 graph 验收。
  回执记录实际生效的 `graph_level`，不能把框架自动降级当作请求模式已通过。
  `graph_fallback.attempts` 按序覆盖所有更高优先级模式，每级单独提供配置、失败签名、
  原因、修复尝试、限制、恢复条件和可核验的证据，见[证据契约](../../docs/framework-evidence.md)。
- 图模式选择服务于实测性能，按通用工作流比较同条件吞吐、时延和显存；性能问题需先
  尝试优化，仍无法解决且有对比证据才能作为回退依据。
  后续冻结并发的小批量、精度、性能验收和启动脚本绑定最终验证模式，改变后重新验证受影响项。
- 小批量/正式精度前准备最小根级 `start-model.sh`，按
  [统一服务启动入口](../../docs/remote-operations.zh-CN.md#统一服务启动入口)删除非必要缓存目录环境变量。
  精度用 `./start-model.sh`，性能用同一脚本的 `./start-model.sh --performance`；基础配置及
  脚本 SHA-256 不变，只切换前缀缓存。记录实际生效配置及服务实例，交付保留已测脚本。
- 小批量预检覆盖文本请求，图像模型同时覆盖图像请求；核对切题、输出健康及图像理解，
  不要求开放式回答逐字一致。新 sanity manifest 使用 schema 2，原始响应与独立逐项审阅
  通过哈希绑定，旧 `reference_consistency` 检查名对应预期行为审阅；不能仅凭 HTTP 成功通过。
  明显性能问题先修复再做正式精度，历史 schema 1 比较规则保留。
- 性能验收不强制预设目标；精度通过后取得完整有效测量，记录配置、吞吐、时延和资源情况。
  用户另行要求并冻结的优化目标仍须达成，不能删除目标绕过失败。`optimized` 仍要求全部
  验收和交付检查通过，不代表无基线时已证明提速。
- 正式精度使用 FlagEval 容器及仓库统一精度入口，按冻结阈值判定。
- 所有非性能工作保持前缀缓存开启。
- 性能服务必须显式使用 `--no-enable-prefix-caching`，并验证实际启动命令和服务实例；性能后
  恢复普通的前缀缓存开启配置。
- 最终 `start-model.sh` 使用最终验收选定 graph 模式的最小生产命令，默认调用不携带
  `--no-enable-prefix-caching`；该参数仅由显式性能开关启用，不保留诊断、profiling、dump 或临时参数。
- `launcher_minimal` 同时审查指令和参数：脚本不安装依赖、更新源码、应用补丁、运行评测
  或收集报告；仅保留服务启动必需内容。外部验收负责就绪检查和取证。
- `installed_component_imports`：不设置 `PYTHONPATH` 或其他导入覆盖，核实服务解释器实际
  加载容器内安装且完成修改的组件，并记录路径、版本、文件哈希及适用时的 Git diff。
- `launcher_self_contained`：按[远程操作细则](../../docs/remote-operations.zh-CN.md)核实交付
  脚本和必要配置/代码/运行库实际位于镜像可保留的容器文件系统；不能只核实挂载路径存在。
  记录必要外部输入的明确部署约定；实际打包后再记录新容器验证，未执行时不得声称镜像已验证。
- `source_review` 必须覆盖每个被改的 Plugin、FlagGems、FlagGems-vllm 组件，按
  [贡献标准](../../docs/plugin-contribution-policy.md)逐块核对真实 diff 与变更清单，尤其是
  删除/替换依据、跨组件必要性、已有路径回归及试验残留。无法解释的增删、无关重构、重复
  workaround 或已知回归未解决不得通过；服务跑通或精度/性能结果不能代替审查。
  同时核对[开发规范 v1](../../docs/inference-plugin-development-v1.md)全部适用条款的证据，
  包括算子归属与公开依赖固定版本、真实分发/独立数值/graph 测试，以及新模型或厂商的
  README 支持列表和可运行 example。适用的【必须】未满足不得标记规范审查通过；
  【应该】的偏离须给出理由与验证，硬件不可用项按 F4 如实披露。
  被改算子组件同时按[算子层规范](../../docs/operator-development-standard.md)审查全部适用
  条款，以 `operator:<编号>` 记录证据：公开导出/注册/实际分发、独立数值与 ATen 变体、
  graph 新输入新结果、autotune 状态恢复、同条件组件 benchmark 与目标仓库准入、日志/版权
  和 PR 齐套性。适用【必须】未满足不能通过 `source_review`；未验证项不能记为不适用。
  组件 benchmark 不恢复整模型适配必须预设速度目标的要求。复用已有审查回执，不新增阶段。
  此项为有证据的设计判断，现有工具核验回执与证据绑定，不自动判定代码是否合理。
- 完成前记录 vLLM 未变化证据、各被改组件版本/基线、实际 diff、服务身份及全部验收回执。
