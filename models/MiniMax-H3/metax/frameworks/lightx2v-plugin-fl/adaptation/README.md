# HTTP-001 显式服务接入（进行中）

仅实际安装Plugin新增server/__init__.py、server/minimax_h3.py、tests/test_h3_server.py，并向既有docs/minimax-h3.md追加服务末节。专用入口先导入原H3 runner完成注册，再通过公开RUNNER_REGISTER选择H3ServerRunner；幂等选择和外来owner保护齐备，原CLI及Plugin普通导入不自动选择服务runner。生产entry SHA256 `794039db537d60f58bc3e62f98fd4b583eb743651e4276c96361b6d160bd9a75`。

子类run_request在每rank的实际调用线程进入真实H3OperatorPolicy，再调用原super一次；不修改只读LightX2V、原Policy或全局ATen注册，不启可选fusion/graph/compile。原nativeHTTP的rank0 processing thread和其他rank worker走同一方法。源码/CPU作用域证据不能代替本轮运行时每请求恢复/真实native缓存命中观测。

CPU-v1真实框架import触发CUDA初始化断言失败，保留失败。v2用host doubles隔离框架import、真实Policy测试5项通过，但fixture模块/parent属性污染需修；v3原生CPU回执为5 passed（0.03秒）、pytest RC0，CUDA初始化前后均false；fixture finally精确恢复或删除sys.modules entry和parent.minimax_h3的原存在性/对象，含setup断言失败路径及恢复身份assert。实际test SHA256 `dd6c5eb01f8a92b28a2db0b84fbb84c4075ff5b5cad0ad9aa9068c1a180e3387`；原件为证据root02-issues/HTTP001/cpu-tests-v3.txt/json，生产entry7940未变、HTTP未重跑。host doubles不是实际8rank或GPU证明。原安装文档backup失败及HTTP001/HTTP-001控制根拼写差异保留；后续追加与原生收据由主接受，不重放部分成功playbook。

canonical `/public-flash/jinghao/minimaxH3-dependencies-20261116/start-model.sh`为8行最小容器内入口，SHA256 `1b3e37ea9247cb10a5ecb5686b80f8c27e519ceae59649a97ea0c59be0b12aea`；用户目录start-model.sh为同文件symlink。保留原run.sh离线CLI。必要PLATFORM=flagos、DTYPE=BF16、DISABLE_FLAGCX、8rank、原config/TP4SP2/text8、queue1和8000/8001；没有docker、诊断、安装、cache override或监控。运行原件位于证据root01-environment/HTTP-001、04-runs/HTTP-001，产品源diff/CPU记录沿原02-issues/HTTP001原件路径引用，不迁移或覆盖失败。
