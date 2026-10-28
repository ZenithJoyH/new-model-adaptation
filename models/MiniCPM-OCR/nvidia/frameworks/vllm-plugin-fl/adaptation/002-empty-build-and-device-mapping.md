# 002：empty 构建及 NVIDIA UUID 兼容

2026-10-20，H100-149；证据均位于批准根 `/public/flagos/jinghao/MiniCPM-OCR/flagos`。

## 已验证安装问题

基镜像缺少git/cmake，GitHub直连DNS失败。使用用户授权代理安装构建依赖及获取上游默认分支。代理任务no_log，凭据不进入服务启动器、源码或模型记录。初次无代理apt进程本轮内经身份核实后TERM，未停止容器或其他工作负载。

卸载原生vLLM后，v0.24.0源码`ee0da84ab9e04ac7610e28580af62c365e898389`以`VLLM_TARGET_DEVICE=empty`、`--no-build-isolation --no-deps`成功构建，metadata为0.24.0+empty。Plugin以VLLM_VENDOR=cuda构建。首次CMake失败签名为`CUDA_nvrtc_LIBRARY ... NOTFOUND`；实际库在`/usr/local/lib/python3.12/dist-packages/nvidia/cuda_nvrtc/lib/libnvrtc.so.12`。设置CMAKE_ARGS显式指向该库后扩展构建与实际import均成功。没有复制未知二进制或更换CUDA/Torch。原始日志`04-runs/install-20261020/install-plugin.log`、`install-plugin-nvrtc.log`。

FlagGems上游master为8200f71f51d784d54a5a51019cb955acb74d64c1；FlagGems-vllm上游main为fa78ddee4c3e78ce5047213ff0ef02acff34b2d5。浅克隆构建的版本标签分别为0.0+g8200f71f5与0.3.0.dev1，以确切提交/文件身份为准。Torch2.11.0+cu129、Triton3.6.0、Transformers5.12.1、NumPy2.2.6均保持。证据`01-environment/upstream-revisions.json`、`packages-before.json`、`packages-installed.json`及`vllm-installed-sha256.json`。

## 设备UUID问题及受限修复

容器仅透传物理GPU1，CUDA选择整数0或GPU UUID才可见，CUDA_VISIBLE_DEVICES=1无设备。UUID独立torch检查通过，但eager引擎在Plugin worker设备转换时抛出`Non-integer device ID 'GPU-...' is not supported by nvidia`，还未加载模型。日志`04-runs/eager-v1-20261020/service.log`。

Plugin PlatformFL仅接受整数控制ID；上游NvmlCudaPlatform支持UUID但模块依赖empty安装缺失的原生CUDA扩展，直接委派的首轮测试失败。随后Plugin内同契约NVML转换的9项边界测试通过，但真实映射发现单设备透传后容器NVML索引也重编号0，并非宿主索引1。现场tensor device UUID为c0e18c12-3dff-8bdc-3478-7ef9d103a3b1，与宿主GPU1一致。

最终方案是运行配置选择容器CUDA_VISIBLE_DEVICES=0。临时PlatformFL方法及其试验测试已完全撤回，git diff --exit-code -- vllm_fl/platform.py通过；没有为配置问题留下共享平台行为变更。最终映射证据01-environment/gpu1-mapping-v2.txt。旧测试和失败日志保留作为诊断历史，不作为最终额外产品修复。

## 嵌套挂载失效与恢复

原容器Docker配置声明只读父目录加可写flagos子目录，但内核/proc/self/mountinfo最终只存在只读父挂载；Triton addmm编译第一次写绝对缓存路径报EROFS。这是工作目录可写性问题，不是已证实的addmm数值/内核缺陷。路径inode相同及Docker inspect RW字段不足以证明可写；重新检查statvfs确认只读。

没有停止、重启或移除原容器，也没有变更其挂载。以docker commit --pause=false保留已安装环境为本地恢复快照，创建运行容器minicpm-ocr-flagos-runtime，ID9b0f522c5a7688c76053de8b34642370e4b9f885d6aa938cbd44967e6a3597ff，恢复image ID sha256:3331198c9ba0191a6bbd259a12ddd535be5fb60ac7a07d0056c7df1a46007cf9。使用工作根单独RW、权重目录单独RO；既有原生参考材料只读映射/opt/ocr-reference供功能测试使用，不作为产品代码依赖。

新容器statvfs、工作根缓存实际写入及权重只读检查通过，/proc/self/mountinfo同时列出相互独立的RW/RO映射，证据01-environment/runtime-mounts.json。旧容器持续运行。eager-v3-20261020开始新的真实推理验证，不复用先前失败run。

另按FlagGems依赖声明修正本轮SQLAlchemy至<2.1；pip check剩余NIXL1.2.0/nixl-cu12 1.3.0冲突已在原生容器同样复现，是基镜像既有问题，TP1本轮未启用NIXL传输，不擅自改动该可选路径。最终状态及hash待交付核实。

## 最终交付核对

SQLAlchemy最终2.0.55；实际导入/产品文件与empty vLLM2449文件完整性均已核实。FlagGems与FlagGems-vllm生成代码使用FLAGGEMS_CACHE_DIR而非仅XDG；最终启动器显式归06-cache/flaggems，保留早期默认缓存并安全迁移可复用项。16项最终sanity复验不再依赖临时诊断缓存设置。最终脚本不含代理凭据、PYTHONPATH、黑名单或安装步骤。
