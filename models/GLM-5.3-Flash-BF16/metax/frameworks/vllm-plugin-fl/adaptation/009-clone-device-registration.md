# 009：FlagGems clone 的 Autograd 注册越过设备边界

2026-10-27，状态：局部修复及两机回归通过，整模重试中。

`glm-eager-bringup-v2-20261027` 已完成真实权重、profiling、cache分配和API预热；
框架报告50K上下文缓存容量18.77x。首次completions请求在PP0 embedding预处理失败：
`get_masked_input_and_mask → torch.compile → preserve_rng_state → torch.clone(CPU RNG)`，
进入FlagGems GPU clone后报 `Expected a cuda device, but got: cpu`。因此不能认定eager推理通过。

核对实际 `/opt/FlagGems@3eab0949`（修改前干净），`_FULL_CONFIG` 的clone额外注册写成
`(AUTOGRAD_DISPATCH_KEY, fallthrough_kernel)`，但registrar把外层每个元素分别解释为key
或二元组；实际先将GPU clone安装到全局Autograd，再对函数对象key注册失败。需要一层
嵌套表示key/implementation pair；同时不能把fallthrough放到全局Autograd，以免覆盖CPU
原有反向传播。应只对当前设备的 `Autograd<backend dispatch key>` 安装fallthrough，GPU
clone继续使用原有自定义autograd节点，CPU保留原生实现。

| 组件与文件/符号 | 变更边界 | 验证 |
|---|---|---|
| FlagGems `src/flag_gems/__init__.py:_FULL_CONFIG` clone项 | 仅修正额外key/implementation pair的嵌套及设备key；不改公共registrar、clone数学实现或其他算子注册 | CPU RNG clone负对照、CPU/GPU clone梯度、现有clone测试与两次变输入graph |
| FlagGems `tests/test_clone_registration.py`（新） | 加入注册行为回归，直接使用真实use_gems和torch dispatch | CPU值/非alias/梯度；GPU值/梯度及capture/replay，不mock计算 |

已读FlagGems CONTRIBUTING及当前注册器/clone实现；其链接的 `docs/contribution.md` 在实际
安装树不存在，未据此虚构额外要求。现有 `tests/test_clone.py` 保留。其他平台没有实际硬件，
设备key契约需静态核对并明确限制。新问题不通过禁用全部compile、屏蔽错误或改vLLM规避。
修改先在102验证，再同步101；实际源码变化后重新冻结部署身份和受影响阶段证据。

负对照 `clone-registration-baseline-20261027/mx-102` 两项CPU测试均复现设备错误，且捕获
`Skipped registering operator: can only concatenate str (not "function") to str`，与tuple解析相符。
修复仅改clone项为嵌套的设备专属Autograd/fallthrough pair；没有新增Torch计算回退。
`clone-registration-fixed-20261027/<host>` 两机各31项通过，包含9项新注册测试和22项现有
布局/非连续/梯度回归；两种dtype图均capture后用两个不同输入回放。FlagGems源文件哈希从
`79445521594e88eb42f2b83e73048cd85c8419d2afe3cb6e3c92ca60b53d3fb4` 变为
`6020d37838f2058a6064c6f531b3cd509133f30c3cdf9389be378d3a1e964f02`。
其他设备硬件未验证，修改只保留当前设备key，CPU原有梯度由真实测试覆盖。

失败请求、服务日志及停止记录保留原路径。102 headless正常终止（rc0只表示退出），101
worker已退出但API在SIGTERM宽限期后仍挂起；核对启动ticks、命令hash及所有GPU worker已退
后，仅强制结束该任务API PID，并取消等待中的任务HTTP探针。两个适配容器均保持运行。

下一轮 `glm-eager-bringup-v3-20261027` 将上下文提高到65536、max_num_seqs设8，保留TP8/PP2、
BF16、2048批token及prefix cache。提高上限是为后续60K reasoning生成预算留出prompt空间；
50K实测缓存容量约938592 tokens为8路提供初步依据，仍须真实请求验证。显式align保持未来
性能cache切换时的基础Mamba协议一致，glm45 parser用于正常reasoning/content分离。
