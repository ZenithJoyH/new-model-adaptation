# 002：Triton 无法发现容器内 libcuda

## 元数据

- 状态：受控环境 workaround 已验证，容器级根因待镜像维护者处理
- 日期：2026-09-28
- Host/容器：`H100-149` / `MinicpmV4.7-1B-native`
- 范围：vLLM 0.24.0+cu129、Triton 3.6.0，GPU 0 TP1 基线启动

## 现象、诊断和受控对照

首次基线在导入 vLLM GDN/Triton kernel 时抛出
`AssertionError: libcuda.so cannot found!`，尚未加载权重；日志为
`04-runs/baseline-46-alias-20260928/service.log`。
容器存在 `/usr/lib/x86_64-linux-gnu/libcuda.so.1`，但 `ldconfig -p`
未列出它。只增加 `TRITON_LIBCUDA_PATH=/usr/lib/x86_64-linux-gnu` 后，
同一别名配置成功加载 3.04 GiB 权重并就绪；对照日志为
`04-runs/baseline-46-alias-driver-20260928/service.log`。

## 处理与限制

此变量只指向已存在的驱动库目录，不改系统路径、镜像、挂载或权重；
后续 eager、graph 和最终启动脚本均保留。若容器镜像修正 linker cache，
可在相同环境中受控移除该变量并重测。当前结果只证明这一容器镜像的路径问题，
不推广到其他 Host。过程脚本在 `01-environment/`，原始日志在 `04-runs/`。
知识库决定：`local-only`。
