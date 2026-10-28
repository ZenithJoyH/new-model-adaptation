# 003：与父目录启动参数对齐

2026-10-27，用户要求原生启动参数尽量对齐 PPU-01 的 `/mnt/nfs/users/jinghao/MiniCPM-OCR/start-model.sh`。参考脚本SHA-256为 `56d0ab9debf95cb6ba742b77bea5b97a217e5b4d3465d872a9968b8bb112e4fa`。

## 限定变更

仅改当前任务启动配置，不修改任何产品源码、权重、依赖或参考脚本：上下文32768→262144，max-num-seqs 8→64，视觉注意力显式选择TORCH_SDPA；删除额外固定的max-num-batched-tokens=16384，使用API服务默认值并在现场核对。显存比例0.55、前缀缓存开启、图像4/视频1、FULL_AND_PIECEWISE和权重路径保持对齐。

保留原生服务的PPU4、8014和MiniCPM-OCR-PPU-native，避免占用当前FlagOS服务的PPU2、9999及模型名。原生不加载VLLM_PLUGINS=fl或FlagGems专用环境变量。nohup和日志重定向留在启动操作中，最终脚本仍只含必要服务命令与缓存分支。

修改前验证新容器仍为c7761d51…、持续运行，Host/容器根同为批准的ppu-native且device:inode仍为41:15135181180，control.mode=agent。只SIGTERM本任务已核实的39469 API；没有停止容器或其他服务。原脚本、部署身份、交付材料和参考脚本保存在批准根 `01-environment/parameter-alignment-20261027/`，原验收verification保留到framework.yml的control.history，不套用于新部署。

## 验证计划与边界

已确认本镜像MMEncoderAttention及CUDA平台支持TORCH_SDPA。按新262144/64/0.55配置重验真实权重eager和FULL_AND_PIECEWISE、直接capture/replay计数及6类OCR参考；默认正常缓存开启。保留已证实的FULL后端UNIFORM_BATCH阻塞，不重新声称FULL通过。然后用同一更新后的根脚本启动最终API，重新绑定服务并运行冻结5例sanity、文本/视频和64路短请求检查。

仅配置最大上下文不代表满长质量通过；64路短请求也不证明64路满262144上下文。正式精度/性能和新镜像验证仍未执行。

## 已完成的模型与源码复核

新配置eager和FULL_AND_PIECEWISE均6/6匹配独立参考的prompt及生成token IDs，差异0只指该冻结OCR集合，不指logits。图进程直接计数538次capture_end、98次replay；原始结果 `04-runs/aligned-eager-20261027/`、`aligned-graph-20261027/`。源码11文件及权重文件SHA复核未变；现有GDN源文件仍声明UNIFORM_BATCH，视觉改用TORCH_SDPA不改变该FULL限制。证据在 `01-environment/parameter-alignment-20261027/graph-capability.json`。

本次改动没有新增/删除产品文件，无新的Git/PR操作。对齐参数及脚本分支已审阅，保留最小正常启动与显式性能缓存分支；后续API身份、小集合和并发结果单列于本轮验收记录。
