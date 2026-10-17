# 最终项目结构

| 路径 | 作用 |
|---|---|
| `frontend/src/App.vue`、`components/shell/` | 紧凑导航、演示控制、系统状态、自检、页面错误边界和关于平台 |
| `frontend/src/views/{Dashboard,Operation,Pipeline,Risk,Simulation,Review}` | 六个业务页面 |
| `frontend/src/store/` | 实时、应急、管网、回放、Demo、质量状态；回放与实时隔离 |
| `frontend/src/three/` | 场景管理、相机、渲染、资产、特效、标签与分档质量 |
| `frontend/src/api/` | REST 接口；实时服务独立管理 WebSocket |
| `frontend/scripts/verify-*.cjs` | 原 M1–M9 与比赛版真实浏览器验收 |
| `backend/app/api/` | 设备、管网、事故、预测、应急、readiness 与 Demo API |
| `backend/app/services/` | 业务服务、模型加载、采样、预测与历史归档 |
| `backend/app/models/`、`backend/alembic/` | 资产和记录模型、数据库迁移 |
| `backend/simulator/` | 单权威时钟、设备、气象、内涝、泄漏模型 |
| `algorithm/` | 已训练模型、数据生成/训练/评估脚本与真实报告 |
| `scripts/` | 准备、种子数据、就绪检查、历史核验、数据库备份恢复 |
| `start-dev.sh` | 原开发启动入口，前后端热更新 |
| `prepare-demo.sh` | 幂等准备、模型检查和本地构建 |
| `start-demo.sh` | 无 reload 生产后端 + 本地静态预览；显式比赛控制 |
| `docs/M1*`—`docs/M9*` | 保留的历史验收产物，不被最终回归覆盖 |
| `docs/final/` | M10 最终测试、性能、截图与结构 |

启动脚本采用 Linux `setsid` 管理进程组。独立启动后端可运行 `backend/.venv/bin/python scripts/start-demo-backend.py`，前端运行 `npm --prefix frontend run preview -- --host 127.0.0.1 --port 5173 --strictPort`。准备过程不会从外网下载模型或自动训练。
