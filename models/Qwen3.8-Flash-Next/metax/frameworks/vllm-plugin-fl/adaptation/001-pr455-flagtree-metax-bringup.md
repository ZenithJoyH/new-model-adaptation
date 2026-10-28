# 001：PR455 与 FlagTree 源码安装及 MetaX bring-up

## 范围、基线与计划

2026-10-23，用户指定 `mx-101` / `qwen3.8-flash`，过程根为宿主机、容器同路径的
`/public-flash/jinghao/qwen3.8-flash`。容器 ID 为
`06b36c1d70e22ca68adef42e521d76f9b597f3fc6e8c0a9a8738ef03e1b85289`；保持 running。
采用 active `vllm-plugin-fl` profile v7、v2 证据契约。状态：进行中，未完成验收。

- Plugin：实际 editable 安装 `/opt/vllm-plugin-FL`，`main@f41b7de883ed71526716738a7e05d810f49ded58`，原工作树干净。
- 指定 PR455：冻结 `65759c432cef847c311ccd0ab9dc077ab91454ed`，与当前 HEAD 的共同祖先
  `5463eae824b1fbaa3d331564ab2fb4c51f1b6e09`。只应用该共同祖先到 PR 的差异，保留当前 main 后续变更；不提交或推送。
- vLLM：只读 `/opt/vllm@ee0da84ab9e04ac7610e28580af62c365e898389`，安装版本
  `0.24.1.dev0+gee0da84ab.d20261023.empty`。继承 87 个权限位差异，内容增删为零；
  原完整 diff SHA256 `2a77f03f2b92a12aef3a189be40352e238e98b2795a857d1a37ed7626ae361ec`。
- FlagGems：`/opt/FlagGems@e510c6bbe3ffd9eb22c41021d82f15c21098f998`，master，继承66个权限位差异，保留不清理。
- FlagGems-vllm：`/opt/FlagGems-vllm@c9003571a6bd06bdc94ca3dbfad4cc606a8d82f8`，main，工作树干净。
- 模型 config/index SHA256 与模型级中文架构记录一致；架构上限262144，初始服务上下文按规范50000。
- 设备 C550 64GiB ×8，检查时无设备进程；容器仅有原始 shell。系统盘剩余6.3GB，构建空间需单独核验。
- 原生基线位于远端 `01-environment/baseline.json` 和逐组件 `*-baseline.patch`。

## 改前变更边界

| 工作 | 组件与文件/符号 | 增删范围与必要性 | 验证 |
| --- | --- | --- | --- |
| 应用用户指定PR | Plugin `models/qwen3_8_flash_next/**`、`patches/qwen3_8_flash_next.py`、对应 `tests/qwen3_8_flash_next/**` | 新增模型注册、配置、HC/PLE/QSA/MTP实现和测试；实际服务先验证BF16文本 | 注册、权重加载、状态/缓存和运行策略测试；设备 eager/graph |
| PR共享接入 | Plugin `__init__.py`、`compat/**`、`ops/{custom_ops,activation}.py`、`ops/fused_moe/**`、`platform.py`、`utils.py`、`quantization/quant_linear.py`、`worker/{model_runner,model_state,worker}.py` | 按PR接入模型状态、KV owner、MoE/FP8能力判断，保留未命中路径 | PR共享回归、非目标模型/平台能力隔离；不声称其它硬件已测 |
| PR其余原有改动 | `dispatch/manager.py`、`dispatch/config/sunrise.yaml`、README与FP8文档、对应unit tests | 完整保留所请求PR的53文件变更清单；不另做格式化或清理 | 每块对照上游patch；记录非MetaX未验证范围 |
| 源码安装FlagTree | 用户明确要求的依赖安装例外；容器内部 `/opt/FlagTree`，不在过程根复制源码 | 现无FlagTree checkout；从官方main建立唯一构建源；用同一解释器安装，禁止PYTHONPATH | 固定最新SHA、构建日志、pip元数据、实际triton导入、设备编译数值与graph检查 |
| 后续必要修复 | 仅已核实安装的Plugin/FlagGems/FlagGems-vllm | 目前未选择额外产品修复；新缺口先补本记录的文件/符号与证据再改 | 逐次最小回归，保留失败与最终diff审查 |

## 经验复用与接口

已读 Plugin dispatch README、FlagGems CONTRIBUTING、FlagGems-vllm AGENTS，以及仓库贡献规范。
Qwen3.6 MetaX历史升级案例提示核对实际原生SDK能力及版本兼容，但其vLLM0.20与本次0.24开发版不同，不能直接套用。
PPU Qwen3.8旧问题只作假设来源，不作为MetaX结果。优先沿用PR注册、model-owned state及统一dispatch；
保持vLLM源码只读。FlagGems同步前检查dirty和远端分支；不丢弃继承权限改动。

## 结果与限制

PR应用、FlagTree构建、eager/graph、正式精度、性能和交付均待验证。
源码审查尚未完成，不能标记阶段3完成或optimized；知识状态 `local-only`。

## 已完成检查与当前问题

- PR应用后 `git diff --check HEAD` 通过，无unmerged路径；PR patch SHA256为 `ad9fab5e33528abeb60f892d41d5d49f3624b461825b54117691d68ec7319d91`。实际修改53文件、10272增/89删，均为指定PR；没有新建提交。
- `04-runs/pr455-import-baseline/import.log`：Plugin/平台注册、实际FlagGems与FlagGems-vllm路径、Qwen模型类导入成功。保留MACA patch循环导入告警及Transformers视频processor文档告警；不把导入通过扩展为视觉验收。
- 原编译器回归 `04-runs/pr455-tests-before-flagtree/pytest.log`：110 passed、4 skipped、1 failed（26.36s）。失败为QSA metadata kernel graph replay用例，在编译阶段报 `Internal Triton mlir opt error`，stderr为不能建立 `/root/05-tmp/compile-maca-log-*`（目录不存在）。调用端TMPDIR已指向批准根；旧MetaX编译链仍引用其他路径，具体来源待核实。尚未进入graph数值对比，不据此判定PR数值错误，也不创建未经批准的/root过程目录掩盖问题。
- 官方Git克隆180秒超时，PR应用成功不回滚。改用官方GitHub API冻结FlagTree main `2f1229e51c03b345a1c72207854828eed7282de9`（2026-10-23），下载该SHA源码包；网络传输较慢但仍在增长。API记录在 `04-runs/flagtree-source-20261023/upstream-main.json`。
- 后续顺序：完成源码安装→重验失败最小用例→通过后推进组件及整模；不在当前失败未解决时启动整模。

## FlagTree构建身份与执行

官方源码包已完整下载并提取到容器内 `/opt/FlagTree`：main SHA `2f1229e51c03b345a1c72207854828eed7282de9`，压缩包22261247 bytes，SHA256 `95b18f5d0ae02551c3ba89d41b977858f291fdd865759bd5c5639877c6602539`。该树保留不完整克隆的.git目录，不将其HEAD当成版本依据；准确来源记录在 `SOURCE-PROVENANCE.json`。没有在远端工作根建立第二份源码checkout。

已读该SHA的CONTRIBUTING、setup.py、build_helpers及MetaX hook/CI。当前hook要求LLVM19 3.8.0.6 v0.6.0与 `metaxTritonPlugin` v0.6.2，比Wiki示例插件v0.6.1更新；采用源码声明版本。缺少CMake与pybind11-stubgen，先按pyproject范围安装构建依赖，不升级已有PyTorch、vLLM或其它模型依赖。构建命令为 `FLAGTREE_BACKEND=metax MAX_JOBS=32 python -m pip install . --no-build-isolation --no-deps -v`，cwd `/opt/FlagTree`。

构建日志 `04-runs/flagtree-build-20261023/{build-dependencies.log,build.log}`；官方支持的FLAGTREE_CACHE_DIR、TRITON_HOME和TRITON_BUILD_DIR分别设置到批准根的 `06-cache/flagtree`、`06-cache/triton-build-home` 和 `05-tmp/flagtree-cmake`，TMPDIR为 `05-tmp`。安装与运行验证尚未完成。

## 路径取证纠正（本任务执行错误）

进一步核实发现 Ansible `ansible.builtin.command` 默认 `expand_argument_vars=true` 在shell启动前展开了脚本文本中的 `$PWD`，错误地形成 `/root/05-tmp` 和 `/root/06-cache`。前述“TMPDIR已指向批准根”的判断不成立，110/4/1测试失败的临时目录原因属于调用路径错误，不能作为编译器或PR缺陷证据。保留原失败记录，后续命令关闭该展开功能且全部使用字面绝对路径。

第一次FlagTree构建补齐了CMake4.0.3、stubgen3.0.0，自动准备LLVM/MetaX插件及CUDA工具链；在下载可选Proton的nlohmann/json时网络关闭，构建失败，原Triton3.6.0+metax3.8.2.2仍安装，FlagTree尚未安装。错误缓存6.0GB挤满系统盘。尝试按已核实PID停止本任务构建时，该进程已自行退出，未发送信号，容器与其他进程保持不变。

核实 `/root/06-cache` 是本任务20:15后创建，内容对应本次导入、测试、pip及FlagTree下载。对该目录完整生成逐文件SHA256与symlink清单后，完整移入批准根 `06-cache/path-correction-20261023`，不丢弃数据；前后校验结果见 `04-runs/flagtree-build-20261023/cache-{before-relocation,relocation-verified}.json`（完成后复核）。不删除无关内容，不修改容器挂载。

重试将首先用正确TMPDIR重验原失败最小测试；构建复用已保留工具链缓存，配置 `TRITON_BUILD_PROTON=OFF` 跳过本次推理不需要的可选NVIDIA profiler及其JSON下载。该选项只影响构建，不是服务图模式降级或模型算子fallback。

路径纠正已完成：5598项文件/符号链接前后匹配，系统盘恢复5.2GB；`cache-relocation-verified.json`确认未丢弃内容。原失败的唯一用例在原Triton下用正确绝对TMPDIR重验，`04-runs/pr455-path-corrected/pytest.log` 为 **1 passed in 22.86s**；`path-check.log`同时核实环境变量和tempfile实际目录一致。因此此前失败已定位为调用环境错误，不需要修改QSA或旧编译器。原110通过和当前最小重验分别保留，未将两轮拼作单轮全量结果。

FlagTree重试日志为 `04-runs/flagtree-build-20261023/build-corrected.log`；实际环境已写入 `corrected-environment.json`，所有路径为字面绝对路径且Ansible `expand_argument_vars=false`。

第二次构建在setuptools metadata备份阶段出现NFS `Errno 5 Input/output error`，目标为 `05-tmp/pip-modern-metadata-*/flagtree.egg-info.__bkp__`，尚未开始编译。此签名与已读Qwen3.6 MetaX问题018的pip metadata copytree EIO一致（组件不同，安装机制相同）。重试仅将安装器原生临时目录改为已核实当前构建源内 `/opt/FlagTree/build/install-tmp`；大型工具链缓存、CMake对象与完整日志继续在批准工作根，不复制第二份源码。日志 `build-native-tmp.log`；该路径是组件构建过程目录，不含一次性适配代码或额外产品实现。

第三次已通过metadata，CMake发现新的独立路径问题：`third_party/metax/CMakeLists.txt`非editable分支只在 `$HOME/.flagtree/metax` 找插件，未使用FLAGTREE_CACHE_DIR。官方插件已正确下载且复制到当前源码，MD5 `de37eb019ce32cb3b50ac89885f0c7c6` 与hook要求前缀 `de37eb01` 一致。采用setup.py原有 `TRITON_APPEND_CMAKE_ARGS=-DBackendTritonPluginLib=/opt/FlagTree/third_party/metax/metaxTritonPlugin.so` 指定同一库；不改HOME、不在默认/root缓存新写文件、不修改FlagTree源码。第四次日志 `build-plugin-path.log`。注意官方setup在准备安装时会将该库复制到当前site-packages/triton/_C；安装失败并不代表目录完全无变化，最终须按实际导入和文件身份复核。

第四次插件路径问题已解除，CMake configure完成但generate失败：官方LLVM导出的LLVMSupport/lldELF要求 `ZLIB::ZLIB`，容器只有zlib运行库、没有头文件与开发链接。apt模拟确认只新增 `zlib1g-dev=1:1.2.11.dfsg-2ubuntu9.2`，0升级/0移除。按FlagTree必要构建依赖安装该包，日志 `zlib-install.log`；第五次构建 `build-zlib.log`，其它条件保持不变。

第五次源码构建与安装成功：`build-zlib.log`记录416目标编译、wheel创建和 `Successfully installed flagtree-0.7.0+metax`。本轮源码构建wheel大小426262725 bytes，SHA256 `3d49d5c76b0e2845bdcc16e1ccd2164a4828d2692e94e369f57430aed3fdc28f`。`installed.txt`显示FlagTree与旧Triton distribution元数据并存；真实import/文件归属与设备运行尚在复核，不能仅依据pip成功宣称编译器完整通过。CMake对象约12GB保存在批准根05-tmp，容器内build约1.6GB，安装打包阶段系统盘余量约2.5GB，未进行数据清理。

## 新编译器ABI问题

安装后实际import为site-packages的FlagTree `triton.__version__=3.6.0`，direct_url为 `/opt/FlagTree`，设备目标 `GPUTarget(backend='maca', arch=80, warp_size=64)`；ldd确认MetaX插件从同一site-packages/triton/_C加载，不依赖宿主机挂载的工具链库。新wheel确实包含核心和MetaX插件库。

新编译器下PR回归 `04-runs/pr455-tests-flagtree/pytest.log`：110 passed、4 skipped（graph memory profiler只支持CUDA/Kunlunxin）、1 failed。失败改为 `metax.load_dialects(ctx)` TypeError（MLIRContext类型不兼容）。核对FlagTree RECORD确认compiler.py、driver.py和libtriton.so均属于新FlagTree，非旧文件调用。

对两个实际加载的.so作只读ABI标记取证：libtriton.so为 `__pybind11_internals_v12_system_libstdcpp_gxx_abi_1xxx_use_cxx11_abi_1__`，官方metaxTritonPlugin.so为对应v11。构建原有pybind11为3.1.0，二者不兼容；候选修复只固定构建头文件为pybind11 3.0.1（先断言其internals.h定义ABI11），重编同一SHA。未修改任何模型代码或FlagTree产品代码。安装/断言日志为 `pybind-abi-install.log`、`pybind-abi-check.txt`，重编日志 `build-pybind301.log`。修复结论待重新JIT与graph用例确认。

ABI11重编安装成功。`04-runs/pr455-tests-abi11/compiler-import.log` 直接执行 `metax.load_dialects(ir.context())` 通过；最小QSA编译/graph用例 `minimal.log` 为1 passed（22.06s）。同一新编译器下完整PR回归 `pytest.log` 为 **111 passed、4 skipped（25.59s）**；4项是声明仅CUDA/Kunlunxin支持的graph memory profiler，不是MetaX核心graph跳过。该受控对照验证了pybind ABI不一致的根因及构建依赖修复。尚无模型产品代码新增修复。

开始运行FlagGems-vllm已有六组Qwen核心算子quick测试（HC、PLE conv/fusion、QSA prepare/attention及self kernels），结果在 `04-runs/qwen-kernels-abi11/`；先collect-only，执行使用-x，首个失败停止，未将收集或跳过当成数值通过。
