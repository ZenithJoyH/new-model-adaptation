# 适配问题索引

- [001：editable Plugin 被安装目录中的 namespace package 遮蔽](001-editable-import-shadowing.md)：容器内兼容模式 editable 重装后，已验证不设 `PYTHONPATH` 的导入和服务实启。
- [002：MiniCPM-V 4.7 注册与 canvas M-RoPE 接口差距](002-v47-model-integration.md)：模型专用实现及文本、图片、短视频、decode-full 功能通过；复杂位置等价性待验证。
- [003：FlagGems cuDNN attention CUDA 错误](003-flaggems-cudnn-attention.md)：已独立复现并修复广播 mask 寻址，56 项新增与 4 项原有测试通过；issue #6869 / PR #6871；整模去黑名单复验待执行。
- [004：GDN 限制 FULL graph](004-gdn-full-graph.md)：FULL 请求降为 mixed PIECEWISE + decode FULL；显式 decode-full 的模型与服务功能通过。
- [005：服务脚本精简与前缀缓存默认值](005-launcher-minimality.md)：省略缓存开关实测会关闭缓存，已恢复；28 行版本曾实启通过。用户随后修改的当前脚本仅通过语法检查，存在端口、日志/缓存边界与服务身份回归，未实启。
- [006：1B 与 35B 共用适配器](006-unified-dense-moe-adapter.md)：新容器内共用 dense/MoE 与 canvas 实现；双模型 TP2 eager/graph 共 50/50 API、14 项契约及 8 项 checkpoint 位置对照通过，整模不设旧 attention 黑名单。
- [007：独立容器接入 DSpark draft](007-dspark-draft-service.md)：vLLM 0.28 + Plugin V2 接入，修复 Triton 3.7 缓存 launch；独立脚本下 FULL_AND_PIECEWISE 文本/单图/4 并发 9/9 请求完成，草稿接受 306/1386 token；正式精度/性能未执行。

- [008：DSpark 切换至 Plugin 0.4.0-dev](008-dspark-plugin04.md)：按用户要求采用面向 vLLM 0.28 的分支，仅迁移 MiniCPM 模型扩展；33 项聚焦回归、eager 与独立缓存 FULL_AND_PIECEWISE 各 9/9 请求完成，最终启动器实启通过。
- [009：评测响应缓存挂载消失](009-evaluator-cache-mount.md)：128 客户端并发重测遇到缓存卷脱离和 SQLite 写入失败；现场保全后停止本轮客户端，模型服务健康；采用新评测容器本地 overlay 缓存缓解，卸载根因未确认。

001–005 保留独立容器各历史轮次状态；006–008 的新容器复验不改写旧运行回执。
