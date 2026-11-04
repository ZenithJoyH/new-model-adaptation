# MetaX 环境分析

日期：2026-11-03。仅 `mx-102`、`mx-103`，profile v7 / evidence contract v2，Agent控制。

## 已核实边界与基线

容器均为 `deepseek-v41-text-plugin028-20261103`，指定镜像固定digest
`sha256:34dfb5c72b60cf0a7c2c1ff0d73c24cc8bc4314b3b0deb36c51306000d85b6f1`。
102容器ID `c068b055a3364bc97cdcb024520465043250be614dc8f272b06becbfaca57c5e`；
103为 `9f34d25c86db04d3a05738495439829a530e9f3ccb44af1bca1e47a28d0df2ee`。

host/container root均为 `/public-flash/jinghao/deepseekV4.1`，inspect、realpath和inode已验证一致。
底层共享NFS，证据按Host分目录；模型目录独立只读挂载。使用host network、host IPC、无限memlock，
映射 `/dev/mxcd`、`/dev/dri`、`/dev/infiniband`。容器保持运行；后续按用户明确授权停止竞争推理worker，见003。

每机8×C550 65536MiB、驱动3.8.1。初检每卡858MiB驱动占用，未发现GPU计算进程。
解释器 `/opt/conda/bin/python`；torch `2.10.0+metax3.8.2.2`，FlagTree `0.7.0+metax` / Triton3.6，Transformers5.17。

| 组件 | 实际导入根 | 初始HEAD/状态 |
|---|---|---|
| vLLM | `/opt/vllm/vllm` | `2cf0a6915ce544dc493a0990f2ea38d81601128a`，0.28.0+empty，干净、只读 |
| Plugin | `/opt/vllm-plugin-FL/vllm_fl` | `37f2127367cfbc24349a1f28cb37c4c629b9ed6c`，detached origin/0.4.0-dev，含继承改动 |
| FlagGems | `/opt/FlagGems/src/flag_gems` | 初始 `c2b27429b16f3eb01741095d04c9dc6c03ddecef`；两机已在原树ff-only同步至 `e584bded1ddb0ea2a638653043ef0d48931119a3`，干净 |
| FlagGems-vllm | `/opt/FlagGems-vllm/src/flaggems_vllm` | `f108ba81bf6799ccfe48c86f77cbb3ce117c4179`，main，干净 |

无PYTHONPATH或第二份checkout。原生身份在 `01-environment/<Host>/identity-20261103.json`：
102 SHA-256 `f7439c76c9c9d7dc1d275bd716bf4b6ddb7f8d611e7ad5fc509159189714c167`，
103 `d59c9eb3dc38443e200a5d9f1852619dddb7ca70dc01b42ffdccab8810a5aa49`。

Plugin继承修改为 `fix_standalone_compile.py`、`pynccl_wrapper.py`、`_kths_triton_unified_attention.py`、
`dispatch/config/metax.yaml` 和四个standalone-artifact/mccl-abort未跟踪测试，全部保留。
目标Plugin tracked files没有AGENTS/CONTRIBUTING，使用现存README、dispatch/README、pyproject、测试体系和本项目规范。

## 检查与阻塞

- 初始 `get_config(..., trust_remote_code=False)` 不识别 `deepseek_v41`；配置切片已修复并在两机通过20项单测，见[001](../adaptation/001-v41-registration-and-contracts.md)。
  镜像缺少V4.1模型与sparse_mqa_indexer；不能升级或修改只读vLLM绕过。
- 实际配置最大位置1,048,576，初始服务上下文50,000；TP16显存与cache预算待实测。
- 容器没有 `ip`、`ibdev2netdev`，网络由主机和容器sysfs核对，未安装诊断包。
- 主机四个bnxt_roce端口ACTIVE，一个bnxt_re端口DOWN。容器provider仅支持kernel ABI1、主机为ABI8；
  102容器实际枚举0个HCA、主机5个，见[002](../adaptation/002-rdma-provider-abi.md)。
- 官方 `MetaX-MACA/mccl_tests@1e44d4af1b177f2ab9e23bdd0b393ad757d08f4e` 已在102容器构建到
  `05-tmp/mccl-tests-1e44d4af/`。已核对pinned README、cluster.sh、build.sh和Makefile；
  cluster.sh固定mlx5与推导subnet不适合现场，不能照搬。

102单机8 rank、BF16、8B–256MiB、factor4、warmup5、20次、`-c 1`：
AllReduce/AllGather/ReduceScatter均退出0、Out of bounds0；全尺寸平均busbw为60.3628/52.6091/44.5691GB/s，
不是大包峰值或模型吞吐。rank归属和实际库路径在
`04-runs/mx-102/mccl-local-20261103/result.json`，SHA-256
`54a2a5c45db4bc689cbd80c80d465c6b0791a0ccf799d92d75ab9e0f23127c79`。
103同条件三项均通过、Out of bounds0，平均busbw60.5387/52.5903/44.7602GB/s；
原生结果SHA-256为 `3d5f84312d2d69b59f3f3d99cbee70716bda48171d2f4f79fada5869bde82f9f`。

已按用户授权仅复制并为任务进程选择主机bnxt provider，系统libibverbs未改。
双机16rank三项均通过且Out of bounds0；每rank均在对应实际适配容器内、实际加载库观察16/16齐全，
使用NET/IB、RoCEv2 GID3，详见[002](../adaptation/002-rdma-provider-abi.md)。
原生结果 `04-runs/mccl-cross-sixteen-rank-host-orchestration-v3-freegpus-20261103/result.json`，
SHA-256 `bd024e0d23a7965ac1032c4dbf6214d4e5c0daa20fba231b16dd78e0ee8577f4`。

两机当前安装树、导入路径、配置与容器映射快照为
`01-environment/<Host>/environment-snapshot-v2-20261103.json`，102/103 SHA-256分别为
`2cac68640137c5b625dfc6962fbfb33cb8f5558c0bd9583b2e0460745a0917b2`、
`fa91bbebfd175154515aa0b161153e74867104d8940dcc1ac1fc738471c035e2`。
快照明确 `planned_model_runtime.state=not_launched`；TP16/上下文50000是候选，不是有效服务配置。

运行缓存默认在容器 `/root` 下，未额外覆盖；正式服务前核实可写性、mount归属和实际解析路径。
评测cache仅用 `06-cache`。
当前环境身份清单 `01-environment/observed-environment-identity-20261103.json` 绑定上述两机快照，
SHA-256（当前部署fingerprint）为 `55d66b1065e4a37544236260cc3f00dc07962eb2af090aa12a258c11e24dcd5d`。
该身份是未启动模型的环境基线；后续代码/运行配置改变时重新采集，不能沿用为服务验收身份。
尚未冻结有效服务契约，无最终启动脚本或整模验收通过声明。
