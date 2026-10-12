# 002：完整 MoE 入口与分阶段调用的性能对照

日期：2026-10-09。范围：mx-59 / `qwen3.6-35B`，当前 Qwen BF16 TP2 的局部算子
对照。诊断完成；本轮没有新增 Plugin/FlagGems-vLLM 产品修改，不代表整模性能验收。

## 当前实现与结论

上一轮已增加 MetaX 完整入口：

```text
TritonExpertsFL.apply
  → flaggems_vllm.runtime.backend._metax.ops.outplace_fused_experts
  → fused_experts_impl(..., inplace=False)
```

`outplace_fused_experts` 是 out-of-place 语义包装，不是另一套计算。
现场同时核实 `flaggems_vllm.fused_experts_impl.__module__` 为
`flaggems_vllm.runtime.backend._metax.ops.fused_moe`。
因此用户提出的完整入口调用方式在当前已安装代码中已经成立；FP16/BF16 非量化、SiLU、
无 LoRA/无 expert-map、权重 dtype 与输入一致时进入该路径，其他条件保留既有分阶段处理。

完整入口可以统一配置 GEMM、融合激活，但不是单个覆盖全部 MoE 的 kernel，也不能仅由
函数名推断加速。当前实测有收益，也有回归；不能概括为完整入口总是更快。

## 实验边界与方法

复核容器 ID、映射、解释器和源码身份，与 [001](001-mx59-moe-flaggems-vllm.md) 一致。
工作根仍为用户批准的 `/public-flash/jinghao/qwen3.6-35B`，host/container 同路径，
realpath/stat 与 Docker bind mount 再次核实。只使用空闲物理 GPU 0（MetaX C550），
没有向运行中的模型服务发送评测请求，没有停启服务/容器或操作其他 Host。

- BF16，`E=256,K=2048,N=256,topk=8`，`w1=[256,512,2048]`、
  `w2=[256,2048,256]`。M 是单次 MoE 处理的 token 数，不是请求并发。
- 两条路径使用相同输入、权重、路由和 `expert_map=None`，无 LoRA；包括完整路径
  写入 caller output 的 `copy_`，以及原分阶段路径的实际工作区/activation/求和。
- 对照只在诊断脚本内暂时替换 Plugin 模块的 fast-path 平台守卫，使同一 `apply`
  进入分阶段实现；backend adapter 的真实 MetaX 检测、strict dispatch、原始计算均保留。
  未通过 identity expert-map 增加另一条路径独有的排序成本；未替换实际计算为 mock。
- 三个阶段算子解析到 `default.flagos`；完整路径记录两次真实库内 GEMM dispatch，
  分阶段路径记录两次实际阶段 GEMM；计数包装在计时前恢复，计时不带 profiler。
- 每个 M 在 eager 与 graph 各预热 10 次，5 轮各 100 次，轮间交替路径顺序；
  记录 CUDA event 与 wall time，下表是 event 单次耗时的 5 轮中位数。
  eager event 区间包含可能的主机发射间隙，不等同于单个 kernel 的纯执行时间。
- 每种 M 都对 FP32 PyTorch 按 expert 分组的参考检查完整输出，
  `rtol=0.02,atol=0.0003`；graph 额外两次修改输入后 replay 并重新对照。
  10 种 M 的 20 个 eager/graph 组合均通过，初始对照最大绝对误差不超过 `1.99e-5`。

这是组件级诊断，不调用服务性能 Skill 的 single-scenario/full-suite，也没有生成
正式 benchmark receipt。不存在服务端前缀缓存参与；原服务配置未改变。完整模型的精度
与性能验收仍须按项目原生 runner、缓存机制和先精度后性能的顺序执行。

## 实测结果

加速比 = 分阶段耗时 / 完整入口耗时；大于 1 表示完整入口更快。

| M | graph 分阶段 μs | graph 完整入口 μs | graph 加速比 | eager 加速比 |
|---:|---:|---:|---:|---:|
| 1 | 65.69 | 64.26 | 1.022× | 1.171× |
| 8 | 229.24 | 216.42 | 1.059× | 1.184× |
| 16 | 367.35 | 352.29 | 1.043× | 1.654× |
| 32 | 554.58 | 547.39 | 1.013× | 1.100× |
| 64 | 824.36 | 701.16 | 1.176× | 1.157× |
| 128 | 809.79 | 688.50 | 1.176× | 1.227× |
| 256 | 829.83 | 727.81 | 1.140× | 1.144× |
| 512 | 874.65 | 951.83 | 0.919× | 0.941× |
| 1024 | 1143.94 | 914.55 | 1.251× | 1.238× |
| 2048 | 1237.34 | 1295.43 | 0.955× | 0.953× |

M=512/2048 的 graph 延迟分别增加约 8.8%/4.7%；补测 M=1024 又有约 1.25× 加速，
排除了本轮以单一 token 阈值分割两条路径的依据。保留完整入口和已有兼容路径，
不为这些离散点添加新的 shape/M 白名单或全局策略。

## 实现事实与未证实归因

- M=1/8 时库内 `FUSE_SILU=False`；M=16 及本次更大 M 时 GEMM1 的
  `FUSE_SILU=True`，GEMM2 为 False。这是输入相关融合，不能称所有情况都融合。
- 全部记录的 `direct_sum=False`；当前库把该 cutoff 设为 `1 << 60`，未观察到该路径。
- 当前 TP2 shape 的 `_is_qwen_plain_half_shape=False`，未命中该专门分支；普通半精度
  配置随 M 改变，包括 tile 和 num_warps。诊断保留两次 GEMM 配置供后续单变量调优。
- 更少 Python dispatch 和激活 kernel 是候选收益来源；M=512/2048 的根因未通过
  单变量 config 试验或设备 profiler 证实，不能把差异归因于某一个配置项。
- 没有调优库内 kernel/config，也没有验证真实模型吞吐；本轮收益只覆盖上述输入分布、
  installed revision、设备和单算子测量。其他 GPU 同机运行状态不是整机独占保证。

## 可复核证据

以下均相对批准工作根；完整产物留在远端：

- 诊断：`02-issues/moe-full-vs-staged-20261009/{compare.py,compare-boundary.py}`。
- 首轮：`04-runs/moe-full-vs-staged-20261009/{plan.json,identity.json,results.json}`。
  results SHA-256：`19f7ae20f7e0c177faa0c183f0676e9c0316320e9861e9d5f8823cbb203870e8`。
- 补测：`04-runs/moe-full-vs-staged-boundary-20261009/{plan.json,identity.json,results.json}`。
  results SHA-256：`bc20a651fc08e11c8b58db9e5a8ca13f3828faa97e634ae3a6a8b8148a0c6273`。
- 汇总：`04-runs/moe-full-vs-staged-summary-20261009.json`，SHA-256：
  `13b054397ab0cb626a828cb664f9d26bf86396aa6e5b9583fcbb8a341b8ef40a`。
- 同名 `.log` 保存 stdout/stderr；每轮的源文件哈希、Git HEAD/status 与计划同时保存。
  汇总器重新核对 20 项记录、5 轮计时完整性、三个相关源文件哈希，以及四个组件的
  HEAD/status；结果与测量前一致。

示例复现（仍需先确认 GPU 0 空闲；使用新 output 路径，避免覆盖已有证据）：

```sh
# 容器 cwd: /public-flash/jinghao/qwen3.6-35B
CUDA_VISIBLE_DEVICES=0 FLAGGEMS_VENDOR=metax VLLM_FL_STRICT=1 \
  python -B 02-issues/moe-full-vs-staged-20261009/compare-boundary.py \
  --tokens 16 64 256 1024 --output 04-runs/<new-run>
```

复现时缓存、TMPDIR 沿用该工作根的 `06-cache/` 与 `05-tmp/`，不使用 `PYTHONPATH`。

## 审查与状态

本轮结论为“无新增插件变更”：复核并验证了上一轮完整入口，新增内容只有仓库外诊断
和本地精简记录。Plugin detached HEAD、未确认 PR base； inherited dirty/untracked
改动保留，未提交/推送/建 PR；vLLM 只读且保留原有 dirty 修改，不能称其 clean。
现有推理 worker 仍是原 PID，本轮未重启，它们不会自动加载此前新增入口。
完整框架五阶段状态未推进；不将算子微基准当作正式模型验收。
经验状态：`local-only`。
