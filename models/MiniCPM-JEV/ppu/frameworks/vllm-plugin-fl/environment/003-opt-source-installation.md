# /opt 源码安装与长上下文验证

2026-10-23，用户要求将适配 Plugin 改为 `/opt` 下源码安装，并验证默认 262144 上下文。范围仍为 PPU-01 / minicpm-jev-vllm，容器 ID `2f1cde3f3c36963b0e5fe86e0fd76fd7af764209252408b5a8b838d7e591a5f8`。先核对 `/opt/vllm-plugin-FL` 不存在、`/opt` 非符号链接且不在 `/mnt:/mnt` 绑定挂载内，再从原适配源码复制完整 checkout，保留 Git revision 和既有 dirty/untracked 改动。原源码未删除或重置。

使用同一 `/usr/local/bin/python` 执行 `pip install --no-index --no-deps --no-build-isolation -e /opt/vllm-plugin-FL`。版本 `0.0.0+g06014201f.d20261023`，direct_url 标明 `/opt/vllm-plugin-FL`、editable=true，实际加载 `/opt/vllm-plugin-FL/vllm_fl/__init__.py`。不设置 `PYTHONPATH`。Git HEAD `06014201f8ea8cd7092a56a945d8fc7998c5a46c`，312 个 Python 文件及既有 dirty 状态迁移前后核对一致；vLLM 1886 个安装 Python 文件未变化。后续 Plugin 产品修改以此实际安装的 `/opt` checkout 为准，历史 `/workspace` 副本保留原样。

源码安装后的 worker / 视觉插值测试 9 passed，覆盖 CPU、PPU、FP32/BF16 和变输入图重放。先按用户脚本启动 API PID147481 / start tick545711128、EngineCore PID147769，完成失败现场验证；修复下述调度问题后，仅替换本任务服务，最终 API PID161804 / start tick545909862、EngineCore PID162148。启动脚本 `/mnt/nfs/users/jinghao/MiniCPM-JEV/start-model.sh` 未改变，SHA-256 `4ddc5c3ad044f1a4cd10968282711550e8076f927f0d36d6649a3413a152ee8b`，保留 max-num-seqs=64、默认 max_model_len=262144、双图、LAST classify、PIECEWISE/eager backend。容器始终运行。

长上下文为单请求容量/稳定性验证，不是长文业务精度或正式性能验收。以固定 s02 双图案例为基底，在 OCR 文本后追加换行和重复 ` a`，用服务 `/tokenize` 调整到精确目标长度，再断言 `/classify` 的 `usage.prompt_tokens` 与目标一致。不同长度和满长度重复使用不同 cache_salt，排除前缀计算复用；未设置截断。计划测试 32768、131072、262144、独立冷缓存重复 262144、超限 262145 拒绝，以及结束后 12 个短样例回归。每个推理请求超时预算 1800 秒，资源约每 10 秒采样一次。

首轮 32768/131072 token 正常，但 262144-token 请求在 1800 秒后超时。定位为原生 Scheduler 也给 pooling 预留一个生成 token，导致恰好上限的请求少计算最后一个 token 并在调度循环停滞。已通过 Plugin 自有 scheduler_cls 子类取消同步 pooling 的生成预留；vLLM 未改，输入上限未放宽。原生 64-token 调度负对照准确复现只调度 63 token，修复与既有回归共 17 passed。设计、守卫、退出条件见 [009 调度边界问题](../adaptation/009-pooling-context-boundary.md)。

修复后使用相同脚本、同样双图、精确 token 构造和独立 cache_salt 完整复测通过：

| 检查 | 实测结果 |
| --- | --- |
| 32768 token | 实际消费 32768，有限二分类概率，通过 |
| 131072 token | 实际消费 131072，32.412 秒，通过 |
| 262144 token | 实际消费 262144，119.918 秒，通过 |
| 262144 独立冷缓存重复 | 119.332 秒，与前次概率完全一致，max Δ=0 |
| 262145 token | HTTP 400，明确报输入 262145 超过上限 262144 |
| 长请求后 12 短样例 | token 一致，最大参考误差 0.004417300 < 0.005 |
| 服务与资源 | health 200，无 OOM，10 秒间隔采样显存峰值 90928 MiB（88.797 GiB） |

满长度输出为 `[0.9100022316, 0.0899977833]`，两次一致。耗时为容量验证过程的观察值，不是正式性能指标。测试为单请求并发，未验证 64 路同时各 262144 token；合成填充仅证明容量、边界和稳定性，不证明长文业务判断准确率。

2026-10-23 09:11 UTC，按用户要求清理源码管理器中的无关修改标记：实际 `/opt` checkout 有 22 个文件仅可执行权限从 Git 记录的 0755 变为 0644，另一个 MoE 配置符号链接被展开成内容相同的普通文件。逐项核对内容后恢复权限和原链接；633 个跟踪/未跟踪文件的读取内容 SHA-256 前后全部一致，Git index 未改。当前仅剩 3 个实际适配修改文件及 6 个新增源码/测试文件；未改代码、未重启服务，health 200。原始 diff、操作清单、链接展开内容备份及校验结果保存在工作根 `04-runs/git-metadata-cleanup-20261023T091110Z/`。

证据目录相对工作根 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt/vllm-plugin-fl`：`04-runs/opt-source-long-context-20261023-1/`。父目录保留源码安装身份、原生超时、诊断和回归日志；`fixed/` 保存修复后的逐例输出、完整汇总、资源采样、服务身份、最终源码清单/diff 与 `final-environment.json`。程序分别在 `03-acceptance/validate-opt-source-long-context.py` 和 `03-acceptance/validate-opt-source-long-context-fixed.py`。旧正式回执仍对应历史部署，不自动绑定本轮 `/opt` 安装与新服务；新镜像打包验证未执行。
