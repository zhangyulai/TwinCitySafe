# M7 应急推演架构

## 数据流

`Emergency API → 模板与可用性校验 → 同一 SimulationCopy → Baseline / A / B / C 独立副本 → 物理 rollout → PostgreSQL 比较快照 → 用户确认 → 执行引擎 → 既有 DeviceSimulator / FloodService → 1 Hz 实时状态与 EMERGENCY_EVENT → Pinia / Three / ECharts / M6`。

比较在线程池计算，复制仅包含模型状态，不复制引擎任务、数据库或 socket。场景时钟只由原 SimulationEngine 推进。每个副本使用同一降雨计划、故障年龄、启动过渡与原水位历史，互不继承候选结果。预览 API 也只运行副本。

## 模板与动作

数据库保存 FLOOD-A（P01，delay 0）、FLOOD-B（P01 delay 0 + P02 delay 10s）、FLOOD-C（双泵 + B2-EAST CLOSE_ENTRANCE delay 20s）。启动幂等补齐缺失模板，既有模板不覆盖。UI 不定义动作。

统一模型包含 action_type、target_id、parameters、delay_seconds、duration_seconds、priority。M7 执行适配器支持 START_PUMP / STOP_PUMP / SET_PUMP_STATE、CLOSE_ENTRANCE / OPEN_ENTRANCE、REDUCE_OCCUPANCY。duration_seconds 表示动作开始后的最短完成等待时间，不表示自动撤销。相同目标重复动作一律拒绝，避免含糊的冲突时序。OPEN_ENTRANCE 停止后续人数递减，不凭空恢复人员。REDUCE_OCCUPANCY 使用 people_count 目标，沿相同 300 秒常数渐近。

CLOSE_VALVE / OPEN_VALVE 被模型识别，但验证器明确拒绝，因为 M5 未实现逐段排水拓扑水力耦合。没有伪造阀门对水位的效果，M4 原控制保留。

匹配检查活动内涝、风险阶段、设备存在/故障/离线、额定值、入口、动作冲突和参数。正式模式风险至少 60；DEV 可提前测试。执行中禁止另起比较/执行，已完成后允许再次比较。

## 共用物理扩展

泵能力 = 运行泵资产额定排量 × 当前效率 × startup_progress。startup_progress 复用 M3 settling 60 仿真秒，0→1；HI 不重复扣减。既有默认运行 P03 的进度为 1，所以原未启备用泵的 M5 轨迹保持不变。

CLOSE_ENTRANCE 通过 FloodService 改封控状态，vehicle_entry_rate=0（原 M5 为固定车辆存量，本来就没有新增车辆模块），现有车辆保留。人员暴露保持连续浮点剩余量，再向上取整作为人数，时间常数 300 秒；关闭当刻水量与人数不变。积水始终由原体积守恒计算。

原强雨/极端雨/正常雨曲线不变。显式 M7 演示 duration 60min、极端雨至 30min、30–35min 回落至20mm/h。所有方案共用它。持续100mm/h入流1020m³/h大于三台120m³/h泵，因此不声称措施单独能排空。C 与 B 的水位和面积相同，C 风险因人员暴露降低而减少。

## 指标

每个方案 31 个分钟点；内部 5 秒步长。当前状态作为 0 点，在应用动作之前记录。峰值为本次未来窗口含起点，非全事故历史峰值。响应时间在内部5秒采样上寻找首次严格低于60/40；起点低于即0，未达null。资源指数按 P01/P02 活跃时间积分（含启动）每分钟各1，新封控一次10。已运行备用泵在 Baseline 中也计算成本。相对 Baseline 的降低量可为负，不强制裁剪为改善。

## 执行、并发与持久化

比较最多缓存30次；每次数据库保存基线 SHA256、场景/会话、仿真时间、模板快照、31点曲线和指标，不保存巨大逐秒模型。SHA256 审计载荷包括实时状态、指令、故障年龄、settling、额定能力、原水位窗口和降雨计划。阈值化 stale 与完整 hash 分工：暂停心跳 revision 不使结果立即过期。

执行需 comparison_id + confirmed_simulation，检查模板和资源，先保存 pending 意图，再在存储 await 后重新检查当前状态；通过后挂到原引擎，下一 tick 施加。泵动作调用 DeviceSimulator.set_state，入口调用 FloodService。每个子步检查计划延迟和过渡是否完成，日志只在转换时追加。动作 completed 与风险 STABILIZING 分开；STABILIZING 要求风险相对执行时下降超过1且60秒回归增长率≤0。告警依旧由 FloodRiskService 计算，不关闭事件。

取消仅取消 pending；已施加步骤标记完成但注明不撤销，设备过渡及暴露演化继续。中途故障会失败并取消未施加步骤。Reset/场景替换取消未完成动作，保留历史；服务重启标失败且不自动重放。日志后台每秒持久化最新状态，有界待写队列达到100时拒绝新执行；不保证断库期间全部中间写入。

四张 SQLAlchemy 表通过 Alembic revision adab6941d89a 创建，继承 b655e1756d27。模型数据存JSON同时独立存execution steps，execution外键引用comparison、steps引用execution。operator 固定 demo-user，无正式权限系统。

## 实时与界面

复用原 socket，事件与最新状态共享有界64消息队列；普通实时状态合并为最新，事件保留有界窗口，慢客户端仍按原超时关闭。事件是提示，完整状态包含日志，可用于断线恢复。

useEmergencyStore 管理 plans/comparison/selectedPlan/execution/baseline/loading/error 和最多100条事件，不复制 Flood 状态。场景/会话变化清缓存，异步请求以 generation 防止旧响应覆盖。比对两张独立单位图表，每图 Baseline+A/B/C 四系列。没有自动Winner。方案卡切换复用单个 OutlinePass；入口闸门常驻并透明预热。三维状态、水面、雨、热区、设备对象继续复用。

M6 历史模型元数据仍标识 m6-simulator-v1；后续重新生成数据使用 m7-simulator-v2-startup，避免把新启动水力语义误认作原生成器。M6 仍读取30维当前特征；新执行ID、入口状态和启动进度参与缓存失效。物理预测共享 SimulationCopy，包含待执行动作；ML 没有动作干预编码，不用于方案排名，新工况需看实际差异。Dashboard/Risk 各显示一行当前应急。M7不实施M8泄漏与M9事件关闭/复盘。
