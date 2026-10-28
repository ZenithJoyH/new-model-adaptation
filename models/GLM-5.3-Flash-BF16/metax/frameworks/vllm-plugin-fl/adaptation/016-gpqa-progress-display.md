# GPQA中间计分显示（2026-10-28）

正式运行glm-gpqa-final-v14-20261028已发出198题、4并发，原生主进程正常运行。
随附score_progress.py报IndexError，不能据此显示中间分数；该助手是独立sidecar，
主评测退出码不由sidecar决定。原始错误保留在client-run/stdout.log。

当前正式配置使用v2 `datasets`描述符，而loader同时填入空的旧dataset_path/name默认值；
冻结的显示助手只读取旧字段，导致它没有使用已经验证的GPQA Diamond缓存描述符。
不修改正在运行的runner、助手、冻结配置、journal或模型源码，也不重启评测。

拟以批准根02-issues内的一次性只读监视器，将同一冻结描述符映射为助手的内存输入，
先核实全部198个真实task prompt/target和缓存key映射一致，再读取实际SQLite响应缓存。
无法解码、未匹配或重复doc必须仍显示unavailable，不以缓存行数冒充得分；所有中间数值
仅用于进度观察，正式结论仍来自全量198样本的原生acceptance-result.json及gate。
进度快照保存在该运行的observations，不改变实际评测输入或已冻结工具bundle。

首个监视器拒绝目标表示差异并保留unavailable：原生目标是`(D)`、助手是`D`，前3条
真实cache key均已存在。第二版只允许原生`(A)`～`(D)`四种精确格式并提取对应字母，
随后仍逐条验证全部198个真实prompt/target、生成kwargs的数值类型/键顺序及源文件哈希；
不删除数值/coverage断言，不把未匹配cache计入正确率。首次只读缓存查询已有10条响应，
主评测持续运行，未重启或重试。

第二版随后实际核对198条prompt/target及原生kwargs/源码哈希通过；首个有效快照有10条
唯一匹配响应，unmatched/key_misses/解码失败/重复doc均为0、timeout为0。
`observe-gpqa-v14`据此记录原生journal完成数，并保存确切客户端进程身份。
主评测、冻结工具bundle与配置未改变；此监视不是正式精度回执。
