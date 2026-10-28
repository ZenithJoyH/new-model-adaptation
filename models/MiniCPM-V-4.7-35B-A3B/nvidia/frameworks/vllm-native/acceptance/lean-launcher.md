# TP2 混合图启动脚本二次精简

2026-09-30；Host `H100-149`；容器 `MinicpmV4.7-35B-native`；模型
`/data/models/MiniCPM-V-4.7/weights/35b-a3b`。最终脚本的 Host/容器同路径为
`/public/flagos/jinghao/MiniCPMV4.7-35B/native/start-model.sh`，权限 `0755`，
SHA-256 `d947e59229f8d9b9602ca2530e1e7b5c8511778bfe9b244eb3a1b26e122ae5aa`。
前一版已备份在 `02-issues/start-model-before-mkdir-removal.sh`，SHA-256
`1bca4bb0ac4c190cde1b30dc1da289b3361e2ac558340cfac820d8c7829efb54`。
Ansible `--check --diff` 核实本次唯一改动是删除预先创建
`06-cache/xdg/torch/kernels` 的 `mkdir -p`；`XDG_CACHE_HOME` 仍将实际缓存
置于已验证的 `06-cache/`，当前缓存目录已存在。容器内 `bash -n` 通过，
Host/容器路径映射及文件哈希一致。

对用户列出的其余设置逐项核对：端口探测保证脚本拒绝覆盖现有服务；
`CUDA_VISIBLE_DEVICES=2,3` 固定已验收的物理 GPU；`LD_LIBRARY_PATH`
补入该镜像默认缺少的 `/usr/lib/x86_64-linux-gnu`，否则 `libcuda.so.1`
不可定位；`XDG_CACHE_HOME`、`VLLM_CACHE_ROOT`、`PYTHONPYCACHEPREFIX`
和 `TMPDIR` 分别约束 Hugging Face/Torch、vLLM、Python 字节码与临时写入
到批准工作根。vLLM 默认缓存路径是 `/root/.cache/vllm`，不会受
`XDG_CACHE_HOME` 代替。`PYTHONPATH` 加载 `01-environment/sitecustomize.py`，
`MINICPM47_TRITON_PER_PROCESS=1` 启动已通过 TP2 单变量对照的 Triton
进程隔离；省去这两个设置曾在首个请求触发 Parastor `EBUSY`。因此这些行
保留。服务参数和前缀缓存、`FULL_AND_PIECEWISE` 保持前一版已验证配置。

变更前核对本任务 8107 服务 Host PID/PGID `600304`，命令包含精确模型、
TP2 和图模式；另一 8019 服务属于独立进程组，未操作。只向 `600304`
进程组发送 `SIGTERM`，验证适配容器保持运行，随后用最终脚本启动新服务，
Host PID/PGID `1038051`、容器 API PID `23592`。`/health` 与模型列表返回
200，prefill/mixed PIECEWISE 5/5、decode FULL 4/4 捕获完成。
独立探针 `03-acceptance/lean-launcher-probe.py` SHA-256
`2fa4b2e34c66bdd7691d2105411aa36b044bf66af8857b7d5dda877c7ea5e9d9`；
结果 `04-runs/start-model-lean-v1/probe.json` SHA-256
`50dbe9408baaaf31ae62a73b3cda614fb5b525dab36292222cb0fa810d5d105e`；
本次启动日志快照 `04-runs/start-model-lean-v1/service-startup.log` SHA-256
`9501b11fe32f659445202fb40c05045d82c2f6983bda01b480dec3bd5b5c5cf0`。
文本 `17+25` 为 `42`、红图为 `red`、视频按红蓝两帧顺序回答，
十个混合并发请求 10/10 正确；请求后 `/health` 再次为 200。
日志快照未出现 `ERROR` 或 `Traceback`。

最高已验收 full 图覆盖仍是 decode-full；prefill 采用 PIECEWISE。
本次是启动脚本与请求级回归，固定 GPQA sanity、正式精度和性能未执行。
