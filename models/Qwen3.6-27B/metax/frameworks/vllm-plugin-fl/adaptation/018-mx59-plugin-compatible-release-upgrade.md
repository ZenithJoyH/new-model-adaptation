# 018：mx-59 更新兼容 Plugin 分支并恢复 MetaX 原生 KV-cache

## 范围与身份

- 2026-10-10，按用户请求仅更新 mx-59 / `qwen3.6-27B` / Qwen3.6-27B 的已安装 Plugin，属第3阶段局部适配；未选择正式验收、其它主机或其它组件更新。
- 容器 ID `1f62bdcb818d7119ed6595133dc64c3f14c194ae565c95dba18ef89bbd4fe657`，始终 running；完整 `/public-flash` 同路径 RW挂载及权重RO别名已复核。批准过程根 `/public-flash/jinghao/qwen3.6-27B`；实际 editable 安装树 `/workspace/vllm-plugin-FL` 在容器内部，不是宿主机 bind。
- 原 Plugin HEAD `675548ab2ee52b8124b0b6a82a2f795c0553e1fa`；改为官方 `release/0.2@8b059122e32b9ac47b9820a9c7b1bb95077481a4`。安装元数据为 `0.2.2rc2.post1+g8b059122e.d20261010`；`direct_url.json` 与模块定位均确认仍来自 `/workspace/vllm-plugin-FL`，未用 PYTHONPATH 或第二份 checkout。
- vLLM 保持 `0.20.2+empty` / HEAD `bc150f50299199599673614f80d12a196f377655`，完整 `git diff` SHA256仍 `a5f23833739f2a4082eadf3ecacc8dfbe6fb3d34f68e424101520aa68766ac9d`。FlagGems保持用户冻结的 HEAD `7599dd130046f84df099aa771e91d35d5991e69a`，公共 sort SHA256仍 `e200fbf2287ebd4104e8e312fe0dab90e6a05326a8f56b25cccc604c7c46a199`。FlagGems-vLLM未修改。
- 用户 `start-model-flagos.sh` 保持 SHA256 `1cc015c75db3a171244a663b9ae049813796826bd7020a9f1d6a93a4283f7de2`，未改参数或覆盖日志。

## 上游选择与失败保留

复用017白名单导致 KV-cache 无候选的诊断，升级前先核查实际原生能力。`vllm_fl.register()` 加载 mcoplib后，`torch.ops._C_cache_ops.reshape_and_cache_flash` 确实存在；不能仅凭empty vLLM源码树未带 `_C.so` 判断整个进程没有SDK算子。

直连 GitHub首次查询超时（rc124），按用户授权使用临时代理成功 fetch 官方 main 和 release/0.2；secret只传给该次Git进程，未写入Git配置、文档或源文件，最终检查无持久化proxy配置。main冻结到 `cf5d1e3998d414149417a1b0de448ecedddef85b`，官方README明确main匹配 vLLM0.24.0、release/0.2匹配0.20.2；main与当前HEAD也非快进关系，最初祖先断言返回1。保留该失败，不盲升main或同时升级vLLM。

兼容分支源差异已审阅；当前RC分支与release分支历史不同，采用非强制 `git switch --detach` 切换冻结SHA，并迁移本地适配。不是声称已安装最新main或最新发布tag。

初次 `pip install --no-index --no-deps --no-build-isolation -e .` 以共享 `/public-flash/.../05-tmp/` 为TMPDIR，在setuptools复制元数据备份时遇到 `Errno 5 Input/output error`，保留 `pip-install.log`。改用已验证容器内安装树的常规build临时目录 `/workspace/vllm-plugin-FL/build/mx59-upgrade-20261010` 后成功；不构建原先不存在的Plugin `_C` 扩展、不安装依赖，成功日志 `pip-install-localtmp.log`。

## 保留内容与所有权

更新前保存9个tracked改动、6个untracked文件：`02-issues/plugin-upgrade-mx59-20261010/plugin-before.patch`、`plugin-local-files.tar.gz`、`local-files-before.sha256`；归档SHA256 `4001a2676e7949d1d47ebba68686a4044a782fed5026c95fb9a33c6e73c60819`。Git stash对象 `d3aa458f79fddc305c098207c2e8972eac32b06a` 保留未drop；没有提交、推送或强制reset。

stash apply在两个FlagGems文件出现冲突，按上游移除旧KV-cache dispatch方法/注册，但完整保留GDN适配与高层注册；两个低层GDN kernel不增加独立dispatch。公共GDN hook仍在 `vllm_fl/patches/gdn_linear_attn.py`，由Worker加载模型前安装。原worker的vLLM0.20 KV配置list解包及current-config上下文处理也保留，不因换分支丢失。

13个继承文件逐个SHA256一致，包含全部6个untracked文件、FlagOS attention、MetaX连续prefill与GDN两路注册、配置、manager和worker；另两个FlagGems文件只移除上游弃用的cache方法/候选，已审阅GDN差异。ready-PID manager SHA256仍 `59f5fa67d0d698206baa00d1486b59467e7895cb60a726a7414773f44f5ced50`；worker仍 `a0f821e23286992420b7145917559447efa09dd3c69a8b332bdbdee96b01a5fd`。

## 当前 KV-cache 链路与验证

MetaX vendor FA现在使用上游原样 `fa_utils.reshape_and_cache_flash = vllm._custom_ops.reshape_and_cache_flash`，后者调用mcoplib注册的 `_C_cache_ops` CUDA kernel。`fa_utils.py`无本地diff，SHA256 `049218963f0ac80bccf3e7a1b5dd2a618f046775dc1f88f32047b5d0b4989bd2`。不新增假vendor标签，也不绕过白名单强制启用FlagGems cache；这不保证其它所有白名单外算子都有原生fallback。FlagOS attention backend原有直接FlagGems cache调用保持不变。

原生证据位于 `04-runs/plugin-upgrade-mx59-20261010/`：

1. `dispatch-tests.log`：280 passed in 30.00s，包含GDN候选过滤、公共hook保留原链路、worker安装顺序及ready-PID回归。
2. `native-cache-tests.log`：实际物理GPU2，使用用户原白名单，不含reshape_and_cache_flash；assert该算子dispatch候选为空、attention/GDN均选vendor.metax、原生CUDA kernel存在且FA绑定与原vLLM函数同一对象。8组FP16/BF16、16/784页、连续/非连续输入，全部eager通过；各执行2次改变K/V及slot mapping的CUDA graph replay，写入与CPU scatter逐元素一致，含负slot和跨页。
3. `service.log`：临时18001、GPU2/3、TP2/BF16、8192batched tokens、显存0.9、FULL_AND_PIECEWISE/max capture64；运行时确认默认compilation mode=3。沿用用户白名单和连续prefill开关，诊断启用prefix cache、独立编译缓存，未改或直接执行用户performance脚本。mixed PIECEWISE与decode FULL均完成11/11捕获，15:21:04完成API启动；没有再出现017的cache无候选异常，也未降级图模式。
4. `request-results.json` / `request-check.log`：health=200，4条chat请求HTTP200，实际内容依次为 `2`、`21`、`北京`、`Paris`，符合预期；关闭thinking，仅作短请求正确性检查，不替代正式精度。
5. 按冻结PID、start_ticks与cmdline只向诊断API325595发送SIGTERM；上游shutdown处理其owned workers，未停止容器或其它服务。`stop-verification.json`确认API、tracker326150、engine326151、workers326425/326426均退出且18001释放，最终docker top只剩原有shell。15:24:10的mx-smi确认GPU2/3均0%利用率、约860MiB占用，与测试前859MiB基本一致。关闭日志有上游owned-worker SIGKILL信息及resource_tracker semaphore清理警告，已保留，不隐瞒或等同启动失败。

当前Plugin完整 `git diff` SHA256 `53ad72e0b0736f677818ccb53403d87c64f90f4e9cd0fd599c3338d416a8e27b`。本地syntax-check的252项workflow测试（skip1）及6项operations测试通过，但整体审计仍有既有12个profile-revision错误与78项待复核，不能表述为整体审计通过。

最终源与证据身份保存于 `01-environment/plugin-upgrade-mx59-20261010/source-and-evidence-final.txt`。dispatch日志SHA256 `552b885d9a1333ca9e2d0e8c7768531ca0df1e18ce71e3cb62f127bf32a01dbd`，native-cache日志 `2f5fb817eae5d929ceeeb06a55204d0486d629d365ab6da37af7e7371dd4e84c`，4条response JSON `a47ed68d3b9a51d1d114aac45fce90b6c0fc478fd85c88e0bed97be77efeaa07`，已关闭的service日志 `a8b844180c7dcee4ddabfa8cb9fc24d05f29fde89ddb66500f3ca79d3604e967`，stop验证 `39f37c9f901bf873b78f5d9e5dd7ea33247d5862b64beb2b81ed3f7b866862fb`。

## 边界

状态：兼容分支部署、原生cache回归及限定模型启动/短请求已验证，017的缺失路径已修复。用户仍可使用原启动脚本，无需为此追加cache白名单；本轮验证不是原脚本逐参数复跑（prefix cache/端口/alias/缓存根有上述诊断差异）。未跑正式准确率、吞吐或其它平台回归；未重新打包镜像，不将容器更新当作镜像已包含。暂不更新framework.yml或标记optimized。限定设计审查采用官方兼容分支，保留已有dispatch语义和真实原生能力检查；知识状态local-only。
