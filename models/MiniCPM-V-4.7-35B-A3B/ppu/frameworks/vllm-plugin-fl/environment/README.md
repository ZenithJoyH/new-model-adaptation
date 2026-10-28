# PPU-13 / MiniCPM-V 4.7 35B-A3B 环境分析

核实日期：2026-09-28。唯一目标 Host 为 `PPU-13`，连接检查解析到
`bm-aliyun-wlcb-zonea3-c-810e-96g-10-13`。目标容器 `minicpmV4.7-35B`
（ID `145f15078dc1c953d9e136ce595e3185003a6606c28993e30061a2047d3f3653`）
保持运行；镜像 ID 为
`sha256:52536a088a055b2c24cdfca21d0ea9e8d68c1f5f82fee7a40f7ec8f72e4a`。

| 项目 | 现场事实 |
| --- | --- |
| 硬件 | `ppu-smi` 1.28，driver `2.1.1-rbd225`；16 张 PPU-ZW810E，每张 98,304 MiB；15:44 全量检查均仅用 1 MiB，未见运行进程。初始服务选可见设备 0、1，TP2。 |
| 工作根 | 宿主机及容器内均为 `/mnt/nfs/users/jinghao/MiniCPMV4.7-35B`；Docker `/mnt` bind mount，根目录两侧 `stat -L` 均为设备号:inode `41:14016406509`，无符号链接改写。七个标准产物目录已通过单 Host Ansible `--check --diff` 后创建。 |
| 权重 | 容器内 `/mnt/cpfs/models/MiniCPM-V-4.7/weights/35b-a3b`，与宿主机为同一 `/mnt` 挂载；两侧设备号:inode `40:1106071`。`config.json` SHA-256 `3973e7ad0bd9f96887341cb134173118b0e445695014a73e736de48e9a9b5646`，与模型级记录相同；17 个 shard 和索引存在，权重保持只读。 |
| 软件 | Python 3.12；PyTorch `2.10.0`，Transformers `5.8.1`，vLLM `0.24.0+empty`，Plugin `0.3.0rc2.post1+g3a27a6fb2`，FlagGems 包 `5.3.5`，FlagGems-vllm `0.1.0`。 |
| 源码 | Plugin 为 `/workspace/vllm-plugin-FL` editable 安装，基准 Git HEAD `3a27a6fb2d514cdf55c00481bf813225dac63319`，改动前工作树干净；实际 `vllm_fl` 从该树导入。vLLM 从 `/usr/local/lib/python3.12/site-packages/vllm` 导入，源码 checkout `/workspace/vllm` HEAD `ee0da84ab9e04ac7610e28580af62c365e898389`，保持只读。FlagGems checkout `/workspace/FlagGems` HEAD `1a38df24f72ca5a4a6a24650b5d66356709750ba`，但 `flag_gems` 包从 site-packages 导入；FlagGems-vllm editable checkout HEAD `6b0b7d7a84ff56f1959215c2eb94ccf8f2bc797b`。 |

`AutoConfig` 和 `AutoProcessor` 在批准工作根的缓存路径下，以
`trust_remote_code=True` 成功读取权重自带的 4.7 配置与处理器：文本配置为
`Qwen3_5MoeTextConfig`，视觉处理器和视频处理器均为 4.7 专用类。vLLM 只有
`MiniCPMV4_6ForConditionalGeneration` 注册；它的文本骨干是稠密 Qwen3.5，位置
算法是顺序 M-RoPE。4.7 必须有独立 Plugin 模型注册、MoE 构造和 canvas M-RoPE。
模型配置上限为 262,144 token；项目规则要求初始服务使用 50,000 token，不能以
降低上下文长度掩盖适配失败。

初始 eager 配置在容器内
`/mnt/nfs/users/jinghao/MiniCPMV4.7-35B/01-environment/start-eager-tp2-v1.sh`，
同路径可由宿主机读取。配置固定设备 0、1，TP2、50,000 token、最多 8 序列、
`--mm-processor-cache-gb 0`，启动时未显式指定前缀缓存；后查明生效值为
`False`，见[005 问题](../adaptation/005-prefix-cache-effective-default.md)。进程日志位于
`04-runs/eager-tp2-v1/service.log`，缓存位于 `06-cache/eager-tp2-v1/`。
17 个权重 shard 已加载，TP2 API 的 `/health` 返回 200，`/v1/models`
返回目标模型与 50,000 token 上限。首次纯文本最小请求返回 `42` 并正常停止；
图像最小请求虽返回 HTTP 200，却输出 128 个 `!` 并因长度限制停止，视觉推理
尚未通过。原始结果分别位于 `04-runs/eager-tp2-v1/text-smoke.json` 与
`04-runs/eager-tp2-v1/image-smoke.json`；视觉异常见[002 问题](../adaptation/002-visual-garbage.md)。
为诊断该问题，先确认仅本任务 API PID 2852 及其 EngineCore/Workers，
于 2026-09-28 16:43（Asia/Shanghai）向 API 发送 TERM 并确认四个进程退出，
容器保持运行。随后仍在设备 0/1、TP2 和同一端口启动
`01-environment/start-eager-tp2-sdpa-v1.sh`，仅将视觉 attention 后端从
默认 `FLASH_ATTN` 改为 `TORCH_SDPA`；独立结果位于
`04-runs/eager-tp2-sdpa-v1/`。启动和 `/health` 通过，红图第一次回答错误颜色，
重复红图与蓝图仍出现连续 `!`；纯文本仍返回 `42`。为隔离 TP2 视觉分片，
随后只把视觉编码器改为 data 模式；初次启动遇到 vLLM 视觉 fused QKV 加载
`KeyError`。4.7 Plugin 已安装仅限加载期间的映射修正，独立
`04-runs/eager-tp2-sdpa-data-v2/` 服务加载及健康检查通过，但红图仍返回
连续 `!`。后续有限值探针定位到视觉编码器第 7 层首次出现非有限值；仅针对
平头哥视觉第 7 层及以后采用 FP32 分块数学注意力后，当前产品候选 eager TP2
服务 `04-runs/eager-tp2-sdpa-data-product-v2/` 已完成文本 `42`、红图“红色”、
蓝图“蓝色”的最小请求及健康检查。红图冷启动耗时 220.346 秒；graph、复杂图像、
视频及正式精度/性能尚未验证，环境阶段只确认部署身份和可运行基线。
完整诊断见
[002 问题](../adaptation/002-visual-garbage.md)。

2026-09-29 重新核实 `config.json`、权重索引、`tokenizer.json` 和
`tokenizer_config.json` SHA-256，及四个 Plugin 变更文件的 SHA-256；具体值与
容器、镜像、源码 revision、TP2 设备 0/1、基准服务参数一起保存在
`01-environment/deployment-identity-20260929.json`。该文件经宿主机与容器路径
分别读取，SHA-256 均为
`0e71e92a4c367a07d5c478df82ca79d96a648a1cce360d913c0bfab1b01420ab`。
以其规范 JSON 计算的部署指纹为
`9ceae54ecba53f019fec4dc466cdcfb5609d186759af1d286d4b4c01e3a73226`；
其声明的前缀缓存开启状态与 EngineCore 实际 `False` 不符，现仅保留为失效的
历史身份，不可用于正式阶段验收。待新实例明确开启并核实后重建部署身份。
2026-09-29 新 eager 服务在既有模型、源码、TP2、设备与推理参数上显式添加
`--enable-prefix-caching`；EngineCore 生效值为 `True`，健康检查 200。
`04-runs/eager-tp2-sdpa-data-product-v3/` 的文本、红图、蓝图分别返回 `42`、
“红色”、“蓝色”，三个请求均为 HTTP 200 且正常停止。其结果 SHA-256 依次为
`4685a05c70e3a81e318b9843d756720dff40a2be81db28b790f9df9b645f3fac`、
`1273d2e2d1002883b651e2d901b60ed56201ad20a3302c03cead872d89911c55`、
`9f5102d9ab7a578684c289492028a0418e0dedfed6b1e6709c3f55eac56311de`。
新部署身份见 `01-environment/deployment-identity-cache-on-20260929.json`，文件
SHA-256 为 `7405c35358cd2b1b5b347f5b1f68571d3599bf0a2e0c52a94bbf333daf8da0fd`，
规范 JSON 指纹为
`e66b5c293bb60296c932b1e3291282867a6d66c70d7be42e37411f7e31f09a37`。
该身份与 eager、graph 两种非性能服务的缓存开启生效值一致；新的环境回执位于
`04-runs/environment-ppu13-cache-on-20260929/framework-check.json`。eager API PID `895730`
及其 EngineCore/worker PID `896503`/`896788`/`896789` 已在切换前核实，
只停止了这些本任务进程且确认完全退出；适配容器保持运行。

已有经验检索：NVIDIA 同权重 Plugin 适配记录的 4.7 注册、MoE、canvas
位置问题与模型结构相同，但硬件、镜像和 Plugin revision 不同，仅作为接口候选。
`docs/troubleshooting/` 暂无与当前加载现场完整匹配的 PPU 失败签名。
FlagGems 源码同步须单独授权，尚未执行；在此之前不作该仓库具体算子可用性结论。
