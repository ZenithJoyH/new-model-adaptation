# Plugin 适配计划与差距清单

材料导航：[环境索引](README.md) · [Plugin 设计审查](plugin-change-review.md)。
设计审查与整模型验收分开判定；本轮目录整理未重写以下计划或验证结论。

## 输入材料

- 模型结构与推理链路分析：`../../architecture-and-inference.md`。
- 平台环境分析：`../environment/environment-analysis.md`。
- 用户提供的参考文件：模型目录本身；用户未提供额外 patch 或实现文件。
- Plugin、FlagGems、vLLM baseline：见 `runtime-config.yml`、`history/progress.md` 和 `reference-files.md`。

## 修改边界

- 只允许修改适配容器中的 Plugin 代码。
- vLLM 源码必须保持不变并保留前后状态证据。
- 适配容器不得停止、重启或删除。
- 服务和当前适配相关进程可以按需停止或重启，但必须记录并核对目标。

## 初始差距清单（保留初始判断，当前状态见下节）

| ID | 模型组件/阶段 | Plugin 当前路径 | 平台能力 | 算子来源 | eager 影响 | graph 影响 | 修改计划 | 最小验证 | 状态 |
|---|---|---|---|---|---|---|---|---|---|
| G01 | config/模型注册 | `vllm_fl/models`、`vllm_fl/configs`、plugin init | vLLM plugin registry | Plugin 新增 | import/load 目前失败 | 注册必须在 capture 前稳定 | 引入与当前 vLLM API 兼容的 `glm5_next` config/model，保持 vLLM 只读 | AutoConfig/registry/import、dummy load | open |
| G02 | 权重映射/TP16 | model loader 与新模型类 | 16×96GiB | Plugin 新增+既有 loader | BF16 120 分片 | load 后地址需稳定 | 映射视觉、45 层、MTP、MoE experts | 参数名/shape 覆盖率 100%，最小 load | open |
| G03 | KDA linear attention | 无 GLM5 路径 | PPU Triton/可能 FlagGems | 同步后确认 | 34 层 prefill scan/decode update | state/conv cache 不得动态分配或 host sync | 先检索 FlagGems；兼容则按 dispatch 接入，否则 plugin-owned Triton | PyTorch reference，dtype/shape/boundary/eager/graph | open |
| G04 | mHC | 无 | 通用 tensor ops/可能融合 | 同步后确认 | 4 路、20 次 Sinkhorn | 固定循环可 capture，禁止数据依赖 host 分支 | 参考实现→dispatch→必要时 Triton | 固定 seed 数值、45 层组合、replay | open |
| G05 | sparse MLA/Indexer | 已有 Hy4 MLA/Indexer 候选 | PPU native + FlagGems | Plugin 已支持候选，需 contract 验证 | q/kv/index shape 不同 | paged cache/top-k 地址和宽度 | 对照 GLM5 shape 重用或扩展既有 dispatch | cache/update/topk/sparse MLA eager+graph | open |
| G06 | dense MLP/SwiGLU | 既有 linear/activation dispatch | PPU GEMM/Triton | Plugin 已支持候选 | `swiglu_limit=10` 可能需新语义 | fused activation capture | 验证 limited SwiGLU 语义和 TP mapping | BF16 数值、极值和 graph | open |
| G07 | 288-expert MoE | Hy4 MoE candidate | PPU native routing + FlagGems GEMM | Plugin 已支持候选，需扩展 | `noaux_tc`、top8、FP32 router | 动态 token routing | 验证 routing、dispatch、expert、combine 与 TP/EP | 每子算子及组合 eager+graph | open |
| G08 | 视觉 encoder/merge | 无 GLM5 multimodal model | 通用 attention/GEMM | Plugin 新增/既有算子 | 可变图像/视频 token | 需要 bucket 化 | 实现 processor contract 与 vision tower | 文本/单图/短视频 | open |
| G09 | MTP | Hy4 MTP 只能作候选 | vLLM speculative API | Plugin 新增/候选 | 单层 nextn | cache/index sharing capture | 先完成非 MTP 正确性，再接入受支持接口 | logits/acceptance、eager+graph | open |
| G10 | sampling/服务 | vLLM 通用路径 | PPU logits ops | vLLM 只读+plugin dispatch | vocab 154880 | dynamic batch bucket | 配置 TP16/50K；验证 reasoning/tool parser 后再固化 | readiness、固定 prompt、并发 8 | open |

算子来源必须明确为：Plugin 已支持、FlagGems 兼容实现、Plugin 内新增 Triton 实现，
或尚未确认。不能使用临时直接调用绕过 Plugin dispatch。

## FlagGems 同步与检索证据

- 同步前 master、upstream 明确、工作树 clean，revision `60d043094d0217cad75528cb0e47a606c87ab1e4`；remote 细节见 environment 及同步 playbook。
- fast-forward-only 同步命令：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/sync-ppu13-flaggems-master.yml`，fetch 后 ff-only pull。
- 同步后 revision `db33988eca77bcc45bb70719ca6b1db94229b4c6`，clean。
- 原 FP8 index cache 量化实现不兼容 PPU FP8 类型，已打包 `/bug`；当前专用插件分支通过 PPU BF16 cache 路径规避。

## 当前实施状态（2026-09-04）

专用插件路径 `/workspace/vllm-plugin-FL-glm53-adaptation`，基线 `2658244`。
以下结论替代初始差距表中的“无实现”，但不将组件测试等同于整模验收。

- G01：已有 GLM5 config/registry/VLM 支持，模型专项 27 项通过。
- G02：整模 BF16 TP16 120 个分片完成加载，482.36 秒；未完成推理数值验收。
- G03–G07：采用专用分支既有 model-ops dispatch、PPU backend、FlagGems 及插件 kernel；
  dispatch 275 项、PPU eager/graph 28 项通过。精确测试入口见 `tests/run_glm53_reference_ppu_tests.sh`。
- G05：新增三个整模集成修复：有效 profile 黑名单传播、worker MLA prefill 注册、
  worker GLM compressed-cache adapter 安装。四种压缩页的 eager/graph 最小测试通过。
- G08：保留 ConditionalGeneration 和视觉塔，没有偷偷改为纯文本架构；视觉请求尚未验证。
- G09：当前服务不启用 speculative decoding；MTP 未验收，不能声称可用。
- G10：TP16/50K eager 第四次启动中，尚无成功请求，正式验收未开始。

剩余重点风险：完整缓存初始化、prefill/decode、graph 整模运行、多模态请求、
graph 并发 8、GPQA 全量准确率与性能。当前不做优化，先建立正确性基线。

## 验证顺序

依次验证导入与注册、单算子、组件组合、最小模型执行、完整服务，并为适用项覆盖
`eager` 与 `graph` capture/replay。

## 2026-09-07 40K 截断样本复核的部署边界

本轮不改 Plugin、vLLM 或 FlagGems 代码；唯一服务语义变化是下一 graph 实例的
`max_model_len: 50000 → 65536`。定向评测只重放正式轮中 19 个 `finish_reason=length`
样本，将请求 `max_tokens: 30000 → 40000`，采样参数和 prompt 保持不变。客户端超时设为
14400 秒，仅作为覆盖 40K 生成耗时的 transport guardrail，不改变采样；定向结果不拼接成
正式 GPQA acceptance。

部署指纹在服务切换前从实际容器中采集。Git clean/dirty 不能只看 HEAD；tracked diff 按
原始 `git diff --binary --no-ext-diff HEAD --` 字节散列，untracked 按模板指定的规范 JSON
散列。模型 revision 使用正确权重 `config.json` 与 safetensors index 的内容摘要组合：

```bash
sha256sum models/GLM-5.3-Flash-BF16/ppu/environment/runtime-config.yml
ssh PPU-13 'docker exec glm5.3-flash bash -lc '\''set -euo pipefail; sha256sum /mnt/cpfs/models/GLM-5.3-Flash-BF16/config.json /mnt/cpfs/models/GLM-5.3-Flash-BF16/model.safetensors.index.json; for repo in /workspace/vllm /workspace/vllm-plugin-FL-glm53-hy4-adaptation /workspace/FlagGems; do echo REPO=$repo; git -C "$repo" rev-parse HEAD; git -C "$repo" diff --binary --no-ext-diff HEAD -- | sha256sum; python3 - "$repo" <<"PY"
import hashlib,json,pathlib,subprocess,sys
repo=pathlib.Path(sys.argv[1])
names=subprocess.check_output(["git","-C",str(repo),"ls-files","--others","--exclude-standard","-z"]).split(b"\0")
items=[]
for raw in names:
    if not raw: continue
    rel=raw.decode("utf-8")
    items.append([rel,hashlib.sha256((repo/rel).read_bytes()).hexdigest()])
payload=json.dumps(sorted(items),ensure_ascii=False,separators=(",",":")).encode()
print(hashlib.sha256(payload).hexdigest(),json.dumps(sorted(items),ensure_ascii=False,separators=(",",":")))
PY
done'\'''
```

启动、sanity 与 19 题定向重放由同一个实际驻留 supervisor 管理。切换前重新核实
8010、16 张物理 PPU、三个 checkout 以及当前服务身份；只停止 PID 文件与 8010 共同
指向的当前适配服务，不停止或重启 `glm5.3-flash` 容器。

远端工作根按用户指定统一为 `/mnt/nfs/users/jinghao/glm5.3-flash`（host/container 路径
相同且映射已核验）。最终环境 helper 放 `environment/`，验收 wrapper 放 `acceptance/`，
本轮日志/结果放 `runs/graph-65k-40k-20260907-v2/`，临时/cache 放 `tmp/`、`cache/`。
FlagGems tuned DB 从现有容器依赖复制到 scoped cache，服务显式使用该副本；checkout 和
权重保持外部只读。

首次采集命令把 `git ls-files -z` 的 NUL 分隔符误写成字面量 `\\0`，在 Plugin 首个
untracked 路径报 `ValueError: embedded null byte` 并因 `set -e` 停止；已取得的模型摘要、
vLLM clean 摘要和 Plugin tracked diff 摘要有效，但 Plugin untracked 与 FlagGems 未完成。
修正上方命令为 Python 字节 NUL `b"\0"` 后重新运行完整三仓采集，不复用半截输出。
