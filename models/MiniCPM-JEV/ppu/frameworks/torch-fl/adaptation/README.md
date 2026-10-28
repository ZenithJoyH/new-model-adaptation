# 适配问题索引

按发生顺序维护 `NNN-short-title.md`。每条记录只描述一个问题的现象、诊断、受控对照、根因、
解决方法、验证结果和限制，不保存过程脚本或原始日志。
# 本轮记录

- [001：Transformers / Torch-FL 算子路由性能优化](001-operator-routing-performance.md)：2026-10-26，PPU-01 / minicpm-jev；局部GDN融合与原路径同条件对照通过，18项回归通过，正式验收未执行。
- [002：在线评分服务](002-transformers-online-service.md)：同一容器PPU3、8331端口，18层GDN优化常驻，12例HTTP与并发/非法输入验证通过。
- [003：GDN 推理 demo](003-gdn-inference-demo.md)：容器内部独立单样例入口，显式启用 GDN；s02 验证通过，原 demo 和在线服务不变。
- [004：FlagGems ATen 实际调用](004-flaggems-aten-routing.md)：12 例跟踪中 GDN 公共融合算子 216 次，未观测到其他通用 FlagGems ATen 实现。
