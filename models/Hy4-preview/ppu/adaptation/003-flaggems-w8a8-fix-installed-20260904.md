# FlagGems 根因修复安装与插件分块保护移除

后续状态：2026-09-04 23:52已完成修复源码重载，eager/graph整模型及graph八并发sanity通过，
64 并发全量 GPQA 后续因 FlagGems 调优 SQLite 锁失败；详见[精度验收汇总](../acceptance/accuracy-results.md)。
以下为安装完成时23:10的历史快照，其中“尚未重载”不再代表当前服务。

验证日期：2026-09-04，最终源码/服务核实时间 23:10:48 +08:00。
主机 `PPU-07`，容器 `hy4`。本轮为依赖/插件部署及聚焦验证，不是整模型验收。

## 当前结果与边界

- FlagGems 已安装为 `5.3.5+g842b19d8a`，editable 源码 `/workspace/FlagGems`。
- 分支 `codex/fix-w8a8-moe-config`，跟踪 `zenith-w8a8/codex/fix-w8a8-moe-config`，
  remote `https://github.com/ZenithJoyH/FlagGems.git`。
- 生产修复提交 `051f303a6178d9c898cad1c8b20ada6202482af2`：给 `_get_config_dtype_str`
  增加 `use_int8_w8a8` 分类，并从 `fused_experts_impl` 传入。INT8 不再按 BF16
  进入不应用 INT8 scale 的 plain-half 优化。保留非量化 BF16/FP16 优化。
- 最终提交 `842b19d8ad5bd8bd66cce1e52b26ade54b0b851f` 仅修正测试样本，生产代码不变。
- 插件 `/workspace/vllm-plugin-FL-hy4-preview/vllm_fl/quantization/w8a8/moe_experts.py`
  已移除 `_flaggems_fused_experts_impl` 的 2048-token 分块 helper，恢复既有
  `FlagGemsW8A8Experts.apply()` 中一次 `flag_gems.fused_experts_impl()` 调用。
  W8A8 标志、scale、路由、输入合约检查、NVIDIA 路径及已有 graph custom-op 边界不变。
- 容器未停启，现有 API PID `3377378`（2026-09-04 22:03:47 启动）未重启；
  `/health=200`。该进程仍是之前加载分块保护的服务，**不能把磁盘部署当作运行中
  服务已加载新实现**。需要随后受控重启并验证整模型，未重跑全量 GPQA 或性能测试。

## 基线、环境与保护

模型：`/mnt/cpfs/models/Hy4-preview-W8A8-linear-moe/`，Hy4-preview W8A8，TP16。
权重 config/index 哈希及模型结构沿用 `../../architecture-and-inference.md` 与本轮
`005-gpqa-corruption-triage-20260904.md` 的已核实身份；权重没有修改。
设备 PPU-ZW810E capability 80，16 × 98304 MiB；PPU-SMI 1.28，driver 2.1.1-rbd225，
HGGC 13.0，torch 2.10.0，vLLM 0.24.0+empty，pytest 7.2.0。
镜像：`harbor.baai.ac.cn/flagos-inner-models-release/ppu-pp001-gems0.0.0-tree0.6.1-cxnone-plugin0.3.0-vllm0.24.0-cp312-pt210-hggc130-x64-1.3.2-d7f5a2:lingjunbase`。

FlagGems 安装前 master/origin/master 为 clean `8416e6dab471451cc437aac3896fdc382dce382e`；
依次快进到 051f303、842b19d，没有 reset 或丢弃改动。安装命令为
`python3 -m pip install --no-deps --no-build-isolation -e .`，没有升级其他依赖。
安装前 metadata 的 `5.3.5+g38653f94c` 与 editable 源码 HEAD 不一致，安装后已更新。

插件 HEAD 仍为 `11848598449f6d650df64170db4187c387361ce5`，分支 `support-hy4-preview`，
已有 dirty 工作树完整保留，本轮远端只替换上述一个 Python 文件。未提交/推送插件。
`/workspace/vllm` 在部署前后均为 clean `ee0da84ab9e04ac7610e28580af62c365e898389`。

启动脚本 `/mnt/nfs/users/jinghao/hy4-preview/start_hyv4-preview.sh` 未改，
SHA256 `197fd97491f6702f2a594bbf5e4d9b2464aacddde80683571c8ae731e961f7a4`。
端口 8010、100000 上下文、8192 调度 token 上限、TP16、0.9 显存预算、
`FULL_DECODE_ONLY` 均未变；未清理缓存或停启任何容器。

## 验证结果

| 检查 | 实际结果 |
|---|---|
| 真实模块导入/torch 配置测试 | 22 passed，不再仅依赖本机 AST 隔离检查 |
| 原始 `/bug/hy4-w8a8-large-m-raHNmgWY/repro.py` | E256/K6144/I128/top8/M8192，BF16，eager/graph 最大误差均 0.0009765625；没有分块或禁用优化常量 |
| 最终 FlagGems 数值 UT | 20 passed；FP16/BF16，M32/4095/4096/4097/8192，eager/graph，改变输入后 replay；atol=0.003、rtol=0.04 未放宽 |
| 实际插件候选 `apply()` + 服务 ATen 黑名单 | 同样 20 passed；30 次 Python 调用覆盖 warmup/capture，每次完整批次只调一次 FlagGems；包含 M8192 |
| 负对照 | 仅在独立进程恢复原 dtype 分类，BF16/M4096 失败；524180/524288 元素超差，最大误差 884736 |
| 部署校验 | 目标文件 hash 与测试候选完全一致；vLLM clean、API PID/启动时间不变 |

插件文件旧 SHA256：`534c1b67d82415394891fa95af058a7fb3ff3f1eb40fe23bd6c3d7c7ec65f3f0`。
新 SHA256：`568701d549ab592df38b14782d24d886119fc452155b52f6bdedd20582ddc2b1`。
备份：`/tmp/hy4-unchunked-3ivyC7Jn/moe_experts.before.py`。
最终 FlagGems `fused_moe.py` SHA256：
`ebf2ec697ee40f62472622604e9af2146b0109346cea32faca022cd5973edfba`。

## 测试中遇到的问题及处理

初版随机小形状 UT 在 FP16/M4095 有 36/524160 元素超出原容差，最大差
0.0458984375。逐阶段发现 Q1 已有 3 个 INT8 值相差 1，scale 差约 1.86e-9；
以设备实际量化值为条件，GEMM2 和最终输出与 CPU 参考逐位一致。仅固定输入 scale
的尝试仍因后续激活/量化舍入敏感而失败（11 个元素、最大差 0.234375），未据此移除保护。

最终定向样本令 gate=32、up=code/4、激活输出为可精确表示的 8*code、第二轮
scale=8，保留非单位逐通道 weight scale；原容差不变。全部 20 项及旧分类负对照
通过验证后才安装插件。原随机测试、失败尝试、诊断及定向样本保留在
`/bug/hy4-w8a8-rounding-m1IFDEzP/` 和 `/bug/hy4-w8a8-rounding-aa3bxdvb/`。
这不声称所有随机 FP16 跨设备量化舍入差异都消失，亦不替代整模型精度。

## 可复现入口

- 基线：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-flaggems-fix-install.yml`
- 安装：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/install-ppu07-flaggems-w8a8-fix.yml`（安装前使用 `--check --diff`）
- 依赖验证：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/verify-ppu07-flaggems-w8a8-fix.yml`
- 原始随机测试诊断：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/diagnose-ppu07-fixed-w8a8-reference.yml`
- 定向样本探索记录：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/verify-ppu07-w8a8-exact-input-scale.yml`
- 插件候选/备份/部署：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-w8a8-unchunked-adapter.yml`（先 `--check --diff`）
- 最终身份及负对照：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/verify-ppu07-unchunked-final.yml`
- 测试证据归档：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/package-ppu07-w8a8-rounding-evidence.yml`
- 当前插件候选快照：`working/ppu07-plugin-w8a8-moe_experts-unchunked.py`

以上均使用 `./scripts/playbook <path> --limit PPU-07`，不包含服务重启操作。
原 `working/ppu07-plugin-w8a8-moe_experts.py` 是带分块保护的历史快照，不是当前部署版本。

后续：受控重启该模型服务并完成最小推理/graph 回归，再按验收顺序运行 sanity、
全量 GPQA 和性能测试。未将平台标记为 optimized 或整体验收完成。
