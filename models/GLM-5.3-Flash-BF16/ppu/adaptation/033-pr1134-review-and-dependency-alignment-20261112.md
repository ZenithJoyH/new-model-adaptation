# PR #1134 修订、Plugin 依赖对齐与 PPU-166 验证

日期：2026-11-12。范围为用户要求的两个 PR 修订、相关算子测试和依赖对齐；本次不更新模型验收状态。

## 来源与执行边界

PPU-03 堡垒机资产不可达后，用户指定 `PPU-166`，并授权使用
`harbor.baai.ac.cn/flagos-inner-models-release/glm5.3-flash-ppu-pr` 启动验证容器。
实际主机为 `bm-guoke-alish-zoneo1-810e-96g-0-166`。

- `glm53-pr-validation`：`08b138165d62`，上述模型镜像；实际镜像 ID 为
  `sha256:c87764db9b8095f9d71afa93bf4762a61dba3d835de5f3548a11256b61feca0b`。
- `glm53-pr-ci-validation`：`5c85e6755207`，为复现 CI 数值故障使用官方 CI 镜像
  `harbor.baai.ac.cn/flagos-dev/vllm-plugin-fl@sha256:7a898b404194105514a8a6bf731468df6ce7c6e04c04989c42f6c07ba5863e48`。
- 宿主机及容器证据根均为 `/mnt/cpfs/users/jinghao/glm5.3-flash-pr-validation`，已核实 RW 映射。
- 实际源码为 `/workspace/vllm-plugin-FL` 和 `/workspace/FlagGems-vllm`；实际普通安装的算子包为
  `/usr/local/lib/python3.12/site-packages/flaggems_vllm`。所有运行验证使用正常或 editable 安装，无 `PYTHONPATH` 替换。

仅修改已验证的 Plugin、FlagGems-vllm 及其测试/依赖记录。保留镜像继承的源码修改和 Git HEAD；
vLLM、torch、Triton、FlagGems 未作产品修改。既有 `hy4`、`pccl-test` 未停止或修改，两个验证容器保持运行。

## 最终交付身份

| 项目 | PR | Head | 完整源码树 |
| --- | --- | --- | --- |
| FlagGems-vllm | [#1134](https://github.com/flagos-ai/FlagGems-vllm/pull/1134) | `9d4b358d944d28269eeb6ebfa4dd6165ecd2ddb9` | `61f9f49d0995933a120e748943a2a032557337d3` |
| Plugin | [#572](https://github.com/flagos-ai/vllm-plugin-FL/pull/572) | `7b4f1bcebe5437995ba93edca6ddb9e4b5dec5e4` | `080ff62084b0268af281ef1888ed079b24887272` |

两者均为正式、开放 PR；最终检查均可自动合并，但未执行合并。使用正常追加提交，未强推。
FlagGems-vllm 已集成的主线基线为 `3049b821d088f5566b825bdc564120249a26181d`，Plugin 审查基线为
`d6d83803980fb78d84dcc1b3bc5b915b1fddb237`。最终 PR 分别为 22 和 15 个文件。

容器源码 Git HEAD 仍分别是原有 `93fd1b0c` 和 `7cd610c96`，不能据此声称安装了对应 PR 提交。
最终核验重建完整源码树并逐文件比对，结果与上表相同；安装元数据也已刷新并验证。
Plugin installer、glm5 extra、依赖文档统一固定到公开 fork
`https://github.com/ZenithJoyH/FlagGems-vllm.git@9d4b358d944d28269eeb6ebfa4dd6165ecd2ddb9`。

## 修订结论

FlagGems-vllm 保留必要的非 TLE 可选导入、NVIDIA MNNVL 可选依赖隔离、mHC 编译器状态恢复和
MLA graph padding 契约修复。新增明确的 `qsa_sparse_paged_attention_unpacked` 公共 API，复用现有
vendor replacement 和 T-Head 实现，并排除 ATen 注册。

此前直接导入 generic QSA 函数虽然保留 unpacked 签名，却绕过已有 PPU 最小 16 行实现，导致
CI 的 3.6 编译器上两个数值测试失败。最终在算子库修正公开 API 的派发，Plugin 仅调整导入。
没有修改数值 kernel、grid 或调优候选，没有放宽断言或误差。Plugin 最终差异不含 HY4 实现变更。

补齐可选导入、异常传播、状态恢复、独立数值参考、偏移/非连续输入、保护区、CUDA graph 和两次
变化输入 replay 测试；CI 保留原映射并增加严格 PPU 必测入口、真实 Git changed-path 和汇总回归。
基准入口复用已有 QSA workload/reference，只有 smoke 数据，不宣称性能提升。

逐 hunk 审查依据：`plugin:A1`、`plugin:A2`、`plugin:B1`、`plugin:B3`、`plugin:D3`、
`plugin:F1-F7`；`operator:D1`、`operator:D2`、`operator:D5`、`operator:E1-E3`、`operator:F6`。

## 已验证结果

| 验证 | 结果 |
| --- | --- |
| 用户指定镜像上的 non-TLE PPU 核心套件 | 84 passed，0 skipped |
| 其中 unpacked API/导出/注册与真实数值/graph | 15 passed，包含 12 个真实数值/graph 参数 |
| CI 选择、报告与汇总 helpers | 74 passed |
| 精确 CI 镜像上的新库 API + Plugin QSA 回归 | 18 passed，导入的编译器为 3.6.0 |
| Plugin GLM/installer CPU 回归 | 439 passed，40 GPU 参数 deselected |
| PPU prefill 数值/graph 与独立进程回归 | 9 passed |
| 最终依赖 pin/provenance 测试 | 13 passed |
| BF16 single/split 标准基准 smoke | 2 个 pytest case passed，无加速比结论 |
| 最终普通安装包 | 493 个源码/配置文件与源码一致，502 条哈希 RECORD 有效 |
| 用户镜像的 vLLM 只读核验 | 1886 个 Python 文件哈希不变 |
| CI 镜像的 vLLM/torch/Triton/FlagGems | Python 源码哈希不变 |

原模型镜像为 torch 2.10.0、vLLM 0.24.0+empty、导入的 Triton 3.5.0、
FlagGems 5.5.0.dev0+g9c1046e19.d20261109。CI 镜像的 FlagGems 为 5.3.4；未升级 SDK 或修改第三方库。

## CI 快照与未完成项

截至 2026-11-12 05:13 UTC：

- Plugin [CI 43157845506](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/43157845506)
  的 lint、build、T-Head、Iluvatar 功能 job 成功。
  [T-Head job](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/43157845506/job/130983099973)
  明确从公开 VCS 安装最终 `9d4b358`，单元测试 1450 passed / 164 skipped，功能测试 13 passed / 42 skipped。
  [Code Scan](https://github.com/flagos-ai/vllm-plugin-FL/actions/runs/43157845353) 成功。
  其他平台及 E2E 仍运行或排队，不能声明整体 CI 全绿。
- FlagGems-vllm [rule-check](https://github.com/flagos-ai/FlagGems-vllm/actions/runs/43157505857) 成功。
  [basic CI](https://github.com/flagos-ai/FlagGems-vllm/actions/runs/43157506267)
  在 pre-commit hook 仓库下载阶段遇到 HTTP 418，未执行代码检查，依赖 job 被跳过。
  连接器重跑返回 403（Actions 写权限不足），作者登录页面也无重跑入口；需有 Actions 权限的维护者重跑。

PPU-166 本地 GitHub 下载失败，算子普通安装由完整核验的源码构建，`direct_url.json` 如实记录
`file:///workspace/FlagGems-vllm`；公开 VCS 安装已由最终 Plugin CI 独立验证。
本地全量 16 worker Plugin 测试曾报告 4 个原有 clamp fixture/order 失败，该未改动文件单独执行 18/18 通过；
保留失败证据，不据此声称本地全量测试成功。

镜像 TileLang 保持 `0.1.8+v0.1.0.ppu2.1.0`，完整 glm5 extra 要求的 0.1.9 未验证。
独立 FlagGems ATen 修复交付、完整 GLM 服务启动、精度、正式性能和其他硬件路径均不在本次通过结论内；
未更新 `framework.yml` / `platform.yml`，未重启已有模型服务。

## 证据位置

原生日志、JUnit、基准结果和逐 hunk 审查位于远端证据根的
`02-issues/pr1134-review-followup-20261112/`，核心索引为
`source-review.json`、`delivery-verification.json`、`plan.json`；包含上述两个最终源码树和依赖 pin。
数值故障复现证据另在 `07-bugs/qsa-ci-abi-20261112/`。原始失败未删除，本地只保存本记录。
