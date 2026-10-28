# 011：以 FlagGems split-KV 修复替代视觉 FP32 缓解

## 范围与状态

- 2026-10-08，用户要求尝试 [FlagGems PR #6873](https://github.com/flagos-ai/FlagGems/pull/6873)。范围为适配诊断与定向回归，不执行正式精度、性能或镜像打包。
- Host `PPU-13`，容器 `minicpmV4.7-35B`，ID `145f15078dc1c953d9e136ce595e3185003a6606c28993e30061a2047d3f3653`；镜像 `sha256:52536a088a055b2c24cdfca21d0ea9e8d68c1f5f82fee7a40f7a5f7ec8f72e4a`。
- 宿主/容器根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`；现场核实 `/mnt` RW bind，容器根 realpath 不变，device:inode `41:14016406509`。
- Plugin editable 安装 `/workspace/vllm-plugin-FL`，HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`。继承差异为模型注册、35B adapter、FP32 helper 和其测试，保留无关修改。
- FlagGems 5.3.5 实际安装 `/usr/local/lib/python3.12/site-packages/flag_gems`；直接修改安装文件，不升级整个包、不使用导入路径覆盖。现有 `/workspace/FlagGems` HEAD `1a38df24f72ca5a4a6a24650b5d66356709750ba`，不是当前导入来源，本轮保持只读。
- vLLM 0.24.0+empty 从 site-packages 导入，源码 HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`、工作树干净，全程只读。
- 当前状态：`verified`，算子修复、无 FP32 的 35B 完整 eager 视觉链及 TP2 图服务定向回归通过；已移除专用 helper 和测试。正式精度与性能仍未验收。

## 已有证据与根因边界

历史 [002](002-visual-garbage.md) 首错在窗口合并后的视觉第 7 层：Q/K/V 有限，注意力输出异常。模型视觉结构为 hidden size 1152、16 heads，即 head dimension 72，合并插入层为 6。

1B 的 [同类问题记录](../../../../../MiniCPM-V-4.7-1B/ppu/frameworks/vllm-plugin-fl/adaptation/002-visual-output-corruption.md) 已确认 ATen flash → FlagGems → split-KV combine 的输出寻址缺陷，并通过无 FP32 完整链验证。结构及故障签名相近，但容器、模型和并行拓扑不同，本轮独立复测。

PR 修正 head stride，并将 flatten 的 batch/head/query 行号解码后按实际输出 stride 写回。原实现可能重叠写、漏写和越界写；这是内存地址契约错误，不是 BF16 本身精度不足。本轮完整 35B 已捕获与历史首错形状匹配的实际 split-KV 调用，修复后原图片及完整请求通过，支持撤除原缓解。没有重建全部历史故障实例，也不将它外推为 GPQA/GDN 或 ERQA 分差的完整根因。

## 受控操作与算子回归

冻结 PR base `0958d2da98055f1e2198a56201e3eea6f7591981` / HEAD `c13d2aba866e46b235a7bcae88a68e7ec2090e04`，只应用其公共 `ops/flash_api.py`、`ops/flash_kernel.py` 两处产品改动。PR 的 Enflame caller 未包含在当前安装包，未创建或替换其他平台组件。其他已安装 vendor 的 combine 为独立实现，不改其接口。

全部原生证据位于远端 `04-runs/pr6873-20261008/`；PR 快照及原版测试位于 `07-bugs/pr6873-20261008/`，备份位于 `05-tmp/pr6873-20261008/before/`，过程代码位于 `02-issues/pr6873-*.py`。运行测试始终导入实际安装包；独立 pytest 目录用于隔离旧 checkout 的无关 conftest 依赖，没有 mock 目标计算。

| 轮次 | 改变 | 结果 |
|---|---|---|
| 修复前 | 原安装包，PPU3，PR 公共入口测试，首次失败即停 | 7943/9792 元素不匹配（81.1%），最大误差 123.3125；数值失败证据保留 |
| 修复后 | 仅应用 PR 公共算子修复，其他测试输入不变 | 34 passed，0 failed/error/skipped；含 FP16/BF16、3 种布局、边界保护、公共入口 alias/LSE，以及 4 项各两次变输入 graph replay |
| 完整模型 | 仅解除 adapter 的 T-Head FP32 绑定，回到既有 MMEncoderAttention 分发 | PPU3 上 BF16/TP1 eager 9/9 正确，189 次实际视觉 attention 全有限 |

安装文件 SHA-256：

| 文件 | 修改前 | 修改后 |
|---|---|---|
| `ops/flash_api.py` | `9d6f1e1ec802d132b074a618c173a9ea424f4d5793fd0cbcead687796155a70f` | `ffbe6e6aa05940c5586d3fee08644c4eec86044cf220db856d913fcaa6630b15` |
| `ops/flash_kernel.py` | `eef0202e6c0ed08bef8098adede1a603c63354c54b54a19414e210b675157265` | `19940f11b4a3de9b77399166fd595498ae6d22da8aa6ef2ff4eb1ddf62f7a3aa` |

初始备份清单发现 wheel 未包含 Enflame 路径而中止，未修改产品；随后按实际安装范围完成清单。一次 Docker inspect 的 Go template 被 Ansible 解释而失败，改用 JSON 读取成功；这些过程失败不算模型失败，也不隐去数值负对照。

### 完整 eager 视觉链

使用正常 Plugin 注册加载完整 35B 权重，PPU3、TP1、BF16、50,000 诊断上下文、4 个序列、显存比例 0.88、前缀缓存开启。该诊断上下文不改变 8010 服务配置。观察 hook 只检查数值与 dtype，Python profile 只记录调用，不替换计算或分发。

原 64×48 红/蓝图、224 红/蓝/绿、448 红/蓝、重复红图和双图共 9/9 正确，均正常停止；189 次实际 attention 及对应视觉层输出、logits 无非有限值。重复红图与双图复用了 encoder cache，其 attention 计数为 0，不计入新视觉计算。全部 attention 为上游 `MMEncoderAttention`，输入 Q/K/V 为 BF16，无 FP32 绑定。真实进入已安装 FlagGems flash → mha_fwd，记录到 140 次 split-KV 调用；原 64×48 输入命中 `Q=252、H=16、D=96、n_splits=2`，与历史首错形状吻合。

证据为 `offline-result.json`、`offline.log`，执行脚本 `02-issues/pr6873-offline.py`。首次预热包含 GDN/MoE 编译，缓存持续更新；不把冷启动时间当作性能评测。进程退出时有未显式 destroy NCCL 的警告，后续需确认设备资源释放；没有据此隐藏推理错误。

离线通过后，核对旧 API PID `1847751` / start tick `387827190`、PPU0/1、启动命令与两次零在途指标，仅 TERM 本任务服务并确认其进程树退出。首次仅移除 `--no-enable-prefix-caching` 后，新 API `1920609` 已完成两类 7/7 捕图且健康，但生效 `enable_prefix_caching=False`，守卫拒绝继续 HTTP 测试。该模型的缺省行为与 [005](005-prefix-cache-effective-default.md) 相同；失败证据 `restart.log`、`intermediate-startup.log` 原样保留。

随后只将根级脚本改为显式 `--enable-prefix-caching`，重新核对中间实例 PID/start tick 和零在途指标，再 TERM 本任务进程树、重启。最终脚本相对用户原脚本仅将该一个参数由禁用改为启用，其他参数完全一致；旧脚本完整备份可回退。控制脚本为 `pr6873-restart.py` / `pr6873-restart-v2.py`，证据为同名日志。容器始终保持同一 ID 和启动时间。

### 最终 TP2 图服务及清理

15:44:54（Asia/Shanghai）完成最终核验：API PID `1944850` / start tick `416099830`，命令 SHA-256 `bf4b42bfcd836912aeaba602f804b3d7ec689203505c92459430efb93ef983aa`；BF16、TP2、8010、默认 262144 上下文、前缀缓存开启。`FULL_AND_PIECEWISE` 下混合 PIECEWISE 和 decode FULL 各 **7/7**，尺寸 `[1,2,4,8,16,32,64]`。当前 `compile_mm_encoder=False`、`cudagraph_mm_encoder=False`，不声称视觉 encoder 本身已捕图。

HTTP 定向回归 **25/25 正确且 HTTP 200、finish_reason=stop**：5 项顺序文本/单图，以及文本、224/448 红蓝绿黄单图和双图共 10 项的两轮 10 并发。双图改用此前未请求的 225×225 红/蓝图，避免复用已测试单图的 encoder cache。前后 API 身份一致，最终 `/health=200`。这是合成颜色的小范围回归，非 GPQA/ERQA 正式评测。

通过后校验原文件及备份哈希，删除 `vllm_fl/dispatch/backends/vendor/thead/vision_attention.py` 与 `tests/unit_tests/dispatch/test_thead_vision_attention.py`；从 adapter 移除绑定和已无用的 `current_platform` import。无残留 Python 引用；模型 adapter 最终 SHA-256 `db2bc92342d81f7877759e6565d5bf3a9339fa652e54526c738bb817acab206b`。Plugin 仅剩继承的模型注册与 adapter 差异。vLLM 与非导入来源的 FlagGems checkout 保持 clean。

最终根级 `start-model.sh` 的 Host/容器路径相同，0755、`bash -n` 通过，SHA-256 `4c48934d95b428f4952ba4550657e33ce1e39afcbca9b5dfb87aa63ba33f41ba`。该脚本是本轮已启动验证的用户配置，不据此签发完整正式验收。PPU3 诊断进程已释放；PPU2 原其他服务 EngineCore 宿主 PID `3666437` 保持。

最终原生核验与哈希清单 `final-verification.json`，实际增量 `product-delta.patch`。主要证据 SHA-256：

| 证据 | SHA-256 |
|---|---|
| `after-pytest.xml` | `30fb3ec71763e1bccc4ef276828faa11ba831a702a87400549466145237b0864` |
| `offline-result.json` | `83f7fb201f238300b7cccb7b3962cf5ff640d1c88be9862d1606d72c1b874b8f` |
| `service-smoke.json` | `db661aefe61f5d81c6c567450d1b97371d72e2b86b916ddc3591bf67c02788a6` |
| `new-startup.log` | `1d281d4d94f5d4aa767c5ece87a41b32306ae47303aa366005aae3bd65995edb` |
| `product-delta.patch` | `91f910317f31d8c291ba44b75f4c8b43a7721637bdc6f1fa39ab7fd9d49ec279` |

## 设计审查与退出条件

公共内核负责合法输出布局，优先修复 FlagGems 既有 combine，而非维持模型专属 FP32 attention。公共 API、split 选择、归约和 mask 语义不变；仅合并内核内部参数与其 caller 同步。插件撤除点位于模型 adapter，不新增 dispatch 或模型名例外。其他平台原先不进入 T-Head 绑定分支，撤除不改变其策略。

实际整模 eager 和 TP2 图服务均通过，已退出原 FP32 缓解，保留本次修改。若后续发现回归，按文件哈希核对后恢复本任务备份并重启本任务服务。现有服务在离线验证期间保持运行。正式精度、性能、其他平台硬件与镜像打包均未测；不更新 `framework.yml` 的历史验收绑定或阶段状态。当前实际 diff 已复核，属于上游公共算子修复与插件旧 workaround 的撤除；没有新 Plugin PR、提交或推送。

本地 `git diff --check` 通过。workspace audit 仍有原有 12 项 profile revision 错误（含本模型）及其他历史材料警告，本轮没有用新哈希伪装历史验收有效。

经验处理状态：`local-only`，完整验证完成后再补充结论。
