# 2026-10-31 mx-103 开发容器迁移与 Plugin 同步

用户选择仅启动适配容器，更新 origin/main 并保留现有适配修改；不启动模型推理服务。
本任务不是新一轮整模型验收，不沿用 mx-101 历史结果证明 mx-103 的新代码通过。

## 已核实范围与执行方式

源机 mx-101 的 qwen3.8-flash 容器 ID 为
06b36c1d70e22ca68adef42e521d76f9b597f3fc6e8c0a9a8738ef03e1b85289，
2026-10-31 现场为 exited；保持该状态，不启动、停止、重启或提交源容器。
目标 mx-103 无同名容器；两机共享 /public-flash。
批准工作根沿用 /public-flash/jinghao/qwen3.8-flash，仅在带 mx103 标识的新任务目录写入过程产物。
目标 /dev/dri、/dev/mxcd 均存在，模型 config SHA256 为
889658f2508e8c61d409b02e70e0d78d8d4452ec65aaafbe129805d213d2e74b。
两机 Docker 存储均有约 24TB 可用，工作卷约 13TB；为约 46GB 源文件系统及迁移峰值预留至少 150GiB。

复制实际安装的解释器、FlagTree、Plugin、FlagGems、FlagGems-vllm、只读 vLLM、
厂商运行库及已验证的容器内部启动脚本。保留 SDK/编译资源及链接目标；排除挂载数据、
权重、root/home 凭据与历史、临时目录、运行缓存和日志。Git 信息独立归档，仅恢复到新开发容器，
不放进运行时镜像；不上传 registry。代理凭据仅配置于新容器私有文件，不写入镜像或记录。

产品代码写入限定为新容器实际安装的 /opt/vllm-plugin-FL。修改前核实导入路径、HEAD、
工作树、仓库指引及原适配差异；完整备份 tracked/untracked 修改。
将 main 快进到本轮实际 fetch 的 origin/main，再逐项合并原适配差异，记录冲突及解决依据。
保留源容器与所有非 Plugin 组件，不修改 vLLM，不自动提交、推送或创建 PR。

适用 plugin:A1/A2/A4、C1/C2、D3、F4/F6；按实际冲突扩展必要条款。
本次不开发新算子，不借同步任务迁移历史数值 kernel。
验证包括复制前后文件身份、无导入覆盖的实际安装导入、Plugin 注册及适用的 CPU 测试。
硬件数值、graph、正式精度及性能未选择，不启动整模服务或据 CPU 检查宣称其通过。

## 完成结果

mx-103 的 qwen3.8-flash 开发容器已运行，ID：
`31022d2372f941b64ad4da9c7cde8d1be5aacbaff650857e49e8f4e6d1201d89`。PID1为`/usr/bin/sleep infinity`，最终仅剩该进程；没有模型服务、推理请求或监听端口验收。
工作根同路径RW绑定，模型目录独立RO绑定，/opt无host源码覆盖。用户可在mx-103执行：

```bash
docker exec -it -w /public-flash/jinghao/qwen3.8-flash qwen3.8-flash bash
```

源mx-101原容器始终未被启动/停止/替换；最终现场仍为exited，原停止时间为2026-10-29。
本轮只从其当前文件系统生成过滤归档，未使用docker commit或暂停源容器。
运行归档约24.1GB，Git开发归档约420MB；运行时镜像不含.git仓库目录、挂载权重、root/home状态和代理。
私有迁移底包`local/qwen3.8-flash:mx103-env-20261031`的ID为`sha256:4290d9410d7db87b5a16c96cb121a111897ad195d94852998ffae564e602f315`。
它是更新前的运行底包；Git恢复、Plugin更新、代理及临时目录修复位于当前容器可写层，
不把底包当成已经包含这些更新的可重建发行镜像。未推送registry，未做整模型镜像部署验收。

复制后、更新前核对了/opt下93471个普通文件、23215973007 bytes的SHA256，
与实际源文件一致。目标Docker为29.1.3，host Ubuntu22.04.5，容器Ubuntu22.04.3；
维护入口accelerator-check --limit mx-103确认8张MetaX C550、单卡65536MiB、driver3.8.1，
host工具报告MACA3.7.1.5；容器实际SDK兼容检查报告3.8.2。没有据此宣称GPU数值或图验证通过。

## Plugin 更新与修改保留

从`f41b7de883ed71526716738a7e05d810f49ded58`快进10个上游提交到main：
`7094141e28a2680644fc41073aa9dfdfbf1f0044`；原适配差异以tracked/index补丁、untracked归档和WIP stash完整保留，
stash为`d4816cd7adb7ad818efb934c5a289495e91ed09a`。没有新建分支提交、push或PR。

按原PR455提交65759c432cef847c311ccd0ab9dc077ab91454ed逐文件对照：39项与新main相同；
13项是未经本地修改的PR代码，采用主线的更新/替代；4项自动三方合并，3项本地新增原样恢复。
无文本冲突。不是把旧工作树整体覆盖到main；最终额外差异只保留以下7个文件：

- `tests/unit_tests/compilation/test_metax_standalone_compile.py`
- `tests/unit_tests/ops/test_rotary_embedding.py`
- `tests/unit_tests/worker/test_mamba_cache_compat.py`
- `vllm_fl/compat/mamba_cache.py`
- `vllm_fl/dispatch/backends/flaggems/impl/rotary.py`
- `vllm_fl/dispatch/backends/vendor/metax/patches/fix_standalone_compile.py`
- `vllm_fl/worker/model_runner.py`

4个产品文件分别负责异构Mamba复制缓冲/调用、RoPE functionalization边界和MetaX编译产物兼容；
3个测试文件为对应既有回归。6个保留文件与源字节相同，model_runner同时保留主线的新变化。
相关差异块已复核：plugin:A3/C1/E1/E2/F3；本地保留部分未新增数值kernel，未迁移无关历史实现。
其他组件HEAD、完整dirty diff及untracked文件哈希均与本轮更新前一致；vLLM保持只读。
FlagTree原Git HEAD不可解析的情况保留，以复制文件身份及实际安装版本为准，不伪造Git revision。

更新直接作用于实际安装的/opt/vllm-plugin-FL；使用同一/opt/conda/bin/python，
执行pip install --no-index --no-build-isolation --no-deps -e /opt/vllm-plugin-FL，未下载或升级依赖。
当前发行元数据版本为`0.3.0rc2.post1+g7094141e2.d20261031`。
实际导入为Plugin /opt/vllm-plugin-FL、vLLM /opt/vllm、FlagGems /opt/FlagGems、
FlagGems-vllm /opt/FlagGems-vllm、Triton /opt/conda/lib/python3.12/site-packages/triton。
调用者没有PYTHONPATH覆盖。注册时已安装TileLang自行添加其包内TVM路径，已核实其中没有
另一份上述组件；未修改该第三方依赖或通过导入覆盖替换版本。原始导入观察中的
no_import_override是在注册后取样为false，保留原记录，以补充的caller/实际路径证据明确其来源。

## 代理、运行目录与验证范围

代理仅保存于容器/root/.config/qwen3.8-flash/proxy.env，权限0600，所在私有目录0700。
交互Bash与登录Bash自动加载http_proxy/https_proxy，并保留localhost的no_proxy；
直接docker exec不经过Bash时不会自动加载该Shell配置。凭据配置任务使用Ansible no_log，
未写入镜像、Git、公开日志或本记录；本地临时凭据在成功配置后已删除。

过滤动态缓存时最初遗漏/tmp目录，导致首次安装选用/var/tmp，首次SDK导入出现LLVM版本探测警告。
已在新容器补回/tmp及1777权限、恢复/root为0700，并完成临时文件写入/fsync。
新进程tempfile默认/tmp，无缓存目录环境覆盖；重新导入后无缺失/tmp或SDK LLVM探测失败。
最初警告日志保留，未通过修改SDK依赖掩盖。私有底包尚未重建包含这一步，当前容器已修复。

Plugin实际导入、平台入口和4个Qwen架构注册通过。原生pytest收集71例，按明确CPU/Meta范围
选择43例，43 passed、0失败、0错误、0 skip，28个GPU/CUDA参数例未选择；耗时278.86秒。
范围为CPU编译缓存、RoPE编译边界、Mamba元数据、Qwen运行配置/权重加载/公开算子绑定。
不把接线、Meta或CPU检查当作真实MetaX数值/graph验证，没有执行LLM或HTTP请求。
当前最小启动脚本与容器内部副本SHA256仍为`c207cc11bfba76819ec04510cd34c8647ecc5fec92492dd48e8ba1eff6e3eda3`，仍仅2项必要导出；
代理没有混入启动脚本，未重新加入缓存目录或FLAGGEMS_DB_URL覆盖。

GPQA全198及九场景性能保持2026-10-25原mx-101实例的历史结果，未作为此次main/mx-103的通过证据。
framework.yml的验收状态、部署指纹、validated_hosts与原生旧回执未改写或提升。
英文[环境交付指南](../acceptance/deployment-guide.md)仅说明已验证的开发容器入口和实际限制。

## 证据

下列路径均相对两机共享批准根/public-flash/jinghao/qwen3.8-flash；原始日志、补丁和结果未复制进本地模型目录。

| 原始证据 | SHA256 |
| --- | --- |
| 04-runs/migrate-mx103-source-20261031/source-identity.json | 75e293d8f8c3b6468b2b0eeb682448191c713b01c001b7748b11b8f8923a23e7 |
| 04-runs/migrate-mx103-source-20261031/inclusion-manifest.jsonl | 24802dc48deba0aaf50300dad238d1c8cec9e0a2360037139b36257cf61d0eea |
| 04-runs/migrate-mx103-target-20261031/container.json | 2d58eb320827e18e6ac5b1bb55deb3c3d2d224c626272070806832cfde1d559a |
| 04-runs/migrate-mx103-target-20261031/image.json | edfd3894c58c5db9913d64688741648b46602d639d6b52b13f24c376742d6e13 |
| 04-runs/migrate-mx103-target-20261031/clone-verification.json | 6ebf078b0e15ac18151306f5f37a8f672210d5afd826d8bbec59039c9a89c993 |
| 04-runs/migrate-mx103-target-20261031/proxy-config-verification.json | ae4c6597de35253739c9e79be6d4ed5f5099b9246e68bd4c77c8aac7fa94596e |
| 04-runs/migrate-mx103-target-20261031/runtime-directory-check.json | ee21bdd6272d88ac57582298d82a8681969083efeda885175140390b976c7ffe |
| 04-runs/plugin-main-mx103-20261031/before.json | 471d5f20d4bc80f18dcdb3ec0e47aeb0b4033db46f1b67899fcbf0f82e702bff |
| 04-runs/plugin-main-mx103-20261031/merge-candidates.json | f62aa368c382ca3a3f03b1e10fffdc2666046ccf4d200e74d70c1af1514ecb11 |
| 04-runs/plugin-main-mx103-20261031/source-update.json | 56dfc5ac0bfe398b5c2d8ff5a5862a34aa345c1e1f01c3655d42522fb2579dcb |
| 04-runs/plugin-main-mx103-20261031/stash-identity.json | 0efb99983bbca10a5e2474bf32309d993ef65846e3c9f63fb2eeacf7996c67d5 |
| 04-runs/plugin-main-mx103-20261031/preserved-adaptation-final.patch | 61078a979c0db480ff974ff2febc000adbb49b34cd75001bae33c66f3cfe2b1d |
| 04-runs/plugin-main-mx103-20261031/import-origin-final-check.json | 5b79823f9dbfc5c785a19f7d6409196e3bbdddb77751f940c34f07b5ac99cb72 |
| 04-runs/plugin-main-mx103-20261031/fresh-runtime-after-directory-fix.json | 599407acc33d242aa3928f807499c1b3d1dca6ad81d523905a30f7b14c5067c7 |
| 04-runs/plugin-main-mx103-20261031/cpu-regression.xml | 944831c83b5bbce1bcb6ce579726979f8774b175557dd8f337068776756d7792 |
| 04-runs/plugin-main-mx103-20261031/cpu-regression-summary.json | 488c33b011779cc49603aa28471f61d29abae4b018a01d38c30be4c80c34a578 |
| 04-runs/plugin-main-mx103-20261031/validation.json | 7e6da49940ab94ec52a5e30c8bb477d80fa2e2f735e2e84e86124fb48e2e7107 |

源/目标迁移阶段分别记录在04-runs/migrate-mx103-source-20261031及migrate-mx103-target-20261031；
代码备份、候选、当前补丁、安装日志和原生JUnit位于04-runs/plugin-main-mx103-20261031/。
迁移归档与私有底包保留，不清理既有数据、镜像或其他容器。
