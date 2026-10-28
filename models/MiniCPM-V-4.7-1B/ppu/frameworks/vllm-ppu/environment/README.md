# 推理环境分析

## 2026-10-08 只读发现

- Host：`PPU-13`；容器：`minicpmV4.7-ppu`，ID
  `a7171373be0a93b76f4e91f840914e81a754e3048e4a456350f89497fb40b770`，保持运行。
- 镜像：`sha256:9168c1a258c5ef3d5a3d3dfdc6dfa32436c5765174d220c527980e0157bd2eca`。
- 实际 vLLM：`0.23.0+v0.2.0.ppu2.1.0`，导入目录
  `/usr/local/lib/python3.12/site-packages/vllm`。沿用已安装 4.7 adapter，尚无本轮产品改动。
- 指定模型：`/mnt/cpfs/models/MiniCPM-V-4.7-1B`，真实路径相同。
  `config.json` SHA-256 为
  `0d2f763cf97a0a5beec8f52b13b4cbf7262680df6fd35e1f0e48c09288c4bb12`；
  Dense `qwen3_5_text`、24 层、canvas M-RoPE、最大位置 262144。
  checkpoint 的 canvas helper、参考 modeling 和 tokenizer 哈希与已有架构记录一致。
- 当前 `model.safetensors` 为 780 个 tensor、3109054480 字节，SHA-256 为
  `8c4921ac83182c85190ad10c3aeb118d51e385d2d98ec13b88b514bbf6cac002`。
  与模型级旧记录的权重文件哈希不同，不把旧推理结果视为本次验证。
- 当前 adapter `minicpmv4_7.py` SHA-256 为
  `d5ae0d259ec88be4266d16d186391a73b32040cc2275289a508548ba6b0f3d00`，
  已有 Dense/MoE 分派。GDN builder 仅声明 `UNIFORM_BATCH`；用户指定
  `FULL_AND_PIECEWISE`，七档图尺寸仍需实际捕获验证。
- 查询时 GPU 5 空闲、8023 未监听。35B 服务 8022 的 `/v1/models` 返回 HTTP 200；
  未停止、重启或修改其服务。
- Docker `/mnt` 为读写 bind mount。宿主机与容器的
  `/mnt/nfs/users/jinghao` realpath、device:inode `41:7520499121` 一致。
  建议独立工作根 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B-ppu` 尚不存在，等待用户确认后
  才创建并核验完整根映射。未在远端创建本轮文件、启动服务或修改产品。

检查通过维护的 `./scripts/ansible PPU-13 -m ansible.builtin.command` 执行，
宿主命令及 `docker exec -w` 均显式指定已有工作目录。
以上为只读发现，尚无保存到批准根的原生证据或完成回执；不声明环境、适配或验收通过。

## 同日追加：脚本交付与功能检查

用户追加要求生成同容器的 1B 脚本。本轮复用此前已批准且重新核实映射的
`/mnt/nfs/users/jinghao/MiniCPMV4.7-ppu`，以 `start-model-1b.sh`、
`04-runs/1b/`、`04-runs/1b-bringup-20261008/`、`06-cache/1b/` 分开保存产物，
没有创建未确认的 `/mnt/nfs/users/jinghao/MiniCPMV4.7-1B-ppu`。
同一容器、镜像、StartedAt 保持不变。1914 个 installed vLLM Python 文件与
35B bring-up 后清单逐一比较，无新增、删除或哈希变化，Dense 分支已满足本轮加载需求。
当前 1B 权重整文件 SHA 在功能检查后复核，仍为上列 `8c4921ac...cac002`。
具体实测范围、脚本并发修改和限制见 [本轮报告](../acceptance/launcher-20261008.md)。
本项仅交付附加脚本与功能检查，不将共享工作根记录为独立 1B 正式阶段通过。
