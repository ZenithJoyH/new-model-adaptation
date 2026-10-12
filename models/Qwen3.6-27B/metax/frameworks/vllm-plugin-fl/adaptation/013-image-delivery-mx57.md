# 013：mx-57 容器交付

## 范围与结果

- 日期：2026-10-08；用户要求在 `mx-57` 也启动 `qwen3.6-27B` 容器。
- 状态：`verified`，仅覆盖镜像加载、容器启动及限定验证；不代表模型服务或正式验收完成。
- 复用 [012](012-image-delivery-mx59.md) 的原始归档镜像，不重新选择依赖版本，不修改已安装产品代码。未操作 mx-58/mx-59，也未停止 mx-57 原有容器/服务。
- 容器：`qwen3.6-27B`，ID `48fc01e5626af44f0cf974c0801f979adbddca584d9d422f46df535f0f80610f`，最终 running、unpaused。
- 镜像：`flagos/qwen3.6-27b-metax:adapted-20261008`，ID `sha256:17523db510149bad9c4c6a8f9dcb1d788cc06bc849c74c0de48606fb7785f091`，与 012 保存的 image ID 一致。
- 归档：`/public-flash/jinghao/qwen3.6-27B/01-environment/image-delivery-20261008/qwen3.6-27b-metax-adapted-20261008.tar.zst`，15,757,543,776 字节；SHA256 `ad6a22cf7ecdc925d8621468a53a72313e053cf7c32802cb50ff377b0d803049`，mx-57 校验通过。

## 当前部署

| Host 路径 | 容器路径 | 权限 |
|---|---|---|
| `/public-flash` | `/public-flash` | 读写 |
| `/public-flash/models/Qwen3.6-27B` | `/models/Qwen3.6-27B` | 只读别名 |

完整 `/public-flash` 挂载可从原路径写入模型目录；只读别名仅约束别名访问，不提供全局写保护。
host/container 的 `/public-flash` stat 均为 `55:3145731`；工作根
`/public-flash/jinghao/qwen3.6-27B` 映射到同名容器路径。

- 默认 `CUDA_VISIBLE_DEVICES=4,5`，根据部署前空闲设备选择；本次 smoke/FA 验证仅使用物理卡 4。
- 保持与交付容器一致的 privileged、host network/IPC、`label=disable` 配置；不挂载 `/workspace`、`/opt/conda` 或 `/data`。
- 工作目录 `/opt/flagos/qwen3.6-27b`；镜像内部启动器 `/opt/flagos/qwen3.6-27b/start-model.sh`，本轮未执行。
- PATH 优先使用 `/opt/conda/bin`，无 `PYTHONPATH`；未额外设置 GDN 开关/黑名单，不改变共享启动脚本。
- 进入命令：登录 `mx-57` 后执行 `docker exec -it qwen3.6-27B bash`。

## 验证证据

- mx-57 为 MetaX C550，MACA `3.7.1.5`、kernel driver `3.3.12`，与 mx-59 的 `3.8.1` 不同。未升级驱动；本轮实测设备计算与两项 FA 用例通过，不能据此推断全模型兼容性已验收。
- 四个组件的版本、HEAD、import origin、Git status、tracked diff SHA 和 FA/GDN/启动器关键 SHA 与 012 原交付回执一致。继承的 vLLM dirty 文件未在本轮修改。
- 组件导入、启动器 `bash -n`、设备 smoke 通过。
- FA：`test_metax_swapped_decode_paged_graph[1-0-784-6]`、`[4-0-784-6]`，`2 passed in 7.63s`，覆盖 eager 和 graph capture/replay；不等于重新完成 011 的 78+4 回归。
- 原生证据根：`/public-flash/jinghao/qwen3.6-27B/04-runs/image-delivery-mx57-20261008/`，含 `archive-check.log`、`load.log`、`image-id.txt`、`container-id.txt`、`imports.log`、`fa-regression.log` 和最终 `result.json`。
- 加载 job `j9381052513.1934448` finished / rc=0，保留于工作根 `05-tmp/ansible-async-image-delivery-mx57-20261008/`；过程 playbook/验证脚本保留于 `02-issues/image-delivery-mx57-20261008/`。
- 相关 playbook syntax/check-mode 通过；通用离线检查中的 252 workflow（1 skipped）、6 operations 测试通过，整体仍因既有结构审计 12 errors / 78 review 返回 1，未修复无关历史记录。

## 限制

仅容器部署，没有启动模型服务、运行模型请求或完成全模型精度/性能验收。
`framework.yml` 的正式阶段状态不变，不将 mx-57 加入正式验收已通过 Hosts。

知识库处理状态：`local-only`。
