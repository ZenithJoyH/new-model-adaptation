# 直接安装插件与启动脚本精简（2026-09-04）

范围：PPU-13，运行容器 `glm5.3-flash`，GLM-5.3-Flash-BF16。

## 改动与边界

此前安装的 `vllm-plugin-fl` editable 入口指向
`/workspace/vllm-plugin-FL-hy4-preview`，服务通过 `PYTHONPATH` 指向专用插件。
用户要求直接安装适配插件，因此执行：

```bash
docker exec glm5.3-flash env -u VLLM_VENDOR python3 -m pip install \
  --no-deps --no-build-isolation --no-index \
  -e /workspace/vllm-plugin-FL-glm53-adaptation
```

仅更换插件安装入口，不更新依赖、不删除旧 Hy4 源码、不改 vLLM。
插件版本元数据为 `0.0.0+g265824413.d20260904`；真实代码基线和补丁
仍以 revision `265824413097126166b1072e1f564d00661a347a` 与原有四文件 diff 为准。

在 `/tmp` 中、清除 `PYTHONPATH` 与 `VLLM_PLUGINS` 后验证：导入路径指向专用插件，
platform/general entry points 自动发现，`PlatformFL` 激活，模型 config 可在
`trust_remote_code=False` 下读取。vLLM revision/status 验证通过。

从实际启动脚本移除 `plugin_dir` 临时变量、`PYTHONPATH`、`VLLM_PLUGINS`、
`--trust-remote-code` 和 `--distributed-executor-backend mp`。
保留模型 profile `VLLM_FL_CONFIG`：它包含 slice 等必要的 PPU 算子兼容配置；
保留 breakable graph 开关、capture 配置、TP16、50K、seq32、端口、模型别名及 parser。
没有通过把全部启动参数藏进新包装层来精简，也没有删除正在使用的算子修复代码。

原本检查显存默认值是否为 0.90，断言失败；实测当前 `CacheConfig` 默认是 **0.92**。
因此保留显式 `--gpu-memory-utilization 0.90`，避免此次精简改变资源基线。
该失败是默认值假设错误，不是插件自动注册失败；修正检查后通过。

## 可复现文件

- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-glm53-plugin-installation.yml`：安装入口与配置只读检查。
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/install-ppu13-glm53-plugin.yml`：无依赖变更的 editable 安装及注册/配置验证。
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/deploy-ppu13-glm53-launch-directory.yml`：校验旧文件后更新远端脚本；已执行 check/diff。
- `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/restart-ppu13-glm53-installed-plugin.yml`：核对旧 PID 123167，发送 TERM，
  等待 API/worker 退出，归档日志，再以无路径覆盖的新启动配置运行。

旧脚本与日志保留在容器 graph runtime 的
`start-before-direct-install.sh` 与 `service-before-direct-install.log`。
宿主机发布路径不变：`/mnt/nfs/users/jinghao/glm5.3-flash/`。

## 验证进度

直接安装后的独立进程注册/配置检查已通过。

- 新 graph PID 145798，09:40:35 服务就绪，PIECEWISE/FULL 各 6 档捕获完成。
- 最小推理 job `j675261207890.2371796`，09:40:55 完成，rc=0；最终答案 `2`，
  23 输入/51 输出 tokens，2.3109 秒（此前同请求 2.3154 秒）。
- 并发 8 job `j790165970920.2393416`，09:41:59–09:42:08，rc=0；8/8 正确，
  0 错误/超时，420 输出 tokens，8.8149 秒，47.6464 tokens/s；
  平均延迟 8.6378 秒，最大 8.8049 秒，8 次资源采样无错误。
  16 卡显存范围 88712–88744 MiB，平均利用率 36.5%–50%，峰值 100%。
  达到同一 sanity 阈值（全部正确、最大延迟 <60 秒、>=20 tokens/s）。
  本轮是重启后首轮并发检查，不能直接把它和旧服务热运行 71.86 tokens/s
  当作严格性能 A/B；旧服务首轮 33.51 tokens/s。未进行正式性能评测。
- 09:39:05 进程环境检查只有必要 profile 和 breakable graph 变量，没有
  PYTHONPATH/VLLM_PLUGINS；容器 RestartCount=0，vLLM/FlagGems 基线与插件 diff 不变。
- 原脚本与日志留存可回溯；未删除任何模型权重、旧插件源码或适配缺陷证据。

完整精度/性能验收仍未完成，本次不变更这一结论。

## 后续：默认 PPU 配置与纯推理启动脚本

用户确认将已验证配置放入默认目录。2026-09-04 将
`examples/glm5_next/thead.yaml` 原样复制到
`vllm_fl/dispatch/config/thead.yaml`，没有修改 Python 加载器；现有 editable 安装立即可见。
该配置现在是此专用插件的 PPU 平台默认值，不仅对 GLM 生效。
SHA256：`428364828d7062b9b80123f10e0e9fb21ab286878dc3c36c92e3d51a137a48ee`。

09:52:58 独立进程在没有 PYTHONPATH/VLLM_PLUGINS/VLLM_FL_CONFIG 时通过：
自动路径识别、与原 profile 内容逐项一致、slice 黑名单及设备 slice 操作回归。
对应命令：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/install-ppu13-glm53-default-profile.yml`。

`start_glm53_graph.sh` 删除 runtime_dir、VLLM_FL_CONFIG、PID 写入和日志重定向，
只保留必要 graph 开关和推理命令；它在容器内前台运行，日志写到标准输出。
`start_glm53_graph_host.sh` 负责后台启动、防重复检查和日志/PID 管理，目录仍是
容器 `/workspace/glm53-adaptation-runtime/graph`，不影响模型加载。
两个宿主机脚本保持在 `/mnt/nfs/users/jinghao/glm5.3-flash/`。

旧服务 PID 145798 的重启步骤与归档见
`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/restart-ppu13-glm53-default-profile.yml`；本轮整模回归已通过，结果见下文。

宿主机入口首轮失败：`docker exec -di ... bash -s < script` 的后台执行没有
读入重定向的脚本，PID 随后退出，日志为空，8010 未监听；不是模型或 YAML 错误。
改为 `docker cp` 纯启动脚本到既有 runtime 后，`docker exec -d ... bash start.sh`
按文件执行；记录 PID 和日志的外层 shell 使用 exec，避免 PID 指向已退出的父进程。
修复与重试见 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/start-ppu13-glm53-host-file-launcher.yml`，没有忽略失败检查。

最终服务 PID **158392**，09:59:25 API 就绪，10:00:55 仍正常提供 50K 模型服务。

- 最小请求 job `j649399829307.2755644`，09:59:44 完成，rc=0，content 精确为 `2`，
  23 输入/51 输出 tokens，2.2982 秒；与此前 2.3109 秒基本一致。
- 同一固定并发 8 job `j409560991110.2779258`，10:00:50–10:00:54，rc=0，
  **8/8 正确、零错误/超时**；422 输出 tokens，4.0104 秒，105.2267 tokens/s，
  平均延迟 3.8383 秒，最大 4.0004 秒，所有 sanity 判据通过。
- 4 次资源采样无错误，16 卡显存 88720–88760 MiB，平均利用率 48.5%–64.5%，
  峰值 100%。这是小样本 sanity，不将波动归因于配置位置变更或宣称性能优化。
- 09:56:59 验证新进程仅保留必要的 VLLM_USE_BREAKABLE_CUDAGRAPH，三个路径/加载
  覆盖变量均不存在；容器 running/restarts=0，vLLM/FlagGems 原 revision 与 status 不变。
  插件除原四文件 diff 外新增默认 YAML，故其 SHA256 单独记录，不能只看 git diff hash。
- 主脚本 SHA1 `71c4b024f30a11bb72ab4987becfe5113343352d`，宿主机入口 SHA1
  `2a10c60a39d740725c2618de5f08f00e44389846`；远端内容、0755 权限和语法验证通过。
