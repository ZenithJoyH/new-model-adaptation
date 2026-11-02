# Plugin 主线更新与服务启动验证

2026-11-01，用户要求配置所给网络代理、更新现有容器中的 Plugin 并验证服务能否启动。本轮范围限于 mx-101、mx-102 的 `glm5.3-flash`，沿用批准根 `/public-flash/jinghao/glm5.3-flash` 和实际安装目录 `/opt/vllm-plugin-FL`。不推进此前暂停的全量精度、性能或镜像发布，不沿用旧精度作为新版本结论。

现场：101 原容器已于 10-29 停止，确认原 ID、交互 bash 入口及挂载后启动；102 原容器运行中。两机均无当前 GLM 推理进程，8 卡可用。现有 Plugin 均为 `4e23ae8f24b380ee845f6ab3f5c8c136151d4959` 的 editable 安装，`main` 跟踪 `origin/main`，保留此前 GLM 适配的已修改及未跟踪文件。控制模式仍为 agent。

实施边界：先保存 HEAD、dirty/新增文件、补丁和文件哈希，然后通过进程环境代理 fetch 已配置的公开 origin，核实主线新增提交及与既有修改的重叠，再限定移植文件。只在核实后的当前 Plugin 树中同步，不创建源码镜像目录、不设置 PYTHONPATH。安装仅更新同一路径的 Plugin 元数据，使用原解释器、`--no-deps --no-build-isolation`；vLLM、FlagGems、FlagGems-vllm保持原身份与文件。若主线要求未授权依赖变更，先记录实际阻塞。

验证计划：比对两机最终 HEAD 与适配补丁、实际导入与安装版本；运行与合并内容相关的原有测试，再使用原共享 `start-model.sh`（SHA `a9ccaa4159df8790dd8c7c1833913e239d3f55ba347a65976cf6be29ba6b6626`）启动双机正常服务，核对有效图模式、就绪及真实文本响应。只处理本任务进程，容器保持运行。适用 `plugin:D3/F4/F6`，发生兼容或合并冲突时另按实际符号复核 `plugin:C1/C2/C3`；本轮不新增数值 kernel。

代理通过受保护的 Ansible 变量传入更新进程，敏感任务使用 `no_log`，不写入源码、Git remote 或服务启动脚本。完整原生产物留在批准远端根，当前结果待验证。

主线比较后限定操作：目标固定为公开 `7094141e28a2680644fc41073aa9dfdfbf1f0044`（2026-10-30，GLM-5.3 主线支持）。相对旧 HEAD 有 6 个提交、160 个上游文件变化；与现有 19 个改动文件只在 README、`vllm_fl/__init__.py` 重叠。新主线以 `vllm_fl/models/glm5/` 注册同一模型；旧 `apply_glm5next_patches()` 会再次覆盖注册，不能直接叠加。将现有完整改动保存为批准根内补丁、文件归档和 Git stash 后，仅 fast-forward 主线，不自动重放旧模型或 MetaX 补丁。本轮不新增、删除上游实现或自写算子；归档的原文件可恢复。

已查明 `models/glm5/runtime.py:validate_glm5_config` 明确拒绝 PP>1，而现有脚本为 TP8/PP2。当前选择使用原脚本验证这个真实版本约束，不自行改成 TP16/PP1、不更新主线 `glm5` extra 所要求的其他依赖。此项服务启动检查不等于重新完成模型适配；先取得明确运行结果，再由后续任务决定是否调整拓扑及依赖。

## 已验证结果

两机均已更新到 **`7094141e28a2680644fc41073aa9dfdfbf1f0044`**，安装元数据为 **`0.3.0rc2.post1+g7094141e2`**，实际安装仍是 `/opt/vllm-plugin-FL` 的 editable 源码，工作树 clean，无导入路径覆盖。102 先完成真实导入检查，再更新101；两机实际启动均激活了新 Plugin 并进入新 GLM 配置校验。

旧改动完整保留：101 stash 为 `0b14077d991f5a05dd3a57c72dd5e6bd04d4c9d6`，102 为 `69589eb0cdaeca40a4aa5e05ba02218fc23a95b6`；各机另有 `01-environment/plugin-update-20261101/<host>/plugin-before.patch` 和 `plugin-before-changed-files.tar`。未自动重放旧注册。vLLM、FlagGems、FlagGems-vllm 的 HEAD、源文件及模式均与更新前哈希一致。

102 第一次 pip 安装在 NFS 临时目录触发 setuptools 元数据备份 I/O 错误，日志保留在 `04-runs/plugin-update-startup-20261101/mx-102/plugin-install.stdout.log`。改用此前已批准的本地目录 `/data/jinghao/glm5.3-flash-image-runtime/05-tmp/plugin-install-20261101/<host>` 后安装成功；没有修改 setuptools、pip 或其他第三方依赖。101 直接采用已验证的本地临时目录。

**服务启动检查失败。** 两机使用同一原脚本，实际参数仍为 TP8/PP2、双节点、FULL_AND_PIECEWISE、prefix caching 开启；均以退出码1结束，错误一致：

```text
Glm5ConfigError: GLM5-Next on vLLM 0.24 requires pipeline_parallel_size=1:
mHC state transfer between pipeline stages is not implemented
```

错误来自新主线 `vllm_fl/models/glm5/runtime.py` 的 `validate_glm5_config`，发生在配置校验阶段。API 18530 未就绪，没有执行生成、精度或性能测试，不能据本轮更新声称服务可用。旧版本的174/198精度、执行模式及源码审查仍仅属于原版本，已从当前验证状态转为历史记录。

两机最终原生记录位于批准根 `/public-flash/jinghao/glm5.3-flash`：

| 主机 | 启动与更新核验记录 | 记录 SHA-256 | 完整启动日志 SHA-256 |
| --- | --- | --- | --- |
| mx-101 | `04-runs/glm-plugin-main-startup-20261101/mx-101/verification.json` | `02b5a47c35daed6109a463bde7ec72f722ee717a44cfd69262e157a9b350e8d6` | `5b51dd066ef2f4f1349956812f9ec8ee411c521abff6f3bd18d8ff1dc0639dd8` |
| mx-102 | `04-runs/glm-plugin-main-startup-20261101/mx-102/verification.json` | `e4b0af7a1a8ad806f12424f55e42a53fb4ad696ad98dab88bf424cfa53bd1d6e` | `8cf34b6d764b6870fc93b626d24cf7bdf58892b13d786fbfe5dc3aa1ff7ba401` |

各目录的 `stdout.log`、`state.json` 保留失败现场，`verification.json` 绑定原脚本、安装记录与未变组件身份。两机 `glm5.3-flash` 容器均保持 running、非 paused，已核实无遗留 GLM 服务进程。当前结论仅为“Plugin 更新完成，原 TP8/PP2 服务启动失败”。主线还声明了固定的 FlagGems-vllm GLM extra 依赖；本轮未安装该 extra，其他启动阻塞与拓扑调整后的行为尚未验证。
