# 001：editable Plugin 导入被 namespace package 遮蔽

## 元数据

- 状态：`mitigation-verified`（容器内兼容模式 editable 重装后，无 `PYTHONPATH` 的导入与服务实启均通过）
- 首次出现/最后验证：2026-09-28 / 2026-09-30
- 模型/Host/容器：`MiniCPM-V-4.7-1B` / `H100-149` / `MinicpmV4.7-1B`
- Plugin：`main@3a27a6fb2d514cdf55c00481bf813225dac63319`，修改前干净
- FlagGems：`master@da6727e38f6f8eedef6cba43695a87b4996f9eca`，用户授权同步后干净
- vLLM：wheel `0.24.0+cu129`，只读

## 现象、诊断与受控对照

`pip show vllm-plugin-fl` 报告 editable 位置为 `/vllm-workspace/vllm-plugin-FL`，
但目标容器默认 `python3 -B -c 'import vllm_fl; print(vllm_fl.__file__)'`
输出 `None`；`find_spec` 显示 `/usr/local/lib/python3.12/dist-packages/vllm_fl`
的 namespace package，`register`、`register_model` 均缺失。
vLLM 平台插件加载记录 `AttributeError: module 'vllm_fl' has no attribute 'register'`。
安装目录确有一个缺少 `__init__.py` 的旧 `vllm_fl/`，搜索优先级遮蔽 editable finder。

只改变当前进程 `PYTHONPATH=/vllm-workspace/vllm-plugin-FL` 后，
`vllm_fl.__file__=/vllm-workspace/vllm-plugin-FL/vllm_fl/__init__.py`，
`register_model` 存在，vLLM 报告 Plugin 平台激活并选择 `cuda`。
这是 2026-09-28 导入问题的受控 mitigation；当时根级脚本沿用该变量并成功启动服务，
`/v1/models`、文本和单图请求均通过。证据见
[功能与服务验证](../acceptance/functional-validation.md)。

## 2026-09-30 容器内直接安装

用户要求在容器中安装已适配 Plugin 并复核 `PYTHONPATH`。目标 checkout
`/vllm-workspace/vllm-plugin-FL` 的 HEAD 仍为
`3a27a6fb2d514cdf55c00481bf813225dac63319`；安装前后工作树同为
`vllm_fl/__init__.py` 未提交修改，以及
`vllm_fl/models/minicpmv4_7.py`、`tests/unit_tests/test_minicpmv47_canvas.py`
两个未跟踪文件，没有新增产品源码差异。安装前不设 `PYTHONPATH` 的全新进程仍得到
`vllm_fl.__file__=None`，两个注册入口均缺失；只在该进程末尾加入 checkout
路径后，Python 解析到源码的 `__init__.py`，两个入口均存在。

容器内 setuptools `80.10.2` 的 `editable_mode=compat` 会创建普通路径 `.pth`，
使源码中带 `__init__.py` 的正式包优先于安装目录残留的 namespace 目录。
因此在唯一目标 Host 上执行：

```text
docker exec -w /vllm-workspace/vllm-plugin-FL \
  -e TMPDIR=/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/05-tmp \
  -e XDG_CACHE_HOME=/public/flagos/jinghao/MiniCPMV4.7-1B/flagos/06-cache/xdg \
  -e PYTHONDONTWRITEBYTECODE=1 -e PIP_NO_INDEX=1 MinicpmV4.7-1B \
  python3 -B -m pip install --no-deps --no-build-isolation --no-compile \
  --config-settings editable_mode=compat --force-reinstall -e .
```

Ansible `--check --diff` 只预览目录准备，pip 无 check mode；实际安装成功，
日志在同一 Host/容器工作根 `04-runs/plugin-install-compat-20260930/pip.log`，
SHA-256 `5676018e1fd9b234d602cdc8a41c64583fbd49cd22274be3beddb0e50ee6becf`。
安装元数据仍指向原 checkout 且 `editable=true`，版本为
`0.3.0rc2.post1+g3a27a6fb2.d20260930`；未下载或重装依赖，vLLM wheel 仍为
`0.24.0+cu129`。没有删除安装目录的旧 namespace 文件。

安装后，在工作根内、无 `PYTHONPATH` 的全新 Python 进程中，
`vllm_fl.__file__=/vllm-workspace/vllm-plugin-FL/vllm_fl/__init__.py`，
`register` 和 `register_model` 均可调用；运行中的新 API PID `15252` 的
进程环境也没有 `PYTHONPATH`。根级脚本实启后平台 Plugin 激活、模型身份、
文本与红图请求均通过，详见 [005](005-launcher-minimality.md) 和
[功能报告](../acceptance/functional-validation.md)。这是容器内安装方式的修复；
若重建容器或重新安装 Plugin，应复核 `.pth` 与默认导入路径。

## 解决边界

本次没有修改 vLLM、FlagGems、旧 namespace 目录或 Plugin 产品代码。选择
editable 重装，是为了让已声明的源码 checkout 继续作为运行时唯一 Plugin 实现；
普通非 editable wheel 会把当前未提交适配代码固化在安装快照中。

已有经验仅是导入/打包问题；`docs/troubleshooting/` 现有 TP timeout、full graph 签名均不匹配。
FlagGems 算子故障另见 [003](003-flaggems-cudnn-attention.md)；本 issue 不新增
产品代码，也不推断跨模型兼容性。
