# MiniMax-H3 / MetaX / LightX2V Plugin-FL

2026-11-17接续目标改为mx-104；57已按用户要求暂停，当前没有本任务HTTP服务在57运行。104容器/环境尚未验证，详见[HTTP取证与主机交接](adaptation/002-http-operators-and-host-handoff.md)。下述57结果保留为历史范围，不代表104通过。

本工作区使用experimental profile、evidence contract v2/hash v3、control.mode=agent。2026-11-16已在57原容器保留常驻HTTP服务，两次默认形状任务及队列/下载功能通过；profile的native观测/原tensor/Torch高水位缺口仍在，适配/接受进行中，不能标正式阶段passed或optimized。

目标仅mx-57的minimaxH3容器。可写产品组件只限已核实安装的Plugin，具体文件/符号还须独立有界派发；基架/算子库/厂商栈/权重只读。远端证据工作根是/public-flash/jinghao/minimaxH3-dependencies-20261116。用户服务目录/public-flash/jinghao/minimaxH3为另一个已授权实际路径，不伪装evaluator_root；原离线run.sh/config保持不动。

详见[环境](environment/README.md)、[适配](adaptation/README.md)、[接受范围](acceptance/README.md)与[英文交付草稿](acceptance/deployment-guide.md)。HTTP本机8000、metrics8001；当前服务已运行，不重复执行launcher。旧FULL/OPS只作历史基线；正式accuracy/performance adapter尚无，镜像未包装/发布，新容器部署未验。
