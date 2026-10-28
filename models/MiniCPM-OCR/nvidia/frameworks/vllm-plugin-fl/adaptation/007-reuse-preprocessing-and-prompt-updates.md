# 007：复用图像预处理与占位符生成

2026-10-20，H100-149，用户要求继续减少重复逻辑，保持文件职责并复验处理器零差异、eager/graph与OCR参考。原服务及映射、control.mode=agent、实际安装路径和源码哈希先行核实。现有Plugin HEAD a696859b9aa528dfd5b21f5da3403fdc16bac4cd；初次OCR差异已存在。FlagGems HEAD8200f71f5及attention修复、FlagGems-vllm HEADfa78ddee4、FlagTree0.7.0、vLLM0.24.0+empty和模型均保持。

## 重复点与设计

图像处理器为一处按像素选择source resize复制了父类的切片、归一化、patch打包与字段拼接主体；model.py又复制父类的视频帧尺寸提取和占位符发现。两处均属于OCR模型适配，可沿既有子类方法扩展，不涉及公共worker、dispatch、编译器或其他模型。

image_processing_minicpm_ocr.py从299行减至232行：普通请求直接调用父类_preprocess。需要OCR小图选项时按原图逐项处理，仅未切片图像的浅拷贝携带_source_resize，并由现有find_best_resize钩子消费；切片图不携带该值，refine语义不受影响。完整切片、归一化和patch打包由父类执行，子类只拼接返回字段，再做一次最终输出类型转换。保留调用级copy隔离，不以共享实例状态、按尺寸缓存或临时替换方法承载像素相关选择。同尺寸不同内容及并发测试确认没有参数泄漏。

model.py从353行减至335行：使用父类_get_prompt_updates发现占位符、选择视频处理后尺寸及生成视频回调；替换图像回调以继续依据实际target_sizes计算OCR token。使用dataclasses.replace保留父类对象字段，partial明确绑定每个回调；对父类文本返回值统一做token-ID编码和embedding选择。图像/视频参数仍分别解析，传入父类的视频模式不会覆盖图像回调；4x/16x混合分组、QKV加载标记和视觉模型主体均未变。清理复用后失效的导入。

本轮只改上述两个实现及原有tests/unit_tests/models/test_minicpm_ocr.py，新增7项参数化/并发回归，没有合并、新增或删除产品文件。模型目录生产Python总量825→740，净减少85行（10.3%）；从初次2054行算已减少64.0%。统计不包含测试和.so，不将新增测试行数混入生产缩减收益。

## 验证与证据

批准根/public/flagos/jinghao/MiniCPM-OCR/flagos，当前容器minicpm-ocr-flagos-runtime，ID9b0f522c5a7688c76053de8b34642370e4b9f885d6aa938cbd44967e6a3597ff。04-runs/dedup-20261020/before.json、before-product.tar冻结改动前源码；processor-case-plan.json与processor-before.pt冻结原安装处理器的62项输出。28项原有场景扩展至62项，覆盖RGB图像/视频、4x/16x、普通/原生/自适应选项、同尺寸不同内容、混合尺寸、pt/np/无转换、关闭切片与grouping选项。逐字段、shape、dtype和全部tensor/array精确相等，rtol=atol=0。NumPy快照由本任务生成，比较时仅加载该可信快照，不从替代源码导入。

原生JUnit36项（OCR19+融合包17），失败/错误/跳过均0；新增同尺寸不同内容批量、输出类型及并发选项隔离检查。结果见dedup-20261020/plugin-tests.xml。旧attention24项与CUDA不可见导入限制未重复测试；相关源码及完整算子清单核对未变，历史证据明确保留于source-converge-20261020，不能充当本轮新增测试。

eager与graph各15项真实请求生成token、prompt数、completion数及文本精确匹配独立HF参考（SHA-256 ed317a7e717c72d48987e5f7d6e555259b4d28609860c584260788e7240db360）；证据04-runs/dedup-{eager,graph}-reference-20261020/results.json。新代码重新从FULL启动，GDN仍声明UNIFORM_BATCH，实际回落FAP；19批piecewise、11个full-decode捕获，诊断日志运行计数{'FULL': 230, 'PIECEWISE': 3, 'NONE': 12}。没有跳级或修改vLLM来伪造FULL支持。

最终原start-model.sh实际启动新的FAP服务，原生sanity16/16、其中15项HF token再核对通过，视频按独立冻结native参考。当前容器API PID5895，service_instance_id=b90e75cd558f7851c5894b9f5817b47c3b6ade84ed7f782dfb71d933e26b35af；observer对PID、start_ticks、boot_id、命令及8011监听归属重新取证。health200，模型MiniCPM-OCR-FlagOS。证据04-runs/dedup-sanity-20261020/{service-observation.json,sanity-result.json,token-comparison.json,live-final-check.json}。

## 设计审查、生命周期与交付

审查对照真实HEAD、改动前dirty/untracked快照和当前完整补丁，PR base未由用户指定。继承的注册/config/几何、processor加载、混合模式及QKV修复均保留，FlagGems attention与_C未改。本轮影响只在OCR子类及既有测试；普通请求直接父类、特殊请求逐项调用父类，视频使用父类回调。实际H100/RGB/OCR验证范围可作为PR候选，未执行其他硬件或预计算embedding整模；无卡导入仍受既有设备发现限制，不声称CPU-only支持。没有共享源码特例、宽泛异常数值fallback、导入覆盖或依赖升级。

原服务保持到62项对照与聚焦检查成功，之后仅按PID/启动时间/命令确认的任务进程树切换eager、FULL诊断和最终FAP；停止记录原因已改为本轮去重验证。容器持续运行，其他工作负载未操作。控制器设有失败恢复原文件与最终服务路径，本轮未触发；原始停止/退出日志保留。

启动脚本及内部副本/opt/minicpm-ocr-flagos/start-model.sh SHA均46243791810967ddb0a3b6d5e860fe373990f443b771136b9e85859684b49622；参数、GPU宿主1/容器0、前缀缓存和缓存目录保持。新完整补丁、配置、依赖锁、RESTORE.md在01-environment/delivery-dedup及容器内部/opt/minicpm-ocr-flagos，required文件哈希见dedup-20261020/delivery-files.json。安装身份installed-identity-dedup-20261020.json，新部署指纹747aa6b0dabcc07a8047517573329b3cc05c6dda933bd5e749bc5524ed23c8ee。vLLM2449文件与模型权重重新核对不变。正式精度/性能和镜像打包未执行；旧恢复镜像不能替代当前交付。没有提交、推送或创建PR。
