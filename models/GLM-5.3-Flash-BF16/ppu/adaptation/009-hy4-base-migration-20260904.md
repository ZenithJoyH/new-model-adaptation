# 切换到用户指定 HY4 Git 基线

## 最新安装与清理结果（2026-09-04 14:04后）

用户在获知317/318结果后明确要求安装最新版本并清理无用插件目录。
`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/install-ppu13-hy4-glm53-plugin.yml`以`--no-deps --no-build-isolation --no-index -e`
安装成功，版本`0.0.0+g5329cb129.d20260904`，direct_url及实际import均指向新工作目录。
未更改那项被审查拒绝的单测，未宣称全套通过，未启动整模/graph/GPQA。

安装后配置读取验证失败：原模型目录存在，但`config.json`不存在。
通过`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/inspect-ppu13-installed-plugin-model-path.yml`独立核实后，确认GLM配置类/模型
注册和默认slice黑名单均正常；失败来自模型配置文件缺失，未改权重或换模型路径。
没有重启服务、容器或更改启动命令。主脚本通过环境中安装的入口自动使用新版。

用户要求的清理采用可恢复归档：确认没有进程cwd/cmdline/mmap引用，且新Git树不依赖
旧对象目录后，将以下3目录原子移动到`/workspace/.plugin-archive/glm53-20260904/`：

- 原`/workspace/vllm-plugin-FL-glm53-adaptation`
- 原`/workspace/vllm-plugin-FL-hy4-preview`
- 原`/tmp/vllm-plugin-FL-glm53-reference-2658244`

目的地保留各自同名目录，Git HEAD与工作区status搬迁前后逐项一致；未永久删除
未提交代码，恢复方式是移回上述原路径。见`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/archive-ppu13-unused-plugin-trees.yml`。
需要复现历史命令时先恢复目录，不要直接运行依赖旧路径的一次性迁移脚本。

以下“未安装/原目录保留”为本次安装前的历史阶段记录。

2026-09-04，PPU-13 / `glm5.3-flash` / GLM-5.3-Flash-BF16。
用户明确指定 `https://github.com/ZenithJoyH/vllm-plugin-FL.git` 的
`support-hy4-preview` 分支，随后说明已停止服务并授权直接修改代码。
只读检查8010端口关闭，最终复查仍关闭；没有重启容器或服务。

## 当前代码状态

- 后续适配工作目录：`/workspace/vllm-plugin-FL-glm53-hy4-adaptation`。
- origin为用户指定URL；branch `support-hy4-preview`，upstream `origin/support-hy4-preview`。
- HEAD/新基线 `5329cb1293f397fd194852496cfcc710c35f1bfc`，不切回旧GLM分支。
- 迁移GLM feature提交 `2658244` 相对其父 `e2f51dc` 的功能增量，而非覆盖整个HY4树。
  Git三方应用后4处冲突已逐项处理：保留HY4/Qwen注册钩子，增加GLM注册；
  HY4 MLA prefill函数保留轻量导入，GLM backend类迁入独立文件并保持旧入口兼容；
  PPU保留通用注册并追加GLM专用算子；平台先选GLM专用backend，其他模型沿用HY4。
- 迁入已验证的worker MLA注册、压缩缓存adapter、有效profile黑名单读取修复。
  新HY4基线已支持MLA topk_length，不用旧文件覆盖其sink/cache等新增能力。
- 默认thead.yaml合入GLM专用op绑定及黑名单，并保留已有共享op策略，不新增启动环境变量。
  SHA256 `3d61e2a12b29208397fd44daf35800669bb7d1d1761885910068aee4993f3bae`。
- 共62条Git状态项，无未解决冲突，`git diff HEAD --check`通过；未提交/推送。
  `git diff HEAD --binary` SHA256
  `78e6b42abccadd122503e590db8a54b6c6bfd12c2dd37d624e4b0fe3befbf48d`。

## 依赖与边界

用户随后指定 `/mnt/nfs/users/jinghao/lib` 为so来源。宿主机及容器挂载内核对
三文件名称、大小、SHA256均与已补齐文件和PROVENANCE一致，部署脚本来源已更新为
该用户目录。再次验证为unchanged，不重复覆盖字节相同的文件。

- 根据同步规则，FlagGems干净master从db33988ec快进到
  `9553ae9c745bdf5fd4a25d50e0d67bf80d888030`，最终clean。
  上游差异为Ascend cumsum/multinomial及CI/benchmark；不把旧回归结果算给新组合。
- 首轮测试平台自动发现失败，原因是Git未包含HY4必需的三个PPU原生库。
  从原HY4目录复制与新基线PROVENANCE.md完全一致的三个.so到新目录，三项SHA256
  逐项通过；原文件不改动，未向管理仓库复制二进制。
- vLLM仍`ee0da84ab9e04ac7610e28580af62c365e898389`、clean，未编辑源码。
- 旧GLM目录完整保留，四个tracked修复的diff SHA256仍
  `c058a681a4814d9a78e3038739d694922ce704ba619e632489974a5f453cd55a`。
  原dirty HY4目录也没有改动，仅读取其原生库。

## 验证与当前阻塞

- 补齐依赖后GLM注册/模型测试27/27通过。
- 初次共享单测因旧测试命令隔离掉根conftest导致device fixture缺失；改用原根fixture
  后该设备测试通过，无修改测试断言或设备实现。
- 13:51:21–37完整指定回归：318项，317 passed、1 failed，进程rc1。
  失败为`test_flaggems_quantization_registers_ordered_fallbacks`：测试只mock了
  register_ops模块中的use_flaggems_op，而GLM lazy注册从utils读取同一策略函数，
  进入了测试原本不覆盖的注册路径；其假Registry只有register_many而无register_impl。
  此结果尚未解决，不把它描述成全套通过。更广的graph或整模验证未启动。
- 拟扩展该测试的策略mock到utils（保留现有fallback次序断言）时，auto-review以
  “可能掩盖真实注册回归、抑制失败验证”为由拒绝执行。远端测试文件未修改。
  `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/GLM-5.3-Flash-BF16/ppu/adaptation/patch-ppu13-hy4-glm53-test-isolation.yml`仅为未获批准草案，不应自动执行。
  未通过绕行修改生产逻辑或跳过该case来使测试变绿。

**代码已迁移，但验证未完成，尚未安装新目录。** 当前editable安装仍指向旧GLM目录，
宿主机启动脚本保持原状，服务仍停止。须获用户对测试mock调整的明确批准（或决定
另一验证方案），完成该失败项和eager/graph回归后，才能切换安装并验证服务。
旧GPQA 82.32%/21个长推理截断仅属于旧基线，不代表新基线精度。

## 重现顺序

inspect-ppu13-plugin-hy4-base.yml → prepare-ppu13-plugin-hy4-base.yml →
audit-ppu13-plugin-hy4-migration.yml → prepare-ppu13-glm53-migration-history.yml →
migrate-ppu13-glm53-onto-hy4.yml（预期留下4处冲突，rc1，不重复应用） →
resolve-ppu13-hy4-glm53-merge.yml → configure-ppu13-hy4-glm53-profile.yml →
stage-ppu13-hy4-native-libraries.yml → validate-ppu13-hy4-glm53-migration.yml →
verify-ppu13-hy4-migration-state.yml。

一次性迁移脚本带明确前置断言，不应对已修改树重复执行；诊断和验证可重复。
