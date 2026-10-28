# 012：同步 Plugin 主线及 OCR 源码交付

2026-10-21，用户要求更新当前容器 Plugin 到 flagos-ai 主线、复制到本机，并在 flagos-day0 的 support-minicpm-ocr 分支提交推送。本轮只处理 Plugin 源码；正式精度、性能、跨平台和镜像验收未选择。

## 源码与边界

H100-149，容器 `minicpm-ocr-flagos-public`（ID `7b125058368e142f4010df941e7020c3b26874a6552ec2a862a3286f9a6286f5`）。批准根 `/public/flagos/jinghao/MiniCPM-OCR/flagos`，主机与容器同路径，由完整 `/public:/public` RW 映射提供；8卡可见。实际 editable Plugin 位于镜像内 `/opt/vllm-plugin-FL`，没有通过 PYTHONPATH 选择其他副本。

更新前 HEAD `a696859b9aa528dfd5b21f5da3403fdc16bac4cd`，main 分支，origin 为 flagos-ai。原有 dirty 为 `vllm_fl/__init__.py`、OCR 模型包与测试，另有未跟踪的本机编译扩展。无其他源码变更。目标仓库无 AGENTS/贡献指南文件，已阅读实际 README、dispatch/集成说明、pyproject、测试入口、注册与调用实现；本次新增上游提交没有新的此类文件。

先备份现有 Python 源码及 tracked patch，再 fetch/ff-only 到上游 main `25eddf9a0616b08363e5c1553fc537e44ed4c81d`。上游新增 Ascend 注册前置 shim；仅将原4行 OCR 注册接在该 shim 后，保留双方逻辑。原 root 修改另保存在 Git stash `preserve-minicpm-ocr-before-main-20261021`。原 OCR 数值与几何实现不变。远端直接 GitHub DNS 失败后使用用户授权代理；凭据不写入源码/提交，临时本机 playbook 已清理。

本机源码：`/Users/baai/Documents/ChatGPT/vllm-plugin-FL`。origin 为 flagos-day0，upstream 为 flagos-ai，分支从已确认的 upstream/main 建立。容器与本机11个交付文件哈希全部一致。本机提交 `06014201f8ea8cd7092a56a945d8fc7998c5a46c`，标题 `feat: add MiniCPM-OCR model support`，父提交为上述最新 main；已推送至 [flagos-day0/support-minicpm-ocr](https://github.com/flagos-day0/vllm-plugin-FL/tree/support-minicpm-ocr)，GitHub branch API 与 git ls-remote 均核实远端分支指向 `06014201f8ea8cd7092a56a945d8fc7998c5a46c`；本机工作树干净。未创建 PR。

## 最终设计审查

相对最新上游仅11个文件、1033行新增：10个 Python 文件及 README。继承的 OCR 适配为主体，本轮新增仅 Transformers 能力守卫、对应测试、测试格式与使用说明。无 .so、权重、运行日志、代理凭据或机器绝对路径进入产品提交。完整 diff SHA-256 `33c676bcd93644271d2c5bf90689a32df8dcecac52f8be5bfdea8f82f25cf4cc`。

| 文件 | 必要职责与边界 |
| --- | --- |
| vllm_fl/__init__.py | 通过已有 general-plugin 入口调用 OCR 注册；保留上游 Ascend shim，未改公共调度与 backend 默认值。 |
| models/minicpm_ocr/__init__.py | 独立模型包标识，无导入时设备初始化。 |
| config.py | 继承 Transformers MiniCPM-V 4.6 config，补充 OCR model_type 与必要默认值。 |
| geometry.py | 图像、视频共享 OCR resize/grid 几何，避免重复计算逻辑。 |
| image_processing_minicpm_ocr.py | 复用上游切片、归一化、packing，补充 OCR 的4x/16x与按像素自适应缩放；调用副本防止并发选项泄漏。 |
| video_processing_minicpm_ocr.py | 复用上游视频采样与拼帧，仅提供共享 OCR 几何与逐调用模式。 |
| processor.py | 组合既有 tokenizer、图像和视频处理器并读取模板。 |
| registration.py | 使用 AutoConfig/AutoProcessor/AutoVideoProcessor、vLLM config/model registry；缺少 MiniCPM-V 4.6 能力时提前返回，避免影响旧 Transformers 上的其他模型。注册幂等，模型实现惰性导入。 |
| model.py | 继承 vLLM MiniCPM-V 4.6，补充像素相关占位符、混合 merger 分组及 fused QKV 权重名称；不复制语言/视觉骨干，不绕过算子派发。 |
| tests/unit_tests/models/test_minicpm_ocr.py | 注册重复/守卫两侧、已有注册保留、几何、逐调用选项、批处理数值与并发隔离。能力缺失测试仅隔离元数据，不 mock 数值。 |
| README.md | 记录安装/启动方式、版本与依赖修复、验证范围和未测限制，不分发二进制。 |

结论：可作为声明范围内的源码贡献候选。公共入口的影响由注册幂等、缺失能力守卫、8项已有模型类导入和实际新进程启动覆盖；没有增加厂商依赖、宽泛异常回退或试验残留。其他硬件无实机验证，不宣称通用验收完成。

## 验证与证据

原生产服务继续运行：GPU1/8011，API PID2257，启动 tick8980773；根 `start-model.sh` SHA-256 `9f72b8855063a038d2438fbc12e293ee5b9d6e06ad320559538fc4d7f0541d3d` 始终不变。没有重启该服务或容器，也未操作8000原生服务。

- 最终标准 pytest 入口：`python3 -m pytest -q --import-mode=importlib tests/unit_tests/models/test_minicpm_ocr.py tests/unit_tests/worker/test_model_imports.py`，28 passed（20 OCR + 8已有模型导入）。新主线原 OCR/fused-package 检查36 passed；其中17项 fused 算子测试对应本轮未变的实现。
- 同步前冻结62组图像/视频处理器输出，最终源码逐字段比较：tensor dtype/shape/value、NumPy、metadata 全部完全一致，rtol=atol=0。此处是同步前后处理器一致性，不是新checkpoint独立HF精度证明。
- 最终代码在空闲GPU2/8012先 eager 后 FULL_AND_PIECEWISE 启动，各6种固定请求×2轮，24请求均HTTP200、finish_reason=stop、OCR固定参考文本一致、token计数一致；12对 eager/graph 生成token完全一致。覆盖文本、4x/16x图、小图、双图和视频，最大长度配置262144、前缀缓存开启。仅停止本轮创建且核验PID/启动tick的诊断进程。
- 两个主线版本的24请求回归分别留存，最终注册守卫修改后已重新启动两种模式验证，不使用修改前的证据代替最终代码。
- 本机 Ruff 0.14.0 对测试及修改后的注册文件检查通过，git diff --check通过；其余产品文件保持原已验证实现。

所有路径下列相对批准远端根：

- `04-runs/plugin-main-sync-20261021/`：before.json、before-source.tar.gz、before.patch、vllm-before.json、processor-before.pt、processor-parity.json、plugin-tests.xml、final-unit-tests.xml、final-source.json及首轮服务日志/请求结果。
- `04-runs/plugin-main-sync-final-20261021/`：service-request-plan.json、eager/graph-process.json、eager/graph-service.log、eager/graph-results.json、service-summary.json、production-before/after.json及精确诊断进程清理记录。
- `03-acceptance/plugin-main-sync-parity-20261021.py`：62组处理器零差异工具。
- `02-issues/plugin-main-sync-*.py`、`plugin-final-*.py`：同步与隔离验证控制器；均不在产品仓库。

## 限制

当前生产8011进程未重启，仍持有更新前已导入的模块；新主线源码已由全新GPU2/8012实例验证。原部署观察指纹仅指此前人工启动的生产实例，不能代表本轮更新后的源码身份。正式阶段继续 not_started，不沿用旧权重HF精度、性能或长度边界结果。

现有依赖保留：FlagGems `8200f71f51d784d54a5a51019cb955acb74d64c1` 加已有 attention-mask 广播修复，FlagGems-vllm `fa78ddee4c3e78ce5047213ff0ef02acff34b2d5`、FlagTree0.7.0、Transformers5.12.1、Torch2.11.0+cu129、vLLM0.24.0+empty。本次不升级/提交 FlagGems 修复；该依赖限制在 Plugin README 披露。editable 的版本元数据仍来自原安装，实际主线身份以 Git HEAD 与文件哈希为准。未测试旧版 Transformers 的整套安装，仅验证能力缺失守卫和本机现有模型导入；未跑其他平台实机、TP、新checkpoint独立HF参考、完整262144边界、正式精度/性能或新镜像启动。

## 最终交付检查

`04-runs/plugin-main-sync-final-20261021/delivery-check.json`：11文件与本机提交相等；2469个vLLM安装文件逐一哈希及清单均未变；graph实际FULL286、PIECEWISE6、NONE10。NONE如实保留，不宣称所有请求均在图内。原8011又做6个固定请求全部成功，8011与8000 health均200。启动脚本哈希未变，8011未重启。

`production-six-requests.json` 保存生产请求响应；`installed-imports.json` 核实实际安装路径；`commit-manifest.json` 绑定本机提交/文件哈希；`evidence-index.json` 列出两轮原生产物SHA-256。没有提交本管理仓库的文档或无关改动。
