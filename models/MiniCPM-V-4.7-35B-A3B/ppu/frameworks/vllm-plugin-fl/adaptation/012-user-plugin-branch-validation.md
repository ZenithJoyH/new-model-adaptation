# 012：切换用户的 support-minicpmV4.7 分支并验证

## 范围与结论

2026-10-08，用户明确要求将容器中的 Plugin 替换为
[flagos-day0/vllm-plugin-FL 的 support-minicpmV4.7 分支](https://github.com/flagos-day0/vllm-plugin-FL/tree/aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68)，并验证。
本轮属于适配阶段的定向回归，没有执行正式精度、性能或镜像打包。

- 唯一 Host `PPU-13`，容器 `minicpmV4.7-35B`，ID
  `145f15078dc1c953d9e136ce595e3185003a6606c28993e30061a2047d3f3653`。
- 宿主/容器批准根均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`；再次核实
  `/mnt` RW bind、realpath 不变、device:inode `41:14016406509`。
- 实际 editable 安装 `/workspace/vllm-plugin-FL` 已切换至固定提交
  `aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68`，采用 detached HEAD 固定版本，
  工作树干净。没有叠加本地产品补丁，也没有使用导入路径覆盖。
- 分支单测 14/14、完整 BF16 eager 9/9、TP2 图服务 HTTP 回归 33/33 通过。
  当前 8010 服务保留运行，最终核验时间为 **2026-10-08 16:10:04 +08:00**。

结论仅覆盖当前 35B、PPU、默认视觉 `weights` 并行模式和保留的启动设置。
分支可以替换此前本地模型 adapter；底层 FlagGems 修复仍是独立前置条件。

## 基线、保留项与切换过程

原 Plugin HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`、main 分支，
仅有 `vllm_fl/__init__.py` 修改和未跟踪的 `vllm_fl/models/minicpmv4_7.py`。
目标提交恰好基于该基线，只增加模型注册、4.7 adapter 和两份测试，共四个文件；
其余 backend、Qwen3.5 骨干和原生扩展源码均未变化。

先校验原文件 SHA 并备份至批准根的
`05-tmp/plugin-support-minicpmv47-20261008/before/`，再对这两个文件执行限定路径的
`git stash push --include-untracked`。保留的 stash 为
`b419700bdaa61fce541536ae911c61abf4152b12`，没有丢弃原改动。

容器匿名 GitHub fetch 因需要认证而失败，尚未切换代码或停止原服务；失败日志保留。
随后使用本机已有 GitHub 授权获取固定提交，通过 Ansible 传输并验证 5,951 字节的
Git 增量 bundle，在同一安装目录导入、核对目标提交后切换。bundle SHA-256 为
`2c16d30db3da37d37ca22320e5db70d78980c6c1087fedfdb04cbbec49d9eb83`。
没有向容器传入凭据，也没有在远端工作根建立第二份源码仓库。

本轮仅涉及 Python 源码与测试，沿用实际 editable 安装及既有原生扩展；未重装包或升级依赖。
安装包版本元数据仍为 `0.3.0rc2.post1+g3a27a6fb2`，该字符串不能代表切换后的源码版本；
实际版本以已核实的导入路径、Git HEAD、tree 和文件哈希为准。

| 当前产品文件 | SHA-256 |
|---|---|
| `vllm_fl/__init__.py` | `4082f3a94ff9eb5c928a7b014de2d9d2abc1f8f670b22f01dd199437408e0080` |
| `vllm_fl/models/minicpmv4_7.py` | `9a1ad18e4c23d1ea2c63dc9884618c9260b0b4f7aca094f97816bb920ceaf4a7` |

[011](011-flaggems-splitkv-vision-fix.md) 的 FlagGems 5.3.5 公共 split-KV 修复保持不变：
实际安装 `ops/flash_api.py` SHA 为
`ffbe6e6aa05940c5586d3fee08644c4eec86044cf220db856d913fcaa6630b15`，
`ops/flash_kernel.py` SHA 为
`19940f11b4a3de9b77399166fd595498ae6d22da8aa6ef2ff4eb1ddf62f7a3aa`。
T-Head 专用 `vision_attention.py` 继续不存在，adapter 无 FP32 绑定。
vLLM 0.24.0+empty 的导入路径仍是 site-packages，源码 HEAD
`ee0da84ab9e04ac7610e28580af62c365e898389`，前后工作树均干净，保持只读；
非导入来源的 `/workspace/FlagGems` checkout 也保持干净。

## 验证与服务生命周期

| 验证 | 实际条件 | 结果 |
|---|---|---|
| 分支自带单测 | 安装目录内直接 pytest 两份新测试；正常 conftest，无测试替换 | 14 passed，0 failure/error/skipped |
| 完整 eager | PPU4，BF16/TP1，50,000 诊断上下文，前缀缓存开启 | 9/9 正确、正常停止，189 次真实视觉 attention 全有限 |
| 底层路径观察 | 同一 eager 模型，正常 Plugin dispatch，无 FP32 attention | 140 次真实 split-KV 调用，含 `H=16,D=96,Q=252/256,n_splits=2` |
| 图服务启动 | PPU0/1，BF16/TP2，原根级启动脚本 | PIECEWISE 与 FULL decode 各 7/7，`/health=200` |
| HTTP 定向回归 | 5 项顺序请求，随后每轮 14 项、线程并发设为 10，共两轮 | 33/33 正确，全部 HTTP 200、finish_reason=stop，无请求错误或超时 |

eager 覆盖原 64×48 红/蓝图、224/448 单图、重复输入和双图；观察 hook 只检查数值和
记录实际调用，不替换计算。重复图和已缓存双图的 attention 计数为 0，没有计入新视觉计算。
进程退出有未显式 destroy NCCL 的警告；最终 PPU4 显存已释放至 1 MiB，不能只凭退出码判断释放。

HTTP 覆盖文本、224/448 红蓝绿黄图、双图、1280×720 宽图、720×1280 长图、
1200×600 左红右蓝分色图及反向双图。该集合是合成输入定向回归，不是 ERQA 数据集。
首轮新增大图/混合请求耗时 134.19–153.13 秒，第二轮相同四项为 0.42–0.43 秒；
期间出现新的 Triton 缓存产物和 shared-memory 等待提示，但请求持续完成，未超时。
第二轮可复用 encoder cache，不把这些耗时当作独立视觉计算性能，也未建立性能因果或稳定吞吐结论。

只有 eager 通过后才重启原服务：核对旧 API PID `1944850` / start tick `416099830`、
模型路径、8010、PPU0/1、环境及两次零在途指标，TERM 本任务服务并确认其进程树退出。
未停止容器，未操作 PPU2/3 上的其他负载。
新 API PID `1955096` / start tick `416239761`；HTTP 测试前后身份一致，最终 running/waiting 均为 0。
容器始终保持同一 ID 和 `2026-09-28T07:25:17.93918051Z` 启动时间。

根级 `start-model.sh` 未修改：Host 与容器路径均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`，0755，`bash -n` 通过，SHA-256
`4c48934d95b428f4952ba4550657e33ce1e39afcbca9b5dfb87aa63ba33f41ba`。
新旧 API 命令 SHA 相同，为
`bf4b42bfcd836912aeaba602f804b3d7ec689203505c92459430efb93ef983aa`。
继续保留现有算子黑名单、`mm-processor-cache-gb 0`、显式前缀缓存开启和
`FULL_AND_PIECEWISE`，图尺寸 `[1,2,4,8,16,32,64]`，默认上下文 262144。
视觉 encoder 本身仍未编译或捕图；本轮没有验证接近最大上下文的请求。

## 原生产物与复核入口

全部运行证据位于批准根的 `04-runs/plugin-support-minicpmv47-20261008/`：

- `baseline.json`、`baseline-plugin.patch`、`fetch.log`、`switch.log`、`stash.json`、`switch-result.json`；
- `unit-tests.log` / `unit-tests.xml`、`offline.log` / `offline-result.json`；
- `old-service.json`、`new-service.json`、`restart.log` / `restart-result.json`；
- `new-startup.log`、`service-smoke.log` / `service-smoke.json`、`final-service.log`；
- `final-verification.json`（包含源码、安装身份、结果及证据哈希）、`final-ppu-smi.txt`、`verified-start-model.sh`。

最终 `final-verification.json` SHA-256 为
`54de5213726527064176537635ea247c607a9ad27d49b2058c160dc981c84452`。

过程脚本在同一批准根的 `02-issues/`：`plugin-support-minicpmv47-offline.py`、
`plugin-support-minicpmv47-restart.py`、`plugin-support-minicpmv47-service-smoke.py`。
它们记录本轮固定身份和生命周期步骤，不应在未重新检查当前进程/已有 run 时直接重放重启。
单测原生命令是在安装目录运行 `python -m pytest` 两份新测试，XML 输出至上述 run；
eager 和 HTTP 命令分别执行上述已冻结的诊断脚本，没有设置 `PYTHONPATH`。

## 设计审查、边界与回退

模型注册、骨干选择和 canvas 桥接继续位于 Plugin 的正式 registry/model 扩展点；
T-Head 视觉 attention 沿用正常 dispatch，底层布局缺陷由 FlagGems 负责。
本轮实际 diff 为用户分支相对相同基线的四文件上游变更，目标提交工作树干净，无附加产品补丁。
真实整模只验证了当前 35B MoE；单测中的 dense 选择和初始化 mock 不等于完整 1B 或其他平台验证。

分支没有此前 [003](003-vision-data-qkv-loader.md) 的 data 模式权重加载 workaround；
当前默认 `mm_encoder_tp_mode=weights` 不触发此问题，不能据此批准启用 data 模式。
处理器缓存仍禁用，以保留 canvas 几何信息；现有黑名单用于其他已知问题，本轮不移除。
必要时先重新检查当前工作树和服务，再使用同一安装目录的原基线、已保留 stash/文件备份恢复，
只重启本任务服务，不自动覆盖后续修改。

结论为当前配置的分支替换定向回归通过。未复跑正式 ERQA/GPQA，没有证明历史精度分差已消失；
正式性能、完整验收和镜像验证均未执行。保留 `framework.yml` 的历史状态及绑定，不以本轮 Markdown
或定向回归替代正式回执。未提交、推送或创建 PR。

本地记录无 whitespace 诊断。workspace audit 仍报告原有 12 项 profile revision
错误（包括本模型的历史绑定）及其他历史材料警告；本轮未修改其状态或证据哈希来消除错误。
