# Milestone 8 完成报告

## 1. 已完成内容

第二个完整事故场景已完成：正常观测 → 渐进泄漏 → 多变量检测 → Top 3 定位 → 拓扑影响 → 隔离比较/预览 → 人工确认 → 阀门关闭 → 泄漏受控与停水保留。入口 `/pipeline` 的“泄漏事故模式”。停止在 M8。

## 2. Pipeline Leak Scenario 架构

`PIPELINE_LEAK_DEMO / WATER_SUPPLY_LEAK` 复用 M2 引擎、M4 Graph/资产/阀门/隔离算法、M1 Three 场景及单实时连接。默认 WS-003、严重度 .75 集中配置。Flood/Leak 双向互斥，暂停事故也需 Reset 后才能换场景。详见 [架构](M8-architecture.md)。

## 3. Leak Simulator

30 仿真秒正常期、180 秒渐进严重度。供水连通时采用 `Q=60×severity×sqrt(P)` 的演示标定；压力、流量和入出口观测复用 16 秒松弛。上游/下游由 M4 图确定，无前端写死异常动画。

## 4. Detection Model

压力偏离、流量偏离、压力下降速率、流量变化速率和入出口不平衡五因素。范围 0–1，阈值 .35/.55/.75 集中配置。UI 明确异常匹配度，非真实概率；未使用 M3 设备 Isolation Forest。

## 5. Localization Service

纯观测与拓扑评分，不读取注入目标/严重度。对 WS-003、WS-004、WS-001、WS-007 四个不同注入点测试，目标均排名第一。改写演示真值不改变定位输出。该证据只覆盖示范模型。

## 6. Suspected Segment Ranking

真实浏览器 WS-003 / WS-008 / WS-009 匹配度约 83.42% / 22.94% / 22.94%。Top 3 红/橙/黄，点击聚焦。启动只看给水网络区域，确认后才自动聚焦排名第一。隔离后保留最近位置证据，当前异常强度单独显示。

## 7. Leak Risk

泄漏流量、压力损失、影响建筑、服务损失、增长项的 0–100 规则分解。此次隔离前 **61.988**，最终 **6.000**。隔离初期服务损失增加可短时升至 63.57，随后随残余泄漏衰减；执行函数没有写死风险值。

## 8. Affected Buildings

调用 M4 `get_affected_buildings()`，WS-003 为科研楼 B、实验楼 C。影响节点/管段和实际停水建筑分别记录；关闭 V-W-03 后两栋持续停水，服务损失指数 .4，不把受控误写为全部恢复。

## 9. Three.js Leak Effect

120 粒子固定池、喷射、脉冲环、首位管段脉冲与影响建筑琥珀着色。强度由估算泄漏流量驱动，隔离后渐退。复用 PipelineManager/BuildingManager，按页释放资源。

## 10. 2D / 3D 联动

疑似颜色、选择、预览阀门及隔离管段同步；实际关闭后阀门与隔离管段灰显。原 M4 正常模式及上下游追踪仍可用。1440 布局无横向溢出。

## 11. Isolation Options

直接使用 M4 候选：V-W-03 / V-W-02 / V-W-01，影响 2/4/5 栋、长度 86.92/185.51/224.39 m、服务损失 .4/.8/1.0。只展示差异，没有自动 Winner。

## 12. Isolation Preview

预览关闭阀门、隔离管段和影响建筑，不改变压力、流量或阀门。真实暂停状态下 compare/preview 无副作用验证通过。

## 13. Isolation Execute

必须确认“仅作用于软件仿真，不控制真实阀门。”并引用服务端比较 ID。复验图/阀门/疑似位置/场景/观测及 60 仿真秒有效期；过期返回 409。共享 ValveService 在数据库事务内完成阀门与执行记录，提交成功后更新内存图。

## 14. Valve / Flow 联动

关闭指令离散施加，压力/流量连续过渡；执行即时保留原值，下一真实 tick 才开始衰减。估算泄漏从 **20.966 m³/h** 逐渐接近零，未受影响上游恢复正常目标。暂停变速仍保持冻结。

## 15. Risk Stabilizing

最终 CONTAINED / STABILIZING、供水 INTERRUPTED，告警 ID 不变且 active。事件不关闭。人工重开阀门会重新检测到显著泄漏；每事件不重复执行 M8 隔离。

## 16. Dashboard / Risk 联动

Dashboard 显示管网事故与规则风险。Risk 显示规则分解及拓扑影响，明确“当前 ML 预测模型仅适用于内涝场景”；不使用六个 Flood 模型预测泄漏。原 M6 模型/数据/训练报告保留。

## 17. API

前缀 `/api/v1`：

- POST `/simulation/pipeline-leak/start`（`pipeline_id`, `severity`）、`/stop`、`/reset`；GET 同前缀 `/status`。
- GET `/pipeline-leak/status`、`/localization`、`/risk`。
- POST `/pipeline-leak/isolation/compare`（`pipeline_id`）；POST `/execute`（`comparison_id`, `option_id`, `confirmed_simulation:true`）。
- GET `/pipeline-leak/history/{scenario_id}` 返回已存事件/快照/比较及执行证据，不提供 M9 回放。
- `PIPELINE_LEAK_EVENT` 复用 `/ws/realtime`，无新增 Socket。

## 18. Migration / Database

实际迁移 **f6f65d1e093a → 父 adab6941d89a**，新增 events/snapshots/isolations 三表。5 墙钟秒采样。本轮同一事件 27 条快照、3 次比较、1 次执行，Reset 后保留。告警保存在事件 JSON、按场景去重。34/32/10 管网资产、3 模板和三台各 120 m³/h 泵保留。见 [数据库核验](M8-database-results.json)。

## 19. 新增文件

新增后端 leak schema/model/API/config、检测定位服务、场景服务、共享 ValveService、迁移与 20 项测试；新增前端 LeakPanel/LeakSummary/LeakEffect、类型/API 与两种验证脚本。完整路径与职责见 [文件清单](M8-files.md)。

## 20. 修改文件

增量修改原 PipelineSimulator/Engine、RealtimeService/Socket、M4 阀门 API、PipelineManager/BuildingManager/二维图、Dashboard/Risk、实时缓存、入口与 README。M3 测试只为缩放后的异步重排增加有界等待，原布局检查保留；没有重写 M4 图或训练 M6 模型。

## 21. 测试结果

**后端 107 passed（54.37s）；生产构建通过（6.77s）；Alembic check 一致；M8 真实浏览器 7 组及缓存通过；M1–M7 全部回归通过。** M8 页面 errors=[]。缓存 1800 点/60 仿真分钟，暂停、断线、场景/会话切换与 Reset 边界全部通过。完整结果、复现与初次布局测试情况见 [验收记录](M8-verification.md)。

## 22. 性能情况

定位 500 次平均 **0.0598 ms**、P95 **0.0737 ms**；真实比较计时 **6.690 ms**（不含比较写库与 HTTP）。超过 10 仿真分钟 geometry/material/texture **36/98/9 保持不变**。1920 软件渲染采样 **31 FPS**，不能代表比赛 GPU 达到 45 FPS；需实机验收。

## 23. 演示流程

打开 <http://127.0.0.1:5173/pipeline> → 泄漏事故模式 → 启动并确认 → DEV 10× → 观察检测与 Top 3 → 暂停 → 比较/预览候选 → 选择 V-W-03 → 确认软件隔离 → 继续 → 观察泄漏衰减、风险下降及两栋停水 → 查看 Dashboard / Risk → 停在 STABILIZING。Reset 后可重新演示。

## 24. 当前边界

软件示范管网、简化泄漏与传播模型，非真实水力求解；分数未经概率校准，不用于真实城市安全决策。仅仿真阀门。单 worker 内存引擎；重启不续演，已保存关闭阀门不自动重开；断库仅保存最新待写状态，不补造中间历史。停止于稳定阶段，未实现正式恢复、关闭、回放或最终工单。

## 25. M9 建议

下一阶段可统一 Flood/Leak 事件身份、动作/快照/预测时间轴和历史查询，明确缺失采样；再实现只读回放、恢复与正式关闭条件。保留“泄漏受控”和“供水恢复”的区别。这些仅为建议，本阶段未开发。

Milestone 8 已完成，当前停止开发，等待进入 Milestone 9。
