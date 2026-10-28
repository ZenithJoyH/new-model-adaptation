# 008：模型完整上下文与全卡可见部署

2026-10-20，用户明确要求模型最大支持长度、容器挂载全部显卡，并询问TORCH_SDPA依据。配置text_config.max_position_embeddings=262144；此前50000来自初始部署约定，本轮按用户新要求改为262144，不改权重、RoPE或vLLM限制检查。

H100-149，批准Host/container根/public/flagos/jinghao/MiniCPM-OCR/flagos。先核实旧minicpm-ocr-flagos-runtime仅映射GPU1、当前任务负载在该卡，其余7卡空闲、control.mode=agent。为避免停止/重建原容器，从其已验证源码依赖创建快照，再启动新minicpm-ocr-flagos-allgpu，ID30f6c5ba638e01ab066682ffc140d81dbeb648a7d7dca318aab953da5689ec05，底层快照镜像sha256:d268dae8b7cec5aed7c9a11d7be250d788985d896b2dea0f8d5826154c71e059。实际源安装、13个产品文件、两个算子库完整清单、FlagTree编译库、vLLM2449文件与权重全部核对保持，没有安装、升级或修改产品代码。

## 设备和运行选择

新容器显式暴露/dev/nvidia0至7以及ctl/uvm/uvm-tools，保留原已核实工作根RW、权重RO及驱动库RO映射；未启用privileged。默认CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7，CUDA枚举8张H100，8个UUID与宿主一致，见04-runs/maxctx-allgpu-20261020/device-visibility.json及new-container.json。

全卡可见与TP8分开处理：本轮保持TP1，生产脚本CUDA_VISIBLE_DEVICES=0，选择空闲宿主GPU0（UUID62954cac-bde7-68fe-d74b-3118a92bcdd4），其余卡保留可见供后续明确配置使用。不是8卡并行或8卡负载验证。BF16、max-num-seqs64、显存比例0.55、图像4/视频1、前缀缓存开启等保持；max-model-len改262144，无允许超长或降级长度的绕过。

## 视觉后端参数依据

当前Platform在不指定参数时对视觉head_size72和64均自动选择FLASH_ATTN，已实际查询确认。empty vLLM的vllm.v1.attention.backends.fa_utils.flash_attn_varlen_func实际为None；vllm的flash_attn_maxseqlen_wrapper调用它。小型真实BF16视觉Q/K/V直接复现TypeError: 'NoneType' object is not callable；同一输入在flag_gems.use_gems上下文的torch_sdpa_wrapper通过，对照最大绝对误差0，诊断容差rtol=atol=0.02。原始诊断及堆栈见maxctx-allgpu-20261020/mm-backend-probe.json，未修改产品以掩盖失败。

--mm-encoder-attn-backend TORCH_SDPA选择多模态视觉编码器的SDPA接口路径，避开当前不可调用的视觉FlashAttention；不选择文本骨干的attention backend，也不关闭Plugin/FlagGems或CUDA graph。它是当前empty/Plugin组合的兼容设置，不能推广为模型或H100必须使用该后端。未来提供可用的视觉FlashAttention接入并通过OCR/视频参考和eager/graph验证后可去掉或替换；本轮保留。

## 实测与生命周期

原8011服务保留到新服务通过验证。临时服务最初仅改了就绪探针而遗漏实际CLI端口覆盖；识别后按精确进程身份清理新容器测试进程，修正为8012，保留attempt1-failure.json与maxctx-eager-20261020日志；旧容器生产进程未停止。这次配置错误不计为通过。有效eager使用maxctx-eager-v2-20261020，命令与探针均为8012。

262144配置下eager、graph各15项请求的文本、生成token、prompt/completion数均精确匹配独立HF参考；maxctx-{eager,graph}-reference-20261020保存原始结果。FULL重新检查后仍受GDN UNIFORM_BATCH能力限制，实际FAP；19批piecewise、11个full-decode捕获，诊断运行计数{'FULL': 230, 'PIECEWISE': 4, 'NONE': 45}，保留NONE。

另外实际完成262143个输入token+1个输出token，总长度262144；usage={'prompt_tokens': 262143, 'total_tokens': 262144, 'completion_tokens': 1, 'prompt_tokens_details': None}，耗时23.296秒，仅作为单请求边界/容量检查。262145输入token请求返回400。计划、请求生成配方和SHA、响应分别见long-context-plan.json、long-context-result.json、overflow-rejection.json。这不验证长上下文理解/检索精度，也不声称64路最大长度并发或正式性能。

新服务全部检查成功后，仅停止已记录的临时8012与原任务8011进程树，原、新容器均保持运行。根start-model.sh改为262144并同步新容器内部/opt/minicpm-ocr-flagos/start-model.sh，SHA均066993c36c83080e7d0aeb3fc6c01a1b1c03fcb3b5d10f9888ecdc9e051be5b7；原脚本在maxctx-allgpu-20261020/start-model-before.sh保留。新生产脚本仍无安装、诊断、自动杀进程或性能关缓存参数。

最终8011服务PID3699，实例11c57a2dd1067e49212097665cfb411cd0af61679cdf9451e692d3e908d8fcc7，health200；原生observer核实新容器/PID/启动时间/命令和监听归属。原生sanity16/16、四路并发，其中15项HF token再核对通过，视频匹配冻结native参考。证据04-runs/maxctx-sanity-20261020；当前部署指纹27581af3bea2ad94f559dd65da49bd84420a65ce0dcf8e4412bc253964ef4940。此前62项处理器零差异、36项聚焦测试为未变源码的历史验证，本轮未重复或冒充新增测试。

## 交付与限制

当前交付位于01-environment/delivery-maxctx及新容器内部/opt/minicpm-ocr-flagos，包含新启动脚本、配置、完整原源码补丁、依赖锁和恢复说明。allgpu-snapshot镜像包括已验证源码依赖，但早于本轮最终启动脚本/配置，最终镜像验证仍pending。没有提交、推送或创建PR。正式精度/性能、长上下文质量、TP8及64峰值并发未验证；既有CUDA不可见导入限制与pip依赖提示保留。旧部署和其控制快照保留，当前环境/适配/执行模式/sanity重新绑定新部署。
