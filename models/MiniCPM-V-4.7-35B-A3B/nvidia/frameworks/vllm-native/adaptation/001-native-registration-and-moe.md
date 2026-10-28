# 001：MiniCPM-V 4.7 注册和 MoE 骨干接入

## 元数据

- 状态：`functional_verified`；TP2 整模加载、canvas 位置与文本、图像、视频请求已回归。
- 日期：2026-09-28。
- Host/容器：`H100-149` / `MinicpmV4.7-35B-native`，镜像 ID `sha256:7f698705b6ed1805f16b26634e94c25f7369a8d043b777e610f7001f4d2899e4`。
- 模型：`/data/models/MiniCPM-V-4.7/weights/35b-a3b`，配置 SHA-256 `3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646`。
- vLLM：wheel `0.24.0+cu129`，短版本标记 `gee0da84ab`，无 Git checkout。

## 现象和接口分析

checkpoint 声明 `MiniCPMV4_7ForConditionalGeneration`、`qwen3_5_moe_text`、
256 个专家每 token 选 8 个，以及 `mrope_mode=canvas`。原生 vLLM registry 只含
4.6 类；4.6 adapter 使用 dense `Qwen3_5ForCausalLM`，并把顺序位置复制到三个
M-RoPE 通道。因此不能把 4.6 类作为 4.7 的注册别名。

扩展点是 `vllm.model_executor.models.registry`、模型专用 adapter、现有
`Qwen3_5MoeForCausalLM` 和已有 MiniCPM 多模态处理器/视觉塔/权重映射。
本轮保留 4.6 源码原样；注册新增架构，新建模型专用 adapter 覆盖 MoE 构造。
所有未选择 4.7 架构的调用者继续走原注册路径。初版沿用 4.6 顺序位置
仅用于定位启动过程，第二版已按 checkpoint 的 canvas 算法修正。

## 受控尝试和证据

原始 `registry.py` SHA-256 `ab52495073a046b79d00a314cbc96e719e3ed916ea8a8bf6f3202015062b5676`，
4.6 adapter SHA-256 `fcc4e379f68db4710e1d9b92db043ff42709a5bde89fc94995aa35136cc37b81`。
受用户明确授权，仅在本容器 wheel 安装目录
`/usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/` 修改。
`02-issues/minicpm47-35b-install-v1.py --check` 已验证原始哈希及 registry diff，
随后实际安装。原 registry 与 diff 保存于 `02-issues/registration-v1/`。
新 `minicpmv4_7.py` SHA-256 `afe3c1d616557e330281e4510106b54233de221d06e76032d5430f4321c74937`，
registry 修改后 SHA-256 `58ea925cd79c7771b35455d48c5d991928fd019539d8e0e61e100af541d55d43`。

adapter 以带 CUDA 库路径的进程环境导入成功。eager TP8 服务命令在
`01-environment/start-eager-v1.sh`，原始日志在 `04-runs/eager-v1/service.log`。
服务确认架构解析为 4.7，EngineCore 启动，8 rank 初始化；随后在 Triton
launcher 共享缓存读取时失败，详见 002。此轮尚未证明权重完整加载或输出正确。

用户随后指定 TP2，不继续以 TP8 为目标。`01-environment/start-eager-tp2-v1.sh`
选择物理 GPU 2、3，`--tensor-parallel-size 2`，原始日志见
`04-runs/eager-tp2-v1/service.log`。17 个 shard 全部加载，模型内存每 rank
33.08 GiB，`/health` 与 `/v1/models` 返回 200。确定性文本请求生成 token，
但 32-token 上限使回复在推理文字中截断，尚非正确性通过。256×256 红色测试图
得到停止完成的回复，最终答案 `Red`；原始响应见
`04-runs/eager-tp2-v1/image-smoke.json`。这只验证视觉链路可运行，不能证明
4.7 的 canvas M-RoPE 正确。

对照 checkpoint 的 `mrope_minicpmv4_7.py`，第二轮模型专用 adapter 从视觉
feature 的 `tgt_sizes` / `video_tgt_sizes` 与 prompt 结构标记构造 image bounds，
调用 checkpoint 的 canvas 位置算法，按 vLLM 解码约定计算 position delta。
改动前文件 SHA-256 `afe3c1d616557e330281e4510106b54233de221d06e76032d5430f4321c74937`，
改动后 SHA-256 `91696f38a69091e45bd75fe1c35dd86ca32837c2827dd4d9251fda469ed2931f`。
原文件备份于 `02-issues/registration-v2/`。重启前核对本任务进程组
`2746517`，仅包含 API、EngineCore、TP0/TP1 与资源跟踪器；对该组发送
`SIGTERM` 后确认组内进程退出，容器保持运行。第二轮日志路径为
`04-runs/eager-tp2-v2/service.log`。

第二轮 `02-issues/positions-v2.py` 将构造的三通道位置及解码 delta
与 checkpoint canvas 算法逐值比较；文本 delta 为 0，图像样本 delta 为 -3。
`04-runs/eager-tp2-v2/`、`04-runs/graph-tp2-full-v1/` 和
`04-runs/final-tp2-v2/` 分别保留 eager、图模式与最终脚本的请求结果：
`17+25` 返回 `42`，红色图返回 `Red`，两帧红蓝视频按顺序识别。
最终图模式在 GDN 限制下为 decode-full，详见 003；最终并发 10/10
返回 200、stop 且答案符合这组诊断请求预期。

## 审查、限制与下一步

2026-09-28 审查实际 wheel 文件：`registry.py` 仅添加 4.7 注册；
`minicpmv4_7.py` 在模型专用实现中接入 MoE、结构 token、视觉网格和
canvas 位置；4.6 adapter 哈希未变。镜像内没有 Git checkout，无法确认
PR base、HEAD 或原工作树 dirty/untracked，已以镜像 ID、安装路径、原/新哈希、
备份和 diff 明确替代。影响面是 4.7 注册命中及其文本/图像/视频路径；
注册 miss 仍沿既有分派，4.6 静态未改，其他模型未做运行回归。
进程隔离只是共享 Triton cache 问题的 mitigation，非上游根因修复。
2048 token 以上、复杂切片、跨模型回归和长期稳定性未验证；
用户暂不要求正式精度评测。未提交、推送或创建 PR。
