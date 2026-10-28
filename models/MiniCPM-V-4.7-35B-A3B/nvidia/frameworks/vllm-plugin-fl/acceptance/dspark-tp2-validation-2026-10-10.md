# 35B-A3B DSpark 双卡服务验证（2026-10-10）

## 精确范围

H100-149，当前容器 `MiniCPMV4.7-1B-DSpark-gpu6`，ID
`a650538a4c01fe79d59d0bbacac4edc4cec52046e1072f3255f56c0161f23b11`。
容器本轮始终运行、restart count 为 0，全部 8 张卡仍映射。
本服务仅使用 GPU6、GPU7；1B 服务仍暂停。
vLLM 0.28.0、Plugin `0.4.0.dev0+ge88e4db`、FlagGems `5.4.0.dev0+g0dddb462`，
实际安装路径和继承源码变更见[010](../adaptation/010-dspark-tp2-default-context.md)。

宿主根 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos` 已核实映射为 `/work`。
以下远端证据均使用唯一标签 `dspark-35b-tp2-20261010092547`；它们不是正式评测回执。

## 启动器及有效配置

| 项目 | 已验证值 |
|---|---|
| 物理设备 | GPU6 `GPU-21b327d9-c547-49e9-25e6-58c785af00d6`；GPU7 `GPU-d508af44-d081-7d8d-0ebe-1a2d15266369` |
| 并行/序列数 | TP2；`max_num_seqs=64` |
| 每批 token | 删除显式参数，H100 API 默认值及启动日志均为 8192 |
| 最大长度 | 删除显式参数，模型配置、引擎日志和 `/v1/models` 均为 262144 |
| 执行模式 | `FULL_AND_PIECEWISE`，默认尺寸，最大 capture token 数 512 |
| DSpark | `/work/06-cache/dspark-35b-weights/draft`，14 speculative token |
| 主模型 | `/work/06-cache/dspark-35b-weights/main` |
| Prefix cache | 开启，无性能专用禁用参数 |
| 服务 | `127.0.0.1:18349`，`MiniCPM-V-4.7-35B-A3B-DSpark` |
| API/worker PID（容器） | 5753 / 6733、6804 |
| Worker PID（宿主） | 1065455、1065959，NVML UUID 与上述物理设备逐项对应 |

内部实际启动脚本 `/opt/flagos/dspark/start-35b-model.sh`，SHA-256
`d126721db2dfd4a5008f11d5a5b65d5c97b1410c7c63ad48f45d0799bdac98aa`。
宿主用户脚本 `/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/start-dspark-35b.sh`
对应 `/work/start-dspark-35b.sh`，SHA-256
`db6ecd772e18a1ed8146c40a89fa881117cf8fe2c22c41c2d515a4a689561f29`。
两份脚本参数一致，分别保留内部 `exec` 与用户 `nohup`、后台运行、相对日志的差别；
内部脚本已实际启动，宿主版本通过语法和参数核对，未同时另开第二服务。

本轮保留 GPU memory utilization 0.94、单图/禁用视频的既有范围。
必要的新环境变量 `FLAGOS_KERNEL_CACHE_BASE` 启用两类缓存的逐进程隔离；
两次先前失败、触发证据、内部 `.pth` 路径/哈希和缓解退出条件见 010。
该钩子和内部启动器位于镜像可包含的容器层，没有 `PYTHONPATH`；
新镜像打包及 fresh-container 验证未执行。权重仍使用用户先前授权复制的外部 `/work` 输入。

## 实际结果

- Health 200；模型列表默认长度 262144；最终进程参数 TP2、64 序列，两个旧长度/批次参数不存在。
- 主模型分段图 51/51、解码全图 33/33、DSpark 全图 34/34；每 rank 图内存 2.07 GiB。
- 9 项串行测试全部正确：文本、算术、红/蓝/绿/黄图、重复红图、变输入与多轮记忆。
- Barrier 同时释放 64 客户端，64 个不同算术请求全部正确且正常结束；总计 73/73，工具退出码 0。
- DSpark 累计 94 次 draft、1316 draft token、164 accepted token；验证后 running/waiting 均为 0。
- 最终服务日志没有 ERROR；API 和两个 worker 存活。NVML 核实每卡 worker 占用 79514 MiB。
- vLLM、Plugin、FlagGems 完整 `.py/.so` 前后指纹一致，版本未变；1B 启动器未变。

## 证据及限制

容器证据路径（宿主以已核实的根替换 `/work`）：

- `01-environment/<标签>/components-before.json`、`components-after-config.json`、`component-comparison.json`、`container-{before,after}.json`：组件、容器和脚本绑定。
- `03-acceptance/<标签>/functional.py`：本轮工具，SHA-256 `58f2694f48a4e41b1a60e2d205b9a9c6072e6d481edc95c6e84b69b5474b292f`。
- `04-runs/<标签>/server-isolated-kernels-r2.log`：实际启动、图捕获和请求日志。
- 同目录 `graph-functional.json`、`graph-metrics-{before,after}.txt`、`functional-exit.json`：73 个完整响应、原始指标与退出结果。
- 同目录 `verification.json`、`device-process-proof.json`、`evidence-manifest.json`：最终 health、参数、缓存、双卡进程及固定证据哈希。

这是服务配置及短请求功能验证。未执行正式精度/性能、eager TP2 数据集、长输入或 64 个满长度上下文；
64 客户端正确不证明峰值驻留序列恰为 64，也不证明全部使用 full graph。
KV 规划容量 2,242,180 token，对 262144-token 单请求的规划并发为 8.55x。
缓存隔离是当前 Parastor 环境缓解，没有证明底层根因或测量稳态性能影响；首次启动编译较慢。
`framework.yml` 的历史正式状态不提升，本轮不宣称完整适配验收完成。
