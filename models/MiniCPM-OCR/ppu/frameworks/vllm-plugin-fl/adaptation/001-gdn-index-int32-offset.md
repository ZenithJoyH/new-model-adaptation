# 001：GDN 状态索引读写的 int32 地址乘法溢出

## 范围与结论

2026-10-23，`operator fix verified`；MiniCPM-OCR / `PPU-01` / `minicpm-ocr`。
用户仅要求修复当前容器并验证 eager/graph，明确不重启模型服务。
实际环境见 [environment](../environment/README.md)。本轮只做算子局部修复，模型级验收未执行。

故障首错为 `invalid page / _index_jit_function`，GDN 状态读取后的布尔清零同步点才报告非法访问。
失败请求 797 token，Mamba align 块表 `[1699,1700,7296]` 选择槽 7296。
从寄存器与缓存布局重建的 BF16 状态为 `[12966,16,128,128]`、stride
`[294912,16384,128,1]`。`7296*294912=2151677952` 超出 int32，回绕为负偏移。
保护区数值对照、编译中间码和无保护区单槽同步复现形成确定性缺陷证据。

[FlagGems #6846](https://github.com/flagos-ai/FlagGems/issues/6846) 的 GDN 调用点、
内核与设备错误签名相同，旧 checkout 的 index 文件与本轮起始文件相同。
但历史原案未冻结实际输入，原始日志后来被替换；本轮不追溯宣称那一次崩溃已完全闭环。
另一个历史 index_put 溢出记录作为候选经验，本轮在当前安装重新复现两个写回入口后才修复。

## 产品改动与职责

直接修改实际 editable 安装 `/workspace/FlagGems`，在 `tl.load(indices...)` 后立即
`.to(tl.int64)`，保证地址乘法之前扩宽；既有 program offsets 已由 `ext.program_id`
扩宽，无须改调度/graph。外部索引类型、API、shape、数据 dtype、alias 和注册策略不变。

| 文件 | 职责与必要性 |
| --- | --- |
| `src/flag_gems/ops/index.py` | GDN 状态读取内核的一处索引加载扩宽 |
| `src/flag_gems/ops/index_put.py` | 后续 GDN 状态写回共享内核的一处索引加载扩宽；覆盖 `index_put_`、`_index_put_impl_` |
| `tests/test_index.py` | 追加 4 项可维护大步幅边界回归 |
| `tests/test_index_put.py` | 追加 8 项两个写入入口的边界及保护区哨兵回归 |

没有模型/Host 特例、blacklist、native fallback、宽泛异常重试或导入路径覆盖。
没有修改 Plugin、vLLM、启动脚本、权重或原始故障日志。
保留已复现的依赖版本和 FlagGems HEAD，不通过升级改变受控基线。

## 修复前后验证

所有测试在空闲 PPU0 执行。新增用例使用 BF16 `[9109,16,128,128]`、
stride `[294912,16384,128,1]`、非连续 int32/int64 索引，覆盖槽号
7280、7281、7282、7296、9108。同一分配内的前缀保护区让旧版越界落在本测试缓冲区。
图测试 warmup/capture 后改变输入或写入值两次 replay，数值零容差；写入还核对 native 与哨兵。

| 阶段 | 读取入口 | 两个共享写入入口 |
| --- | --- | --- |
| 旧源码负对照 | 2 个 int32 失败、2 个 int64 通过 | 4 个 int32 失败、4 个 int64 通过 |
| 修复后边界用例 | 4/4 通过 | 8/8 通过 |
| 完整模块 quick/CPU-reference | 46/46 通过 | 66/66 通过 |

以上均无 skip/error。`--ref=cpu` 是现有用例的参考选择，实际 FlagGems 与 graph 在 PPU 执行。
新增用例有原生/精确值对照。修复后新进程重放原 `[12966,...]`、单槽 7296 无保护区用例，
native int32、FlagGems int64/int32 都正确退出，不再出现非法页。

| 算子文件 | 起始 SHA-256 | 修复后 SHA-256 |
| --- | --- | --- |
| `index.py` | `88faa12ea63a30663cd155f5b8097aece39e6dffe5d130897921c28f99fc36cd` | `560e169de3a0036c6b4739d2480a8ec0b6e770665ac66dd72549af55a3f9b6f5` |
| `index_put.py` | `acf250823e7afd93da643d62c6aa1614703086ad8d26b514540c5a83e03396f2` | `75be5c883a2de07c017213f762fd13396ee29887fb181e76a4a4df25e09f6a67` |

## 原始证据与恢复

以下相对路径均以 Host/容器同路径 `/mnt/nfs/users/jinghao/MiniCPM-OCR` 为根：

- 原始定位：`04-runs/ocr-index-6846-20261023/`，保留失败记录。
- 读侧备份：`02-issues/ocr-index-fix-20261023/before/`；写侧备份：`02-issues/ocr-index-writeback-fix-20261023/before/`。
- 对应 `07-bugs/ocr-index-fix-20261023/`、`07-bugs/ocr-index-writeback-fix-20261023/` 保存一次性操作程序，运行时不依赖这些程序。
- `04-runs/ocr-index-fix-20261023/`、`04-runs/ocr-index-writeback-fix-20261023/` 保存 before/after/module pytest 日志、JUnit、包身份、命令和真实源码 diff。
- 读侧结果下 `single-slot/` 与 `final-verification.json` 保存原故障复验、安装路径、哈希、不变项和最终完整 diff。
- 两个相应 `06-cache/` 保存生成内核/编译缓存，没有清空既有缓存或替换依赖。

恢复须先比对上述修复后哈希和当前使用方，再从备份恢复对应两个原文件；本轮未回退已验证修复。
最终核验 FlagGems 仅有上述四个文件差异，`git diff --check` 通过；Plugin HEAD/status/diff hash
与起始一致，vLLM checkout 不变，关键安装文件、启动脚本和原日志哈希不变。
测试进程已退出，PPU0 释放，容器持续运行，没有启动/重启模型服务。

## 设计审查与限制

起始 FlagGems 干净，无 inherited diff；公共算子层承担通用地址位宽语义，未绕开 dispatch、
增加厂商依赖或改变导入/注册行为。两个 quick 模块覆盖小 shape、None/布尔索引、空输入和错误接口。
结论：无 Plugin 产品改动；FlagGems 局部修复在当前 PPU 验证通过，可作为上游候选材料。
本轮未确认 PR base、未准备 PR、未 commit/push，也未发送 GitHub 消息。

其他平台硬件、普通模式完整 dtype 矩阵、性能、模型推理/精度、镜像均未验证。
用户要求不重启服务，不能把算子通过当作模型服务恢复或完整适配验收；正式阶段状态保持未验收。
本地 syntax-check 的 280 项 workflow 测试（19 skipped）、6 项 operations 测试及语法检查通过；
总命令仍因已有 MiniCPM-JEV 缺失部署指纹审计错误返回 1，未修改无关记录。
知识库处理状态：`local-only`，未执行回顾或跨模型推广。

## 2026-10-23：PR 提交与最终差异审查

用户随后明确要求提交 PR 并关联此前 issue。已创建
[FlagGems #7582](https://github.com/flagos-ai/FlagGems/pull/7582)，目标为
`flagos-ai/FlagGems:master`，确认的 base `0ac595314c1b5a8c67b2079284f1259cb6baa6dd`；
head 为当前 GitHub 账号所属 `ZenithJoyH/FlagGems:fix/6846-gdn-index-int32-offset`，
HEAD `f6e50c37440b5132dc5873a6d2001055e595e851`。未修改已有分支或覆盖其他人的工作。

PR 净差异只有 `src/flag_gems/ops/index.py`（1 行替换）和 `tests/test_index.py`
（追加 66 行），两次提交分别为 `4e9adc35f2dbd4c8f3d8e963e50bdf668a32233c` 和上述 HEAD。
API compare 核对为相对已确认 base ahead 2 / behind 0；源文件、测试文件均与本轮容器中
通过验证的内容逐字相同，SHA-256 分别为
`560e169de3a0036c6b4739d2480a8ec0b6e770665ac66dd72549af55a3f9b6f5`、
`05598dd040f92ba2d5b1d764805ac8ffb4057d905464064e87fbc6f9d1eace6b`。
确认 upstream 的两个对应文件与容器起始版本一致，不夹带其他 base 差异、日志、权重或私有路径。
本地 Black、isort、flake8 检查通过，正式 PR 验证说明只引用读取侧 4 项及模块 46 项结果。

为避免重复提交，写回修复由既有 [#6413](https://github.com/flagos-ai/FlagGems/pull/6413)
追踪，不包含在本次新 PR。说明中显式列出与 [#5882](https://github.com/flagos-ai/FlagGems/pull/5882)
通用读取改动的重合；本 PR 额外提供 #6846 相关的 BF16 真实大步幅、非连续索引和变输入
graph 回归，维护者可以选择整合。未擅自改写既有两个 PR。

Issue 章节使用 `Addresses #6846`，保留历史原案未捕获实际输入的限制，没有把未完成的模型级
验收写成通过。设计审查结论：可作为当前范围的 PR 候选；其他平台实测和完整新 upstream
分支由 CI/维护者验证。PR 已创建但未合并；未请求额外审阅人，未给 issue 另发消息。
本轮 PR 整理不修改远端安装、容器、启动脚本或服务状态，先前不重启服务约束继续有效。
