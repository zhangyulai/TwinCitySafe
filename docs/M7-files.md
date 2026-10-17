# M7 文件清单

## 新增实现

- `backend/app/schemas/emergency.py`：统一动作、步骤、执行状态与请求模型。
- `backend/app/models/emergency.py`：四张应急数据表。
- `backend/migrations/versions/adab6941d89a_emergency_simulation.py`：继承 M6 head 的真实迁移。
- `backend/app/services/emergency_plan_service.py`：默认模板、匹配、校验、基线签名及独立分支 rollout。
- `backend/app/services/emergency_execution_service.py`：实时/副本共享的动作时序与日志。
- `backend/app/services/emergency_service.py`：比较持久化、过期验证、执行意图、取消、后台日志写入。
- `backend/app/api/emergency.py`：计划、比较、预览、执行、取消、查询 API。
- `backend/tests/test_emergency.py`：21 项参数化与异步测试。
- `frontend/src/types/emergency.ts`、`frontend/src/api/emergency.ts`：接口合同。
- `frontend/src/store/useEmergencyStore.ts`：方案、比较、选择、执行和事件缓存。
- `frontend/src/views/Simulation/components/EmergencyPanel.vue`、`emergency.css`：方案卡片、双图、过期提示、确认与时间线。
- `frontend/src/components/EmergencyBrief.vue`：Dashboard / Risk 当前方案摘要。
- `frontend/src/three/effects/EmergencyBarrier.ts`：常驻入口闸门和拟封控标记。
- `frontend/scripts/verify-emergency.cjs`：真实 REST / WS / 引擎 / DB 浏览器演示。

## 修改实现

- 后端 `app/main.py`、`app/models/__init__.py`：注册路由和表。
- `app/schemas/realtime.py`、`app/schemas/flood.py`：启动进度、执行、入口、暴露与降雨工况状态。
- `simulator/device_simulator.py`、`simulator/flood_simulator.py`：复用 M3 启动时钟计算有效能力，体积守恒保留，人员暴露逐渐演化。
- `simulator/engine.py`、`simulator/flood_config.py`：动作调度接入原子步及显式雨势回落计划，旧曲线不变。
- `app/services/flood_service.py`、`flood_forecast_service.py`、`flood_risk_service.py`：入口状态服务、共享副本预测、应急文案。
- `app/api/flood.py`：显式 M7 60 分钟演示入口。
- `app/services/realtime_service.py`、`app/websocket/manager.py`：单连接事件流和日志生命周期，保留背压。
- `app/services/risk_prediction_service.py`：执行/入口/启动状态使缓存失效，说明非因果边界。
- `algorithm/risk_prediction/simulation.py`、`features.py`：副本保留降雨计划及待执行动作；特征顺序仍为 M6 的 30 维。
- `algorithm/risk_prediction/config.py`：后续新生成数据标为 `m7-simulator-v2-startup`；保存的 M6 模型/数据/历史报告未覆盖。
- `backend/tests/test_simulation.py`：更新新增 `emergency` 与 `startupProgress` 字段的精确合同断言。
- 前端 `types/realtime.ts`、`types/flood.ts`、`types/realtimeValidation.ts`：兼容并验证新增字段。
- `services/realtimeSocket.ts`、`store/useRealtimeStore.ts`：分流事件，同一 App 连接，按场景/会话清理应急缓存。
- `api/flood.ts`、`views/Simulation/index.vue`、`components/FloodRiskCard.vue`：应急演示、阈值入口和面板联动。
- `views/Dashboard/index.vue`、`views/Risk/index.vue`：活动应急摘要。
- `views/Operation/components/ChartCanvas.vue`：复用原图表生命周期，注册 Legend 组件。
- `three/index.ts`、`three/effects/EffectManager.ts`、`three/device/DeviceManager.ts`、`components/digital-twin/DigitalTwinScene.vue`：复用 Outline、设备环、水面与热区，新增入口对象的生命周期。
- `App.vue`、`frontend/package.json`、`README.md`：M7 标识、验收命令和边界说明。

## 验收与文档

`M7-architecture.md`、`M7-verification.md`、`M7-completion-report.md`、此文件及 M7 前缀的日志、JSON 与 PNG。M1–M6 本轮截图位于 `/tmp/m7-m*`，相应结果复制为 M7 前缀；旧里程碑证据保留。
