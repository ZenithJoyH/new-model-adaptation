# 对齐后原生小集合：5/5通过

2026-10-27，262144上下文、64序列、TORCH_SDPA、FULL_AND_PIECEWISE、前缀缓存开启的8014服务。使用同一更新后的根级start-model.sh启动，重新核验并绑定实际API进程66163的容器ID、boot ID、启动tick、命令哈希和监听端口。

显式操作service-sanity，Skill bundle仍为355bdf2946456710e0dbaaa9b331062f86be2ec4e5740f7be91ac57a6daa167d。新部署的环境/适配/执行模式前置门禁通过后，运行原生preflight及新run；冻结manifest和独立参考不变。默认4x、16x、自适应小图、切片、多图5例全部逐文本匹配，无错误或超时，并发4、超时120秒。

新回执 `04-runs/sanity-aligned-20261027/sanity-result.json`，同目录保存新的challenge、service-observation、preflight和runner.log。新的服务绑定为 `03-acceptance/service-binding-aligned-20261027.json`，部署指纹035672fd74d7a9a7d9a52188a0443e1ab8244c52260a99dcb1f86c75896720e0；没有复用旧服务实例的回执。

这是固定小集合基础验证，不是正式数据集精度。关闭放大时的极小图退化、自由生成差异及完整上下文/并行质量限制继续保留。
