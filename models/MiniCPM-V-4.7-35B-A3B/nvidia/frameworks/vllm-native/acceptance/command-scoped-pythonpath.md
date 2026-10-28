# H100-149：将 PYTHONPATH 限定于 vLLM 启动命令

2026-10-01；`MinicpmV4.7-35B-native` 容器，GPU 2/3、TP2、8020。
工作根在 Host/容器均为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native`。
检查时用户已调整根级 `start-model.sh`，当时 SHA-256 为
`512ec35a8a8c346cf4e3a725c6a253996bda5129ac293984f6920d9d3595285c`；
备份在 `02-issues/start-model-before-pythonpath-scope-20261001.sh`。
用户本次要求去掉 `export PYTHONPATH="$root/01-environment"`。

容器默认 `PYTHONPATH` 为 `None`，默认加载系统的
`/usr/lib/python3.12/sitecustomize.py`，不会自动加载工作根
`01-environment/sitecustomize.py`。因此不能在保留当前 Triton 进程隔离时
直接删除路径设置。本次只将全局 export 移除，并在原来的 `nohup vllm serve`
命令前写 `PYTHONPATH="$root/01-environment"`。vLLM 命令及其 worker
仍继承这个变量，脚本其余行未改。Ansible `--check --diff` 仅显示这两行
变化；当前 Host/容器脚本 SHA-256
`8243f7ce5faf16543941c633e305b7e4e29cb655a0bf0ea2a6f3d973eea58d48`，
权限 `0755`，容器内 `bash -n` 通过。

只停止已确认属于本任务的旧 8020 进程组 `1632956`，其成员为启动
shell、API、EngineCore 与两个 TP worker。GPU 2/3 清空后以新脚本启动；
其他服务和适配容器未操作。新 Host API PID/PGID `2815280`/`2815273`，
容器 API PID `33319`，TP worker PID `33928`、`33931`。
进程环境显示命令级 `PYTHONPATH` 和 `MINICPM47_TRITON_PER_PROCESS=1`；
独立 Triton 缓存目录位于 `06-cache/triton-processes/33928` 和 `/33931`。
生效的 vLLM 命令仍是用户的 262144 默认模型长度、8192 batch token、
0.85 显存比例、前缀缓存及 `FULL_AND_PIECEWISE`；未恢复 2048 上限或
编译 `mode=3`。prefill PIECEWISE 51/51、decode FULL 51/51 捕获完成，
`/health` 返回 200。

请求 `17+25` 在 `max_tokens=192` 时以 `stop` 结束，`content` 为 `42`；
较早的 `max_tokens=32` 请求因 reasoning 用尽额度而以 `length` 结束，
没有把它算作正确回答。成功响应保存为
`04-runs/pythonpath-scope-20261001/text-response.json`，SHA-256
`50b882e27b2bbd98ab5d6d86f4050305a5fa40cd71ca2d51294a1b8fec59ffdd`。
启动日志快照 `04-runs/pythonpath-scope-20261001/service-startup.log`
SHA-256 `44e724db90a67030679fb7a186bff4c4a6d579c1d7683654b05afddab6534513`。
部署身份 `01-environment/deployment-identity-pythonpath-scope-20261001.json`
SHA-256 `d72a91a0ff6140c3ae75f2a10a9d02881f845ad5a36db4ef88e70fe546cda40e`，
指纹 `04853be964c0768e8af1937e8f3d2ae3ea63185f7723608ce2a61e9326808426`。

`PYTHONPATH` 只是不再由脚本全局 export；vLLM 进程及其 worker 仍使用它。
要完全移除该变量，需为 worker 提供另一种同等的按进程缓存初始化机制。
用户当前脚本把持续日志写到工作根的 `service.log`，其他缓存沿用镜像默认
位置；本次遵守改动范围，没有调整这些路径。正式精度、性能和长期稳定性
未验证。
