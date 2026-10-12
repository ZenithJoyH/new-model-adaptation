# 021：FlagGems small-head sparse MLA 原生无 padding 接入

## 元数据

- 状态：`resolved`
- 首次出现时间：2026-09-07
- 最后验证时间：2026-09-08
- 模型：`/mnt/cpfs/models/GLM-5.3-Flash-BF16`
- 平台与 Host 别名：T-Head PPU，`PPU-13`，TP16
- 容器名称与镜像：`glm5.3-flash` / `hy4-ppu07-snapshot:20260903`
- Plugin：`/mnt/nfs/users/jinghao/glm5.3-flash/01-repos/vllm-plugin-FL`，
  `support-hy4-preview@d56f7b285af2b3dd735847cb6d5a30f29beccfb8` 加未提交的 GLM5
  适配；本问题结束时 BF16 padding workaround 已从 worktree/index 移除。
- FlagGems：`sparse-mla-opt-w8a8-moe-fix@bca444b8569294e7d4e4deff7ddfec7f05682033`，
  editable package `5.4.0rc1.post1+gbca444b85`。
- vLLM：`/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`，工作树未修改。
- 执行模式与负载：单卡算子 eager/graph changed-input replay；TP16、65K、PIECEWISE
  graph 整模服务与单请求 sanity。

## 问题现象

- TP16 将全局 query heads 分片为每 rank `HQ=4`。原 FlagGems
  `flash_mla_sparse_fwd` 只接受 64/128 heads，首次真实请求报
  `AssertionError: Unsupported h_q`。
- 插件侧把 4 heads 显式补到 64、执行后再裁剪虽然恢复了功能，但产生额外 tensor、复制和
  无效 head 计算，只能归类为 mitigation。
- 原始和本轮证据均位于
  `/mnt/nfs/users/jinghao/glm5.3-flash/05-runs/021-flaggems-sparse-small-head/`；本轮开始前
  服务健康，容器 `running`、restart count 0。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| [020](020-hy4-latest-minimal-rebase-20260907.md) | 同一 TP16、BF16 sparse MLA、`HQ=4` 签名 | 020 当时安装的 FlagGems 尚无 small-head kernel | high | 复用负对照，撤销 plugin padding mitigation |
| Thead native no-padding backend | 同样能避免输入 tensor padding | 本轮保留既有 `default.flagos` dispatch，改用已支持 `HQ=4` 的 FlagGems | medium | 作为可选实现保留，不再是解决此问题的唯一方向 |

## 诊断与受控尝试

本轮每步只改变一个实质变量：先停止服务并用旧 FlagGems 复现，再只替换 FlagGems 验证
算子，最后删除插件 padding 并启动相同服务配置。

| 轮次 | 唯一变量 | 结果 | 结论 |
|---|---|---|---|
| 负对照 | FlagGems `master@dcd0cfeae8187dee691656c0616c1ed95899c2ae` | `HQ=4` eager 精确报 `Unsupported h_q` | 旧算子契约是直接根因 |
| 算子对照 | 切换并 editable 安装 `bca444b8`，插件暂不变 | eager、graph 和上游 3 项测试通过 | 新 FlagGems 原生接受 `HQ=4` |
| 插件收敛 | 删除 BF16 4→64 padding 和裁剪 | no-padding contract 1 项通过 | workaround 不再必要 |
| 整模验证 | 相同 TP16/65K/PIECEWISE 启动参数 | 120/120 权重、11/11 graph capture、真实请求通过 | 新算子已进入实际服务链路 |

## 根因

已验证根因是旧版 `flag_gems.flash_mla_sparse_fwd` 的公共入口和 Triton kernel 仅按 64/128
heads 实现，和 TP16 的本地 `HQ=4` 不兼容。指定分支不是简单删除断言：它增加 `BH=16`
配置，并对 query、sink、output、max-logits 和 LSE 的 head lane 加 mask；因此外部输入保持
`[SQ, 4, 576]`，无需创建 `[SQ, 64, 576]` tensor。Triton tile 内部仍使用固定 block，
无效 lane 由 mask 屏蔽，这不等同于插件侧 tensor padding。

## 解决方法或 Workaround

- 在已授权的 `01-repos/FlagGems` 干净 checkout 增加
  `https://github.com/ZenithJoyH/FlagGems.git` remote，非强制 fetch 指定分支，并核对远端
  HEAD 为 `bca444b8569294e7d4e4deff7ddfec7f05682033`。
- 切换到 tracking branch `sparse-mla-opt-w8a8-moe-fix`，使用
  `python3 -m pip install --no-build-isolation --no-deps -e .` 安装；源码和 pip editable
  location 均为批准工作根内的同一 checkout。
- 插件仍通过正常 `default.flagos` backend adapter 调用
  `flag_gems.flash_mla_sparse_fwd`；只撤销 BF16 adapter 的 4→64 padding、padded sink 和输出
  裁剪。`tests/dispatch/test_flaggems_mla_sparse_no_padding.py` 验证 kernel 收到原始 query 和
  sink 对象。
- FP8 decode 使用 `flash_mla_with_kvcache(..., indices=...)`，该 API 在目标分支仍限制
  64/128 heads；本轮没有删除 FP8 独立 padding，也不宣称该分支解决 FP8 路径。
- 一次性补丁保存在
  `/mnt/nfs/users/jinghao/glm5.3-flash/03-issues/021-flaggems-sparse-small-head/remove_bf16_sparse_mla_padding.patch`；
  它不属于 plugin、vLLM 或 FlagGems 产品树。

### 服务生命周期

为避免在 editable 源码切换期间运行旧进程，先核对原服务 APIServer PID `2151177`、
resource-lock PID `3060170` 和 host `docker exec` PID `3060172`。向 resource-lock 发送 TERM
后它退出但未转发信号，APIServer 仍健康；随后只向已核对命令行的容器内 PID `2151177`
发送 TERM，确认 APIServer/EngineCore 退出、8010 关闭且容器保持 `running`、restart 0。
安装和局部测试完成后使用既有 `start_glm53_graph_host.sh` 启动；新 APIServer/EngineCore
分别为 `2221549`/`2222040`。未停止、重启或删除容器，未影响其他服务。

## FlagGems 证据

- 旧 revision：`dcd0cfeae8187dee691656c0616c1ed95899c2ae`，`master`、工作树干净。
- 新 revision：`bca444b8569294e7d4e4deff7ddfec7f05682033`，
  `sparse-mla-opt-w8a8-moe-fix`、tracking `zenith/sparse-mla-opt-w8a8-moe-fix`、工作树干净。
- 最小复现目录：host/container 均为
  `/mnt/nfs/users/jinghao/glm5.3-flash/08-bugs/021-flaggems-sparse-small-head/`；没有复制到 `/bug`。
- 复现命令入口：`python3 test_sparse_mla_small_heads.py --mode eager|graph`，运行时 cache/tmp
  分别指向批准根的 `07-cache/021-flaggems-sparse-small-head/` 与
  `06-tmp/021-flaggems-sparse-small-head/`。
- 负对照日志：`before-eager.log`；新版本日志：`after-eager.log`、`after-graph.log`、
  `upstream-small-head-pytest.log`。

## 验证结果

- 负对照：旧版本在 `flashmla_sparse.py:1107` 报
  `AssertionError: Unsupported h_q`。
- eager `HQ=4`：输出 shape `(2, 4, 512)`；output/max-logits/LSE 最大绝对误差分别为
  `1.220703125e-4`、`6.053596735e-9`、`0`，通过 `atol=rtol=2e-2`。
- graph capture + changed-input replay：三者最大绝对误差分别为
  `1.220703125e-4`、`5.587935448e-9`、`4.768371582e-7`，通过相同容差。
- 分支自带 `tests/test_DSA/test_flashmla_sparse_small_heads.py`：`3 passed`，包含 `HQ=4/64`
  和 graph replay。
- 插件 no-padding contract：`1 passed`；BF16 adapter diff/status 中不再存在 padding
  workaround 或反向 test rename。
- 整模：598.52 GiB、120/120 shard 在 5 分 04 秒内加载；11/11 PIECEWISE graph capture
  在约 14 秒完成。真实请求 HTTP 200，`finish_reason=stop`、84 completion tokens，content
  为“北京是中国的首都。”。
- 终态：health 200、16/16 worker、容器 `running`/restart 0；服务日志中没有 BF16 padding、
  `Unsupported h_q`、illegal memory、OOM 或 EngineCore 退出。
- vLLM 仍为 `ee0da84ab9e04ac7610e28580af62c365e898389` 且无 tracked/staged diff。

## 限制与下一步

- 本轮是 adaptation 的算子与整模功能验证，不是新的 acceptance 轮；既有 GPQA 83.84% 失败
  和后续 accuracy/performance 状态不变。
- 尚未对 no-padding 前后做同条件吞吐/延迟性能对照，不能量化收益。
- `flash_mla_with_kvcache` 的 sparse FP8 分支仍只支持 64/128 heads；不能把本结论推广到
  FP8、其他 shape/dtype 或其他平台。
- Plugin 最终 diff 复核结论：本轮没有新增产品实现；只删除此前的 BF16 workaround，使
  `mla_sparse.py` 和 no-padding contract test 回到既有设计。其余 dirty/untracked 文件均为
  021 开始前继承的 GLM5 适配；未 commit、未 push。
- 本轮按要求更新了环境分析中的实际 FlagGems revision，因此旧 environment receipt 的
  evidence hash 失效；随后 adaptation `--check-only` 精确报“environment 证据为空或内容已
  变化”。环境阶段未被本轮选择，未静默刷新旧 deployment identity 或 `platform.yml`
  receipt；这不否定上述远端测试，但阻止把本轮记为新的正式阶段绑定。

## 经验沉淀

- 可复用判断：先区分 `flash_mla_sparse_fwd` 与
  `flash_mla_with_kvcache(..., indices=...)`，并按 exact revision、dtype、cache 格式和本地
  head 数验证，不能仅凭“sparse MLA 优化”名称推断所有入口已支持 small heads。
- 知识库处理状态：`local-only`
