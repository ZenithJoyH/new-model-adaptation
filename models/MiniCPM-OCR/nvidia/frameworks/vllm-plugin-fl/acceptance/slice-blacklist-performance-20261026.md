# slice 黑名单及持久化调优库：v1.1 整页 OCR 复测

2026-10-26，H100-149。使用原固定32页v1.1测试包完整复测，与[原FlagOS基线](portable-performance-v1-20261024.md)及[原生vLLM](native-vs-flagos-performance-20261026.md)比较。

**结果：交互吞吐中位数提高15.57%；批量不稳定、未证明提升；较高负载未见提升。** 原生在稳定的交互、较高负载场景仍分别为当前吞吐的2.15、3.14倍。此前固定单请求延迟降低20.22%，不能外推为整套应用吞吐收益。

## 实际测量环境

现场8012仍是原GPU3进程，尚未加载新黑名单/调优库，前缀缓存开启。本轮没有重启或修改它；在空闲GPU4/8013新建性能专用实例，加载当前已验证的两个环境文件：

- `VLLM_FL_FLAGOS_BLACKLIST_APPEND=slice`，保留平台原有黑名单。
- `FLAGGEMS_CACHE_DIR=/public/flagos/jinghao/MiniCPM-OCR/flagos/06-cache/ocr-slice-blacklist-20261026/persistent`。

配置位于批准根 `/public/flagos/jinghao/MiniCPM-OCR/flagos/01-environment/` 的 `slice-blacklist.env`、`ocr-tuning-cache.env`。实际 `/proc` 环境和启动配置均取证；算子记录不含FlagGems slice，仍含FlagGems attention。没有通过PYTHONPATH切换实现，没有启用profiler。

共同条件：GPU4 H100 80GB，UUID `GPU-37abecc9-c318-840a-1e8b-3e389dd55035`，单卡BF16，FULL_AND_PIECEWISE，TORCH_SDPA，上下文262144、max-num-seqs64、显存比例0.55。权重为 `merge_rl_mergedp1_7140_hf5_4x`，规范化文件身份 `7ffb82b59a2e67201e7994613946b8b278095ec67da79cc43f1347a2c4acc61e`。

独立性能命令沿用原基准的 `--no-enable-prefix-caching --mm-processor-cache-gb 0`；实际argv归一化服务别名后与两份历史基准相同。复用原Triton/Inductor编译缓存，调优库继续正常读写，没有清空或强制固定配置。人工 `start-model.sh` 未改。

软件及已安装源码与前轮诊断相同：vLLM0.24.0+empty、Torch2.11.0+cu129、Transformers5.12.1、FlagTree0.7.0，Plugin/FlagGems/FlagGems-vllm实际源码身份见[013](../adaptation/013-performance-profiling.md)。测量前后安装文件哈希相同。

## 完整协议及结果

页面与区域并发分别为交互1/4、批量4/16、较高负载8/32；每场景完整预热一次，再测两轮。三个场景前两轮波动都超过10%，因此各按固定协议补一轮，没有丢弃慢轮次或继续无限补测。

下表均为成功页/分钟中位数，当前为三轮，两个历史基线为两轮：

| 场景 | 原FlagOS | 当前配置 | 原生vLLM | 当前/原FlagOS变化 | 当前稳定性 |
|---|---:|---:|---:|---:|---|
| 交互 | 14.2765 | **16.4996** | 35.4303 | **+15.57%** | 稳定 |
| 日常批量 | 23.8689 | **23.6629** | 72.2446 | -0.86%，仅描述值 | **不稳定** |
| 较高负载 | 28.2022 | **27.5138** | 86.3773 | -2.44%，未见提升 | 稳定 |

批量最后两轮仍相差约22.03%，不能据中位数宣称稳定排名或确定的小幅退化。交互、较高负载最后两轮分别相差约0.86%、9.17%。原生/当前的描述性比值分别为2.1473、3.0531、3.1394倍，批量比值同样受当前不稳定限制。

| 场景 | 当前三轮页/分钟 | 当前三轮页面P90，秒 | 原FlagOS两轮P90，秒 |
|---|---|---|---|
| 交互 | 14.4744 / 16.4996 / 16.6412 | 8.7773 / 8.6785 / 8.7397 | 11.6290 / 11.7299 |
| 日常批量 | 23.6629 / 20.7984 / 25.3803 | 20.1275 / 24.9634 / 17.9191 | 20.0915 / 17.8649 |
| 较高负载 | 29.9276 / 25.2021 / 27.5138 | 27.8079 / 29.0154 / 33.5070 | 30.9986 / 31.4287 |

三场景每轮均100%完整成功且在项目初始30/60秒时限内。测量完成及达到时限目标，不等于通过稳定性检查或完成优化。

本轮共168个计时页次、**3483次计时区域请求**，另有56个预热页次、1161次预热请求：总计 **4644次请求**，失败、空输出、截断均为0。全部输入token数与原FlagOS同页同区域记录一致，响应ID逐项唯一；各场景每轮平均输出token相对原FlagOS的变化绝对值小于0.09%，没有缩短max_tokens、跳过区域或忽略EOS提速。

客户端含预热总耗时 **765.5744秒，约12分46秒**，其中计时轮次合计435.52秒；其余为预热和控制开销。启动/编译、离线评分另计。历史两轮测试的447.25/155.23秒与本轮轮数不同，不能直接用总时间比较加速比。

## 调优缓存覆盖的实测边界

本轮开始时采用前轮验证的持久化数据库，生命周期内仍增加了调优条目：数据库总行数 **3961→10475**，其中 `_attn_fwd` 的两张v2 benchmark缓存表合计 **1023→2310**。原始表名和逐表数量保存在 `tuning-before.json`、`tuning-after.json`。

这些是含启动、预热和计时阶段的整体统计，证明四个已知形状的缓存复用并不代表完整负载已覆盖。当前benchmark没有额外profiler，不能仅凭条目增长精确分摊各轮耗时或将全部波动归因于autotuning。本轮不修改公共调优策略，也不把更多条目写入缓存描述为根因已修复。

## 同一32页质量筛查

按固定规则，取当前interactive-r1的8页及batch-r1的24页，在同一个既有CPU评分环境、同一官方GT上评分，未挑选质量最好的轮次。

| 指标 | 当前配置 | 原FlagOS | 原生vLLM |
|---|---:|---:|---:|
| Overall ↑ | **97.6364804011** | 97.6365813638 | 97.4744570963 |
| Text Edit ↓ | 0.0195816284 | 0.0196177922 | 0.0195816284 |
| Formula CDM ↑ | 96.8968537415 | 96.8968537415 | 97.0129251701 |
| Table TEDS ↑ | 97.9707503067 | 97.9746695699 | 97.3686089638 |
| Table TEDS-S ↑ | 99.9541809851 | 99.9541809851 | 99.3481203790 |
| Reading order Edit ↓ | 0.1427165127 | 0.1427165127 | 0.1427165127 |

当前Overall比原FlagOS低0.00010096个百分点。66个公式、22个表格评分无超时、错误或异常；32页matching无超时回退。小集分数接近，不等于逐字相同、统计等价或1651页正式精度通过。

## 证据及保留状态

远端结果根（下记S）：

`/public/flagos/jinghao/MiniCPM-OCR/flagos/04-runs/ocr-slice-v1.1-h100-20261026/`

控制脚本、评分配置、Skill指纹和完成状态位于同根 `03-acceptance/ocr-slice-v1.1-20261026/`。所选操作是完整三场景应用suite，性能Skill指纹仍为 `3c46ddd2c4d73b11ca324b230d48429c3d4a40d0c82f56f5b27237d8e81bc9ff`；不冒充正式框架性能回执。

- `S/comparison-result.json`、`S/three-way-comparison.md`：校验后的三方结果、输出工作量及质量。
- `S/measurement/`：九个计时轮次、三个完整预热轮次的全部请求、页面耗时及Markdown。
- `S/service-evidence.json`、`S/deployment-configs.json`、`S/dispatch-evidence.json`、`S/cache-policy-evidence.json`：实际启动、配置、派发及每请求UUID图像缓存规则。
- `S/flagos-install-before.json`、`S/flagos-install-after.json`、`S/checkpoint-identity.json`：安装源码及权重身份。
- `S/quality-summary.json`、`S/quality-current/result/`：32页官方GT评分及原生摘要。
- `S/protected-before.json`、`S/protected-after.json`、`S/service-preservation.json`、`S/worker-cleanup.json`：8012和人工脚本保持、只停止本轮8013的证据。
- `S/evidence-index.json` SHA-256：**`983f02188297d7c75f85d3ba0dbc6d4133682659f8371e126a15353ea768a376`**。两份历史索引及所用文件重新验签，没有改写旧结果。

最终 `verified_complete` 表示本次数据与证据完整，`all_current_stable=false` 如实保留。8012原PID/start ticks/argv及脚本SHA保持，收尾models/health可用；GPU4显存回到0MiB，临时8013已停止，原容器继续运行。启动脚本SHA仍为 `ab1239fa7729e8d532916b8c6feb4574cc0dccc78f3aa0cc8dceccbaf2a65d32`。

未修改安装组件、测试包或启动脚本，未提交推送，不更新framework.yml或宣称optimized。离线语法检查通过；仓库原有其他模型告警与无关失效链接另行保留。
