# 双机环境与适配计划（2026-10-27）

## 已核实范围

用户要求在当前 `glm5.3-flash` 容器适配 BF16 模型，并授权使用 `mx-101`、`mx-102`。
用户已明确确认两机 host/container 同路径工作根
`/public-flash/jinghao/glm5.3-flash`，以及在 mx-102 创建同名容器。
选择 active `vllm-plugin-fl` profile v7，固定新建工作区的 v2 契约。

- 两机连接已通过维护入口；各有 8 张 64 GiB C550，宿主机驱动 3.8.1。
- mx-101 容器 ID 为 `d73d1bc917e3651b04b965c02c495c46096873280997f8de9870abd13e15172f`，
  running；`/public-flash`、`/data` 均同路径 RW bind，host network；`/opt` 为容器内部文件系统。
- mx-102 起始没有目标容器；在创建并核实映射前不声明其容器环境通过。
- 权重目录只读使用 `/public-flash/models/GLM-5.3-Flash-BF16`；120 分片完整，
  config/index 哈希与模型级架构文档一致。不能修改权重或把 PPU 历史结果当作 MetaX 证据。
- 现有其他容器不属于本任务，不停止或修改。两个适配容器需保持运行。

## 安装基线与边界

101 解释器为 `/opt/conda/bin/python`。实际 editable 源码为
`/opt/vllm-plugin-FL@4e23ae8f`、`/opt/FlagGems@89ec1ade`、
`/opt/FlagGems-vllm@ddce1d66`；三棵工作树干净。
vLLM 为 `/opt/vllm@ee0da84a`，继承镜像中的权限位差异，全程只读并绑定完整 diff 哈希。
不使用 `PYTHONPATH` 或第二份 checkout。101 为避免 `/opt/vllm` 同名目录遮蔽，诊断使用
`docker exec -w /`；102 新容器工作目录使用 `/`。

前次元数据修复已完成标准 editable 重装；Plugin 显示 `0.3.0rc2.post1+g4e23ae8f2`，
FlagGems 包版本 `5.5.0.dev0`、运行时 `5.5.0.dev0+g89ec1ade6`，
FlagGems-vllm `0.3.0.dev1`。NFS 的 `system.nfs4_acl` 复制会返回 EIO，前次仅安装进程
对批准临时目录采用 ENOTSUP 兼容处理；运行时没有 preload、路径覆盖或主线源码补丁。

## 初始差距与验证顺序

1. 将 101 当前容器内部安装环境制成同一镜像，供 102 创建同名容器；现场核对镜像、
   挂载、设备、导入路径与组件 diff。镜像归档仅留远端批准根，不写本地模型目录。
2. 核实跨机网络/RDMA、设备拓扑和可用资源，采用最小通信探针验证双机16卡连接。
   并行布局尚未选定，TP16 或 TP8/PP2 均不能在验证前声明可用。
3. 当前 Plugin 主线没有 `Glm5NextForConditionalGeneration` 接入。先对照已发布历史
   GLM 参考与当前 vLLM/Plugin 的配置、注册、hybrid cache、KDA/KPool/mHC/MLA/MoE 接口，
   完成最小变更清单后才写产品代码。历史 PPU 算子/图模式经验仅为待复验假设。
4. 先做导入和注册，再做直接算子 eager/graph 数值测试、组件组合与双机加载。
   初始上下文取 50000，不通过降低上下文隐藏容量或运行时问题。
5. 图模式按 FULL → FULL_AND_PIECEWISE → FULL_DECODE_ONLY → PIECEWISE 逐级诊断，
   选定档位后依次 sanity、GPQA 和性能，全部非性能工作保持前缀缓存开启。

## 验收约定与未验证项

用户确认 GPQA Diamond 全量198题、strict-match ≥0.88；完整样本与超时计错规则按 v2 执行，
并发由实测容量冻结。性能先测量吞吐/时延，业务目标尚未冻结，因此不能声明 optimized。
正式精度选 `formal-full`，前置小集合选 `service-sanity`；正式性能计划选 `full-suite`，
具体场景与目标须在执行前冻结。当前没有整模运行、图模式、精度或性能通过结论。

## 双机基线准备结果

101 当前容器已生成 `local/glm5.3-flash:mainline-20261027`，镜像 ID
`sha256:a6f6bad179f2c6b221225437ae5afd24f74f463966ec3c7d859541279e79b85f`。
归档位于工作根 `05-tmp/glm53-mainline-20261027.tar`，大小 14173335040 bytes。
102 已加载该镜像并创建运行中的同名容器，ID
`cdf5ee8ab707acc5f7d1ab7285aad4ae43cd655d314d6dca6fb36045ee1769a6`。
现场核对两机 `/public-flash`、`/data` 的相同 RW 映射；102 四组件 HEAD、status 和完整
diff 哈希与101相同，真实导入路径均在 `/opt`，无 PYTHONPATH，8张设备可见。
原生记录分别为 `01-environment/mx-101/installed-baseline.json`、
`01-environment/mx-102/container.json`、`01-environment/mx-102/installed-baseline.json`。

102 创建入口曾报告 SSH 发送失败；只读复核发现操作已经完成，因此未重放创建或重建容器。
该失败及恢复事实保留，不把 Ansible 返回状态当作现场结果。
FlagGems 官方主线已前移到 `3eab0949`（仅新增 foreach dtype helper）。两台实际安装目录
均已通过1675-byte增量bundle执行fetch和fast-forward-only merge，并以标准editable方式
重装元数据；工作树干净。运行时版本对应新SHA，无导入路径覆盖。
回执为 `01-environment/<host>/flaggems-synchronized.json`。

## 通信和算子进展

双机16卡的all-reduce、all-gather及一次capture/两次变输入replay均通过，16个rank回执
位于 `04-runs/comm-dual-mccl-ifname-20261027/ranks/`，两机launcher均rc0正常退出。
运行时须使用 `MCCL_SOCKET_IFNAME=inbond1`，NCCL同名变量对本环境实际MCCL无效。
跨机当前为Socket，用户态bnxt_re与内核ABI警告未消除，不宣称RDMA或性能验证通过。

FlagGems-vllm的原生GLM8项基线为6通过2失败：卷积的`tl.gather`触发SDK未知
`maca.shfl.sync`；KDA则为GPU参考数值差异，两者不能混为编译失败。独立CPU参考下
tiny与128维KDA通过。卷积在D512/W4也复现编译失败；已在实际安装FGV中加入MetaX静态
寄存器历史移位分支，原失败用例加既有状态语义回归71项通过，graph回归待完成。
问题003保留完整对照与变更边界；未改FlagTree、SDK或vLLM。

原生产物从工作根 `01-environment/`、`02-issues/`、`03-acceptance/`、`04-runs/`、
`05-tmp/`、`06-cache/`、`07-bugs/` 引用。共享 NFS 中每台机器的记录按 Host 区分。

## 当前组件与首次整模加载（补充）

当前两机实际安装的FlagGems均为 `3eab0949`、runtime `5.5.0.dev0+g3eab0949b`，
主线同步后干净；Plugin/FGV必要修改见问题001、003、005～008。两机source set13文件
初版归档SHA `e81500e7a1cc77c929de04acad0f6bdbca445bec7a855f5bcfb5821eafa3ada9`，
公共PP工厂修复后的第二版归档SHA
`1ade60be6e0adb0118eeab0906f5b2c0378fa7097c1e1bf7987598c3819df7ec`；
101仅按旧/新哈希同步发生变化的两个任务文件，未覆盖其他差异。

两机各28项组合回归通过，包含14项配置/隔离、4项packed KDA（其中decode含graph）、
3项mHC PP分段graph、2项KV/indexer adapter和5项已有Qwen路径。之后新增的text/conditional
公共PP工厂负对照均返回None，修复委托后两机各两项通过。

首次真实双机服务 `glm-eager-bringup-20261027` 使用TP8/PP2、multi-node mp、50K、
max_num_seqs4、max_num_batched_tokens2048、prefix cache开启。120/120分片读取完成；
首次NFS预取约337秒，101权重读取约765秒。随后PP1 profiling因公共PP工厂返回None失败，
运行不算服务通过。仅停止本任务服务，两个适配容器保持运行；原始失败与退出状态保留。

用于正式评测的独立CPU容器 `glm53-mx101-eval-20261027` 已创建并核实，镜像ID
`sha256:1396e5d63553530425db81ebf9a724aa98dc2e11aaf2e677c908f991a9cb7ce3`。
工作根保持同路径bind；response SQLite缓存使用批准根内
`06-cache/flageval/responses` 的4GiB tmpfs，已从HostConfig和实际mountinfo双重验证，
避免NFS WAL锁；HF数据缓存位于 `06-cache/flageval/hf-datasets`，离线预检确认Diamond198题。
未修改原有 `qwen38-mx101-eval-20261024` 容器，也未开始正式GPQA请求。

原生工具仅部署在 `03-acceptance/native-tools-20261027`（51个必要脚本/契约/元数据，
624640 bytes，归档SHA `b949fff6e821b564e21c69823575ef1006b14b334d8701c3f47d75962d0fda97`），
没有复制产品源码仓库或ShareGPT大数据文件。精度 `formal-full` Skill bundle SHA为
`355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d`。

## 本轮环境身份冻结

第二次启动前，两机重新核实容器ID、运行状态、批准根映射、实际安装路径、13文件第二版
源码manifest、KDA gate修复、FGV四个修改文件及干净FlagGems HEAD；vLLM继承diff未变。
逐机证据为 `01-environment/preflight-eager-v2-<host>.json`，部署原始身份为
`01-environment/deployment-identity-bringup-v2-20261027.json`，指纹
`b3a2625ddbd765c7aed41ee86ebeb4f3c5b9a5123d614b32974631758b4f916c`。
它绑定当前eager bring-up配置，后续代码、图模式或基础配置变化必须重新核验绑定。
环境身份通过不代表服务就绪、整模数值、GPQA、性能或适配镜像通过；这些仍待独立验证。
