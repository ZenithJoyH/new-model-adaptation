# Eager与图模式基础验证

2026-10-27，PPU-01 / minicpm-ocr-ppu-native，部署指纹 `95c2a90367feeb90fb704543a220c002557eb0d5c571ab95c83c698ec257ab58`。原始测量为批准根 `04-runs/execution-mode-20261027-final/measurements.json`。

最终冻结配置下，独立eager及graph各执行6类图像：默认4x、16x、关闭放大小图、自适应小图、切片、多图。每项prompt token IDs、生成token IDs和文本均与同权重Transformers参考一致。eager与graph分别6/6，生成token比较最大差异0。该指标不表示logits逐元素一致，也不是正式精度评测。关闭放大的极小图与参考一起识别失败，保持明确限制。

graph测试显式请求FULL，原生GDN后端实际回退为FULL_AND_PIECEWISE；测试进程直接记录6次capture_end、48次replay，6次模型推理。FULL的失败、能力声明、修复评估与退出条件见问题002；未跳到更低档位。最终根脚本显式选择该实际档位，并开启前缀缓存。

最终HTTP服务通过根脚本默认调用启动，配置32768/8序列/16384批次token/0.55，PPU4、TP1、8014。启动证据确认前缀缓存开启、prefill PIECEWISE与decode FULL捕获；文本请求及两帧MP4均HTTP200且视频识别出已知文字。证据 `04-runs/final-service/startup.log`、`extras-result.json`、`text-response.json`、`04-runs/video-final/response.json`。

早期一次就绪等待先于首次编译完成而退出，保留 `extra-not-ready-001.log`；服务随后正常就绪，没有为此重启。所有完整日志与结果留远端，不以早期未就绪记录声明通过。

本轮仅验证实际选定场景和设备。自由文本/Markdown参考有措辞差异；其他平台、TP/PP、量化、满上下文及满8路容量未验证。formal accuracy/performance和optimized均不适用于当前experimental profile。
