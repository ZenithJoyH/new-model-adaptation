# 2026-10-08：双模型共用 Plugin 功能验证

## 验证范围

按用户要求整合 NVIDIA 1B dense / 35B-A3B MoE 的适配代码，并在 `H100-149`
新增 `MinicpmV4.7-unified-20261008` 验证。状态：`functional-passed`。
这是代码整合回归，不是正式准确率、性能或 framework gate 通过记录。
完整设计、源码哈希、继承差异和过程失败见
[006](../adaptation/006-unified-dense-moe-adapter.md)。

共同 Plugin 实际安装、导入路径为容器内部 `/vllm-workspace/vllm-plugin-FL`，
不设置 `PYTHONPATH`，不挂载源码 checkout。原两个容器与服务未更改。
统一按 `text_config.model_type` 选择语言骨干；视觉组件、canvas M-RoPE 和权重加载共用。

## 配置与结果

- 两模型 TP2；容器 CUDA 0/1 对应物理 GPU 6/7。
- BF16，上下文配置 50,000、`max_num_seqs=16`、显存比例 0.8。
- 服务端口 18347，仅绑定 127.0.0.1；显式开启 prefix caching，不设置旧 attention 黑名单。
- eager 用于隔离骨干与图问题；生产选择为用户指定的 `FULL_AND_PIECEWISE`。
  历史 FULL 的 GDN 能力阻断见问题 004；不将分段 prefill 记为全量 FULL。
- 请求 `temperature=0`、`max_tokens=64`、`enable_thinking=False`；请求预算 600 秒。
  回答须 HTTP 200、关键答案/顺序正确且 `finish_reason=stop`。

| 模型 | eager | FULL_AND_PIECEWISE | 结果证据 |
|---|---|---|---|
| 1B dense | 6/6 | 19/19 | `1b-{eager,graph}/checks.json` |
| 35B-A3B MoE | 6/6 | 19/19 | `35b-{eager,graph}/checks.json` |

每个 eager 包含文本 42、红/蓝变输入、绿色竖图、红蓝双图、红蓝双帧视频共 6 项。
每个 graph 额外包含 1200×900 红→蓝→红大图切片 3 项，以及 10 个并发混合图文请求，
共 19 项。视频采用 `data:video/jpeg`，未覆盖 MP4/PyAV 解码。
真实 HF processor 对两模型均产生 7 个 grid：thumbnail `[28,36]` 与六个 `[32,32]`；
两模型各三次大图 API 的 prompt token 均为 489，均回答正确。具体 geometry 见 `highres-geometry.json`。
两模型均实际捕获 mixed prefill/decode PIECEWISE 7/7、decode FULL 5/5。

另完成正常 pytest 入口 14/14：骨干配置选择、未知架构拒绝、constructor 成功/异常
配置恢复、纯文本/非 canvas fallback、缺失/非法 geometry、bounds/grid 数量和视频字段。
新增 backbone 测试在旧 1B 实现上失败，负对照保留。
两个真实 checkpoint 的 thumbnail/portrait/slice/video 位置对照 8/8 逐元素一致，
decode delta 满足 `context_len+delta=max(position)+1`。

## 共用启动器与运行约束

容器内部 `/opt/minicpmv47-unified/start-model.sh`，SHA-256
`33fd3e79c06c4091c42be2d7e83fecb36c8010e589d85459714fb702f6d79f75`；
同内容留档于批准工作根 `01-environment/start-unified-model-20261008.sh`。
在新容器内用 `bash /opt/minicpmv47-unified/start-model.sh 1b` 或 `35b` 选择权重；
共享 GPU 与端口，同一时刻运行一个模型。
脚本包含启动所需环境、目录准备及 `exec vllm serve`，没有包安装、探针或停止进程命令。
35B graph 实际通过该脚本启动并完成 19 项回归，见 `35b-graph/launcher.json`；
1B 使用同配置的直接 CLI 完成 25 项回归，未另行重复整个 1B 脚本启动周期。

`TMPDIR` 使用短路径 `<root>/05-tmp` 避免 UNIX socket 长度限制；
XDG/Triton 缓存位于 `<root>/06-cache/unified-adapter-20261008`。
容器内部条件性 `.pth` helper 按 PID 隔离 Triton 缓存，并硬链接已结束 worker 的编译 seed；
真实 cache.put 原子替换测试确认 seed 不被新 PID 写入污染。
这是共享文件系统已知竞态规避，未声称修复文件系统根因。初次形状编译较慢，
不能将本轮延迟或缓存复用结果作为性能指标。

35B graph 的 19 项请求全部完成后，controller 向本轮进程组发 SIGTERM。
vLLM `mode=abort timeout=0s` 关闭阶段出现 `EngineDeadError` / resource_tracker 警告，
API 退出码为 0；日志顺序明确在请求成功、shutdown trigger 之后。
保留这些诊断，不描述为无警告运行或已验证优雅关闭协议。

## 证据与限制

以下 `<root>` 为 `H100-149:/public/flagos/jinghao/MiniCPMV4.7-35B/flagos`，
原生证据保留在 `<root>/04-runs/unified-adapter-20261008/`：

- `container.json`、`source-container.json`：容器、基础镜像、挂载与设备。
- `source-manifest.json`、`plugin-candidate.patch`、`installed-environment.json`：实际代码及安装身份。
- `backbones-before.log`、`unit-after.log`、`canvas-reference.json`、`highres-geometry.json`：局部契约与位置对照。
- 各阶段 `command.json`、`server.log`、`checks.json`、停止记录及总 `result.json`：真实服务过程。
- `client-events.jsonl` 与 controller 归档：请求、预算调整及保留 API 的恢复过程。
- `cache-isolation.log`、`seed-provenance.json`：缓存隔离实测与来源。
- `no-gpu-import*.log/json`：原/新安装均在未变更的 Plugin→FlagGems 设备检测处失败；
  不声称 CPU 或其他平台验证通过。

最终核验两个原生 JSON 均为 `passed`，源码、runtime helper 与启动器哈希保持一致，
`git diff --check` 通过。vLLM 2057 个 `.py/.so` 文件的路径/内容聚合 SHA-256 前后均为
`8fb38bcb183ed0d912e9ce107a1269865dca66a67d849f5f4469d4c53117ba8d`，
见 `vllm-before.json`、`vllm-after.json`。

| 最终证据 | SHA-256 |
|---|---|
| `final-validation.json` | `4823cad7e977e20472102bd36979edea0b7686f1c60045faf6939a5bbc2b7b4d` |
| `final-host-state.json` | `2cebc4c2b64dfc898e5fd71d9811efc1a141a118863983f937cb503ed11f60bf` |

收尾时新容器保持运行，验证 API 已退出、18347 关闭、物理 GPU6/7 无计算进程。
原两个容器仍运行，原适配器哈希未变，8001/8021 `/v1/models` 均返回 200。
以上是指定时间点的状态取证，不承诺后续外部操作不会改变资源占用。

本轮未运行正式 GPQA/FlagEval、性能 benchmark、长上下文或其他并行拓扑。
基础镜像是合并前快照；合并代码、helper、启动器位于新容器内部，未生成或验证最终发布镜像。
`framework.yml` 保持原状态及历史绑定；本地 repository-only audit 的 12 个已有 revision
错误与 78 项历史待复核保留，未通过改写历史指纹消除。

## 代码提交

后续按用户授权，已推送到指定私有仓库的
[support-minicpmV4.7](https://github.com/flagos-day0/vllm-plugin-FL/tree/support-minicpmV4.7)，
提交 [aa4228e](https://github.com/flagos-day0/vllm-plugin-FL/commit/aa4228e36b2b0af2efc0a8cfc4b8c7affc7fdc68)。
本次提交仅改四个适配与测试文件，提交后哈希与上述验证版本一致。
父版本为已验证的 `3a27a6f`；目标仓库 main 较旧，新分支额外保留其后的 26 个已有上游提交。
完整基线关系和远端核验记录见 [006](../adaptation/006-unified-dense-moe-adapter.md)。
这次提交不重新解释旧 main 的兼容性，也不升级正式验收状态。
