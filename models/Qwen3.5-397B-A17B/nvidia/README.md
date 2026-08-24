# NVIDIA adaptation

- Targets: `H20-141`, `H100-205`
- Hardware query: `nvidia-smi`
- Current state: hardware, Python and ModelScope detected; inference engine not selected.

下一步：选择推理引擎与代码 revision，确认权重路径，建立基线启动命令和最小
推理用例。后续将 `prepare.sh`、`serve.sh`、`smoke-test.sh`、`benchmark.sh`、
配置、补丁和结果摘要保存在本目录。
