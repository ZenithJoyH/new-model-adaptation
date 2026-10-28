# 2026-10-27 启动默认值与缓存目录补充

本文件补充启动脚本精简后的实际环境，不改写已冻结的2026-10-24环境正文或旧回执。
Host mx-101，容器qwen3.8-flash，容器ID及/public-flash同路径RW映射保持一致；
/opt内实际安装源码、解释器和内部交付目录均不在该挂载内。

已安装版本的源码与独立EngineArgs预检确认：未导出GEMS_VENDOR时识别metax；
未导出CUDA_VISIBLE_DEVICES时仍为8卡；唯一已注册vLLM平台插件为fl，默认自动加载。
compilation mode默认解析为3。此模型prefix缓存默认关闭，因此normal必须显式开启，
性能分支显式关闭；mamba align等模型/资源参数保持原值。

现场statvfs的f_bavail=0，f_bfree约27.17GB。后者包含root可用保留块，
不能将其当作可供大型运行缓存自由使用的普通剩余空间；没有清理或迁移其他数据。
批准工作根剩余约15.78TB。因此本轮只删除冗余缓存覆盖，并保留4项必要的临时/缓存目录设置。

| 项目 | 精简后的解析位置 | 依据 |
| --- | --- | --- |
| 临时目录 | /public-flash/jinghao/qwen3.8-flash/05-tmp | 必要TMPDIR，避免默认/tmp占用满盘/保留块 |
| Triton | /public-flash/jinghao/qwen3.8-flash/06-cache/triton-ple-state-fix | 保留覆盖，默认/root/.triton/cache不适宜承载编译缓存 |
| FlagGems | /public-flash/jinghao/qwen3.8-flash/06-cache/flaggems | 保留覆盖，默认/root/.flaggems不适宜承载生成代码 |
| vLLM | /public-flash/jinghao/qwen3.8-flash/06-cache/vllm/473aa021d166 | 保留覆盖，默认/root/.cache/vllm不适宜承载编译缓存 |
| PyTorch Inductor默认 | /public-flash/jinghao/qwen3.8-flash/05-tmp/torchinductor_root | 删除TORCHINDUCTOR_CACHE_DIR后，已安装default_cache_dir跟随tempfile.gettempdir；vLLM自行管理其图编译子目录 |
| HuggingFace默认 | /root/.cache/huggingface | 删除HF_HOME；模型/tokenizer使用批准的本地绝对路径，不下载/复制权重到此目录 |

这些路径来自实际安装代码与预检解析，删除的变量未改为由helper或服务调用者导出。
服务启动及105token固定回归已经通过；完整结果、保留设置理由和哈希见
[启动精简记录](../acceptance/launcher-minimal-20261027.md)。
软件组件/编译二进制和模型输入身份复核仍通过，产品Git HEAD、完整diff和新增文件集合/内容未变。
没有改变镜像、挂载、权重或已冻结的完整评测结果；新镜像验证仍pending。
