# M2 文件清单

路径相对 `TwinCitySafe/`。本清单记录 M2 实时仿真与数据联动的源码、配置和文档；安装依赖目录、Python 缓存、构建输出不属于交付源码。

## 新增后端文件

```text
backend/app/api/realtime.py
backend/app/schemas/realtime.py
backend/app/services/realtime_service.py
backend/app/websocket/manager.py
backend/app/websocket/messages.py
backend/simulator/__init__.py
backend/simulator/config.py
backend/simulator/state.py
backend/simulator/engine.py
backend/simulator/weather_simulator.py
backend/simulator/device_simulator.py
backend/simulator/flood_simulator.py
backend/simulator/pipeline_simulator.py
backend/tests/test_simulation.py
backend/tests/test_realtime_api.py
backend/tests/test_realtime_websocket.py
```

## 新增前端文件

```text
frontend/src/types/realtime.ts
frontend/src/types/realtimeValidation.ts
frontend/src/api/realtime.ts
frontend/src/services/realtimeSocket.ts
frontend/src/store/useRealtimeStore.ts
frontend/src/components/SimulationControls.vue
frontend/src/components/RealtimeWaterChart.vue
frontend/src/views/Dashboard/realtime-dashboard.css
frontend/src/three/effects/RainEffect.ts
frontend/src/three/environment/WaterSurface.ts
frontend/scripts/verify-realtime.cjs
```

## 修改文件

```text
.env.example
README.md
backend/app/main.py
scripts/start-backend.py
frontend/package.json
frontend/scripts/verify-web3d.cjs
frontend/vite.config.ts
frontend/src/App.vue
frontend/src/views/Dashboard/index.vue
frontend/src/components/digital-twin/DigitalTwinScene.vue
frontend/src/components/digital-twin/digital-twin.css
frontend/src/three/index.ts
frontend/src/three/core/SceneManager.ts
frontend/src/three/core/RendererManager.ts
frontend/src/three/device/DeviceManager.ts
frontend/src/three/pipeline/PipelineManager.ts
frontend/src/three/interaction/InteractionManager.ts
```

`main.py` 增加 lifespan 实时服务与路由；`.env.example` 增加可选 `VITE_WS_URL`；Vite 增加 `/ws` 代理及图表分包。前端沿用 M1 场景，通过更新接口和少量新增效果接入数据，未按消息重新创建整个场景。`scripts/start-backend.py` 把 `backend/simulator` 加入热重载目录；M1 浏览器检查将 canvas 计数限制在三维容器，避免误计 ECharts 画布。`RendererManager.ts` 本阶段仅做格式整理。

## 新增文档与验证产物

```text
docs/M2-architecture.md
docs/M2-files.md
docs/M2-verification.md
docs/M2-browser-results.json
docs/M2-web3d-regression-results.json
docs/M2-supplement-results.txt
docs/M2-clear.png
docs/M2-rain.png
docs/M2-underground.png
docs/M2-1440.png
```

浏览器脚本生成的 M2 截图与具体执行结果见 [M2 验证记录](M2-verification.md)。M0/M1 历史设计与验证文档保留，当前运行方式以项目 README 与 M2 架构说明为准。

后端未新增外部依赖，未新增业务数据表或每秒遥测入库；前端复用已安装的 ECharts。正式风险算法、事故仿真、泄漏、应急与回放不属于本次文件范围。
