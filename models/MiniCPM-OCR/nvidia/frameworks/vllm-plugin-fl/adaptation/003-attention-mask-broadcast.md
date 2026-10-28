# 003：最新 FlagGems 广播 attention mask 非法寻址

2026-10-20，H100-149 / minicpm-ocr-flagos-runtime，GPU1（容器CUDA0），BF16、单卡TP1。普通安装实际路径 `/usr/local/lib/python3.12/dist-packages/flag_gems`，上游master 8200f71f51d784d54a5a51019cb955acb74d64c1。

## 签名和受控复现

`04-runs/eager-v3-20261020/service.log`：视觉塔 Idefics2 attention → F.scaled_dot_product_attention → FlagGems `_scaled_dot_product_cudnn_attention` → attention.py `_attn_fwd`，首次dummy视觉计算发生CUDA非法访存。新环境与历史MiniCPM-V4.7 NVIDIA003的完整签名相符，重新检查当前上游源码确认广播维仍直接采用原始stride，不能依据旧记录直接宣称修复。

新专属用例根 `07-bugs/003-attention-mask-broadcast/`，`repro.py`来自已验证旧最小用例并在本工作根原位重新执行，无/bug副本、无旧容器依赖。固定seed42，BF16，QKV `[2,16,128,72]`，strides `(442368,72,3456,1)`，mask `[2,1,1,128]` stride `(128,128,128,1)`；PyTorch MATH SDPA参考。

修复前 `before-scaled-128.log`：241369/294912元素（81.8%）超过atol=rtol=0.02，max_abs=1.0625。独立算子复现证明缺陷存在于当前实际安装，而非只在整模配置出现。1024长度崩溃由实际整模日志保留，复验将覆盖同尺寸独立路径。

## 根因、修复与边界

`scaled_dot_product_attention_forward`以head/query索引完整attention矩阵，却直接传入紧凑mask的非零head/query stride。读取越过实际mask存储，既可能数值错误也可能非法访存。

直接修改实际安装的 `flag_gems/ops/attention.py`：复用已有 `broadcasted_stride`，按 `[B,Hq,Sq,Sk]` 计算目标stride，使size=1轴stride为0。无二次方mask展开、无额外CUDA分配或主机同步。无mask分支不变，完整mask的原stride保留；通用广播mask可按既有shape工具校验。没有新增模型/硬件特判、吞异常或黑名单。bool mask转换、dropout/backward/LSE等既有语义未扩大修复范围。

源码原件、source.patch与patch-manifest.json留在该用例根。before SHA-256 `d6b180e640e0e57965ef6780dc36ab2c266135d9e1cd0d8629f5860579d87a75`，after `56093425822bf1518ea65e19586885ca4c64526e0f4e5c04ca4130119da61850`。构建checkout并非实际导入路径，不在那里放替代版本；没有PYTHONPATH。

维护回归新增至本安装随包测试目录 `flaggems_tests/test_attention_mask_broadcast.py`。覆盖两个public入口、FP16/BF16、65/97边界长度、head_dim72、非连续QKV、compact/expanded/二维/stride2/无mask和变输入graph replay。实际结果待完成后补录。其他硬件、GQA、backward、任意有限bias、bool语义未声称通过。整模eager/graph仍须重新验证。

设计审查：普通安装无Git状态，按版本、upstream提交与实际文件前后hash审查；用户未指定PR base，本轮不提交PR。作用面为共享attention forward的广播寻址，实际导入的维护测试与修复是交付必要内容。参考历史上游PR #6871仅用于经验定位，当前任务不发送消息或更新该PR。

## 已完成修复回归

`regression-after.log`：24/24通过（200.87秒，20项eager与4项graph）；仅存在安装随包测试未带原仓pytest.ini导致的attention marker警告。测试通过实际public FlagGems wrapper运行，未mock目标计算。

`after-scaled-1024-graph.log`和`after-cudnn-1024-graph.log`：两个入口eager最大绝对误差均0.001953125，分别capture一次并在两次修改QKV后replay通过。`manifest-20261020.json`和README.md保存运行环境、精确镜像/容器、命令、容差及证据哈希。整模最终eager15项与HF参考的生成token ID也全部一致，证明没有仅靠规避SDPA或禁用FlagGems通过。
