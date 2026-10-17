# M8 文件清单

## 新增实现

| 文件 | 用途 |
|---|---|
| `backend/simulator/leak_config.py` | 演示目标、渐进曲线、阈值与风险权重 |
| `backend/app/schemas/leak.py` | LeakState、启动、比较和确认执行合同 |
| `backend/app/models/leak.py` | 事件、快照与比较/执行三表 |
| `backend/migrations/versions/f6f65d1e093a_pipeline_leak_scenario.py` | Alembic 生成的 M8 迁移 |
| `backend/app/services/leak_detection_service.py` | 多变量检测与观测/拓扑 Top 3 定位 |
| `backend/app/services/pipeline_leak_service.py` | 场景、影响、风险、比较过期、共享阀门执行与持久化 |
| `backend/app/services/valve_service.py` | 从 M4 控制路径提取的共享阀门校验/写入 |
| `backend/app/api/leak.py` | 场景、定位、风险、隔离与历史 API |
| `backend/tests/test_pipeline_leak.py` | 20 项（含参数化）M8 验证 |
| `frontend/src/types/leak.ts`、`frontend/src/api/leak.ts` | 前端合同与接口 |
| `frontend/src/views/Pipeline/components/LeakPanel.vue`、`frontend/src/views/Pipeline/leak.css` | 管网事故模式、四趋势 Tab、比较预览和确认 |
| `frontend/src/components/LeakSummary.vue` | Dashboard / Risk 场景摘要 |
| `frontend/src/three/effects/LeakEffect.ts` | 120 粒子固定池、喷射与脉冲环 |
| `frontend/scripts/verify-leak.cjs` | 真实 REST / WS / Three / PostgreSQL 完整验收 |
| `frontend/scripts/verify-leak-state.cjs` | 独立缓存边界检查 |

## 修改实现

- `backend/app/main.py`、`app/models/__init__.py`：路由与表注册。
- `backend/app/schemas/realtime.py`：LeakState 及管段入出口观测字段。
- `backend/simulator/engine.py`：复用时钟、暂停、Reset、事件数和实时处理回调。
- `backend/simulator/pipeline_simulator.py`：增量泄漏传播，复用原 16 秒平滑变化和图连接判定。
- `backend/app/api/pipelines.py`：M4 原控制调用共享 ValveService。
- `backend/app/services/realtime_service.py`、`app/websocket/manager.py`：生命周期、采样和单连接事件类型。
- `backend/app/services/flood_service.py`、`app/api/flood.py`、`app/api/realtime.py`：双场景互斥和按当前类型 Reset。
- `backend/tests/test_simulation.py`：精确字段合同接纳 `leak`，原检查保留。
- `frontend/src/types/realtime.ts`、`types/realtimeValidation.ts`：新增实时 Leak 合同检查。
- `frontend/src/services/realtimeSocket.ts`、`store/useRealtimeStore.ts`：同一连接处理 Leak 事件；有界趋势缓存。
- `frontend/src/views/Pipeline/index.vue`、`components/PipelineTopologyGraph.vue`：原 M4 页面增加模式切换、等级颜色、预览阀门和实际隔离状态。
- `frontend/src/three/index.ts`、`pipeline/PipelineManager.ts`、`building/BuildingManager.ts`、`components/digital-twin/DigitalTwinScene.vue`：复用场景、图资产、材质、相机、Outline 与释放机制。
- `frontend/src/views/Dashboard/index.vue`、`views/Risk/index.vue`：当前 Leak 事件、规则风险与 Flood ML 边界。
- `frontend/scripts/verify-operation.cjs`：1440 缩放断言前等待 ResizeObserver 重排，保留原布局检查。
- `frontend/src/App.vue`、`frontend/package.json`、`README.md`：M8 标识、测试入口与使用说明。

M4 `algorithm/graph_search` 算法未重写。M6 模型、训练集和历史评估报告未重新训练或覆盖。

## 证据

M8 前缀的架构、验收、完成报告、日志、JSON 与页面截图。M1–M7 本次回归截图另存 `/tmp/m8-m*`，结果复制为 M8 前缀文件，旧里程碑证据保留。定位微基准可运行 `backend/.venv/bin/python docs/M8-localization-benchmark.py`，它使用独立 SQLite，不操作演示数据库。
