# 用户脚本与安装环境复核

2026-10-23，范围为 PPU-01 / minicpm-jev-vllm 的用户脚本验证与适配 Plugin 普通安装。容器 ID 仍为 `2f1cde3f3c36963b0e5fe86e0fd76fd7af764209252408b5a8b838d7e591a5f8`，`/mnt:/mnt` 可写映射保持原样；容器始终运行。工作根仍为 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt/vllm-plugin-fl`，以下证据路径相对此根。

用户将父目录启动器改为 `nohup vllm serve`，并发上限 64，取消显式上下文长度和缓存环境变量。原文件 SHA-256 `dd59896ae11ff946670d06ff5231aef7529d42ecc7cf9ed625ef5d435c933d5f`，存在模型路径缺失起始双引号的语法错误。只补齐引号，保留其余逻辑；Host/容器脚本同路径 `/mnt/nfs/users/jinghao/MiniCPM-JEV/start-model.sh`，修正后 SHA-256 `4ddc5c3ad044f1a4cd10968282711550e8076f927f0d36d6649a3413a152ee8b`，Bash 语法通过。日志按用户脚本写入工作根 `service.log`，缓存使用容器默认 `/root` 下路径，不将旧脚本的缓存配置重新加回。

已从实际适配源码 `/workspace/vllm-plugin-FL` 离线构建 wheel，通过 `pip install --no-index --no-deps --force-reinstall` 安装到同一 Python 3.12 环境，替换此前 editable 注册。新版本 `0.0.0+g06014201f.d20261023`，实际加载 `/usr/local/lib/python3.12/site-packages/vllm_fl/__init__.py`，两个 `fl` 插件 entrypoint 保留。wheel SHA-256 `139613e54ac5efaf4ea779dc6e3f8ee3d6decb61444d4bc5deab9af9361496c1`，位于 `01-environment/plugin-wheel-20261023/`。构建前 312 个 Python 源文件逐项核对 wheel；除构建自动生成的 `_version.py` 外，安装后再次核对源码哈希。新适配模块及继承改动完整保留，没有通过 `PYTHONPATH` 或源码目录覆盖普通安装。

torch 2.10.0、transformers 5.8.1、FlagGems 与 FlagGems-vllm 保持原环境。vLLM 0.24.0+empty 的 1886 个安装 Python 文件前后哈希一致，没有修改 vLLM。适配源码保留供后续维护；运行不再依赖 Plugin editable 源码路径。未重新打包镜像或更新首轮交付清单。

先核对原任务服务 PID108830 / start tick545358949，再以 SIGTERM 停止该服务并确认退出及 8330 端口释放，直接执行用户脚本，没有为启动额外注入缓存设置。新 API PID111755 / start tick545606946，EngineCore PID112325，解释器 `/usr/local/bin/python3.12`，PPU 1，localhost:8330。日志确认默认上下文 262144、`max-num-seqs=64`、PIECEWISE / eager backend 及 7 个捕获尺寸完成。仅替换本任务服务，没有停止或重启容器。

| 检查 | 结果 |
| --- | --- |
| 普通安装 Plugin 的 worker / 视觉插值单元测试 | 9 passed，包含 CPU、PPU、FP32/BF16、变输入图重放 |
| vllm serve CLI | help 正常，用户实际命令启动并就绪 |
| 原有 12 样例两轮，24 请求 | 全通过，max Δ 0.004417300224304199，token/阈值侧一致，24 个不同 response ID |
| 64 客户端并发，64 请求 | 全通过，同一 max Δ，token/阈值侧一致，64 个不同 response ID |
| 最终健康检查 | HTTP 200 |

完整证据目录 `04-runs/script-environment-20261023-1/` 包含原用户脚本、修正脚本、构建/安装日志、安装身份、前后源码清单、回归日志、启动身份、功能结果与 `final-environment.json`。复测使用首轮已固定请求与参考值，容差仍为 0.005，未放宽。首次仓库级 conftest 导入因普通安装不提供源码 `tests` 包而失败；这两组不依赖该 conftest 的单元测试以 `--noconftest --import-mode=importlib` 执行，并在测试前断言 Plugin 来自 site-packages；原失败日志保留。

实际限制：FlagTune AUTO 平台包 schema 存在 `configs` 字段不兼容警告，受影响变体回退默认调优配置；本轮未修复调优包。`vllm serve --model` 当前可用但提示未来移除。首次运行重编译默认缓存中的内核耗时较长。本轮仅为环境与功能复核，不是正式完整精度、性能或新镜像验收；短样例成功不证明 262144 长上下文已验证，64 客户端并发也不等于每个引擎 batch 都有 64 条。首轮部署指纹和正式回执保持历史身份，不自动绑定新安装、新脚本和新参数。
