# M10 功能审计

状态栏的“已实现”表示已存在可调用实现；最终运行结果以 M10 验收记录为准。原 M1–M9 验收证据和模型报告保留。

| 功能 | 状态 / 演示入口 | 数据来源 | 对应验证 | 已知边界 |
|---|---|---|---|---|
| 六大页面与共享 Header | 已实现：六条原路由、时钟、后端、实时与事故状态 | Router、health、WebSocket | final-demo、三分辨率布局、导航循环 | 桌面比赛适配；不做移动 App |
| 统一 Design System | 已实现：`style.css` tokens、共享深色卡片、风险色、字体与局部状态 | 展示配置 | build、截图人工检查 | 旧业务布局增量调整，未重写核心 |
| Dashboard 实时态势 | 已实现：运行平稳/需要关注/事故演化、真实设备管段统计、当前告警 | 实时设备/管段数组、当前事故、模型、数据库档案 | realtime、operation、flood、risk、leak、final-demo | 离散运行态不包装为综合风险分 |
| 首页快捷演示 | 已实现：暴雨、泄漏、事件复盘 | Demo API / 原事故引擎 / Incident API | final-demo | 场景冲突保留；方案需人工选择 |
| 三维地上/地下/风险 | 已实现：DigitalTwinScene 原实例增量优化 | 静态资产 + 当前状态 | web3d、pipeline、final quality | 原静态建筑风险仍标明示例 |
| 三档画质与全屏 | 已实现：high/medium/low；Fullscreen API | 当前浏览器与渲染器配置 | quality 脚本、final 布局/资源测试 | 低档保留事故核心；不静默自动降级 |
| 实时连接与恢复 | 已实现：单 WebSocket、1 Hz、断线状态、保留上次值与重连 | 后端统一实时引擎 | realtime、最终导航循环、后端重启检查 | 断线期间不伪造新观测 |
| 设备运维 | 已实现：`/operation`，默认 P03 | Device资产、模拟遥测、规则 HI、Isolation Forest | operation、operation-state、pytest | 模型缺失保留规则与 unavailable；不自动维修 |
| 管网资产与追踪 | 已实现：`/pipeline` 正常模式、2D/3D 联动 | DB节点边阀门、Graph Search、实时管段 | pipeline、pytest | 简化示范图，非真实 GIS/精确水力网络 |
| 泄漏检测与定位 | 已实现：`/pipeline?mode=leak` | 压力/流量/不平衡观测、拓扑一致性 | leak、leak-state、final-demo | Top3 为异常匹配，非校准概率 |
| 阀门隔离比较与执行 | 已实现：候选→预览→人工确认 | 当前拓扑、真实比较记录、阀门API | leak、pipeline、incident-lifecycle | 过期拒绝；隔离受控不代表恢复供水 |
| 内涝事故演化 | 已实现：`/simulation` 或一键暴雨 | Weather、设备退化、体积守恒、场景规则 | flood、flood-state、pytest | 原持续暴雨与正式雨势回落演示分开，不能承诺泵必能排空 |
| 风险预测 | 已实现：`/risk` 当前规则与 10/20/30 分钟未来 | 物理副本前推 + 原六个 XGBoost | risk、pytest、final-demo | ML只学习仿真分布，泄漏不适用 |
| 模型解释与误差 | 已实现：主要因素、模型详情、已到期真实误差 | TreeSHAP/标识降级、metadata、Prediction记录 | risk、incident-lifecycle、review | 解释非因果、一致度非置信概率 |
| 应急反事实推演 | 已实现：`/simulation` 第三阶段 | 同基线四个物理副本、已有模板和资源 | emergency、pytest、final-demo | 不自动选赢家；指数非费用；环境贡献单独说明 |
| 方案执行与启动过渡 | 已实现：选择→确认→恢复时钟→动作 | 原设备引擎、Pending步骤、数据库执行记录 | emergency、incident-lifecycle | 暂停时不偷偷施加动作；取消不撤销已生效结果 |
| Incident 与工单 | 已实现：`/review` | Incident索引、Timeline、WorkOrder | incident-lifecycle、pytest | 班组字符串，无复杂身份权限或真实调度 |
| 事件关闭 | 已实现：稳定态人工确认关闭 | DB终态 + 当前活动引用协调 | incident-lifecycle、pytest、final-demo | 冻结事故，保留物理影响；Reset/重启中断是 ABORTED |
| 历史回放 | 已实现：选择档案、播放/暂停/速度/拖动/节点 | 数据库历史帧、独立Replay Store | review、review-state、review-legacy | 上限2000真实点、缺口提示，旧缺失不可恢复 |
| 模板复盘报告 | 已实现：`/review` 生成/读取 | 已保存指标、真实记录、固定模板 | review、incident-lifecycle | 不调用 LLM，不导出 PDF |
| System Readiness / 自检 | 已实现：状态抽屉、自检按钮 | read-only readiness、客户端Socket和Three上下文 | backend pytest、final-demo、API benchmark | 部分模型不可用允许降级，不把服务端推送就绪等同客户端已连接 |
| 正式 Demo Mode | 已实现：`?demo=1` / Header开关、阶段引导、演示控制 | 原实时业务状态与独立Demo接口 | final-demo | 不自动替用户执行方案；不会启动时生成事故 |
| DEV / Demo 分离 | 已实现：开发面板仅显式 `VITE_ENABLE_DEV_CONTROLS=true` | 构建配置 | 构建、默认正式页面检查；旧测试使用显式开发配置 | 隐藏 UI 不是后端授权；后端仍独立检查模式 |
| Demo Reset | 已实现：明确确认，恢复天气/设备/阀门/入口 | DemoService协调现有引擎与数据库 | backend pytest、final-demo | 保留全部历史，未关闭活动事件标中断，不和Close混用 |
| 图表局部故障恢复 | 已实现：四类图表共用主题和单实例管理 | 现有 ECharts options | build、六页只读布局、全回归 | 图表失败只显示局部重试；正常状态仍 setOption，不每秒重建 |
| 全局错误 / Three恢复 | 已实现：ErrorBoundary、场景初始化/上下文状态 | Vue边界、WebGL事件 | web3d、final恢复检查 | 失败不使其他指标白屏，恢复结果以实际运行记录为准 |
| 启动、准备与数据库脚本 | 已实现文件入口见 README | 本地服务、迁移、seed、保存模型 | 准备/启动验收、Alembic check | 无 CDN依赖；需要本地已安装运行依赖；restore须确认 |
| 历史证据与比赛文档 | 已实现整理：README、演示脚本、技术/数据/功能审计、final截图 | 源码、真实运行日志与历史报告 | 文档链接与目录审计 | 不覆盖M1–M9证据、不虚报独显性能 |

## 已发现并处理的展示问题

1. 首页“回放尚未接入 / M9”占位已移除，替换为实际档案与有效入口。
2. 首页设备在线统计改用实际设备数组，未继续展示旧系统汇总默认值。
3. 首页水位图从固定 3 cm 上限改成按实际观测扩展，防止截断事故曲线。
4. 风险页算法身份保留在模型详情，主视图减少重复术语；旧里程碑字样移出比赛 UI。
5. 正式启动入口统一走 Demo 控制，旧开发启动/重置由显式环境配置保留给回归脚本。
6. 首轮只读布局实测发现共享图表 helper 给纯拓扑多加了 grid；已移除该默认项，避免 ECharts 缺组件警告。最终复验结果单独保存，未把首轮失败隐藏为成功。

## 验证追溯

完整测试矩阵包括 M1–M9 的全部既有浏览器/状态脚本、backend pytest、production build、Alembic check 和 `test:final-demo`。本审计不预先填写通过数；运行耗时、失败与修复、性能和最终截图以 `docs/M10-verification.md`、`docs/final/` 为准。
