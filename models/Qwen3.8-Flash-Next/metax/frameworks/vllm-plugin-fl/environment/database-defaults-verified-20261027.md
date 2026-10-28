# 2026-10-27 默认本地SQLite实测

本次在mx-101既有qwen3.8-flash容器中移除FLAGGEMS_DB_URL，接续
[运行缓存默认路径实测](cache-defaults-verified-20261027.md)。原内存设置用于规避NFS数据库反射/查询停顿，
不是模型数学计算要求；如今默认路径为容器本地目录，故按用户要求重新启动并对照验证。

| 实际安装库 | 默认数据库 | journal模式 | 表数 / 行数 |
| --- | --- | --- | --- |
| flag_gems | /root/.flaggems/config_cache/TunedConfig_metax_triton_3_6.db | wal | 20 / 2390 |
| flaggems_vllm | /root/.flagdnn/config_cache/TunedConfig_metax_triton_3_6.db | delete | 0 / 0 |

路径由实际安装的utils/code_cache.py和libentry.py决定；注意FlagGems-vllm使用.flagdnn，
与FlagGems的.flaggems分开。默认数据库文件名由当前metax与Triton3.6生成。
这些路径是UID0可写的容器根文件系统普通目录，不是/public-flash的NFS bind、软链接或新挂载。
切换前的文件状态保存在控制目录default-databases-before.json，现有文件/调优记录未被删除或重置。

实际模型服务组检出32条TunedConfig数据库文件描述符，
包含/root/.flagdnn默认库；独立进程加载实际已安装模块确认DB URL，另以mode=ro SQLite连接读取表，
quick_check均为ok。FlagGems的2390条调优记录已独立读取；FlagGems-vllm在本组请求中
打开默认库但尚未产生调优表/记录，未将空库检查当作持久化调优条目写入证明。没有用环境变量、helper、HOME/XDG改写或PYTHONPATH间接恢复旧路径。
服务启动和24请求数值/延迟回归通过；错误日志未见SQLite锁冲突或引擎异常。
完成时root f_bfree=21479460864 bytes，f_bavail=0；
仍依赖本容器UID0实际可写保留空间，不能推广为其他用户/新镜像的容量保证。

当前仅保留VLLM_FL_FLAGOS_BLACKLIST_APPEND=clone,randn,normal_及VLLM_FL_USE_FLAGGEMS_VLLM=1。
必要性沿用原定向回归；数据库覆盖不再保留。其他缓存继续使用已核实默认目录。
完整对照计划、原生结果、数据库证据与哈希见[本次启动记录](../acceptance/launcher-default-db-20261027.md)。
高并发正式性能和GPQA全量未重跑；镜像打包/新容器验证pending。
