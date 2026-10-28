# 006：源码安装与 OCR 适配收敛

2026-10-20，用户要求两个算子库源码安装，并收敛Plugin适配。H100-149，当前容器/工作根与RW/RO映射已核实；源码边界为/opt/vllm-plugin-FL、/opt/FlagGems、/opt/FlagGems-vllm，vLLM、Transformers和权重只读。实施前两个算子源码HEAD分别8200f71f5、fa78ddee4且干净，Plugin已有本任务OCR差异与原生_C生成项；before.json和before-product.tar保留原状态。

## 源码安装

原来从源码构建为普通安装，导入site-packages副本。现在两个库都通过各自PEP517/660构建做editable安装，direct_url=true，实际FlagGems路径/opt/FlagGems/src/flag_gems/__init__.py、FlagGems-vllm路径/opt/FlagGems-vllm/src/flaggems_vllm/__init__.py，没有PYTHONPATH覆盖。保留原提交与所有修复，没有获取不同分支或用另一份源码绕过。FlagGems-vllm Git树仍干净。

此前安装目录中的attention广播stride修复迁至/opt/FlagGems/src/flag_gems/ops/attention.py，SHA-256仍56093425822bf1518ea65e19586885ca4c64526e0f4e5c04ca4130119da61850，未改变算子逻辑；24项维护测试迁入/opt/FlagGems/tests/test_attention_mask_broadcast.py并重新通过。隔离构建使用该仓库声明的setuptools/scm版本约束，运行时Torch、FlagTree、Transformers和其他组件不变。

## Plugin 收敛设计与结果

模型目录生产Python代码从2054行降至825行，减少1229行（59.8%），统计不含测试和_C二进制。当前逐文件行数、完整源码补丁和设计审查见code-size.json、source-review.json及01-environment/delivery-source/source.patch。

- geometry.py：图像/视频两个真实调用方共用OCR的4x/16x网格和行列选择语义，不增加通用注册或执行框架。
- 图像处理器：继承Transformers MiniCPMV4_6ImageProcessor的默认字段、裁切/细化/patch辅助逻辑；只保留OCR自适应像素判定、小图resize和调用级参数隔离。上游缺少像素相关resize钩子，专用_preprocess仍必需，未为行数牺牲可维护性。OpenCV按需加载。
- 视频处理器：继承现有完整流程，仅保留OCR网格、默认4x和调用级模式隔离，不再复制采样、打包、标准化和重排主体。
- vLLM适配：继承现有process_images/process_videos与视觉结果拼接，保留逐模态参数、actual target_sizes占位符、混合4x/16x分组及必要QKV已加载标记。HF行列在vLLM接口边界显式转换，复用基类视频prompt格式。去掉未被基类调用的_drop_vision_last_layer、重复处理层、无用导入和过时注释。
- config/processor/registration：仅保留OCR默认值、当前Transformers缺少原生OCR类时的显式加载、以及现有Auto/ModelRegistry注册。无模型路径分支、共享worker/dispatch修改、黑名单、数值回退或吞异常。

## 验证与审查

改动前实际安装处理器冻结28项RGB图像/视频输出，覆盖矩形/方形切片、4x/16x、默认/原生尺寸/自适应小图和视频帧选项；改动后逐字段、逐tensor零容差一致，且调用参数不泄漏回共享实例。12项OCR接口与17项融合包真实GPU集成共29项通过；维护的functional conftest通过os._exit省略终端总结，另用原生JUnit确认29项、0失败/错误/跳过。CUDA不可见时的额外导入检查受既有FlagGems设备发现限制而未通过；确认在OCR注册前失败，相关共享源码未改。H100可见设备下重复注册接口测试通过，不声称CPU-only支持。attention24项通过；因测试使用-c /dev/null避免额外源码路径注入，保留attention标记未注册的1项pytest告警，不影响结果。

真实模型eager15/15和graph15/15生成token、prompt与completion数精确匹配独立HF参考，含四路混合请求。新环境重新尝试FULL，GDN仍为UNIFORM_BATCH；实测有效FAP，19批piecewise/11个full-decode捕获，运行时FULL 229次、PIECEWISE 3次，保留NONE计数。显式最终FAP脚本重新启动，原生sanity16/16及其中15项token复核通过，实际PID22126，服务实例17082eef790b49383c7cbb0c3249ea428654fb097eaf0cb4deaf2eac2d856924。

本轮设计审查以实际HEAD加未暂存/未跟踪差异为准，同时区分继承的初次OCR代码与本轮缩减；PR base未由用户指定，没有假设合并基线或创建PR。当前H100/RGB/OCR范围可作为PR候选，其他硬件、预计算图像embedding整模、任意额外媒体格式及正式精度/性能未验证。没有提交/推送或改写历史。

完整原始证据在04-runs/source-converge-20261020、source-*-reference-20261020及source-sanity-20261020。最终补丁、配置、requirements.lock、RESTORE.md位于01-environment/delivery-source及容器内部/opt/minicpm-ocr-flagos。旧交付材料保留，镜像打包/新镜像验证仍待安排；不标记optimized或完整profile验收通过。

生命周期取证：本轮复用前一轮已审阅的进程身份校验函数，停止记录的通用reason文本仍提FlagTree；本轮实际操作目的为源码安装/适配收敛，未再次更换编译器。各stop文件的PID、命令、启动时间及source-*运行路径均与本轮process.json相符。退出时的SIGTERM/EngineDead日志原样保留，最终服务为另起的已验证实例。
