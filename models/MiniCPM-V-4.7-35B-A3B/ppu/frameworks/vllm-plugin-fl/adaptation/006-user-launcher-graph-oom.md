# 006：去掉并发上限后图捕获在 TP1 显存耗尽

## 元数据

- 日期：2026-09-30；状态：`mitigated`，七个指定图尺寸已通过启动和基本推理验证；脚本的独立运行边界仍待完善。
- 模型 / Host / 容器：MiniCPM-V-4.7-35B-A3B / `PPU-13` /
  `minicpmV4.7-35B`；镜像、Plugin、FlagGems 与 vLLM revision 见
  [环境分析](../environment/README.md)，本次未修改这些组件。
- 模式：TP2，设备 0、1，`FULL_AND_PIECEWISE`，前缀缓存开启；仅启动和
  基本服务恢复检查，未运行正式精度或性能。

## 问题现象与证据

用户编辑后的根级 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`
SHA-256 为 `0a9af9c6844ae85ce8dc908588f186acd404187d070a6b0963f9371fa410e599`。
已在容器中 `bash -n` 通过；精确副本在
`04-runs/start-model-user-edit-20260930/start-model-under-test.sh`。测试从批准的
`04-runs/start-model-user-edit-20260930/` 作工作目录，使脚本的相对
`./service.log` 留在 `04-runs/`，并通过启动环境提供 `XDG_CACHE_HOME`、
Triton、Torch、vLLM、FlagGems、`TMPDIR`、禁写 `.pyc` 等既有写入边界。
不提供这些边界时，脚本不能独立满足本项目的远端产物规则。

新脚本省略了 `--max-num-seqs 8` 与编译 `mode=3`。安装的 vLLM
`config/scheduler.py` 的 `DEFAULT_MAX_NUM_SEQS` 为 128；实际 EngineCore
仍自动选择 `VLLM_COMPILE` mode 3，并保留
`cudagraph_mode=FULL_AND_PIECEWISE`、`enable_prefix_caching=True`。
但图捕获范围从此前最多 16 的 PIECEWISE 5/5、decode FULL 4/4，
扩大为最多 512 的 PIECEWISE 51 组。TP1 在混合图 47/51 时于 PPU Triton
benchmark 的 256 MiB 分配处报 `torch.OutOfMemoryError`：GPU 1 为 96 GiB，
当时仅余 304.40 MiB，进程占用 95.74 GiB，PyTorch 已分配 93.83 GiB。
API 未完成启动，`/health` 无法连接。原始日志
`04-runs/start-model-user-edit-20260930/service.log` SHA-256
`8b1d79b4cc62f54e9be6c083eb94e20939902ea38a74ef417b301c3e91a79cb8`。

## 诊断与受控比较

| 配置 | 实际编译和图模式 | 混合图捕获 | 结果 |
| --- | --- | --- | --- |
| 上一版，`--max-num-seqs 8` | mode 3，`FULL_AND_PIECEWISE` | 5/5，最大尺寸 16 | 就绪并通过文本、图片基本请求；见[精简版记录](../acceptance/launcher-minimal-20260930.md)。 |
| 用户编辑版，未指定最大序列数 | mode 3，`FULL_AND_PIECEWISE` | 47/51 后 TP1 OOM，最大尺寸 512 | 未就绪。 |
| 恢复上一版，`--max-num-seqs 8` | mode 3，`FULL_AND_PIECEWISE` | 5/5，decode FULL 4/4 | `/health`、`/v1/models` HTTP 200；文本 `42` 正常停止。 |
| 根级脚本仅新增 `cudagraph_capture_sizes=[1,2,4,8,16,32,64]`，仍使用默认最大序列数 128 | mode 3，`FULL_AND_PIECEWISE`，前缀缓存开启 | PIECEWISE 7/7，decode FULL 7/7，最大尺寸 64 | `/health` HTTP 200；文本 `42`、红色单图 `红色` 均正常停止；无启动期 OOM。 |

编译 mode 的显式与缺省写法在这台 Host 上解析到相同生效值；这不是本次 OOM
的证据。新对照保持默认最大序列数 128，只缩减启动期图捕获尺寸，即可正常
启动并完成基本推理；因此这次 OOM 更具体地关联到此前最多 512、共 51 组的
图捕获规模，不能归咎于默认最大序列数本身。尚未验证超过 64 的实际序列数、
高并发负载或性能，不据此推断这些场景稳定。

## 处理与边界

失败 API PID `1192200`、EngineCore `1192680`、TP0/TP1 `1192971`/`1192972`
均经模型命令和进程身份核对。对 API 发 TERM 后，两轮限时检查仍显示四进程
未退出；随后仅对这四个确定的本任务 PID 发 KILL，确认全部退出。
适配容器未停启，当时未改用户根级脚本。以
`04-runs/start-model-user-edit-20260930/last-known-good.sh`
（SHA-256 `e486d32980a24d7cb3607abd7015783cf7dd9f0bd0f4005c6ba7a314250c1a04`）
恢复上一版服务；API PID `1218143`。恢复日志不可覆盖快照
`04-runs/start-model-user-edit-20260930/recovery-startup-and-smoke.log`
SHA-256 `36b54b4bdad73457a15f2a735b8bf9f5f89d4ce70a4be87f6241325e31a53338`。
随后按用户指定，在根级脚本的编译配置中仅增加七个捕获尺寸，保留其他用户
编辑。Host 与容器路径均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/start-model.sh`，新 SHA-256
`4051002a7e813e81efc71123a5adf5db7c4ba62c44bb9844824d69ae0a258750`，
权限 0755，容器内 `bash -n` 通过。安装前 `--check --diff` 确认仅改这一行。
核实恢复服务 API、EngineCore、两名 TP worker 的 PID 后，只停止了该服务，
没有停启容器。新服务由根级脚本启动，实际 EngineCore 配置确认七个指定尺寸、
`max_cudagraph_capture_size=64`、`FULL_AND_PIECEWISE` 和前缀缓存开启；
启动及冒烟日志快照位于
`04-runs/start-model-seven-graphs-20260930/startup-and-smoke.log`，SHA-256
`5804fa268d7709fe4e4f480d451186f7cd215d58a5365c73bc10790c37dbfffb`。
文本、图片结果分别位于同目录的 `text-full-smoke.json`（SHA-256
`64dcf2ecd5ed1fcaab51649ea7d8745f3e7a0b2b0b28ef0c34e6256079b3f99a`）
与 `image-full-smoke.json`（SHA-256
`a96df544061c48ec31c05536959e5f2feafc85044b472fd9c902d522dde4125b`）。
复验后 PPU 0、1 各用 91,276/98,304 MiB；服务继续运行。

此次测试从批准的 `04-runs/start-model-seven-graphs-20260930/` 作为工作目录，
并由启动环境注入缓存及临时目录边界。脚本仍使用相对 `./service.log`，自身
不设置这些缓存边界，因此验证结论以该启动环境为条件，不能认定为可在任意
目录独立运行的最终生产脚本。未执行正式精度或性能；当前 piecewise prefill
仍未满足 profile 的正式图覆盖验收要求。
本问题不涉及 Plugin 产品代码或 FlagGems 同步，暂不推广为跨平台知识库条目。
