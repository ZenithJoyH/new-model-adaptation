# MiniMax-H3 结构与推理链路摘要

当前已核链路为Qwen3-VL前50层文本conditioner → 联合音视频DiT → 独立视频/音频VAE。flat变体使用transformer与本地text_encoder/tokenizer/processor/vae/audio_vae资产，文本条件为逐token的5120维hidden；默认生成任务t2av。

历史mx-57 FULL-001在TP4×SP2/textTP8、BF16 mixed、544高×960宽/124帧/29步完成离线功能运行，原证据位于/public-flash/jinghao/minimaxH3-dependencies-20261116/04-runs/FULL-001。原64²质量失败与SP数值差异仍保留，不据此声明独立模型数值精度或正式性能。

HTTP-001实际复用原生内存任务队列：rank0 HTTP处理线程提交任务→native广播至八rank→专用H3ServerRunner在各rank实际run_request线程进入H3OperatorPolicy→原resident runner完成DiT/VAE→rank0保存媒体并提供状态/下载。两次任务已完成且PID/startticks与每rank单次加载身份稳定；当前HTTP逐step native/cache/device时窗、运行时Policy退出恢复、rawtensor和Torch高水位仍未观测，不能用旧FULL证据补齐。

本摘要沿既有CAP/FULL及本次有界service合同，不代表重新验证全部结构或profile architecture阶段passed。上游权重完整payload校验和精确下载revision未核；64²失败及SP数值差异继续保留。
