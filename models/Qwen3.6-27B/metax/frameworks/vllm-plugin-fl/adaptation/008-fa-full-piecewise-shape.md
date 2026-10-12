# 008：FULL_AND_PIECEWISE decode 捕获时 FA 输出形状失配

## 元数据与现象

- 状态：旧缓存复用根因受控验证，缓存隔离workaround通过；2026-09-24；Qwen3.6-27B / MetaX / mx-58 / qwen3.6-27B / vllm-plugin-fl profile v3。
- 用户原始脚本、日志：Host/容器同路径 `/public-flash/jinghao/qwen3.6-27B/start-model-new.sh`、`service.log`。
- TP2 BF16 GPU0/1，max_num_batched_tokens=16384，默认 max_model_len=262144、mode=3，FULL_AND_PIECEWISE。
- mixed PIECEWISE 捕获51/51完成；decode FULL 0/35时两个rank均在 `flaggems_vllm/ops/flash_api.py:337` 的输出shape断言失败。GDN prefill/decode均已选default.flagos。早期FA2可用性探测错误没有终止初始化。

## 基线、边界与已有经验

Plugin HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`；继承007的7个tracked修改及2个untracked文件。vLLM HEAD `bc150f50299199599673614f80d12a196f377655`，继承diff SHA256 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`。FlagGems `c6f46cc970ea0bef8927ee657c021bd8621e3bb0`，FlagGems-vLLM `05d0ff0547dc9cc7cce18f47c6f57cc9d04f0777` 均只读、不重新同步，不是新算子选型。Plugin editable安装身份及`/public-flash`同路径bind已核实。8000/PID154980保持不动，容器不停止/重启。

历史003在max_num_seqs=4、tokens=1024下FULL_AND_PIECEWISE通过；007最终patch只测mode0 FULL自动降为FULL_DECODE_ONLY。均不能证明当前规模通过。知识库未找到完整同签名条目。

## 诊断与计划

已知：FA的out和query形状不一致；不知道具体失配维度和上游来源。缓存图标注两者同为`[s18,12,256]`，不足以证明运行时一致。原日志复用了`/root/.cache/vllm/torch_compile_cache/c5a010b2be`。

先在`02-issues/fa-shape-20260924/sitecustomize.py`通过临时导入观察器只读打印失配参数，产品源码不加诊断代码；独立`04-runs/fa-shape-baseline-20260924`及`06-cache/fa-shape-baseline-20260924`。非性能诊断恢复prefix caching启用，与原失败不同，不能作为单变量性能或cache对照。新基线建立后每次仅改变一个实质变量。

修复归属待定位：若输入契约错误则现有attention backend；若捕获/缓存公共语义错误则现有compilation扩展层。不得删断言、盲目reshape、绕过dispatch或改只读依赖。保留FA与GDN各自现有接入路径。

验证计划：最小负/正对照，相关单测，当前规模FULL_AND_PIECEWISE捕获及变输入replay，默认FlagOS和GDN黑名单回原链路，eager回归。只做适配回归，不执行正式准确率/性能/验收或宣称跨平台通过。PR base未确认，不提交推送。

## 受控诊断进展

- 新缓存基线 `04-runs/fa-shape-baseline-20260924/service.log`：FA shape断言未出现，PIECEWISE 51/51完成、decode FULL首档完成；第二档预热在GDN `state.index_select`分配372MiB时OOM。默认gpu_memory_utilization=0.9，max_num_seqs未缩小。进程自行退出，原8000/PID154980仍在。
- 新基线后仅增加`--gpu-memory-utilization 0.8`，新run `04-runs/fa-shape-fresh-20260924`；其独立缓存仍初始为空，用于确认图档位不变情况下资源余量是否足够。
- 原`c5a010b2be`缓存的`artifact_compile_range_1_16384_subgraph_6`日期为9月23日，其内嵌生成代码输出含`[s18,24,128]` GDN张量；用户启动生成的`computation_graph.py`在同一编号输出Attention的`[s18,12,256]`张量。旧缓存复用与当前FX图不一致是待受控验证的根因假设，不视作kernel算错。
- 仅复制原运行时缓存到`06-cache/fa-shape-oldcache-20260924/compile`，重定位两个rank的缓存索引以引用副本，原760MiB缓存不变；不复制任何产品source checkout。

## 根因验证与修复

2026-09-24 11:29容器日志：当前009修复源码、TP2/BF16/GPU0/1、prefix开启、gpuutil0.8等保持不变，将cache_dir指向旧缓存副本后，日志明确`Directly load the compiled graph(s)`。mixed51/51捕获完成，decode FULL0/35再次触发相同FA断言；两rank观察到`q=(256,2,256), stride=(7168,256,1)`，`out=(256,12,256), stride=(3072,256,1)`。因此旧subgraph编号/调用ABI与当前图不一致，不仅仅是某个out buffer大小问题，不可强行reshape或删除断言。证据`04-runs/fa-shape-oldcache-20260924/service.log:665`，进程712355因EngineCore失败自行退出。

对照新缓存的`04-runs/fa-shape-fixed-graph-20260924`同源码51/51+35/35全部完成，8条输出与原vendor一致。旧/新对照另有临时FA观察器开关差异，观察器只包装参数记录并原样委托，不改变数值/参数；旧缓存实际加载及精确shape失配均已直接记录。

`start-model-new.sh`已改用`06-cache/fa-shape-fixed-graph-20260924`命名空间，不删除或覆盖旧cache。保留FULL_AND_PIECEWISE及默认compilation mode3、tokens16384、maxseqs256、TP2/GPU0/1；gpuutil0.8为图捕获临时buffer预留显存。此次用户已自行将脚本gpuutil改为0.8（旧文件SHA256 `085de1160a766a21d258888aa9ce1029e632b27c55c9a15a279518880523523d`），修复保留该更改。原脚本备份`02-issues/fa-shape-20260924/start-model-new.original.sh`字节hash一致。

修复脚本最终SHA256 `5a54d34899a8a78935fd6c173b6c7e93676d5159ac4263574d3f5057055ac286`，Host/container同路径，bash语法检查通过。保留FA既有开关保证kernel选择、明确GPU/端口/TP/BF16及model alias保留服务接口、tokens16384保留用户规模；显式prefix开启用于非性能回归可复现，移除性能专用关闭项。缓存/TMP路径限制隐式写入批准根，独立run目录不覆盖用户service.log，端口guard拒绝覆盖运行服务。额外保留`PYTHONDONTWRITEBYTECODE=1`避免向依赖源码目录写入pycache；首轮launcher版本缺此保护，因此停止本任务PID728881后以最终脚本重启验证。旧cache保持可恢复；未来修改编译相关Plugin路径时需重新隔离并验证缓存，未实现通用cache-key失效修复。

共享NFS的remote_src备份因复制元数据I/O错误失败，原脚本未覆盖；改为读取已校验字节再写备份后成功，保留错误证据并校验备份hash。不停止容器或8000服务。后续发现的GDN乱码是独立009问题，不能以FA启动恢复代替生成数值验证。
