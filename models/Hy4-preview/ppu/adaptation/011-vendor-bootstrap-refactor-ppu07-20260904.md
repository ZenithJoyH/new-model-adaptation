# T-Head 原生扩展初始化职责下沉

2026-09-04，仅修改 `PPU-07` / `hy4` 中
`/workspace/vllm-plugin-FL-hy4-preview` 的初始化代码及新增测试。
插件 HEAD 保持 `11848598449f6d650df64170db4187c387361ce5`，分支
`support-hy4-preview`；保留既有 dirty 工作树，不提交或推送。

## 修改与原因

旧公共入口包含 `_load_thead_native_extensions`、`PPU_SDK` 检测和 T-Head
专属导入，厂商职责泄漏到包根目录。新链路为：

`register()` → `vendor.initialize_native_extensions()` →
`thead.bootstrap.initialize_native_extensions()` →
`thead.impl.native_extensions.load_all_native_extensions()`。

- 公共 `vllm_fl/__init__.py` 删除厂商专属函数，只调用通用早期初始化接口。
- `vendor/__init__.py` 管理轻量初始化钩子表，不判断硬件、不包含 SO 细节，
  不吞掉初始化失败。后续厂商可以增加同类钩子。
- `vendor/thead/bootstrap.py` 内部检测 `PPU_SDK`，只在 PPU 环境调用已有加载器。
- `vendor/thead/__init__.py` 延迟导出 `TheadBackend`，避免非 PPU 初始化导入
  T-Head backend 实现；既有 `from ...thead import TheadBackend` 保持兼容。
- 保持原生加载早于 `_patch_custom_ops()`。不能推迟到 backend 注册或首次算子
  调用，否则原生 SO 与 fallback 的同名 `TORCH_LIBRARY` schema 会冲突。
- 原生 wrapper、SO、算子选择 YAML、模型数学实现均未改变。

## 验证与边界

- 6 项 stdlib 单测通过：公共调用顺序、轻量导入、通用钩子调用/错误传播、
  非 PPU 不导入 loader、PPU 委托与错误传播、延迟导出兼容。
- fresh-process：`NON_PPU_IMPORT_ISOLATION_OK`；在 PPU 主机移除 `PPU_SDK`
  模拟非 PPU 检测分支，未加载 T-Head backend/native loader，loaded libraries
  集合不变。这不是其他厂商真实硬件验收。
- fresh-process：`PPU_EARLY_SCHEMA_AND_IDEMPOTENCY_OK`；真实三库加载、
  重复初始化、fallback 顺序均通过。
- 既有 bundled-native、sparse MLA、MoE dispatch 的数值/eager/graph 三组回归通过。
- `/workspace/vllm` HEAD `ee0da84ab9e04ac7610e28580af62c365e898389` 与
  `/workspace/FlagGems` HEAD `60d043094d0217cad75528cb0e47a606c87ab1e4`
  前后均 clean；本轮不是 FlagGems 算子选型或集成，没有更新依赖。
- 服务 API PID `2084145`、Engine PID `2084625` 及 starttime 前后相同；
  未停止/重启服务或容器。新入口已由独立进程验证，运行中服务未重新加载。
- 未改 PPU-13 `glm5.3-flash`，未更新 20260903 镜像快照。
- 原始三个文件备份：容器内 `/tmp/hy4-vendor-bootstrap-jNsBiUSk/before`。

本轮仅完成用户指定的代码重构，不迁移 workflow 元数据，不做模型服务验收。

## 复现

- 只读基线：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/inspect-ppu07-vendor-bootstrap.yml`
- 部署、测试与失败回滚：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-vendor-bootstrap.yml`
- 测试源码：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/test_vendor_bootstrap.py`，同时部署至插件
  `tests/dispatch/test_vendor_bootstrap.py`
- 标准 unittest discovery：`../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/verify-ppu07-vendor-bootstrap-test-discovery.yml`

## 后续：参考 MetaX 收敛调用位置（2026-09-04）

只读确认 MetaX 在 `ops/_C_ops_registry.py:57–65` 先导入 `mcoplib._C`，
再定义 fallback schema，避免重复注册。本轮参考其顺序，将通用
`initialize_native_extensions()` 从 `register()` 移入 `_patch_custom_ops()` 开头。
T-Head 检测和三库加载仍保留在 vendor 下；不更改 MetaX 路径。
这样直接调用 `_patch_custom_ops()` 也满足先加载原生扩展的约束，而不依赖外层调用者。

执行 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-custom-ops-preload.yml`，仅改插件 `vllm_fl/__init__.py`
和 `tests/dispatch/test_vendor_bootstrap.py`。本地及远端 7 项单元测试通过；
直接 custom-op 初始化、正常 register、重复初始化、错误传播及模拟非 PPU 导入隔离通过。
MLA backend 辅助操作和原生 sparse MLA eager/graph 回归通过，含变更输入后的 replay。
本轮未实测 MetaX 硬件、全模型重启或吞吐。

源码哈希门禁通过，其余插件 Python 源码哈希不变；vLLM/FlagGems 版本和状态不变。
API/Engine PID 及 starttime 仍为 `2084145/114318578`、`2084625/114319949`。
服务和容器未重启，运行中的服务未重新加载本轮源码。未更新镜像、PPU-13 或提交代码。
原文件备份在容器 `/tmp/hy4-custom-ops-preload-eZIkEeII/before-__init__.py`
及同目录 `before-test_vendor_bootstrap.py`。Ansible failed=0、unreachable=0。
测试出现 FlagGems replay benchmarker 不可用、回退 event timing 的警告，但验证通过，
本轮不作性能结论。管理仓库 syntax-check 与本次 playbook syntax-check 通过。

## 最终职责边界：移出顶层文件（2026-09-04）

上一轮只是移动函数内部调用，仍留在顶层文件，没有完全实现用户要求。
现已将整个原生预加载、ABI 探测和 fallback 选择逻辑移至插件
`vllm_fl/ops/bootstrap.py::initialize_custom_ops`；顶层 `__init__.py` 的
`_patch_custom_ops()` 仅保留延迟导入和委托调用，不再含 vendor import、
`initialize_native_extensions`、SO 或 fallback 注册逻辑。
vendor hook 在两种 ABI 的提前返回之前执行，T-Head 细节和 MetaX 原有逻辑不变。

部署为 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-ops-bootstrap.yml`；原文件备份保留在容器
`/tmp/hy4-ops-bootstrap-6nV8ulYr/before-__init__.py` 和
`before-test_vendor_bootstrap.py`。本地与远端 8 项单测通过，包括两种 ABI
早退、缺少扩展的 fallback、错误传播、顶层不得包含原生初始化符号的结构检查。
fresh-process 原生 schema/幂等、模拟非 PPU 隔离、MLA helper 和原生 attention
eager/graph 回归全部通过。其余既有插件 Python 文件哈希不变，vLLM/FlagGems
revision/status 不变，服务 PID/starttime 不变；未重启服务/容器、更新镜像或提交代码。
运行中服务仍未重载源码，不宣称新的全模型验收或性能结果。

## 简化为现有 schema 注册入口（2026-09-04，当前版本）

按用户要求去掉新增 `ops/bootstrap.py` 和 `initialize_custom_ops()` 转发层。
顶层 `_patch_custom_ops()` 直接调用 `ops/_C_ops_registry.py::register_op_schemas()`。
T-Head 的原生预加载并入该现有函数，发生在幂等/ABI 提前返回之前；SO 与平台判断
仍由既有 vendor hook 负责。MetaX 的 `mcoplib._C` 预加载保留在同一注册函数内。
保留两种 vLLM ABI 检查及插件 `_C` 导入行为，随后才定义缺少的 fallback schema。

执行 `../../../../.local/adaptation-history/20260906-workspace-repair/relocated/models/Hy4-preview/ppu/adaptation/deploy-ppu07-schema-preload.yml`：本地/远端 8 项单测、fresh-process
原生加载/幂等、模拟非 PPU 隔离、MLA helper 与原生 attention eager/graph 全部通过。
测试现在检查原生路径没有创建 fallback `_lib`，而不是要求 registry 模块未被导入。
`ops/bootstrap.py` 已从远端源码移出，保留在
`/tmp/hy4-schema-preload-OtAsFCyk/retired-bootstrap.py`，其余原文件同目录备份。
其他既有插件 Python 源码哈希、vLLM/FlagGems revision/status、服务 PID/starttime
均不变；未重启服务或容器，未更新镜像、提交代码或开展全模型验收。
Ansible failed=0、unreachable=0；syntax-check 通过。历史 working 快照仅供历史复现。
