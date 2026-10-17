# M3 文件清单

路径相对 TwinCitySafe/。M1/M2 的核心引擎、WebSocket 与 Three.js managers 均增量扩展。

## 新增后端

```text
backend/alembic.ini
backend/migrations/env.py
backend/migrations/script.py.mako
backend/migrations/versions/0001_equipment.py
backend/app/models/base.py
backend/app/models/device.py
backend/app/models/device_telemetry.py
backend/app/models/device_alarm.py
backend/app/schemas/operation.py
backend/app/api/devices.py
backend/app/services/seed_service.py
backend/app/services/device_service.py
backend/app/services/health_config.py
backend/app/services/anomaly_service.py
backend/app/services/maintenance_service.py
backend/app/services/alarm_service.py
backend/app/services/operation_service.py
backend/app/services/telemetry_service.py
backend/tests/conftest.py
backend/tests/test_operation.py
scripts/seed-devices.py
```

`conftest.py` 为所有测试提供独立 SQLite，测试不修改演示 PostgreSQL。生产建表只通过 Alembic。

## 新增算法

```text
algorithm/__init__.py
algorithm/anomaly_detection/__init__.py
algorithm/anomaly_detection/config.py
algorithm/anomaly_detection/features.py
algorithm/anomaly_detection/dataset.py
algorithm/anomaly_detection/train.py
algorithm/anomaly_detection/evaluate.py
algorithm/anomaly_detection/models/pump_isolation_forest.joblib
algorithm/anomaly_detection/reports/metrics.json
```

模型与报告均为实际训练生成；训练集由同一 DeviceSimulator 生成，不将固定指标伪装成评估结果。

## 新增前端

```text
frontend/src/types/operation.ts
frontend/src/api/devices.ts
frontend/src/views/Operation/operation.css
frontend/src/views/Operation/components/ChartCanvas.vue
frontend/src/views/Operation/components/DeviceList.vue
frontend/src/views/Operation/components/DeviceSummary.vue
frontend/src/views/Operation/components/DeviceRealtimeMetrics.vue
frontend/src/views/Operation/components/DeviceHealthCard.vue
frontend/src/views/Operation/components/DeviceAnomalyCard.vue
frontend/src/views/Operation/components/MaintenanceAdviceCard.vue
frontend/src/views/Operation/components/DeviceTrendChart.vue
frontend/scripts/verify-operation.cjs
frontend/scripts/verify-operation-state.cjs
```

## 修改现有文件

```text
.env.example
README.md
backend/requirements.txt
backend/requirements.lock.txt
backend/app/core/config.py
backend/app/main.py
backend/app/models/__init__.py
backend/app/schemas/realtime.py
backend/app/services/health_service.py
backend/app/services/realtime_service.py
backend/simulator/config.py
backend/simulator/device_simulator.py
backend/simulator/engine.py
backend/tests/test_simulation.py
frontend/package.json
frontend/src/App.vue
frontend/src/types/realtime.ts
frontend/src/types/realtimeValidation.ts
frontend/src/api/realtime.ts
frontend/src/store/useRealtimeStore.ts
frontend/src/components/SimulationControls.vue
frontend/src/components/digital-twin/DigitalTwinScene.vue
frontend/src/three/index.ts
frontend/src/three/building/BuildingManager.ts
frontend/src/three/device/DeviceManager.ts
frontend/src/three/interaction/InteractionManager.ts
frontend/src/views/Operation/index.vue
frontend/src/views/Dashboard/index.vue
frontend/scripts/verify-web3d.cjs
frontend/scripts/verify-realtime.cjs
```

Health 服务保留 M0 liveness 接口，新增设备 HI 计算。旧浏览器脚本改用仍无图表/场景的管网页面检查卸载（Operation 已成为真实功能页），并适配 App 级自动 Health 初始化；未移除原交互、资源清理或重连断言。

## 文档与实测产物

```text
docs/M3-architecture.md
docs/M3-verification.md
docs/M3-files.md
docs/M3-browser-results.json
docs/M3-state-results.json
docs/M3-m1-results.json
docs/M3-m2-results.json
docs/M3-operation-normal.png
docs/M3-operation-fault.png
docs/M3-dashboard-alarm.png
docs/M3-operation-1440.png
```

依赖目录、编译产物和 Python 缓存不列为源码交付。没有实现 M4 及后续阶段。
