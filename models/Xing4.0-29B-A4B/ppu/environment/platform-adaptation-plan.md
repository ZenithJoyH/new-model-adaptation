# Xing4.0-29B-A4B PPU 适配计划与差距清单

## 输入与基线

- 架构分析：`../../architecture-and-inference.md`。
- 环境分析：`environment-analysis.md`。
- 用户参考：vLLM PR [#57135](https://github.com/vllm-project/vllm/pull/57135)，
  head `25aa52a29131753c10e56528d3fa0c4464cead63`；旧容器实现参考 PR #54051，
  但本轮不为旧权重字段做兼容。
- Plugin：`/workspace/vllm-plugin-FL`，HEAD
  `0ef3d87a728f33ce12ea623eda84a018ad81ca6d`，editable install，detached 且有 inherited diff。
- vLLM：`/workspace/vllm`，HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`，
  clean、只读。
- FlagGems：`/workspace/FlagGems`，同步前 HEAD
  `3f2989283fb6212fc5e18dba6a52826c0bc02285`，clean `master...origin/master`。
- 已阅读 Plugin dispatch README、模型/config/注册/parser 实现、测试入口、
  FlagGems-vllm `AGENTS.md`、FlagGems 贡献指南与仓库 `docs/plugin-contribution-policy.md`。

## 修改边界

只修改当前容器 verified editable Plugin 源码及其可维护测试；vLLM、FlagGems-vllm、权重和
外部依赖只读。FlagGems 仅允许 clean tracked branch 上的 fetch + fast-forward-only pull。
不停止、重启或删除容器。过程产物写入批准根 `/mnt/nfs/users/jinghao/xingchen4` 的编号目录。
现有 Plugin dirty diff 不属于本任务，不重置、不覆盖，特别是不修改
`vllm_fl/dispatch/config/thead.yaml`。

## 差距清单

| ID | 组件/阶段 | 当前路径 | 算子来源 | eager/graph 影响 | 修改计划 | 最小验证 | 状态 |
|---|---|---|---|---|---|---|---|
| X4-01 | config/registry | 只有 `xingchen4` | Plugin 注册接口 | import/worker 均受影响 | 增加 `Xing4_0Config` 与 `Xing4_0ForCausalLM` 正式注册 | fresh-process config 与新旧 model registry | resolved |
| X4-02 | 权重协议 | XingChen adapter 同时考虑历史别名 | Plugin model loader | 加载阶段；graph 间接受影响 | 新入口仅接收 `hc_fn/hc_base/hc_scale`，跳过 MTP 层，拒绝旧键 | 4 个 config 正反例 + 41-shard 真实加载 | resolved |
| X4-03 | mHC | `CachedOp("mhc_pre/post")` | Plugin/FlagGems-vllm | eager 和 capture/replay 热路径 | 复用 dispatch，按 checkpoint clamp/epsilon/20 iterations，不引入模型级 `USE_FLAGOS` | 6 个 focused 数值 + 真实 graph capture/replay | resolved for selected graph path |
| X4-04 | MLA/MoE | DeepSeek-V2 组装与 Plugin backend | Plugin/FlagGems-vllm 现有实现 | prefill/decode/graph | 复用现有路径，不新增厂商特例 | TP4 CUSTOM MLA、MoE、最小真实生成 | resolved for selected graph path |
| X4-05 | reasoning/tool parser | 仅旧 parser key | Plugin parser 扩展点 | 服务输出协议 | 注册独立 `xing4_0` reasoning/tool parser；不改变旧 key | reasoning 实际响应；tool parser 3 tests + fresh registration | resolved；tool API E2E deferred |

## 设计选择与共享影响

| 变更 | 所属层级 | 复用接口 | 未选方案 | 公共影响 | 守卫未命中行为 |
|---|---|---|---|---|---|
| 新 model/config identity | model/config registry | Plugin 的 `register_model` 和 config converter | 修改 vLLM registry；按权重路径分支 | 新增精确 key，不改默认模型 | 其他 architecture/model_type 维持现状 |
| 新权重严格 loader | Xing4_0 model adapter | 现有 DeepSeek loader 与 mHC dispatch | 在旧 adapter 加宽泛别名/fallback | 只影响新 architecture | 缺键或旧键显式失败 |
| parser alias/实现 | reasoning/tool parser registry | 当前 Plugin parser 注册路径 | 进程外后处理 | 仅新增 `xing4_0` key | 旧 parser 不变 |

不增加 vendor SDK import，不改变 dispatch policy、缓存或 backend 优先级。新路径应支持重复注册
并保持 fresh process/spawn 可用。代表性回归覆盖新路径、旧 XingChen 注册和一个未命中模型。
其他平台无硬件验证，只做无设备 import/注册隔离，不宣称支持。

## FlagGems 同步与检索

- 同步前：origin `https://github.com/flagos-ai/FlagGems.git`，branch `master`，upstream
  `origin/master`，HEAD `3f2989283fb6212fc5e18dba6a52826c0bc02285`，clean。
- 计划命令：`git fetch origin master` 后 `git pull --ff-only origin master`。
- 同步后：`1c8dce74d9843a599a303c2c16b8cbe762f5429d`，clean
  `master...origin/master`。运行时 `flag_gems` import 指向
  `/workspace/FlagGems/src/flag_gems/__init__.py`；Plugin 专用 mHC/MLA 来自只读
  `/workspace/FlagGems-vllm` revision `bbc94043fd35f357e3e41350adce62246ec6d569`。

## 运行配置与验证顺序

- Host/容器工作根均为 `/mnt/nfs/users/jinghao/xingchen4`；临时诊断仅放
  `02-issues/` 或 `05-tmp/`，日志放 `04-runs/`，缓存放 `06-cache/`。
- 初始最大上下文按规则设为 50000；不使用性能专用 `--no-enable-prefix-caching`。
- 顺序：导入/注册 → config 与 loader → mHC eager → mHC graph replay → 最小模型初始化/
  权重加载 → 最小生成或服务。窄测试失败时不扩大测试范围。
- 实际 graph smoke 使用 `--trust-remote-code` 与 `VLLM_FL_USE_FLAGGEMS_ATTN=1`；后者来自用户
  提供的旧服务命令，是当前 Plugin MLA backend 的必要开关。运行目录为
  `04-runs/graph-smoke-20260916-03/`，服务端口 8040。
