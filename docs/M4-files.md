# M4 文件清单

## 新增

- [backend/app/models/pipeline.py](../backend/app/models/pipeline.py)
- [backend/app/schemas/pipeline.py](../backend/app/schemas/pipeline.py)
- [backend/app/services/pipeline_seed.py](../backend/app/services/pipeline_seed.py)
- [backend/app/services/pipeline_graph_service.py](../backend/app/services/pipeline_graph_service.py)
- [backend/app/api/pipelines.py](../backend/app/api/pipelines.py)
- [backend/migrations/versions/2cae9fa70c8f_pipeline_digital_twin.py](../backend/migrations/versions/2cae9fa70c8f_pipeline_digital_twin.py)
- [backend/tests/test_pipeline.py](../backend/tests/test_pipeline.py)
- [scripts/seed-pipelines.py](../scripts/seed-pipelines.py)
- [algorithm/graph_search/__init__.py](../algorithm/graph_search/__init__.py)
- [algorithm/graph_search/types.py](../algorithm/graph_search/types.py)
- [algorithm/graph_search/graph.py](../algorithm/graph_search/graph.py)
- [algorithm/graph_search/traversal.py](../algorithm/graph_search/traversal.py)
- [algorithm/graph_search/isolation.py](../algorithm/graph_search/isolation.py)
- [frontend/src/types/pipeline.ts](../frontend/src/types/pipeline.ts)
- [frontend/src/api/pipelines.ts](../frontend/src/api/pipelines.ts)
- [frontend/src/store/usePipelineStore.ts](../frontend/src/store/usePipelineStore.ts)
- [frontend/src/views/Pipeline/pipeline.css](../frontend/src/views/Pipeline/pipeline.css)
- [frontend/scripts/verify-pipeline.cjs](../frontend/scripts/verify-pipeline.cjs)
- [frontend/src/views/Pipeline/components/PipelineList.vue](../frontend/src/views/Pipeline/components/PipelineList.vue)
- [frontend/src/views/Pipeline/components/PipelineDetail.vue](../frontend/src/views/Pipeline/components/PipelineDetail.vue)
- [frontend/src/views/Pipeline/components/PipelineTracePanel.vue](../frontend/src/views/Pipeline/components/PipelineTracePanel.vue)
- [frontend/src/views/Pipeline/components/PipelineRealtimeCard.vue](../frontend/src/views/Pipeline/components/PipelineRealtimeCard.vue)
- [frontend/src/views/Pipeline/components/IsolationOptions.vue](../frontend/src/views/Pipeline/components/IsolationOptions.vue)
- [frontend/src/views/Pipeline/components/PipelineTopologyGraph.vue](../frontend/src/views/Pipeline/components/PipelineTopologyGraph.vue)
- [frontend/src/views/Pipeline/components/ValveCard.vue](../frontend/src/views/Pipeline/components/ValveCard.vue)

## 修改

- [backend/app/models/__init__.py](../backend/app/models/__init__.py)
- [backend/app/schemas/realtime.py](../backend/app/schemas/realtime.py)
- [backend/app/services/realtime_service.py](../backend/app/services/realtime_service.py)
- [backend/app/main.py](../backend/app/main.py)
- [backend/simulator/engine.py](../backend/simulator/engine.py)
- [backend/simulator/pipeline_simulator.py](../backend/simulator/pipeline_simulator.py)
- [backend/tests/test_simulation.py](../backend/tests/test_simulation.py)
- [frontend/src/types/realtime.ts](../frontend/src/types/realtime.ts)
- [frontend/src/types/realtimeValidation.ts](../frontend/src/types/realtimeValidation.ts)
- [frontend/src/three/pipeline/PipelineManager.ts](../frontend/src/three/pipeline/PipelineManager.ts)
- [frontend/src/three/index.ts](../frontend/src/three/index.ts)
- [frontend/src/three/effects/EffectManager.ts](../frontend/src/three/effects/EffectManager.ts)
- [frontend/src/three/interaction/InteractionManager.ts](../frontend/src/three/interaction/InteractionManager.ts)
- [frontend/src/three/building/BuildingManager.ts](../frontend/src/three/building/BuildingManager.ts)
- [frontend/src/components/digital-twin/DigitalTwinScene.vue](../frontend/src/components/digital-twin/DigitalTwinScene.vue)
- [frontend/src/views/Pipeline/index.vue](../frontend/src/views/Pipeline/index.vue)
- [frontend/src/App.vue](../frontend/src/App.vue)
- [frontend/package.json](../frontend/package.json)
- [frontend/scripts/verify-web3d.cjs](../frontend/scripts/verify-web3d.cjs)
- [frontend/scripts/verify-realtime.cjs](../frontend/scripts/verify-realtime.cjs)
- [frontend/scripts/verify-operation.cjs](../frontend/scripts/verify-operation.cjs)
- [README.md](../README.md)

- [backend/app/services/telemetry_service.py](../backend/app/services/telemetry_service.py)
- [backend/tests/test_operation.py](../backend/tests/test_operation.py)
- [frontend/src/views/Dashboard/index.vue](../frontend/src/views/Dashboard/index.vue)
- [frontend/scripts/verify-operation-state.cjs](../frontend/scripts/verify-operation-state.cjs)

- [frontend/src/components/digital-twin/digital-twin.css](../frontend/src/components/digital-twin/digital-twin.css)

## 文档与验收产物

M4-architecture.md、M4-verification.md、M4-files.md、M4-browser-results.json、M4 页面截图，以及 M1/M2/M3 的 M4 回归结果。
