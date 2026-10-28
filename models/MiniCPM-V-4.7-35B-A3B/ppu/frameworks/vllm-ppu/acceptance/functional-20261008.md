# 原生 PPU 服务功能验证与交付

2026-10-08 18:47:39（远端时间）实测。范围为 PPU-13 / `minicpmV4.7-ppu`，
模型 `/mnt/cpfs/models/MiniCPM-V-4.7-35B-A3B`。本 experimental profile 的
功能检查通过；没有正式精度、性能验收或 optimized 结论。

## 实测结果

| 项目 | 结果 |
| --- | --- |
| 负基线 | 修改前 4.7 架构不受支持，原失败保留 |
| 处理器与位置 | 文本、单图、宽/长切片、多图、视频，6/6 与 checkpoint canvas 算法一致 |
| eager TP1 | 16 shard 完整加载，8/8 HTTP 200、stop、内容正确 |
| FULL 边界 | 原生 GDN 仅支持 UNIFORM_BATCH，自动转换为 FULL_AND_PIECEWISE；不计 FULL 通过 |
| 最终脚本 TP2 | PPU3/4，8022，显式 FULL_AND_PIECEWISE，无模式降级提示 |
| 图捕获 | mixed prefill/decode PIECEWISE 与 decode FULL 各 7/7；尺寸 1、2、4、8、16、32、64 |
| 十并发 | 10/10 正确，覆盖文本、颜色、切片、多图、两帧视频与重复图 |
| 前缀缓存 | 1905-token 图文请求红、红、蓝均正确；观测命中 1632 token |
| 就绪 | /health 200；/v1/models 名称与模型路径正确，max_model_len=262144 |

诊断请求使用 temperature=0、enable_thinking=false 和短输出上限，只用于功能检查。
未修改模型 generation_config；服务仍读取 temperature=1、top_k=20、top_p=0.95。

## 最小启动脚本

host/container 路径均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-ppu/start-model.sh`，
chmod 755、bash -n 通过，真实启动和占用端口拒绝检查通过。
SHA-256：`beaae8f2e06e64d7f54e3d00657c6ec89d91a41bd82651f0ace2b5516c1ae551`。

保留参数及理由：GPU3/4 与 TP2 用于任务资源隔离；8022 避免已有服务端口；
served-model-name 提供稳定 API 名称；trust-remote-code 加载 checkpoint 4.7 配置与
处理器；enable-prefix-caching 确保 Hybrid 非性能验证开启缓存；mm-processor-cache-gb=0
保证 canvas 几何能够传入位置构造；compilation-config 固定用户要求的图模式与七档尺寸。
缓存环境变量将 HF、vLLM、Triton、DeepGEMM、Inductor 写到 06-cache，TMPDIR 写到 05-tmp。
首次 eager 曾使用 DeepGEMM 默认 /root/.deep_gemm，后续与最终启动已明确改到批准根。

未保留 max-model-len、max-num-seqs、诊断多模态数量限制、TORCH_SDPA、视觉 data TP、
FlagGems 设置、黑名单或调试开关。启动脚本只准备运行目录、检查端口冲突并 exec 服务，
没有安装、补丁、评测、轮询或自动终止进程。

容器内部交付副本 `/opt/model-adaptations/minicpmv4.7-35b-a3b/start-model.sh` 与根脚本
内容、权限、哈希一致；语法和占用端口拒绝检查通过。实际服务本轮从批准根脚本启动。
必要产品代码位于容器内部 `/usr/local/lib/python3.12/site-packages/vllm`；没有 PYTHONPATH。
交付副本运行时相对自身建立日志/缓存目录，checkpoint 为明确的外部输入，部署须在相同
绝对路径提供模型挂载。本轮未打包镜像、未从新镜像验证内部副本启动，不宣称镜像交付已验证。

## 证据与运行身份

批准根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-ppu`：

- `04-runs/bringup-20261008/`：baseline、产品 diff/哈希、处理器位置对照、交付清单。
- `eager-v1/`、`full-v1/`、`final-v1/`（以上 run 内）：各轮进程、请求、响应、检查结果。
- `final-v1/functional-result.json`：最终命令、白名单环境、HTTP/图/缓存/脚本检查实测汇总。
- `deployment-manifest.json`：部署指纹
  `a3795ef75fe1514fa2e919d1e06d31567c226151400c6c809fa8e394599ca6eb`，绑定容器/镜像、
  实际产品 Python 文件 SHA、checkpoint 小文件 SHA、权重 index SHA 与 shard 文件身份、
  尺寸/mtime、设备拓扑和运行配置。未对全部 65.59 GiB 权重进行逐字节 SHA，未将文件
  元数据描述为完整权重内容校验。
- `04-runs/service-20261008-184229-47195.log`：最终服务日志。
- API/进程组 47195，EngineCore 47680，TP rank 47952/47953，tracker 47679。

最终服务保持运行，容器没有停止或重启。仅停止本轮两个诊断进程组，已有 PPU0/1 的
8010 服务与 PPU2 工作负载未操作。轮次之间未更换 installed package 或引入另一份源码。
产品审查对全部 Python 文件比对后仅发现 registry、4.6 骨干 hook 和新增 4.7 adapter 三处
增量；checkpoint 小文件哈希未变，权重未写入。

## 限制

262144 是配置与启动容量检查结果，未发送满长度请求。复杂真实视频、长输出、长期稳定性、
跨模型回归、正式 GPQA/ERQA 精度、性能与新镜像运行未验证。4.6 共享 hook 保留原 Dense
选择，未用 4.6 权重做整模回归。framework 的功能状态不能替代正式阶段回执；未签发
完整 acceptance 完成状态。
