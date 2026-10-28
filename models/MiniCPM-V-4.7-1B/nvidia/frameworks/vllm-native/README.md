# MiniCPM-V-4.7-1B / NVIDIA 原生 vLLM

记录于 2026-10-12 显式升级为 evidence v2 / profile v3。当前 `blocked` 仅表示新契约门禁状态；原状态和回执保存在 `control.history`，不代表重跑或否定历史功能。

[整理依据、原始快照与人工接续](../../../_shared/local-record-maintenance.md)。

## 整理前工作记录（原文保留）

目标为 `H100-149` / `MinicpmV4.7-1B-native` / `vllm-native`。
批准工作根在 Host 和容器中均为
`/public/flagos/jinghao/MiniCPMV4.7-1B/native`，映射已以设备号和 inode 核对。
用户本次明确允许直接修改容器已安装的 wheel。实际导入的 vLLM
`0.24.0+cu129` 中已新增 4.7 模型 adapter 与注册项，
保留原 registry 备份；权重与容器未修改或停启。GPU 0 TP1 的 eager、
显式 `FULL_DECODE_ONLY` 文本/图像/视频推理及十并发变输入请求已通过基本功能验证。
根级 `start-model.sh` 已从其本身启动并验证健康与算术回复。

2026-09-28 按用户要求，端口 8307 的当前 1B 服务改为显式
`FULL_AND_PIECEWISE`：mixed prefill/decode 捕获 PIECEWISE，decode 捕获 FULL。
十并发多模态基本功能检查通过。专用启动脚本在
`01-environment/start-minicpmv47-full-and-piecewise.sh`；本次运行细节见
`acceptance/full-and-piecewise-diagnostic.md`。按用户后续要求，根级
`start-model.sh` 也改为 `FULL_AND_PIECEWISE`，SHA-256
`0e94c30ed5c460b354ea6a3c0e38966ff32b24a7e56f566c5012396d1e9b2e53`（当时版本）。
新脚本已实际启动服务并完成两类图捕获和健康检查；详见
`acceptance/root-launcher-hybrid-update.md`。旧脚本在远端 `02-issues/` 留有备份。

2026-09-30 根脚本已进一步精简，当时 SHA-256 为
`c5fce8aba2f93a66e9fc1a5a23a386900b05c2a5464d326750eabd723aaaa6df`。
合并缓存目录设置，去掉冗余环境变量；受控对照证明本模型不能省略
`--enable-prefix-caching`，因此保留。最终服务健康、两类图捕获和十并发
文本/图片/视频检查均通过；见 `acceptance/launcher-simplification-20260930.md`。

同日按用户后续要求，根脚本移除缓存与临时目录的单独设置，使用
容器默认位置；SHA-256 为
`b08a779b7a86ba208647c953897947611a08717dfb6f80864ab7065953a52bcb`。
仍保留 libcuda 查找、GPU/端口保护和已验证启动参数。当时服务图捕获、
健康检查与十并发多模态请求均通过；见
`acceptance/default-cache-launcher-20260930.md`。

用户随后自行调整根脚本；2026-09-30 原样启动验证的当前 SHA-256 为
`f4be3515cc079773a26465497fef7955355bf68e35201a2704d6e5883350a66b`。
8000 端口健康，十并发文本/图像/视频基本推理 10/10 通过；实际最大模型长度
为 262144，尚未验证长上下文。脚本后台启动、重定向覆盖根目录 `service.log`，
且未检查已有端口/GPU 占用；因此本次仅确认当前实例能运行，不确认脚本
重复执行或冲突时的安全性。详见
`acceptance/user-launcher-validation-20260930.md`。

当前状态为 `functional`。full mixed graph 受 GDN 后端限制，正式原生精度、
性能和完整流程回执仍未完成，不标记 `optimized` 或完整 acceptance。
先前 decode-full 正式证据的部署身份见 `01-environment/deployment-identity.json`，SHA-256
`ac0c3db328583cfeac83ce7b0a508d7aa1383b4cb36be965686283b4193df0fe`。
该身份及 `framework.yml` 中的 execution-mode 回执属于旧启动配置；根脚本
变更后尚未重新绑定正式原生回执，不将旧回执当作新模式的验收通过证明。

2026-10-03 按用户配置，对当前 8000 服务完成 MMLU-Pro 每科 50 题、32 并发测量，共 700 题。
现有严格规则为 271/700（38.71%），同批回复的最终答案规则为 314/700（44.86%）；
700 次请求均正常结束，超时与请求错误均为 0。实际采样参数和 32768 总 token 预算已逐条
核验。详见 [MMLU-Pro 子集测量](acceptance/mmlu-pro-subset-c32-20261003.md)。
这是限定样本测量，未将正式全量 accuracy 子步骤或框架状态标为完成。

2026-10-10 对用户当前 8000 服务完成同范围测量：原始严格规则 279/700（39.86%），
最终答案规则 317/700（45.29%），超时与请求错误均为 0。服务实际加载
`/data/models/MiniCPM-V-4.7-1B`；每题输出预算为 `262144 - prompt_tokens`。
详见 [当前服务 MMLU-Pro 子集测量](acceptance/mmlu-pro-subset-c32-20261010.md)。
本轮只测量该服务的限定样本结果，未更新正式验收状态。

- `environment/`：框架、容器、组件、Host 和平台环境分析。
- `adaptation/`：编号问题记录及解决结论。
- `acceptance/`：验收计划、结果、总结和复盘。

这里仅保存 Markdown 结论；原始运行结果、过程脚本和缓存应留在批准的远端根下。
