# 镜像封装：空间不足与独立候选

2026-10-28现场检查；源码、图模式和正在运行的GPQA参数未改变。

101首次`docker commit --pause=false`失败，原生错误为containerd写入编译缓存时
`no space left on device`。DockerRootDir虽然是`/data/docker`，实际报错路径位于系统盘
`/var/lib/containerd/io.containerd.snapshotter.v1.overlayfs/`。系统盘877G、已用874G、
普通可用空间0；`/data`尚余24T。目标tag不存在，未产生可交付镜像。
两机原`glm5.3-flash`容器均核实running=true、paused=false，GPQA继续运行。
失败记录保留在远端`04-runs/image-candidate-v14-20261028/mx-101/state.json`及
`01-environment/image-candidate-v14-driver.log`，不以重试掩盖失败。

应用本次读取的镜像交付Skill后，封装改为独立候选；不得再次提交原适配容器。
102新候选`glm53-release-candidate-v14`，ID
`621f76472da4eee79a412f99432f7dc39336764a57ac02d9fa207c9fe4b0c496`，
基于已核实a6f6bad基础镜像，无GPU、无挂载、无模型服务，仅sleep保持运行。
记录为`01-environment/independent-image-candidate-v14-mx-102.json`。

基础镜像视图含5.3G旧vLLM缓存、源码仓库元数据及带凭据URL特征的shell历史；
仅检查特征并保存布尔结果，不展示或记录秘密。仅在候选中清理这些内容，保留SDK、
编译器资源、Torch和vLLM代码；从实际安装目录收集冻结的三组件、FlagGems匹配的
editable元数据/入口及八个内部交付文件。输入逐文件前后校验，路径和哈希写入
`01-environment/image-runtime-input-v14.json`；源码未复制成工作根下的开发checkout。

候选必须通过导出清洁文件系统再封装为新基础层，消除继承层内的历史凭据和缓存。
只删除候选可见文件后commit仍会保留旧层，不能作为安全交付。
101原系统盘不足以容纳清洁镜像；已向用户请求两机新增本任务独立Docker存储目录
`/data/jinghao/glm5.3-flash-image-runtime`。未获确认前不写该目录、不变更现有Docker，
也不停止其他容器。候选实际封装、导入和双机fresh-container推理仍待完成。

清洁文件系统导出及归档内核验随后通过：
`05-tmp/glm53-clean-runtime-v14-20261028.rootfs.tar`为24,291,981,312 bytes，
SHA-256 `802f9f34e3ba5c6fdd50a325e2077c3da3fabc2e48be30576cee7b7630a66e4f`；
共159,531条文件系统记录，运行输入逐文件核对通过，排除路径检查为0。
原生记录`01-environment/clean-image-export-v14-20261028.json`及
`04-runs/clean-image-export-v14-20261028/mx-102/state.json`。这是已核验rootfs归档，
尚未成为Docker镜像，不等价于镜像导入或fresh-container服务验证通过。

用户随后明确批准两机使用新增目录。两机独立Docker已依次启动并现场复核：
socket均为`unix:///data/jinghao/glm5.3-flash-image-runtime/05-tmp/docker.sock`，
实际DockerRootDir为该目录的`06-cache/docker`，使用overlay2且关闭containerd
snapshotter，避免继续写入系统盘。102 Docker29.1.3、daemon PID3974766；
101 Docker29.3.1、daemon PID344061。各自独立exec-root、pidfile和Unix socket；
bridge/iptables/ip6tables/ip-forward/ip-masq均关闭，原Docker未重启，原运行容器集合
现场复核全部保持运行。身份及准确进程起始时间/命令哈希保存在
`01-environment/isolated-image-runtime-v14-<host>.json`，不可只凭PID操作。

102已将清洁rootfs导入为单层镜像：
`local/glm5.3-flash:adapted-v14-20261028`，ID
`sha256:eb67b5a6cccb87470c25060fb5a96d86dc1f87f2030d9b8b36f8393d54ae3e34`，
image size24,175,577,895 bytes。镜像工作目录为`/`，环境与实际源容器逐项核对，
不包含旧Docker层；归档保存、另一机加载及新容器验证仍须按各自原生结果判断。

随后归档及101加载通过：
`05-tmp/glm5.3-flash-adapted-v14-clean-20261028.tar`，24,291,995,136 bytes，
SHA-256`d009a3072608c0166268776662da56a30e15650d7f267f3a57241607e29c318c`。
两机镜像ID一致，唯一层SHA与清洁rootfs归档SHA一致，旧镜像层未继承。
原生记录`01-environment/clean-image-candidate-v14-20261028.json`及
`01-environment/clean-image-loaded-v14-mx-101.json`。

两机各创建`glm5.3-flash-imagecheck-v14`临时验证容器，分别属于各自独立Docker。
仅声明权重目录RO及任务`04-runs`日志目录RW；镜像内9107个运行输入条目、实际导入路径、
八项依赖版本、启动脚本SHA及8卡可见性均通过。`/opt`无开发挂载，初始动态缓存为空。
结果在`04-runs/imagecheck-v14-20261028/<host>/static-verification.json`。
原始适配容器及GPQA持续运行，新容器尚未启动模型服务；静态通过不等价于生成验证通过。
八个冻结交付文件已从新镜像按哈希备份到仓库允许的
`deliveries/GLM-5.3-Flash-BF16/metax/vllm-plugin-fl/`；其中明确记录镜像生成验证pending。
