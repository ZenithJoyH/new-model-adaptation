# 2026-10-09：当前 1B DSpark 容器的 35B-A3B DSpark 服务验证

## 当前部署

用户要求在现有容器支持 35B-A3B DSpark，授权复制权重并暂停 1B 服务。
Host `H100-149`，容器 `MiniCPMV4.7-1B-DSpark-gpu6`；GPU6 单张 H100 80GB，TP1。
vLLM `0.28.0`，Plugin `0.4.0-dev@e88e4db`，FlagGems `5.4.0.dev0+g0dddb462`。
本轮完成服务与功能验证，未运行正式精度、性能或镜像发布。

- 服务地址：Host `127.0.0.1:18349/v1`，model `MiniCPM-V-4.7-35B-A3B-DSpark`。
- 容器内启动器：`/opt/flagos/dspark/start-35b-model.sh`，从此文件实际启动。
- Host 入口：`/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-dspark-35b.sh`。
- 容器权重：`/work/06-cache/dspark-35b-weights/{main,draft}`，34 文件合计
  71,224,635,415 字节，逐文件复制并验证 SHA-256。
- API PID 34347、EngineCore 35550；最后 health 200，GPU6 76,025 MiB。
- 容器 ID `8645e61dddfaac3712ec27afaa1efce8b008e9f6f24a263a9e6380dce43cb640`，
  保持运行，restart count 0。原 1B 服务暂停，原启动器保留，其他 GPU 服务未操作。

启动器及两个证据副本哈希相同：
`1e1964fad3ae24064c60cc2782fa129e83c4916f25fe66bca1d1442cdc3f843b`。
`bash -n` 通过，容器内启动器为普通可执行文件，`/opt` 无 bind mount。
已安装 Plugin 源码同样位于容器文件系统，不通过 `PYTHONPATH` 选择。
权重和运行证据位于 `/work` 挂载；本轮未验证将其打包为可独立部署的镜像。

## 启动配置与必要性

| 设置 | 本轮用途与边界 |
| --- | --- |
| DSpark 草稿路径、token 14 | 对应 draft block size 15；真实 speculative decoding |
| `FULL_AND_PIECEWISE`、捕获 `[1,15]` | 单序列与 speculative decode 图；GDN 仅支持 uniform batch FULL |
| 上下文 50000、seqs 1、batched tokens 1024 | 单卡 35B 加草稿的验证配置；客户端并发排队 |
| 显存比例 0.94 | main/draft 加载 67.49 GiB，graph KV budget 6.05 GiB |
| 单图、视频 0 | 限定本轮验证与显存规划范围 |
| host/port/model name、trust remote code | 绑定服务接口及 MiniCPM 权重实现 |
| vLLM/FlagGems 缓存和 op-list 路径 | 运行产物落入批准工作根，区分本轮模型/编译配置 |

不包含安装、端口探测、目录初始化、调试包装、`PYTHONPATH`、同步 CUDA 调试变量，
继承当前容器已配置的 HF/Triton/temp 环境。prefix caching 开启，没有新增算子黑名单。
50K 为实际 API 配置值，不代表已通过 50K 长输入测试。KV token 容量估计 147,706，
日志中的 2.95x 是容量估计，调度上限仍为一个驻留序列。

## 已执行结果

| 验证 | 结果 |
| --- | --- |
| 新增 MoE padding 维护测试 | 5/5；有效行数值、内存边界、CUDA 图变输入 replay |
| 现有 MoE factory/router、MiniCPM backbone/DSpark 测试 | 24/24 |
| 修复后普通 eager | 9/9：文本、四色图、重复图、变化算式、多轮 |
| 最终主模型图捕获 | PIECEWISE 2/2；FULL decode 1/1 |
| DSpark 草稿图捕获 | FULL 1/1 |
| 最终图模式固定请求 | 9/9，同一组答案与 eager 一致 |
| 十客户端同时提交 | 10/10；答案 100–109，全以 stop 结束 |

图服务草稿 20 次、生成草稿 token 280、接受 token 40；证明草稿实际参与，不是仅配置了
DSpark 参数。短题计数不代表加速效果或精度。draft 使用文本输入，主模型处理图像，
未声称 draft 支持外部多模态 embedding。

首次加载失败与修复详见[问题 009](../adaptation/009-dspark-plugin04-single-gpu.md)：
FlagGems fused MoE 路径未支持 vLLM 0.28 padding expert ID `-1`。
只在安装的 Plugin 专家入口按 CUDA forward padding metadata 委托兼容实现；
vLLM/FlagGems 源码指纹保持不变，既有 MiniCPM shim 不变。存在 padding metadata 的
全 false mask 也走兼容实现，未测该选择的性能；量化、LoRA、多 GPU、其他硬件未覆盖。

## 原生证据与验收边界

Host 根 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos` 对应容器 `/work`。
本轮 run 名 `dspark-35b-20261009`：`01-environment/` 中保存源/组件指纹和 Docker
身份；`04-runs/` 中保存权重 manifest、修复前后日志、测试结果、功能完整响应、metrics、
最终启动器、`final-verification.json` 和 `evidence-manifest.json`。

未运行 MATH500/MMLU-Pro 等数据集，不能沿用 1B 精度分数；未进行正式性能、视频、
长上下文或新镜像验证。不更新历史 `framework.yml`，不声称完整 adaptation/acceptance 通过。
