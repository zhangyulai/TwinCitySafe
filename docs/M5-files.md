# M5 文件清单

## 新增

- [backend/simulator/flood_config.py](../backend/simulator/flood_config.py)
- [backend/app/schemas/flood.py](../backend/app/schemas/flood.py)
- [backend/app/models/flood.py](../backend/app/models/flood.py)
- [backend/app/services/flood_service.py](../backend/app/services/flood_service.py)
- [backend/app/services/flood_risk_service.py](../backend/app/services/flood_risk_service.py)
- [backend/app/services/flood_forecast_service.py](../backend/app/services/flood_forecast_service.py)
- [backend/app/services/flood_storage_service.py](../backend/app/services/flood_storage_service.py)
- [backend/app/api/flood.py](../backend/app/api/flood.py)
- [backend/migrations/versions/04ac9081f4fe_flood_simulation.py](../backend/migrations/versions/04ac9081f4fe_flood_simulation.py)
- [backend/tests/test_flood.py](../backend/tests/test_flood.py)
- [frontend/src/types/flood.ts](../frontend/src/types/flood.ts)
- [frontend/src/api/flood.ts](../frontend/src/api/flood.ts)
- [frontend/src/views/Simulation/flood.css](../frontend/src/views/Simulation/flood.css)
- [frontend/src/views/Simulation/components/FloodRiskCard.vue](../frontend/src/views/Simulation/components/FloodRiskCard.vue)
- [frontend/src/views/Simulation/components/FloodForecastCard.vue](../frontend/src/views/Simulation/components/FloodForecastCard.vue)
- [frontend/src/views/Simulation/components/FloodTrendChart.vue](../frontend/src/views/Simulation/components/FloodTrendChart.vue)
- [frontend/src/three/effects/FloodRiskEffect.ts](../frontend/src/three/effects/FloodRiskEffect.ts)
- [frontend/scripts/verify-flood.cjs](../frontend/scripts/verify-flood.cjs)
- [frontend/scripts/verify-flood-state.cjs](../frontend/scripts/verify-flood-state.cjs)

## 修改

- [backend/simulator/engine.py](../backend/simulator/engine.py)
- [backend/simulator/weather_simulator.py](../backend/simulator/weather_simulator.py)
- [backend/simulator/flood_simulator.py](../backend/simulator/flood_simulator.py)
- [backend/app/schemas/realtime.py](../backend/app/schemas/realtime.py)
- [backend/app/models/__init__.py](../backend/app/models/__init__.py)
- [backend/app/services/realtime_service.py](../backend/app/services/realtime_service.py)
- [backend/app/api/realtime.py](../backend/app/api/realtime.py)
- [backend/app/main.py](../backend/app/main.py)
- [backend/tests/test_simulation.py](../backend/tests/test_simulation.py)
- [frontend/src/types/realtime.ts](../frontend/src/types/realtime.ts)
- [frontend/src/types/realtimeValidation.ts](../frontend/src/types/realtimeValidation.ts)
- [frontend/src/store/useRealtimeStore.ts](../frontend/src/store/useRealtimeStore.ts)
- [frontend/src/views/Simulation/index.vue](../frontend/src/views/Simulation/index.vue)
- [frontend/src/views/Dashboard/index.vue](../frontend/src/views/Dashboard/index.vue)
- [frontend/src/views/Dashboard/realtime-dashboard.css](../frontend/src/views/Dashboard/realtime-dashboard.css)
- [frontend/src/three/environment/WaterSurface.ts](../frontend/src/three/environment/WaterSurface.ts)
- [frontend/src/three/effects/RainEffect.ts](../frontend/src/three/effects/RainEffect.ts)
- [frontend/src/three/core/SceneManager.ts](../frontend/src/three/core/SceneManager.ts)
- [frontend/src/three/building/BuildingManager.ts](../frontend/src/three/building/BuildingManager.ts)
- [frontend/src/three/index.ts](../frontend/src/three/index.ts)
- [frontend/src/components/digital-twin/DigitalTwinScene.vue](../frontend/src/components/digital-twin/DigitalTwinScene.vue)
- [frontend/src/components/digital-twin/digital-twin.css](../frontend/src/components/digital-twin/digital-twin.css)
- [frontend/src/App.vue](../frontend/src/App.vue)
- [frontend/package.json](../frontend/package.json)
- [frontend/scripts/verify-pipeline.cjs](../frontend/scripts/verify-pipeline.cjs)
- [README.md](../README.md)

## 文档与验收产物

M5-architecture.md、M5-verification.md、M5-files.md、M5-browser-results.json、M5-state-results.json，M5 页面截图及以 M5 前缀保存的 M1–M4 回归结果。既有 M1–M4 验收产物保留。
