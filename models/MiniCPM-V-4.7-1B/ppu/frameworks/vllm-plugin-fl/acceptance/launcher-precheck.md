# 用户修改后的启动脚本验证（历史实例，非正式 summary 验收）

2026-10-01，目标 Host `PPU-13`，容器 `minicpmV4.7-1B`。本次直接验证用户修改后的 Host/容器同一路径 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/start-model.sh`，未改写脚本。Host 与容器映射设备号 `41`、inode `12346634685`、权限 `0755`；SHA-256 均为 `b8248ed0dcf1775b0e6840713568bc4e693c1287b0e47a850d1269b996b992a7`，容器内 `bash -n` 通过。脚本使用 `nohup vllm serve`，显式绑定 PPU2、监听 `127.0.0.1:8000`，模型为 `/mnt/cpfs/models/MiniCPM-V-4.7/weights/1b`，模型名 `minicpm-v-4.7-1b-ppu`，前缀缓存开启，图模式 `FULL_AND_PIECEWISE`。

切换前，原任务服务 PID `216706` 在 `8327` 健康。对其启动 tick、命令哈希、子进程、无运行/等待请求、当前脚本 SHA 和新端口空闲做精确检查后，发送 SIGTERM；确认原进程及子进程退出、`8327` 不可用。停服回执为 `04-runs/user-launcher-test-20261001/stop.json`。适配容器未停止或重启。对启动 Ansible Playbook 做单 Host `--check --diff`，并确认 `service.log` 原先不存在，随后执行用户原脚本。仅返回的 shell 成功不能证明模型启动，因此另查原始日志、API 和请求。

新 API PID `246468`、启动 tick `353055612`、命令 SHA-256 `0dca7546324b1248b370e6586bfdc3bfbc987af2fa49bbcba78ab701b81e77c9`。有效配置为 TP1、BF16、`max_seq_len=262144`、前缀缓存 true、`FULL_AND_PIECEWISE`；mixed prefill-decode PIECEWISE `51/51`、decode FULL `51/51` 捕获成功。引擎初始化日志耗时 `474.17` 秒；API 启动完成，`127.0.0.1:8000/health=200`。vLLM 编译缓存写到容器默认 `/root/.cache/vllm/torch_compile_cache/`。启动后 `ppu-smi` 显示 PPU2 占用 `94283/98304 MiB`，仅余约 4 GiB；这是该默认容量配置的资源余量限制。

不计分连通性检查向当前 API 发送一条文本和一张 224 像素图片，均 HTTP 200、产生 completion token，前后健康检查均为 200 且服务进程身份不变。回执 `04-runs/user-launcher-test-20261001/smoke-result.json`，SHA-256 `6fef16275abdaf89fce24775231e520128e99c562a33b5f42ef63fd48c87d7b8`，`formal_accuracy=false`。本次没有运行精度或正式性能测试。

用户脚本把日志写到工作根目录的 `service.log`，没有按项目约定放在 `04-runs/`；该文件为运行中服务持续写入，本次验证未移动或改写。脚本也未保留端口/显存预检，并由 `nohup` 后台启动，调用脚本返回时不能判定服务就绪。本次靠外部精确预检及独立 API 验证控制切换。当前 `FULL_AND_PIECEWISE` 不满足 profile 正式 `full` 或 `decode-full` 图级别，不能据此签发最终 summary 通过回执。正式精度此前未过门槛，用户要求暂停精度测试；性能和 summary 仍未验收。

后续状态（2026-10-01）：用户又修改根目录脚本，当前 SHA-256 `0bb6618fa01fe65536fea9c407dca9c92b85d737325d6fb62af069ee418c0f12`；上述 PID `246468` 的启动验证不再代表当前服务。随后另一实例在精度负载下发生 PPU 非法页，API `8000` 已退出，见 [问题 006](../adaptation/006-gdn-index-invalid-page-under-accuracy-load.md)。

## 2026-10-03 当前脚本复核

目标仍为 `PPU-13` 的 `minicpmV4.7-1B`，Host/容器同路径 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B/start-model.sh`。旧脚本 SHA-256 `9cf99b5cc88914a60bef0a991ad8bae7110d0afd9a186257a6a1a01c89375ebe` 经核对后备份于 `02-issues/mmlu-corruption-boundary/start-model-before-atenoff.sh`；只将算子设置改为 `VLLM_FL_FLAGOS_WHITELIST=attention_backend`、日志改入 `04-runs/`，当前脚本 Host/容器 SHA-256 `baee3f4658befa9598b81104d5c30fcd51601cefb2b5be5b6e1e428e7da219f9`。容器 `bash -n` 通过。容器映射、实际命令和物理 PPU2 已复核；服务端未显式加 `--max-model-len`，前缀缓存仍开启，图级别为用户要求的 `FULL_AND_PIECEWISE`，有效 mixed PIECEWISE/decode FULL。

先检查 `8000` 端口空闲，再执行脚本。2026-10-03 API PID `351457`、EngineCore PID `351962` 启动成功；`/health=200`、`/v1/models` 返回 `minicpm-v-4.7-1b-ppu`，短题结果在 `04-runs/start-model-atenoff-verification-20261003/probe.json`，回答连贯。当前日志 `04-runs/service-atenoff-20261003T082546Z-351451.log`；有效 oplist 仅 `default.flagos` attention。该脚本可正常启动且完成基本推理，容器未停止；诊断评测的 700 题结果见 [全科报告](mmlu-pro-atenoff-limit50-20261003.md)。它仍不是已完成的正式 summary 验收脚本，因为 profile 的正式图级别与 GPQA 精度尚未通过。
