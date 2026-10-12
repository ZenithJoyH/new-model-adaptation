# 009：FlagOS GDN 非连续分页状态写回错误

## 元数据、症状与边界

2026-09-24，mx-58，Qwen3.6-27B / MetaX / vllm-plugin-fl v3，容器与版本同008。状态：根因已验证，算子及模型graph/eager回归通过。Plugin基线继承007；本次只改FlagOS backend，不改vLLM/FlagGems/FlagGems-vLLM。PR base未确认。

008更换编译缓存后图捕获完成，但默认GDN生成重复感叹号/乱码；同样FA与FULL_AND_PIECEWISE下，仅黑名单`gdn_prefill,gdn_decode`的8条输出恢复正常。默认GDN eager也出现相同异常，排除“只有graph才错”。此前007仅检查HTTP/非空文本，证据不足以支持数值正确，不能沿用该结论。

## 受控定位

证据均在Host/容器同路径`/public-flash/jinghao/qwen3.6-27B/04-runs/`：

- `fa-shape-fresh-20260924/`：默认GDN graph，8条HTTP200但输出健康失败。
- `fa-shape-blacklist-20260924/`：只将GDN切回原实现，8条正常文本，PIECEWISE51/51+FULL decode35/35。
- `fa-shape-eager-20260924/`：默认GDN eager同样输出健康失败。
- `gdn-state-repro-20260924/`：连续状态缓存，recurrent eager及两次变输入/索引graph replay均匹配FP32参考，状态最大误差约1.2e-7。
- `gdn-state-strided-20260924/`：仅改状态leading stride为`24*128*128+8192`，eager当前token输出仍正确，但状态44.9%元素不匹配，最大绝对误差0.86977458；实际后续decode读取错误状态，造成输出崩坏。

## 根因与修复

FlagOS MetaX适配中`state.index_copy_(0, indices, updated)`进入FlagGems的`index_copy_`。目标分页cache有页间padding，源updated连续；该实现用目标`inp_stride_dim`解析源offset，并用`inp.numel()`限制物理地址，不能正确覆盖该布局。不是FlagGems-vLLM recurrent计算公式错误。

选定层级为既有`FlagGemsBackend.fused_recurrent_gated_delta_rule_fwd`的ABI转换：新增`impl/gdn_state_layout.py`，两个小型Triton状态搬运入口按cache真实四维stride读取/写回，并融合V-major↔K-major转换。只搬运活跃页，不经`dim_compress`复制整个paged cache。空槽0及padding不写入；recurrent仍调用原FlagGems-vLLM kernel，不增加低层dispatch、不改变黑名单/vendor、FA或OOT。非MetaX原guard直接return路径不变。

旧实现备份在`02-issues/fa-shape-20260924/flaggems-before-layout.py`。新GPU回归`tests/functional_tests/ops/test_gdn_state_layout.py`覆盖连续/非连续、非方形K/V、FP32/BF16、padding/null及storage/alias保护，真实model-strided QKV，以及eager/两次变化输入和索引graph replay。

## 修复后证据与实际差异审查

- `04-runs/gdn-state-strided-fixed-20260924/result.json`：同一非连续布局，eager及两次变输入graph replay均通过；状态最大误差1.192e-7。
- `04-runs/gdn-layout-tests-20260924/test.log`、`junit.xml`：6个维护性GPU用例全部通过。Plugin dispatch单测276/276通过（29.12s）；`git diff --check`通过。
- `04-runs/fa-shape-fixed-graph-20260924/`：无诊断导入hook，默认FlagOS，GPU0/1 TP2 BF16，tokens16384、maxseqs默认256、maxlen262144、gpuutil0.8、prefix开启；不传compilation mode，最终mode3/FULL_AND_PIECEWISE。mixed51/51、decode FULL35/35捕获成功，8条变输入文本逐条与`fa-shape-blacklist-20260924`的vendor结果完全一致。第二轮原始completion的选择题续写不作为正式问答准确率通过。
- 独立上游bug复现：`07-bugs/flaggems-index-copy-stride-20260924/repro.py`及`result.log`；只调用FlagGems index_copy_，目标shape(6,8)/stride(10,1)，与原生参考最大差1.8826；不依赖Plugin或vLLM，未改只读依赖。
- `04-runs/fa-shape-fixed-eager-20260924/`：修复后默认GDN eager，8条文本均无旧版重复乱码；7/8与graph完全一致，最后一条在32token截断范围内呈不同thinking续写，不视为逐token全一致或正式准确率通过。

审查于2026-09-24：Plugin HEAD仍`675548ab2ee52b8124b0b6a82a2f795c0553e1fa`，完整tracked diff SHA256为`7d0f87c0302c19c183cda22ec8d72ce4da28a7e85fe2d3b091ee2a4a0e85ca82`。7个tracked修改中，仅本次追加flaggems.py的状态转换；其余为001～007继承。保留原2个untracked，新增helper（SHA256 `77b3e02e384f06362e30c6f764f25b5d74ecb13a9d0b21260aa27c64afac3f75`）和GPU测试（`d303541fdd1df8f2b9f72e06a7d6f27148f039c76c859547b11dc326ed203d5f`）。vLLM inherited diff及FG/FGV clean身份与008一致。未commit/push，PR base未确认。

影响边界：只有FlagOS MetaX recurrent ABI分支使用新helper；vendor/黑名单、FA、non-MetaX guard miss不改。保留原state对象、storage及stride，空槽0和padding不写；活跃索引唯一性是调度器契约。非MetaX及其他模型未硬件验证；speculative/KDA限制继承，未新增fallback吞错。

状态转换优化也减少临时buffer，但本轮没有性能测试，不作性能提升结论。修复属于Plugin ABI适配与局部workaround；上游index_copy_完整stride契约修复并回归后可评估移除，不能无证据改回旧写法。

## 当前限制

用户launcher最终验证完成：`04-runs/start-model-new-20260924-113703-754937/repair-verification.json`（UTC 03:43:31，2026-09-24），PID754946保留运行，GPU0/1、端口8001、模型名qwen36-27b-allnewgems；原8000与新8001均health200。最终8条请求均成功、前4条预期答案检查通过；7/8与vendor逐字一致，第8条正确中文选项后的thinking续写不同，完整差异保留。最终图mixed51/51+FULL decode35/35通过，源码diff及launcher SHA再次核对一致。

正式accuracy/performance未选择，适配保持in_progress。知识库暂local-only，不执行未选择的环境/正式验收阶段；007环境身份为历史快照，不能用于接受本次源码。本地audit仍有无关DeepSeek profile错误及78条历史警告，无Qwen当前布局错误，不把audit视为远端验证。
