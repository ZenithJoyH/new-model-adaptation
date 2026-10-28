# PPU-13 重启后 GPQA Diamond 32 并发全量诊断

日期：2026-10-02。唯一目标 Host `PPU-13`，模型容器 `minicpmV4.7-35B`，
评测容器 `flageval_llmeval-jinghao`。批准工作根在 Host、两个容器内均为
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`，设备号:inode 同为
`41:14016406509`；模型权重只读路径为
`/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`。

## 服务与输入身份

用户重启后的根级 `start-model.sh` SHA-256
`62d97f6ec4b9be9bcd7ebefbaa37aa08b6685fabac9b683ba859be3f422806b7`。
与上一版脚本 SHA-256
`398f50145f6f66f8423007233a9155e1004380255838a6f5a8608d32b20d03f1`
逐行比较，仅增加
`VLLM_FL_FLAGOS_BLACKLIST=nonzero_numpy,index_put,nonzero,copy,index_put_,index`。
当前 API PID `1709269` 的进程环境确有该变量和
`CUDA_VISIBLE_DEVICES=0,1`；Plugin 的 `vllm_fl/utils.py` 会读取这一变量。
TP2 的 EngineCore/Worker PID 为 `1709749`、`1710034`、`1710035`。
服务仍是 8010 端口、前缀缓存开启、`FULL_AND_PIECEWISE`，
PIECEWISE 和 decode FULL 均完成 7/7 图捕获；终态 `/health` HTTP 200，
同一 API PID 未变。Plugin、vLLM、FlagGems checkout HEAD 分别为
`3a27a6fb2d514cdf55c00481bf813225dac63319`、
`ee0da84ab9e04ac7610e28580af62c365e898389`、
`1a38df24f72ca5a4a6a24650b5d66356709750ba`，Plugin 保留此前
已有工作树差异。本轮没有修改源码、权重、根级脚本或容器。

原生评测 runner `llmrun.py` SHA-256
`4f9076aaae6e3efb32246a66053f971d1d70b04d99f196599daf5e57ca2eb2cc`；
GPQA task YAML SHA-256
`8b94339a9f47545f44edcbb509ce277e0809057294e162638ed1caccb7be4a9e`。
冻结配置位于
`03-acceptance/gpqa-32c-restarted-20261002-1820/config.json`，SHA-256
`809f9776d1562b4c993513e6d107546c4674599b60f034a6e71e83ce8095e662`。
保持原参数：`temperature=1.0,do_sample=false,max_gen_toks=18000,top_p=0.95,top_k=20`，
并发 32，请求超时 600 秒，重试 0，GPQA Diamond 全量 198 题；
`formal_acceptance=false`。独立缓存位于
`06-cache/gpqa-32c-restarted-20261002-1820/`，临时目录为
`05-tmp/gpqa3/`。Ansible 语法、`--check --diff`、原生 preflight、
冻结文件哈希、防覆盖和当前服务实例绑定均通过后启动。

## 结果

原生进程退出码 0，198/198 题、396 行样本齐全，0 timeout、0 API 错误。
与 NV 参考 `gpqa_cpm-35B_nv.jsonl` 的 `doc_hash`、`prompt_hash`、
`target_hash` 和 `target` 均逐题 198/198 一致。原生结果：
`strict-match` **146/198（73.74%）**，`flexible-extract`
**134/198（67.68%）**。按两份参考文件均能逐题重建的历史答案提取式，
同一份新输出的严格分数为 **153/198（77.27%）**；NV 参考为
152/198，之前未启用此黑名单的 PPU 同参数复跑为 151/198。
本次与 NV 的同口径配对是共同正确 139、NV 独对 13、PPU 独对 14、
共同错误 32。

当前 task YAML 的原生提取结果与参考提取式在 10 题不一致，净造成
7 道正确题的分差。诊断提取式是对 `resps[0][0]` 使用
`re.findall(r'answer is[\s*]*[\(\[]?([ABCDEFGHIJ])', text, re.I)`，
取最后一次匹配、未匹配记 `[invalid]`；它能逐题 198/198 重建
原始 NV/PPU 参考文件的 `filtered_resps`，但没有原始 task 版本回执，
因此 **153/198 是参考同口径诊断分数，146/198 才是本次原生分数**。
第 127 题达到 18,000 token 上限且未给出完整最终回答，两个提取式
从思考文本中选到不同字母；该题保留在 198 题分母中。
原始异常第 7 题重复感叹号、第 33 题乱码此次均未出现，两题均正常
回答且按本次原生规则得分。

结果与样本位于远端
`04-runs/MiniCPM-V-4.7-35B-A3B/gpqa-32c-restarted-20261002-1820/gpqa_diamond_generative_cot/attempt-1/MiniCPM-V-4.7-35B-A3B/`。
`results_2026-10-02T10-42-23.695288.json` SHA-256
`9a4f8653292f843d2c55d2a5f28333037ddc4b3e3b2da91d5b7577b653bb81e8`；
`samples_gpqa_diamond_generative_cot_2026-10-02T10-42-23.695288.jsonl`
SHA-256 `bbb54558ec31646f23ba75d3cf75d9a2e15884572bd3967146af4cc4beac664e`。
控制日志 `04-runs/gpqa-32c-restarted-20261002-1820-controller/controller.log`
SHA-256 `79af690497ca2e1f4c89ea03075af91542623870dd1d08570e92025a632774d8`；
`exit-code` 为 0，生效配置 SHA-256
`77f933a0186c5c9ae20623427ee2f119c091b3db6bca7aa317cbc8e2a6b9ce9a`。
当前服务日志无 `invalid page`、非法访存、EngineCore 崩溃或 RPC timeout。

这次在新增黑名单的实例上完成一轮 32 并发全量 GPQA，未复现设备故障；
单轮成功不能证明黑名单就是根因修复，也不能从 151→153 的同口径
波动断言精度提升。当前 prefill 仍为 PIECEWISE，正式执行模式、
sanity 和冻结阈值的精度验收前置条件尚未完成；`framework.yml`
继续保持 `environment_ready`、accuracy `not_started`。
