# 1800秒 RPC 超时验证及精度重跑

最终更新（13:31）：重跑13:25:12以1退出，198题中21个TIMEOUT标记，结果校验失败。
服务PID314202仍在且health成功，未观察到本轮RPC TimeoutError/EngineCore退出。
不能认定失败标记由1800秒RPC超时引起，来源待排查。文件strict-match 82.32%、
flexible-extract 31.31%不构成有效全量精度；88分未通过。详情见
`../acceptance/gpqa-full-20260904.md`。本轮不自动重跑或修改服务，监控结束。

用户授权：调大超时，验证后重跑全量GPQA。仅增加
`VLLM_EXECUTE_MODEL_TIMEOUT_SECONDS=1800`；TP16、50K、seq32、BF16、graph及插件均不变。
远端启动脚本 SHA1 `a018666ab94e969527f037dfd57f5330ef5d281c`，已通过
`deploy-ppu13-glm53-launch-directory.yml --check --diff`、实际部署和内容/语法核验。

确认旧PID158392已退出、8010未监听后，归档旧日志/PID/脚本至容器
`/workspace/glm53-adaptation-runtime/graph/gpqa-c64-failed-20260904/`。
旧service.log SHA256 `8daff604058bf51f0d090c1acde9db8dbdf72093af3f91dd403b40e7887408f4`。
随后 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/start-ppu13-glm53-timeout1800.yml` 仅启动本任务推理服务，未停止/重启容器。

验证顺序：服务就绪和进程环境 → 超过2048 token prefill两次 → 并发8 sanity →
原llmrun预检 → 198题、64并发、strict-match>=0.88精度重跑。
长输入测试为固定2900次hello填充及1+1，tokenizer与API均检查实际prompt长度>2048，
要求最终答案严格为2；`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/test-ppu13-glm53-long-prefill.yml`，每请求最多1860秒。
不因为延長超时就宣称原故障已修复，不以运行中或部分成绩替代全量结果。

新轮预留目录 `/mnt/nfs/users/jinghao/glm5.3-flash/accuracy/gpqa-20260904-c64-t1800`，
新eval_model隔离响应缓存；原c64失败目录完整保留。当前仅准备本地评测配置，
尚未执行预检或重跑，须先通过上述验证。

后续状态更新：上述验证均通过后，12:20:30预检通过，12:20:58正式启动runner12171。
12:21:46确认进程存活，客户端64并发、198请求、旧缓存0。每10分钟监控
`ppu-13-gpqa-1800`已建立；最终精度待全量完成。此前“尚未执行”为准备阶段历史状态。

## 已核实结果

- 新服务PID314202，12:09:46启动，12:12:28就绪；进程环境明确1800秒。
- 首次测试job `j855120762617.1361018` 在请求前失败：Transformers接口返回对象，
  旧测试取len得到字段数2。改为先render再encode计数，未修改模型/模板，未发送失败请求。
- 修正后job `j72861618573.1384769` 返回0，12:14:33–12:16:49完成两次请求。
  本地及API均2937 prompt tokens；两次61 completion tokens、stop、最终content=2。
  首次112.0945秒，后续23.3454秒。12:14:36进入MQA，12:15:57进入topk，证明继续推进。
- 该输入两次均小于300秒；不能证明1800是必要条件或已修复原混合批次故障。
  只能确认1800设置有效且长prefill路径可完成。py-spy未安装，没有采得worker栈。
- 同一PID314202 graph sanity job `j675029313951.1522012`：12:18:12–16，rc0，
  8/8正确、错误/超时0、420输出tokens/3.8363秒=109.4805 tokens/s，
  平均3.6637秒、最大3.8255秒。16卡显存89630–89662MiB，利用率均值45.5–73%，
  峰值100%，采样4次，无遥测错误。与此前105.2267 sanity相近，不作为正式性能优化结论。
