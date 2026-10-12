# 推理环境分析

以下为启动诊断的已核实身份，不声明正式 environment phase 通过。

- Host `mx-59`；容器 `deepseek`，状态 running；镜像 `harbor.baai.ac.cn/flagrelease-public/metax-vllm-0.24.0-pluginfl-tree3.6:xingchen4-0907`；MetaX C550 ×8。
- 用户批准工作根 `/public-flash/jinghao/deepseekV4`，容器内同路径；2026-09-21 再次 docker inspect 确认 `/public-flash:/public-flash` bind mount。没有修改挂载或重启容器。
- 权重只读路径 `/public-flash/models/DeepSeek-V4-Flash-Quant-W-INT8-PerChannel-A-INT8-PerToken`；config architecture `DeepseekV4ForCausalLM`，SHA-256 `50807d6ad0bb7f21bd203f6c6e9b7fffc865d2b9a82e9e60042f4e61f249a966`。
- 可写 editable Plugin `/workspace/vllm-plugin-FL`；分支 `pr-427-metax-validation`，base `fd5c727fcdb607bc4354cd11384761bb5d5ecfba`；PR 427 ref `da62cddeb538f3d9d203e4e07cbc164e94f76869`。35 个 staged 文件、未提交；继承的 `metax.yaml` linear 黑名单未改。本轮 sparse MLA 两文件候选差异仍 unstaged。
- vLLM `/workspace/vllm`：`ee0da84ab9e04ac7610e28580af62c365e898389`，工作树干净、只读。
- FlagGems `/workspace/FlagGems`：`711cf839c4ee5557776c626e1f8b20cc4007fa63`；FlagGems-vllm `/workspace/FlagGems-vllm`：`c0ffa628e945dc6b51af466d4f1a9b81df9ac4b8`，本轮开始时工作树干净。用户随后明确授权调整 sparse MLA，当前该算子及聚焦测试属于本轮可写例外；不授权其他依赖或算子变更，见 [006](../adaptation/006-metax-sparse-mla-config.md)。

所有相对运行路径均相对于工作根：

- 最近整模运行 `04-runs/pr427-eager-tp8-20260921-19-qnorm-abi/`，包含 `start.sh`、`identity.txt`、`service.log`。启动器 SHA-256 `5c2d7ded03d31087f1481e1da74c4c5a10de34948ea768b4fc7d9c89def02b12`；该轮 staged diff SHA-256 `cfdc1e623d947539975bb98b73cff6e167a799d3a279b14ca8c15993da2d6172`。
- TP8、EP、eager；max model len 50000、batch tokens 1024、seqs 1、FP8 KV、block 256、memory utilization 0.90；prefix caching 未禁用；`VLLM_FL_FLAGOS_BLACKLIST_APPEND=bmm,mm`。OpenAI API 8000，名称 `deepseek-v4-flash-int8`；该轮初始化失败，未进行真实请求。
- 复现 `07-bugs/sparse-mla-adapter/reproduce.py`：使用容器 `/opt/conda/bin/python`，cwd 同 reproducer 目录；`GEMS_VENDOR=metax`、`VLLM_FL_PLATFORM=metax`，缓存均在 `06-cache`、TMPDIR 在 `05-tmp`。结果 `04-runs/pr427-sparse-mla-device-20260921/output.txt`（rc=1，共享内存超限）。
- 单测 `04-runs/pr427-related-unit-after-sparse-mla-20260921/{junit.xml,pytest-output.txt}`：51 passed、3 skipped。不是 eager/graph 或数值验收凭据。
