# 002：GDN 的 FULL 支持边界

日期：2026-10-08。状态：边界已复现；显式 `FULL_AND_PIECEWISE` 最小脚本复验通过。

复用此前 Plugin 的 [GDN 图模式诊断](../../vllm-plugin-fl/adaptation/004-gdn-full-graph-limit.md)，
本次重新检查原生 PPU wheel，未沿用 Plugin 的实现或旧结论作为通过证据。
原生 `GDNAttentionMetadataBuilder._cudagraph_support` 仍为 `UNIFORM_BATCH`。

受控启动 `full-v1` 请求 `FULL`、抓图尺寸 `[1,2,4,8,16,32,64]`，TP2/PPU3、4，
默认上下文 262144，前缀缓存开启。18:38:56 两个 rank 均明确记录：
`FULL is not supported with GDNAttentionBackend`，随后设置 `FULL_AND_PIECEWISE`。
因此这不是 FULL 通过。未修改后端能力声明来绕过检查；支持任意预填充 FULL 需要
后端实现支持，而本轮用户要求的模式已有原生支持。

实际图捕获为 mixed prefill-decode PIECEWISE 7/7 和 decode FULL 7/7；每卡图池约
0.13 GiB。服务健康检查 200，文本、图像、切片、多图、视频与重复图共 8/8 请求
返回 200、stop 且内容正确。精确命令、日志与请求见批准根
`04-runs/bringup-20261008/full-v1/`。启动期间共享内存等待提示发生在内核编译中；
缓存持续生成，最终正常启动，未放宽超时。

FULL 请求运行结束后，仅终止本任务进程组 15604 并核实无存活成员及端口 listener。
随后使用根目录 `start-model.sh` 显式启动 `FULL_AND_PIECEWISE`；七档图尺寸保持一致，
未降到 decode-only 或纯 piecewise。最终脚本的实际运行验证另记。
