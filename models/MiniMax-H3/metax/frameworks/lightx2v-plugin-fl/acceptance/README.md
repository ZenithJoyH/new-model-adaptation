# HTTP-001 HTTP功能已验证，profile接受未完成

2026-11-16同一常驻服务完成两次显式t2av任务，544高×960宽/124帧/29步、seed42、TP4×SP2/textTP8、BF16mixed、全resident。HTTP8000/metrics8001，queue1包含pending与processing。canonical launcher/config绑定见环境与适配记录。服务PID32222/startticks104418197与8rank身份前后相同，load_once每rank1，验证后保持running。

任务MN7Y-02NM-ZWP5-EIUY-MJ73、T6K7-WWGB-O1XJ-LDP7-ME1K均completed，服务报告61.23/52.61秒，非受控benchmark。unknown字段422、忙时503、结果下载通过，结束queue active/pending均0。两份媒体均124帧960×544/24fps、32kHz stereo/165600samples，解码非零非恒定；MP4 SHA分别 `6980745acdfb1ccb73aad58fda796ee48b8547c87886ee121a3d2c09f1ce5d7f`、`6e02136470ad010ec0e0e34ffdf1e6e2d77fd02398f08a77c415d62b8e485a75`。

主Agent实际审阅request1帧0/62/123及request2帧62：白桌面/背景杯子清楚，中帧红球居中，末帧向右出画，无旧64色块；支持可辨识场景与位置移动。未听审音频，不声明严格画质或高精度数值。旧64失败、SP数值差异与离线FULL证据边界保留。

**profile functional仍incomplete**：未观测原始生成tensor健康、逐rank Torch allocated/reserved高水位、当前HTTP的逐step Flash/RMS native及cache launch/device时窗、每请求runtime Policy退出恢复。mcTracer一次在docker-it的TTY前失败，未exec/attach；未重试、未增加第三次生成。不能用旧FULL native计数补本HTTP缺口，也不伪造framework_check或phase passed。正式accuracy/performance、image包装/发布/新容器部署均未验。

远端证据root `/public-flash/jinghao/minimaxH3-dependencies-20261116`：04-runs/HTTP-001/result.json（SHA `faa5ad798bf50a955e0a291bcf4bb3f1cc048ec74f2c161481dec8c78e1c2814`）、44项SHA256SUMS（SHA `c6a8cb9ed7b7a043c33638fd09983a4e96a563f04a8fddcec74d311dfad848e2`）、03-acceptance/HTTP-001/summary.md。138份完整物理采样最高约38.6481GiB/card，非瞬时精确峰值/非Torchpeak；293分发/core保护一致。仅HTTP功能观察passed，profile functional/evidence/summary和正式接受不通过。[英文交付草稿](deployment-guide.md)为documentation-only，不代表已发布镜像。

元数据限制：既有audit要求任何阶段in_progress同时有已核实部署指纹；本轮没有产生原生profile部署指纹/phase回执，因此framework.yml保持原合法not_started状态，用blocker/note与本记录表达实际HTTP功能已通过、适配/接受仍在进行。不得把readySHA或手写check当成部署指纹。首次audit该项error保留，未修改通用工具绕过。

主Agent末次只读核实：2026-11-16 20:45 CST，/health正常、queue为0，同CID/init保持，host torchrun2968830及八rank2968935–2968942继续运行。该时点核实不表示后续永久可用或重启恢复。
