# 推理环境分析

记录当前 framework profile 在目标平台上的容器、组件、revision、导入路径、修改边界、服务
协议、执行模式、Host、远端工作根目录及已核实映射。只保留 Markdown 结论和准确证据引用。
# 2026-10-26 已核实运行身份

Host为PPU-01，容器`minicpm-jev`，ID `0ee63bbcec91264acfef52636b7a2983d53bf31ccb976c808fe827646673e069`，始终运行。工作根 `/mnt/nfs/users/jinghao/MiniCPM-JEV/rm_hf_infer_demo_v1_20261015_with_ckpt` 在Host/容器同路径，`/mnt:/mnt` RW，dev41/inode18374857198相同；另有`/data:/data`挂载，本轮未使用。PPU3空闲后用于测试，0/1/2既有服务未操作。

Python3.12.3、torch2.10.0+cpu，经Torch-FL加载PPU CUDA-ABI运行库；Transformers5.10.4。实际Torch-FL editable源为`/workspace/PyTorch-Plugin-FL`，HEAD `ac2ca673d8ee56b28719ab0bcc38d5c40baf6d82`。初始tracked clean，仅`torch_fl/lib_ppu/`为既有untracked运行库。FlagGems为`/workspace/FlagGems`，HEAD `367d19367880eaf8843449abe11db4cfb7d47e03`，clean并保持只读。构建记录为PPU、boxing/flaggems/vendor；默认配置`torch_fl/configs/backends_ppu.conf`。没有PYTHONPATH覆盖。

现场dispatch key证明`cuda:0`是CUDA，`flagos:0`才是PrivateUse1；已有真实CUDA运行时，因此Torch-FL不会安装cuda→flagos别名。原始HF计时使用CUDA路径，不能将其描述为已进入PrivateUse1路由。`fla`、`causal_conv1d`均未安装，HF GDN默认使用纯Torch分块实现。

GPU为PPU-ZW810E，Driver2.1.1-rbd225。模型和12个输入沿用原demo及checkpoint，哈希在原生结果中绑定。只新增Torch-FL显式适配及测试，未改厂商库、Transformers或模型。Ruff0.15.12隔离安装在本轮`05-tmp/.../tools/`，不改变推理依赖。详细证据见适配001及本轮`product-before.json`、`product-after.json`。
