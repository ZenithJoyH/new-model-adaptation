# Qwen3.8-Flash-Next / PPU-01 环境分析

2026-09-04，只读连通性检查通过。目标仅 PPU-01 的 qwen3.8-flash，容器ID `806fa222e7bfdbc074ed1d29ec50f7b1bbb1f7d3a8730e3340700807f0923cac`；源镜像 `glm5.3-flash-ppu13-snapshot:20260904-215131`，image ID `7755ef5656bd33703eb7c3c81fb6b2099b154284ba582488861f5ec99e3f7b30`。

16×PPU-ZW810E 96GiB；0–7被其他任务占用，8–15采集时每卡约51MiB、0%利用率。本任务只使用8–15，测试/启动前再次核对。拓扑PCI地址在container-baseline.json；链路带宽尚未测试，TP8正确性和性能由后续collective及服务验证。
容器 Ubuntu24.04.2 x86_64，host kernel5.10.134，Python3.12.3，GCC13.3；约2TiB主机内存，采集可用1.8TiB。
PPU-SMI1.28、driver2.1.1-rbd225、HGGC13.0；PyTorch2.10.0。vLLM0.24.0+empty来自/workspace/vllm@ee0da84，detached且clean，必须保持只读。
原插件editable路径/workspace/vllm-plugin-FL-glm53-hy4-adaptation，support-hy4-preview@5329cb1，有继承的GLM本地修改，完整git status已记录，不能reset或覆盖。
FlagGems源码/workspace/FlagGems，master跟踪origin/master，71d3736797ed2cefc23cddc075179156343a785f且clean；安装元数据5.3.5+g38653f94c与源码revision不同，以源码+editable路径为实际代码依据，必须同步后选算子。
FlagGems-vllm main@5865ed53，clean；Transformers5.8.1。triton distribution名未找到，不能据此断言模块缺失，后续检查FlagTree提供的triton模块版本。

host network、host IPC、privileged，/mnt bind；infiniband/alixpu/alixpu_ctl设备继承。/workspace镜像内独立，/mnt/nfs和/mnt/cpfs为共享挂载。存储可用约11TiB/16TiB，不复制权重。当前容器只有bash，无推理服务。

已知兼容缺口：镜像内三个框架均无Qwen4Exp定义。候选support-qwen3.8-flash@2b2fe95支持相同vLLM revision，选择新目录/workspace/vllm-plugin-FL-qwen38-adaptation保留原插件。其文本BF16/PPU边界与当前权重匹配；新FlagGems组合仍需回归。
初始计划TP8/PP1、8038端口、50000上下文、32 seq，禁用MTP/EP/DBO，先eager后graph。端口及设备使用在启动前重新确认，配置尚不代表服务就绪。

证据：collect_container.py、collect-ppu01.yml、container-baseline.json；检查命令./scripts/connectivity-check --limit PPU-01、docker inspect及容器内ppu-smi。未对任何未请求平台开展环境分析。

## 2026-09-06 运行现场复核计划

为诊断正式 GPQA 中 22 个达到 30000-token 上限的样本，在更改服务前执行只读复核：

```bash
./scripts/connectivity-check -i inventory/hosts.yml -l PPU-01
./scripts/playbook -i inventory/hosts.yml models/Qwen3.8-Flash-Next/ppu/environment/revalidate-current-state.yml
```

复核容器身份与运行状态、模型 `config.json` 哈希、PPU 设备、当前服务 PID/健康状态和启动参数，
以及 vLLM、Plugin、FlagGems 的 revision、分支、upstream 和工作树。复核通过前不重启服务。

复核标识：`env-revalidation-20260906-maxlen65536`。结果保存在
`current-state-revalidation.json`：容器 `806fa222…` 仍基于镜像 ID `7755ef56…` 且运行；模型配置
哈希不变；当前 graph 服务 PID 550165、健康200、max-model-len50000、TP8设备8–15、执行超时1800秒。
vLLM `ee0da84…` 干净；Plugin `2b2fe95…` 仅有最终运行配置和三项可维护回归测试；FlagGems
`34bd6d68928c8b0039c42987840929da52aa6a62` 干净且等于 `origin/master`。`ppu-smi` 返回0。
该现场支持进入65536上下文诊断；不据此宣称65536性能或准确率通过。

## 2026-09-10 环境重验证

本轮因用户要求以最新 HY4 代码为基线，并将 Qwen 新算子迁入 FlagGems，重新执行 environment
核验。`./scripts/connectivity-check --limit PPU-01`、`./scripts/health-check --limit PPU-01` 和
`./scripts/accelerator-check --limit PPU-01 --show-processes --full-output` 均到达唯一目标
`PPU-01`；主机为 `bm-aliyun-wlcb-zonea3-c-810e-96g-10-1`，加速器查询仍为 `ppu-smi`，驱动
`2.1.1-rbd225`，16 张设备均为 PPU-ZW810E。

容器仍为 `qwen3.8-flash`，ID `806fa222e7bf…`、镜像 ID `7755ef5656bd…`，状态 running、
`OOMKilled=false`、`RestartCount=0`。容器保持 `/mnt` 到 `/mnt` 的读写 bind；新批准工作根
`/mnt/nfs/users/jinghao/qwen3.8-flash` 在宿主机和容器内的 device/inode 都是
`41:26846893832`。已用单主机、`serial: 1` Playbook 创建当前规范的 `01-environment/` 至
`07-bugs/` 过程目录；这里不放源码 checkout。旧工作根
`/mnt/nfs/users/jinghao/qwen38-adaptation-20260904` 已在两侧消失，既有本地引用只作为历史事实，
不据此声称旧原始产物仍可访问。

当前实际 editable 安装身份如下：

- Plugin distribution 的 `direct_url.json` 指向
  `file:///workspace/vllm-plugin-FL-qwen38-adaptation`，导入文件为该目录下
  `vllm_fl/__init__.py`。Git 为 `support-qwen3.8-flash@2b2fe95e…`，跟踪
  `origin/support-qwen3.8-flash`，现场相对远端为 `+1/-139`，并有三个一次性 runtime test 和一个
  `thead.yaml` 未跟踪文件。修改前必须将这些历史过程文件移出 editable 产品树，并从 clean 的
  最新 HY4 基线重新建立 Qwen 分支，不使用工作根中的第二 checkout。
- FlagGems distribution 为 editable `file:///workspace/FlagGems`，导入路径
  `/workspace/FlagGems/src/flag_gems/__init__.py`；现场 `master@dcd0cfeae818…` clean，跟踪
  `flagos-ai/FlagGems` 的 `origin/master`。本轮目标是用户 fork 的
  `flaggems-for-day0@39271555a71256977978bbe1c73826d207f6f833`，需新增清晰命名的 fork remote，
  fetch 后建立 tracking branch，再做 fast-forward-only 同步。
- vLLM 实际导入 `/usr/local/lib/python3.12/site-packages/vllm`；源码
  `/workspace/vllm@ee0da84ab9e04ac7610e28580af62c365e898389` detached 且 clean，继续只读。

GitHub 回读的基线为 Plugin `support-hy4-preview@039029853ed95b0c3da05af6cca0bb0517883fb3`、
现有 Qwen 分支 `support-qwen3.8-flash@a5c6f0ca373afa606b68d2daa4bb4a9dcc1833c5`，以及
FlagGems `flaggems-for-day0@39271555a71256977978bbe1c73826d207f6f833`。最新 HY4 已将 day-0
Triton kernel 放在 FlagGems `fused` 命名空间，Plugin 只保留 backend/dispatch 接入，本轮 Qwen
按同一职责边界整理。

资源现场已变化：16 张 PPU 全部由四组 TP4 worker 占用，PID 1350494–1376912；这些进程不属于
本轮容器，不能停止或借用。`qwen3.8-flash` 内当前仅 PID 1 的 shell，8038 无服务。因此可以进行
Git、静态、CPU/import 隔离工作，PPU 数值、graph 和整模回归必须等待设备释放，不能沿用
2026-09-07 的硬件结果冒充新 revision 验证。
