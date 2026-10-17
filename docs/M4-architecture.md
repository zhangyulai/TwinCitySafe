# M4 地下管网数字孪生架构

本模块使用软件示范管网，不代表真实城市地下设施。没有实现泄漏事故、泄漏概率、工单、应急决策或新机器学习模型。

## 资产与数据库

`pipeline_nodes`：稳定字符串 ID、node_code、node_type、名称、xyz、building_id、area_id、metadata、时间戳。SQLAlchemy 使用 attributes 映射数据库 metadata，避免保留字段冲突。

`pipeline_edges`：稳定 ID、pipeline_code、pipeline_type、起止节点外键、管径 mm、长度 m、埋深 m、材质、安装日期、设计压力 MPa、初始压力/流量、基础健康分、状态、时间戳。实时读数只由 M2 提供，数据库 current_pressure/current_flow 是初始资产快照，不伪装成实时传感器值。健康分保留示范资产基础值 96，未新增模型。

`valves`：稳定 ID、node_id 唯一外键、valve_code、类型、open/closed/fault、开度、维护日期、时间戳。关闭阀门不会删除节点或边。

迁移：`2cae9fa70c8f_pipeline_digital_twin`，前置 `0001_equipment`。仅创建三张表，外键、唯一索引和开度约束；不改动 M3 设备表。启动时不自动建表或 Seed。

Seed 为缺失 ID 插入资产，已有属性与阀门状态保留。给水 12 节点 / 11 边 / 3 阀门，排水 12 / 11 / 3，消防 10 / 10 / 4，总计 34 / 32 / 10。消防包含绕行支路。五类建筑连接映射现有 A-OFFICE、B-RESEARCH、C-LAB、D-SERVICE、B2-PARKING。WS-003 下游接科研楼 B 与实验楼 C。

## Graph 与影响语义

独立 `algorithm/graph_search` 只依赖不可变 Node / Edge / Valve DTO；没有 SQLAlchemy、FastAPI、Three.js 依赖。正向、反向邻接表保存目标节点、边 ID、长度权重。BFS 用 visited 去重，支持环、支路、断连与多水源。

给水/消防：source → connection。排水：connection → sink，判断运行连通性时从 sink 沿反向边遍历。关闭阀门视为阻断节点，offline/isolated 资产边不参与连通。普通追踪遵循设计方向；无向模式用于保守检查潜在反向供水路径。

失效影响 = 当前连通节点 − 移除目标边后仍连通节点，建筑从这些节点上的 building_id 映射获得。不是写死的受影响数组，也不会把原本失联的建筑再次计为新增影响。阀门控制返回当前所有失联连接，页面明确展示实际隔离影响。

候选隔离：从目标边上下游搜索最多 3 层阀门，最多 10 个候选阀门，枚举至多 3 阀组合（最多 175 次组合）。对每组关闭阀门，从供给终端重新遍历；目标两端均不可由物理无向供给路径抵达才可视为隔离。再按运行方向计算失联节点、管段、建筑、累计长度，按隔离范围去重，按建筑数/长度/阀门数排序，至多返回 5 个。候选不宣称全局最优，也不自动执行。

WS-003 默认得到三组不同范围：关闭 V-W-03 影响 2 栋，V-W-02 影响 4 栋，V-W-01 影响 5 栋。靠近水源、既有关闭状态或无可用边界的管段可能没有候选；系统不会强行生成三条假方案。

## 实时引擎

后端启动时在工作线程读取 PostgreSQL 资产 DTO，一次配置现有 PipelineSimulator；从 3 个示意状态扩充至 32 条正式管段，WebSocket 仍每秒一份全量状态。没有第二套模拟器或 WebSocket。保留既有实时枚举 drain，正式资产 drainage 显式映射。

阀门开发控制先保存事务，再更新图和同一引擎状态，立即广播。状态标记立即切到 isolated；压力和流量按现有 relax 的 16 模拟秒时间常数向零衰减，重开后平滑追随原目标。此为拓扑引导的合理动态，不模拟压差分配、反压、倒流、真实水力学或水锤。排水隔离读数的下降表示可用输送能力，不能据此推断真实堵塞后的压力走势。

Valve 状态跨重启保留，Reset 保留资产与阀门边界，仅重置模拟时间/读数。仍要求单 Uvicorn worker。服务启动前必须迁移、Seed；缺失资产不会生成假的正式 32 管段，前端显示资产加载问题或等待实时数据。

## 前端与 Three.js

usePipelineStore 保存资产、选择、拓扑、追踪与候选方案；pressure/flow/status 始终从 useRealtimeStore 获取。异步分析用递增 generation 防止旧管段响应覆盖新选择。

PipelineManager 增量改为根据数据库节点坐标生成 TubeGeometry。每管段持有可复用材质/offset uniform；共享同一 shader program cache key。每帧只推进 offset，flow 决定速度，沿 start → end 流动，暂停时冻结。参考 [Three.js Material 官方说明](https://threejs.org/docs/pages/Material.html)。无纹理创建，无逐帧几何或材质分配。

正常低 emissive，Hover 增强，Selected 高亮；追踪青色，方案预览橙色，实际 isolated/offline 灰色。EffectManager 管理 temporary highlight 的清理回调。过滤只改 visible，不重建 geometry。一个 CSS2D 标签复用显示选中管段/阀门。

阀门为 Cylinder 组合，open 青绿、closed 灰、fault 橙。独立 Raycaster 优先检查阀门，再管段。复用 CameraManager Tween，管段保持地下观察距离。

ECharts Graph 使用数据库节点坐标，箭头表示设计方向，菱形表示阀门、矩形表示建筑连接。点击节点/边发 Vue 事件，三维选择反向同步到图。参考 [ECharts 事件官方说明](https://echarts.apache.org/handbook/en/concepts/event/)。图表和场景卸载均 dispose，断开 ResizeObserver、移除只读开发诊断钩子。

地下建筑使用预创建半透明简化外轮廓减少重叠绘制，回到地上/风险模式恢复原建筑细节；地面保持半透明、B2 保留实体可辨识结构。没有重写 SceneManager。

## 边界

无鉴权的开发控制仅适用于既有本机开发部署，production 下阀门控制返回 404。当前只有查询接口和开发阀门状态更新，没有资产管理增删改 UI。数据库模型支持后续管理功能，但未增加超出 M4 请求的公开写入接口。

图搜索不提供事故检测能力，不把连通性等同于真实供水能力；正式管网事故留给 M8，M5 不在本阶段实现。
