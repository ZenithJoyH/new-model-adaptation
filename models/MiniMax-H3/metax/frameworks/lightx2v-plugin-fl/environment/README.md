# HTTP-001 环境记录（2026-11-16）

实际Host为mx-57，容器minimaxH3，CID99cd2bd857e567440a9f73d50752e486b591b7a046e4388490bf7e502e7be3d8，既有init host PID2530337；实际解释器/opt/conda/bin/python。这些是既有已核身份，不是新profile环境阶段通过。启动前须重新核当前进程、8卡占用和端口。

已核安装源：/opt/LightX2V固定归档c58c16d607c49bf6021fecc6238ed177752d7e87（只读）；/opt/lightx2v-plugin-FL固定归档2cf49116b12383122db0d1247b484d24ba4409c3（唯一候选可写产品组件）；/opt/FlagOmni431a7e6fcb9251fd7b44cdcb665839f4771b425f及/opt/FlagGems只读。不是Git checkout，不声称现场HEAD；厂商Torch/FlagTree/MACA/MCCL与293分发保留。权重/public-flash/models/MiniMax-H3只读。

证据root：host/container均/public-flash/jinghao/minimaxH3-dependencies-20261116；用户服务root均/public-flash/jinghao/minimaxH3，两个目录独立且同名RW绑定。framework.yml只登记唯一证据root，不扩大到公共父目录。config为/public-flash/jinghao/minimaxH3/config.json，SHA256 `5121fc6e3841c56d2391905f03f53d0914a32265a7a86ad9affa00ecf76a9c93`。

纯web模块fastapi/uvicorn/pydantic/multipart/httpx实际CPU导入5/5通过，未导入Torch/LightX2V。native任务管理为进程内OrderedDict加锁，无Redis daemon；redis客户端8.1.0与声明6.4.0不一致保留，不为未使用路径降级。容器host网络，HTTP8000/metrics8001。默认runtime cache `/opt/LightX2V/save_results/server_cache`已明确批准，父目录root-owned0775、overlay rw；不增加cache环境变量。

原生服务已保留：container PID/PGID32222、startticks104418197，8个rank32304–32311；两次任务前后PID/startticks相同、每rank初始化1次。设备为8×MetaX MXC550；138份完整8卡采样约2.02–2.43秒间隔，最高约38.6481GiB/card，属于采样物理占用，不能称Torch高水位。293分发及核心源前后保护一致。容器dsh入口缺失，已按native helper回退builtin；旧只读smoke有限成功不等于容器执行能力通过。

原件：远端证据root的04-runs/HTTP-001/result.json及SHA256SUMS（44项，清单SHA `c6a8cb9ed7b7a043c33638fd09983a4e96a563f04a8fddcec74d311dfad848e2`）；环境只读报告/补件保留首次SSH超时及随后成功事实。原ENV/FULL/OPS仅作历史输入，不自动迁移profile阶段passed；Torch allocated/reserved峰值本轮未测。
