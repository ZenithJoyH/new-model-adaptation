# 005：FlagTree安装与服务复验

2026-10-20，用户追加要求在现有适配容器安装FlagTree。目标仍为H100-149的minicpm-ocr-flagos-runtime，ID9b0f522c5a7688c76053de8b34642370e4b9f885d6aa938cbd44967e6a3597ff，工作根/public/flagos/jinghao/MiniCPM-OCR/flagos，实际RW/RO挂载重新核实。

按官方NVIDIA/Triton3.6安装说明选择FlagTree0.7.0官方Python3.12 wheel（388.3MB），SHA-256 a660cf03397b6cf6825d23f089b92d3c3894e4e2796e877aad5200863be0de75。下载完成后才停止准确绑定的本任务8011进程树，保留原Triton安装归档05-tmp/triton-before-flagtree-20261020.tar，pip卸载triton后无依赖安装该wheel。没有路径覆盖、复制第二套导入源或修改vLLM/Torch包；容器持续运行。安装、wheel元数据、包依赖及进程转换证据在04-runs/flagtree-install-20261020/。

实际FlagTree 0.7.0，triton API 3.6.0，路径/usr/local/lib/python3.12/dist-packages/triton/__init__.py。GPU eager计算、一次graph capture和两次改变输入的replay通过。随后eager15/15参考token完全一致；重新尝试FULL，实际同一GDN UNIFORM_BATCH能力阻塞，源码未变；诊断引擎有效FAP，19批piecewise/11个full-decode捕获，运行时FULL 229次、PIECEWISE 3次，保留NONE计数，不声称所有prefill均入图。对应15项生成token、prompt和completion数精确匹配冻结独立HF参考。

随后显式FULL_AND_PIECEWISE最终根脚本实际重启，项目原生sanity runner并发4验证16/16文本、图像、视频；其中15项独立HF生成token及prompt数再次核对一致，视频对照单独native参考。最终API PID15623、服务实例123b201221985b2f04e531dc5b6d450ee544083131a03401e1702c86d2eeaebe以原生监听观测绑定。原始产物04-runs/flagtree-sanity-20261020/，不是用旧编译器结果替代新验证。

新增的FlagTune默认缓存配置为FLAGTUNE_MODEL_CACHE=<工作根>/06-cache/flagtune_models；首轮诊断没有可用H100预训练调优模型时按库默认回退，没有以关闭FlagTree或算子黑名单处理。最终根脚本和/opt/minicpm-ocr-flagos/start-model.sh SHA-256均为46243791810967ddb0a3b6d5e860fe373990f443b771136b9e85859684b49622。必要配置、源码补丁、依赖锁和恢复说明更新到01-environment/delivery-flagtree与容器内部/opt/minicpm-ocr-flagos；旧材料不覆盖。

pip check新增的Torch/humming-kernels/xgrammar缺triton发行包提示来自FlagTree包名与其triton模块名称差异；实际模块导入、GPU及整模验证通过，未伪造发行元数据。基镜像NIXL冲突仍保留。原始冷编译耗时/诊断超时和FULL能力限制留作历史，未声称性能优化；正式精度、性能及最终镜像验证仍未选/待安排。
