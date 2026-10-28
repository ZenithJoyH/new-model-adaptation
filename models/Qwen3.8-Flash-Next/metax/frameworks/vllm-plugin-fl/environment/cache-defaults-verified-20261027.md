# 2026-10-27 默认运行缓存实测

本记录接续同日第一次精简后的[保留路径判断](launcher-defaults-20261027.md)。用户进一步要求删除四项路径导出，
因此增加真实写入和冷缓存整模验证，不再仅凭f_bavail=0认定默认目录不可用。

Host mx-101，qwen3.8-flash容器ID06b36c1d70e22ca68adef42e521d76f9b597f3fc6e8c0a9a8738ef03e1b85289，
UID0；/public-flash同路径RW映射不变。默认缓存是容器根文件系统上的普通目录，无新增挂载或软链接。
f_bavail=0而f_bfree约27GB，root可实际写入；四个默认目录均完成匿名临时文件1MiB写入及fsync。

| 项目 | 现在使用的默认路径 |
| --- | --- |
| 临时目录 | /tmp |
| Triton | /root/.triton/cache |
| FlagGems | /root/.flaggems |
| vLLM | /root/.cache/vllm |
| Inductor默认 | /tmp/torchinductor_root；vLLM的AOT子目录由其自身管理 |

启动脚本及调用者均不导出TMPDIR、TRITON_CACHE_DIR、FLAGGEMS_CACHE_DIR、VLLM_CACHE_ROOT，
没有改用XDG_CACHE_HOME、TRITON_HOME或HOME来间接搬迁缓存，没有复制旧缓存来伪装默认位置。
vLLM已实际保存AOT产物到/root/.cache/vllm/torch_compile_cache，冷缓存整模启动及105token回归通过。
完成时f_bfree=21617643520 bytes、f_bavail=0，未触发本轮启动保护，没有清理其他数据。
该结论限于当前UID0、实际容器文件系统与剩余空间，不把保留空间数字当作镜像或其他机器保证。

旧NFS缓存目录du查询超时，保留为不完整观察；没有据此声称完成了整个历史缓存体积统计。
默认目录写入、参数展开、调用者环境、当前服务进程与内部交付文件均有独立证据，见
[当前启动与回归记录](../acceptance/launcher-default-cache-20261027.md)。
先前冻结的环境正文、2026-10-25完整精度/性能与第一次精简记录保持原样；
本次没有修改产品代码、权重或镜像，也没有重跑正式精度/性能评测。
