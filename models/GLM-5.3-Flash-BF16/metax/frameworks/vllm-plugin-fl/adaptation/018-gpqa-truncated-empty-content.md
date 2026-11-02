# GPQA长度截断的空答案及离线计分

2026-10-28终态更正：实际全量运行将9个null转为`<TIMEOUT>`，没有触发下面单独复现的RegexFilter异常，但汇总错误排除了这9题。逐题核验为174/198＝87.8788%，达到用户随后批准的85%门槛。已整理并按用户要求暂停；详见[当前精度与暂停记录](../acceptance/accuracy-current-state-v18.md)。以下保留此前发现、授权和工具实施过程，不能替代终态结论。

2026-10-28，原正式运行`glm-gpqa-final-v14-20261028`保持运行和冻结，未重发题目。
实际API响应`chatcmpl-b52992f98d079802`正常返回，`finish_reason=length`，生成60000
tokens，`message.content=null`。原缓存保留原生None值。此项不能算正确答案。

已离线复现原生`RegexFilter.apply([[None]], ...)`抛出TypeError；当前冻结的
`llmrun.validate_samples`也会拒绝空响应。原生证据为批准根
`02-issues/gpqa-empty-content-compatibility-v14-20261028.json`，含实际响应摘要/哈希、
三个相关源码哈希及原生异常，不保存完整模型推理到本地。

用户已明确批准例外：在完整198题生成完成后，保留全部原始响应与失败回执，仅离线
重新计分，将已核实为length截断的空答案计错，仍以198题为分母和0.88为门槛；
不重发题目、不修改当前运行。这不允许放宽未知空值、执行错误、样本覆盖或阈值。

实现范围限定为新增原生离线恢复入口、`framework_evidence.native_accuracy`的显式恢复
校验分支、所需负例回归及本地精度Skill/契约的新增操作说明。普通formal-full规则和
正在运行的冻结bundle不变；新工具使用独立bundle。输入须绑定原配置/生效配置、原生
终态报告、原始响应日志及只读缓存快照、全部198个prompt/target和原生过滤器身份。
缺题、重题、未知缓存结构、无length证据的None、参数或数据集漂移均拒绝恢复。
非空答案保持原字节；只在离线过滤时将获准的None视为无答案，保存原始None及显式
截断标记，计零分。不得把空答案改成超时或通过辅助显示分数替代原生恢复回执。

本记录为授权与实现边界；离线恢复、全量精度及性能目前均无通过结论。

实现及验证：新增`gpqa_recovery_contract.py`与`recover_gpqa.py`，普通入口不变，
`framework_evidence.native_accuracy`只对显式`offline_recovery`执行额外严格核验。
新的`score-existing-run`默认只预检；显式`--run`才产生独立回执，仍不发送模型请求。
原nonce、runner字节及缓存路径绑定；原生API响应与缓存值逐项计数核对，选定指标由
gate逐题重新计算。原None保存在`raw_resps`，明确截断标记不获得分数。

15项本地回归及实际评测容器中的同15项均通过；另在实际原生task上用明确标记为
“合成数据”的198题过滤器夹具验证原始prompt/target、过滤器和metric身份。这些是
工具测试，不是模型精度结果。普通精度生命周期20项（1项跳过）、既有framework23项、
协作契约39项和精度证据21项回归通过；预期空值拒绝的负例日志保留。

新工具独立部署在`03-acceptance/native-tools-gpqa-recovery-v1-20261028`，55文件，
归档SHA`c28b01d3806d06f31696666c5db0049d05af27e685fb6afcccfd393f1715e122`；
精度Skill bundle SHA`019d740648cedabc0b561c2041723a1fe358ee48239e76c44626e772354e9399`。
原正在运行的bundle未改变，性能runner保留原始字节。NFS copytree因ACL/copystat EIO
报告失败后，逐文件校验已复制内容，只以无xattr的内容复制补齐；差异文件不会覆盖。
工具验证原生记录为`04-runs/recovery-tool-validation-v15-20261028/result.json`。

只读等待任务已准备并启动：全量原运行终态后才保存未改写的SQLite快照、原始日志和
失败回执，原DB/WAL前后哈希必须一致；缺题或非预期终态直接失败。状态目录为
`04-runs/gpqa-terminal-snapshot-v15-20261028`，遇人工接管停止后续动作。
当前尚未执行实际198题离线恢复。
