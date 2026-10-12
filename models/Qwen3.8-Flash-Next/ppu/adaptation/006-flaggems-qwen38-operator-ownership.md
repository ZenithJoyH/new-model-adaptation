# 006：Qwen3.8 新算子迁移至 FlagGems

## 元数据

- 状态：`resolved`；源码整理、PPU 算子回归、eager/graph 整模验证均通过。
- 首次出现时间：2026-09-10。
- 最后验证时间：2026-09-11。
- 模型：Qwen3.8-Flash-Next，权重 `/mnt/cpfs/models/Qwen3.8-Flash-Next`。
- 平台与 Host 别名：T-Head PPU，`PPU-01`。
- 容器名称与镜像：`qwen3.8-flash`；`glm5.3-flash-ppu13-snapshot:20260904-215131@sha256:7755ef5656bd33703eb7c3c81fb6b2099b154284ba582488861f5ec99e3f7b30`。
- 最终远端 revision：Plugin `939600b323c02c21916f1f76bfb4cd8c2b02578d`；FlagGems `7ba32ded1365d3ce6d3b7e28f41af7ddc7ff095c`；vLLM `ee0da84ab9e04ac7610e28580af62c365e898389`。
- 本轮执行模式与负载：静态与 CPU 回归、PPU 8 上四组算子测试、PPU 8–15 TP8 eager 与 graph 整模验证；服务 maxlen 65536、maxseq 32、maxbatch 4096。

## 问题现象

上一版将 10 个 Qwen3.8 专用 Triton 算子放在 Plugin 的
`vllm_fl/dispatch/backends/triton/qwen38/`。最新 HY4 分支已经明确由 Plugin 复用 FlagGems
算子与既有 `default.flagos` 注册路径；继续由 Plugin 持有加速器算子会形成第二套后端和依赖检测，
也使算子测试无法随 FlagGems 演进。

影响限于代码所有权和可选依赖边界。本轮没有观察到新的运行时错误；原始迁移前 PPU 结果不能证明
迁移后的模块导出、注册和 graph 行为。

精简证据：远端
`/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/flaggems-ownership-static-20260910.txt`。
SHA-256：`d89f680e94a0f631a94df04040a195e8306ead2cd6d6be230b4bd29ad58553d9`。
补丁传递过程文件位于同一工作根的 `05-tmp/`，不属于产品仓库。

## 已有经验匹配

| 知识条目或历史问题 | 相同点 | 差异 | 可信度 | 本次验证决定 |
|---|---|---|---|---|
| 最新 `support-hy4-preview` 的 FlagGems 接入 | 使用 `FlagGemsBackend`、`default.flagos` 和可用性守卫 | Qwen3.8 首先使用 10 个新的语义 ABI，并含 vLLM block-table 对象 | 高 | 复用注册路径；对象拆包留在 Plugin |
| FlagGems day0 graph-safe sequence kernels | 算子由 `flag_gems.fused` 对外导出并覆盖 graph 变输入 | QSA、PLE、GDN 和 slot mapping 的 ABI 不同 | 高 | 按算子语义新增顶层模块和测试 |

未发现与本次代码所有权问题直接匹配的 troubleshooting 条目；旧算子缺失证据只解释初版选择，
不能继续作为 Plugin 持有算子的依据。

## 诊断与受控尝试

已验证事实：容器内 Plugin 为 editable install，源码根
`/workspace/vllm-plugin-FL-qwen38-adaptation`；FlagGems 为 editable install，源码根
`/workspace/FlagGems`；vLLM 工作树保持 detached clean。FlagGems tensor API 不导入 vLLM 或
`vllm_fl`。Plugin 仅有 common-slot mapping 需要把 vLLM 多 cache-group 对象拆成张量、stride 和
CP 元数据。

| 轮次 | 唯一变量 | 基线 | 本次设置 | 结果 | 结论 |
|---|---|---|---|---|---|
| 1 | 源码基线 | Plugin 旧 Qwen 分支、FlagGems master | Plugin 最新 HY4；FlagGems 最新 day0 | 两个补丁均可干净应用 | 迁移不要求修改 vLLM |
| 2 | 算子所有权 | Plugin-local Triton 注册 | FlagGems 导出 10 个 ABI，Plugin 走 `default.flagos` | 80+390 项无 PPU 测试通过 | 注册、CPU 参考、逐算子缺失能力守卫和共享 dispatch 回归成立 |
| 3 | PPU 测试 | 迁移前历史结果 | 最终 FlagGems revision、物理 PPU 8 | 97 passed，1 个已有 benchmarker warning | 新 ABI 的 eager、changed-input graph 和参数路径通过 |
| 4 | 整模执行 | 旧 Plugin/FlagGems 组合 | 最终 revision、TP8 PPU 8–15、maxlen 65536 | eager 与 graph 均健康并正确返回 `2`；graph capture 6/6 | 迁移后整模调用链通过 |

## 根因

根因是初版开发时 FlagGems 尚未提供这些 ABI，临时实现直接进入 Plugin；后续 FlagGems day0 分支
已成为新增融合算子的正确所有者，但 Plugin 分支未同步收口。该问题是职责边界债务，不是通过扩大
fallback 或模型名特判解决的运行时故障。

## 解决方法

- FlagGems 按语义在 `src/flag_gems/fused/qsa.py`、`ple_state.py`、`gdn_packed_decode.py` 和
  `common_slot_mapping.py` 持有实现；根 `flag_gems.fused` 显式导出 10 个符号。目录和公开 ABI
  均不绑定首次使用它们的模型名。
- 公共 ABI 只接收张量和标量布局信息。FlagGems 不依赖 vLLM 数据结构；CPU 路径用于数值参考和
  边界测试，加速器路径继续使用 Triton。
- Plugin 删除整个 `dispatch/backends/triton/qwen38` 及其独立注册器，在现有
  `FlagGemsBackend` 中延迟导入这些符号。dispatch 名称直接使用算子语义，每个符号分别检测
  callable；安装只缺其中一个 ABI 时，其余算子仍可被其他模型或调用方选择。缺失项继续让已有
  vendor 候选由 dispatch policy 选择。
- Qwen 模型专用代码合并为一个 `vllm_fl/models/qwen3_8_flash_next.py`。原 package 内部导入和
  `common/gpu/ops` 转发层全部删除；文件内部用分段注释保留 config、PLE、QSA、GDN、cache
  metadata 和模型装载边界，模型代码直接通过通用名字解析 dispatch。
- `compute_common_slot_mapping_flaggems` 是唯一 Plugin adapter：逐 cache group 传入张量与 CP
  元数据，并且只在第一组更新共享 `num_computed_tokens`。
- Plugin 主线先同步最新 upstream/main
  `e2c6e2c2e7f19d889c417eabeb040291c93379f7`，再按原顺序重放
  `support-hy4-preview@ff87b683ec9c6c1925dbedf12261914e45569b52` 的五笔净变更，最后只用
  一笔提交加入完整 Qwen3.8 适配。旧 Qwen 分支中的重复 cherry-pick 和历史对齐 merge 已移除。
- 重放后的 HY4 提交依次为 `492bc7e`、`08ddffe`、`0f31c6d`、`51fe9ca`、`134a45e`；
  Qwen3.8 最终提交为 `939600b`。以上提交的 author 与 committer 均为
  `ZenithJoyH <1355922182@qq.com>`。

2026-09-10 的首次迁移分支与提交：

- `ZenithJoyH/FlagGems:flaggems-for-day0` → `37716d41b0d6da34b9a9672b637d52f028d1a4e1`。
- `ZenithJoyH/vllm-plugin-FL:support-qwen3.8-flash` → `939600b323c02c21916f1f76bfb4cd8c2b02578d`；该 head 本身就是唯一的 Qwen3.8 适配提交。

两个分支按用户要求通过带精确 lease 的历史改写推送并从 GitHub 回读。服务器已测试树与本机
推送树分别以 tree
`8cb8cf98de8760cfbec0ec4f2c5f20af45c9fd4c`（FlagGems）和
`aeada664f13f0bb04efd8e5b54410c56cca149cb`（Plugin）一致性核对。容器、服务和 PPU 进程均未
停止或重启；vLLM 未修改。

## 2026-09-11 通用源码命名空间整理

用户将 FlagGems 目标分支调整为 `support-qwen3.8-flash` 后复核发现，新分支虽然继续从
`flag_gems.fused` 导出通用 ABI，但实现被放回
`src/flag_gems/fused/qwen3_8_flash_next/`。这会把纯 tensor/scalar 算子所有权再次绑定到首个
模型，与本问题已经确认的职责边界不一致。

本轮先将唯一 Qwen 提交重放到当时官方最新 `upstream/master@851ba604`，再将实现整理回
`fused/qsa.py`、`ple_state.py`、`gdn_packed_decode.py` 和 `common_slot_mapping.py`，删除产品源码的
Qwen 子包，并移除四个实现模块说明中的模型名和 day-0 表述。模型几何与 oracle 测试仍保留
`qwen3_8_flash_next` 名称，因为它们记录首个实际调用方的输入协议，不形成产品运行时命名空间。

最终 FlagGems 仍只有一笔适配提交：

- 分支：`ZenithJoyH/FlagGems:support-qwen3.8-flash`；
- revision：`7ba32ded1365d3ce6d3b7e28f41af7ddc7ff095c`；
- tree：`b8ad1870325e567be3c3b494f75bfcc838182919`；
- parent：`851ba60493692f5c84c5636f9117c53ab1f156ae`；
- author/committer：`ZenithJoyH <1355922182@qq.com>`。

提交通过精确 lease 更新，GitHub 回读、容器本地 HEAD 和
`zenith/support-qwen3.8-flash` 三者一致。容器内 FlagGems editable checkout 已切到该分支并保持
clean；适配容器没有停止、重启或删除。精简证据位于
`/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/flaggems-ownership-organized-20260911.txt`，SHA-256
为 `ae28fca9410ccae05cfb3fc3d4224ad3ac245c1f457b22e7714ac9094b9d5cf1`。

## FlagGems 证据

同步基线为 `187fc1f7bc59616d0c9eadd8d463e8d6068b22d9`，新增提交为 `37716d41`。
算子测试和独立 reference 一并提交到 FlagGems `tests/`；测试源码不导入 vLLM 或 Plugin。
本轮属于所有权迁移，没有新增 `/bug` 复现目录。

## 验证结果

- 静态：两个源码树目标模块 `compileall` 与 `git diff --check` 通过；容器没有 Black、isort、
  flake8 或 Ruff。
- FlagGems：80 passed，覆盖 CPU stride/dtype/null/duplicate 边界、QSA 独立参考、GDN/slot
  参数校验；1 个已有 benchmarker fallback warning。
- Plugin：405 passed，覆盖逐算子注册与 capability、完整共享 dispatch、vendor miss path、未来
  上游注册保护、runner n-gram、权重映射、PLE/QSA CPU 参考和 GDN 参数校验；3 个环境 warning。
- PPU 算子回归：最终源码树在物理 PPU 8 上运行四个 Qwen 调用方测试文件，`97 passed`，1 个
  已知 benchmarker fallback warning。原始证据：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/flaggems-ppu-regression-20260911.txt`，SHA-256
  `6f0900c57845b4e0bff63b4f5628809c5a570e25649c89a9e3b616b7b6a0a680`。测试暴露的唯一问题是
  测试仍导入已删除的模型命名空间；修正为公共 `flag_gems.fused` 后通过，并以同一逻辑提交修订为
  `7ba32ded`。
- eager 整模：TP8、PPU 8–15、maxlen 65536，健康 200；最小请求正确返回 `2`，响应 SHA-256
  `f2fae3d0bd49de7cbd32ce697cee13bc13fd50e4be32c8b1b619877d8946468b`。运行目录：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-eager-7ba32ded-20260911/`。
- graph 整模：相同容量，`FULL_DECODE_ONLY` 捕获 1/2/4/8/16/32 共 6/6；健康 200，最小请求
  正确返回 `2`，响应 SHA-256
  `44be46aadef730384da213591d6746e5d949fea1ec63b78137cb2df2183e1709`。运行目录：
  `/mnt/nfs/users/jinghao/qwen3.8-flash/04-runs/execution-mode-graph-7ba32ded-20260911/`。

## 限制与下一步

设备级与整模回归已完成，本问题可以关闭。正式 GPQA 精度仍由 acceptance 阶段独立判定；PPU
0–7 上的无关服务未被触碰，适配容器未停止、重启或删除。

设计审查结论：职责边界合理，静态、CPU、PPU 算子与 TP8 整模均无回归阻塞。

## 经验沉淀

- 可复用结论：推理框架对象拆包留在 Plugin adapter，tensor-level 加速器算子归 FlagGems；可选
  ABI 应使用能力守卫，避免旧 FlagGems 在注册成功后才运行时失败。
- 知识库处理状态：`local-only`。该结论已由现有贡献规范覆盖，暂不新增 troubleshooting 条目。
