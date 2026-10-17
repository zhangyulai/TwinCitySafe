# M9 文件清单

## 新增核心文件

- `backend/app/models/incident.py`：统一业务档案、时间轴、动态快照、工单和报告。
- `backend/app/schemas/incident.py`：工单与关闭输入校验。
- `backend/app/services/incident_service.py`：来源聚合、时间轴、指标、报告、工单和关闭事务。
- `backend/app/services/incident_replay_service.py`：只读 DTO、下采样、缺口和关键节点。
- `backend/app/services/incident_runtime_service.py`：采样、失败重试、Reset/重启中断、实时关闭协调。
- `backend/app/api/incidents.py`：历史查询和业务命令 API。
- `backend/migrations/versions/9fdda90bd972_incident_timeline_review.py`：M8 后继迁移。
- `backend/tests/test_incident_review.py`：M9 后端验证。
- `scripts/backfill-incidents.py`：显式幂等历史回填。
- `scripts/verify-incident-archives.py`：已关闭档案、原资产、只读API数据库核验。
- `frontend/src/api/review.ts`、`frontend/src/types/review.ts`、`frontend/src/store/useReplayStore.ts`。
- `frontend/src/views/Review/components/ReplayChart.vue`、`RecordValue.vue`、`frontend/src/views/Review/review.css`。
- `frontend/scripts/verify-review.cjs`、`verify-review-state.cjs`、`verify-review-legacy.cjs`、`verify-incident-lifecycle.cjs`。
- `docs/M9-api-contract.md`、`M9-architecture.md`、`M9-verification.md`、`M9-completion-report.md`，以及 M9 前缀的真实验收日志、结果和截图。

## 修改文件

- `backend/app/models/__init__.py`、`backend/app/main.py`：模型及 API 注册。
- `backend/app/services/realtime_service.py`：接入事故归档观察器。
- `backend/app/api/realtime.py`、`flood.py`、`leak.py`：Reset/替换场景明确中断旧事故。
- `frontend/src/views/Review/index.vue`：占位页升级为完整复盘中心。
- `frontend/src/components/digital-twin/DigitalTwinScene.vue`：Live/Replay 数据源隔离。
- `frontend/src/three/index.ts`：历史状态更新和可取消相机引导。
- `frontend/src/three/core/SceneManager.ts`：天气未记录时使用独立静态光照，避免跨事故残留。
- `frontend/src/three/device/DeviceManager.ts`、`pipeline/PipelineManager.ts`：动态历史及灰色未知状态。
- `frontend/src/three/environment/WaterSurface.ts`、`effects/FloodRiskEffect.ts`：即时跳转到历史水面及热区。
- `frontend/src/App.vue`、`frontend/package.json`、`README.md`：M9 状态、脚本与复现说明。

本里程碑没有重写 Flood/Leak 仿真器、M6 模型、M7 应急引擎或 M4 图算法。M1–M8 历史验收产物保留。
