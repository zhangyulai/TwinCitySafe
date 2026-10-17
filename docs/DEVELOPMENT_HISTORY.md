# 开发历史与里程碑证据

以下保留 M0–M9 的原 README 记录。当前比赛启动入口见项目根 README。

# 孪城智安 TwinCitySafe

基于 Web3D 数字孪生与智能风险研判的智慧园区运维安全平台。面向园区运维与安全场景，按里程碑逐步构建监测、预测、推演、处置和复盘闭环。

**当前范围：Milestone 9 — Timeline Replay & Incident Review。** 在 M5–M8 事故历史上增加统一档案、持久化时间轴、Three.js 历史回放、处置复盘、工单与人工关闭流程，保留 M0–M8 功能。

**所有数据均为软件仿真，异常模型基于仿真工况训练。** 设备正常、轴承退化、过热及低效率可通过开发控制面板演示；没有真实园区生产数据，M4 地下管网是软件示范管网，并非真实城市地下管网。M5 使用简化水量平衡模型和 Flood scenario risk score（场景规则模型）；非 CFD、非实际防洪工程设计模型，不用于真实安全决策。M6 XGBoost 使用软件仿真数据训练，只学习当前仿真分布，不能代表真实城市泛化能力，仅用于比赛软件演示。M7 为软件仿真动作，不控制真实泵、阀门或入口；不替代人工应急决策，不提供真实工程安全保证。M8 使用简化泄漏模型和观测/拓扑匹配，仅为软件示范管网，不用于真实城市安全决策；阀门执行仅仿真。M9 仅回放已保存的软件仿真历史；旧记录缺失项保留“未记录”，复盘报告使用数据模板。

## 首次启动

完成下方原有依赖和 PostgreSQL 配置后，从项目根目录依次执行：

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python scripts/seed-devices.py
backend/.venv/bin/python scripts/seed-pipelines.py
backend/.venv/bin/python algorithm/anomaly_detection/train.py
./start-dev.sh
```

打开 <http://127.0.0.1:5173/pipeline> 切换“泄漏事故模式”；暴雨内涝与应急推演在 <http://127.0.0.1:5173/simulation>。先迁移、Seed，再启动服务；若服务已运行，请重启后端加载全部资产。设备运维仍在 <http://127.0.0.1:5173/operation>，默认选择 P03；Dashboard 仍在 `/dashboard`。训练脚本也可在其目录用项目 venv 的 `python train.py` 执行；后端启动只加载模型，不重复训练。重新训练后重启后端加载新模型。模型未加载时服务继续运行，页面明确提示。

在“仿真控制”选择 P03 故障工况 → 轴承退化，观察振动、温度、HI、异常分数、颜色和维护建议变化。建议先用1×观察，演示可选5×/10×加速；切回正常工况会逐渐恢复，Reset立即恢复默认仿真参数。默认故障渐变约90个模拟秒；真实采样与WebSocket仍按各自固定频率。

M3 新增配置：`TELEMETRY_SAMPLE_INTERVAL_SECONDS=5`（最小5秒）、`APP_ENV=development`。生产设 `APP_ENV=production` 将禁用故障注入API；前端生产构建隐藏 DEV 面板。使用单 Uvicorn worker；数据库历史按开发数据保留，不自动删除。Reset 清空实时缓存但不删除已采样历史或累计运行小时。

资产与接口、评分和告警语义见 [M3 架构](M3-architecture.md)，模型指标与验证见 [M3 验收](M3-verification.md)，文件清单见 [M3 文件](M3-files.md)。

新增 REST（前缀 `/api/v1`）：`/devices`、`/devices/{id}`、`/devices/{id}/realtime`、`/telemetry`、`/health`、`/anomaly`、`/maintenance-advice`、`/alarms`（后六项均接在设备路径后）；另有 `/telemetry/status` 和 `POST /simulation/device/{id}/fault`。

```bash
npm --prefix frontend run build
npm --prefix frontend run test:operation
npm --prefix frontend run test:operation-state
# 仍可运行 test:web3d 与 test:realtime；浏览器验收需开发服务运行。
(cd backend && .venv/bin/python -m pytest -q -W error)
```

## M4 管网演示与接口

选择给水 → WS-003 → 上游追踪 / 下游追踪 / 影响分析 → 隔离方案。三个候选分别关闭 V-W-03、V-W-02、V-W-01，比较 2、4、5 栋建筑的影响；点击方案只预览、不执行。开发模式把 V-W-02 改为 Closed，观察流量平滑下降和灰色隔离管段，再改为 Open 恢复。

阀门状态写入 PostgreSQL，重启与 Reset 均保留；Reset 重置模拟读数后仍按已保存阀门连通性运行。后端使用同一 M2 引擎和 WebSocket，`drainage` 资产类型映射为既有实时协议的 `drain`。

REST 前缀 `/api/v1`：

| 方法 | 路径 | 内容 |
|---|---|---|
| GET | `/pipelines` | type / status / keyword 筛选 |
| GET | `/pipelines/network`、`/pipelines/statistics` | 完整资产图、汇总 |
| GET | `/pipelines/topology/validate` | 节点数、无效边、孤立节点、重复 ID、水源/出口 |
| GET | `/pipelines/{id}`、`/pipelines/{id}/realtime` | 资产、实时值 |
| GET | `/pipelines/{id}/topology` | 同类型拓扑 |
| GET | `/pipelines/{id}/upstream`、`/downstream` | 有向追踪，后者同样接在管段路径后 |
| GET | `/pipelines/{id}/affected-buildings`、`/valves` | 建筑影响、最近上下游阀门 |
| POST | `/pipelines/{id}/isolation-options` | 至多 5 个候选方案，不执行 |
| POST | `/simulation/valve/{id}/state` | `{ "status": "open" 或 "closed" }`，仅 development |

运行 `npm --prefix frontend run test:pipeline` 进行实际浏览器验收。详见 [M4 架构](M4-architecture.md)、[M4 验收](M4-verification.md) 和 [M4 文件清单](M4-files.md)。

## M5 暴雨内涝演示与接口

若已完成 M4，执行 `backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head` 后重启后端即可。新增迁移 `04ac9081f4fe` 创建 `flood_scenarios` 和 `flood_snapshots`，不需要事故历史 Seed。

1. 打开 `/simulation`，点击“启动暴雨内涝推演”，确认“将启动软件仿真事故场景，不影响真实设备。”
2. 镜头切到 B2；开发模式选择 10×，约 3 分钟覆盖 30 个仿真分钟。雨量逐步从 8 升至 100 mm/h。
3. 第 3 个仿真分钟触发既有 M3 P03 轴承退化：温度、振动上升，效率逐渐降至约 76%。这是当前 M3 模型标定结果，不是另造的内涝效率。
4. 查看积水面积、水位、风险热区和 +10/+20/+30 分钟预测；风险≥60 显示“建议进入应急方案推演”。30 分钟末软件模型水位约 25.9 cm、风险约 82.8，冻结事故而不执行恢复。
5. 可启动 P01/P02 比较排水能力与预测变化；可暂停/继续或 Reset。Reset 恢复日常状态，但保留已写入的场景与快照、设备和管网资产。

模型使用 `Qin = 雨量÷1000÷3600×汇水面积×径流系数`、`Qpump = Σ额定能力÷3600×实时效率×启动进度` 和体积守恒。Weather 与 Device 分别为唯一天气/设备真值。只有运行/告警态泵计入能力，待机/离线泵不计。人员/车辆暴露默认 32/48，可在 DEV 面板调整。

预测复制当前模型状态，按计划雨量与设备趋势外推，不推进真实引擎；即使演示时长结束，预测仍展示这些假设持续下的未来，不代表事故已恢复。风险权重为水位35%、降雨20%、泵能力损失20%、上涨趋势15%、暴露10%，不是 AI 综合风险预测。

REST 前缀 `/api/v1/simulation/flood`：

| 方法 | 路径 | 内容 |
|---|---|---|
| POST | `/start` | DEV 手动场景；scenario: normal / heavy_rain / extreme_rain |
| POST | `/demo-start` | 正式软件演示模板 |
| POST | `/stop`、`/reset` | 暂停、归档并恢复日常状态 |
| POST | `/exposure` | DEV 人员/车辆参数 |
| GET | `/status` | 当前内涝状态 |
| GET | `/forecast?horizons=10,20,30` | 水位、面积与场景风险预测 |
| GET | `/storage` | 采样存储状态 |
| GET | `/scenarios`、`/snapshots/{scenario_id}` | 真实场景与历史采样 |

继续复用 `POST /api/v1/simulation/start`，速度、设备控制也复用原 API。事故期间独立天气控制返回 409，Reset 后可再次操作。快照每5个墙钟秒采样，不随 10× 速度提高写入频率；数据库不可用时仿真继续，界面提示并重试最新快照，中间点不保证补齐。单进程内存演化，后端重启不会自动接续旧事故。

```bash
npm --prefix frontend run build
npm --prefix frontend run test:flood
npm --prefix frontend run test:flood-state
(cd backend && .venv/bin/python -m pytest -q -W error)
```

查看 [M5 架构与公式](M5-architecture.md)、[M5 验收记录](M5-verification.md)、[M5 文件清单](M5-files.md)。

## M6 风险预测与训练

已完成M5的项目：安装更新后的 `backend/requirements-dev.txt`，执行 Alembic `upgrade head`，重启后端。新增迁移 `b655e1756d27`。打开 <http://127.0.0.1:5173/risk>；先在 `/simulation` 启动极端暴雨并选10×，再进入风险页观察物理预测、XGBoost预测、差异、一致度和解释。

仓库保留六个原生JSON模型和 metadata；启动只加载，不训练。若模型缺失、特征版本不符或文件校验失败，页面显示“模型未加载”，继续显示物理预测。重新生成/训练/评估使用项目虚拟环境：

```bash
backend/.venv/bin/python algorithm/risk_prediction/generate_dataset.py
backend/.venv/bin/python algorithm/risk_prediction/train.py
backend/.venv/bin/python algorithm/risk_prediction/evaluate.py
# 重启后端加载新模型
```

默认生成250个独立场景、60000条样本，30项共享特征；训练/验证/测试按整场场景分为170/40/40，禁止逐行随机切分。数据生成不连接实时Web服务，不会改变演示状态。完整 `training.npz` 被Git忽略；保留样例、分布报告、指标和模型。

输入包括当前雨量、水位、积水、上涨速度、各泵指令/效率/额定能力、P03故障信息、人员车辆和已知降雨计划。标签由真正的M5模型前推生成。HI/IF继续作为M3诊断展示，不另造诊断值作为训练特征。

实际测试集水位10/20/30分钟MAE约0.292/0.482/0.733cm，风险MAE约0.996/1.390/1.420分。完整MAE/RMSE/R²和风险等级一致率见 [metrics.json](../algorithm/risk_prediction/reports/metrics.json)，三组深度的验证比较见 [training_trials.json](../algorithm/risk_prediction/reports/training_trials.json)。这些指标只说明对当前软件仿真分布的拟合能力，不证明真实园区泛化。

当前规则贡献与未来ML贡献分开。全局增益保存在报告；当前+30分钟解释使用XGBoost原生TreeSHAP，无需独立shap包，失败时明确降级到增益×偏离度近似排序。模型一致度由水位/风险差异分档，不是概率置信度。

预测缓存约5秒、解释约10秒，当前场景每10墙钟秒保存一组预测。仿真实际达到预测时刻后，用相邻真实观测插值计算误差；未到期不造actual，Reset/进程重启中断未完成预测，保留数据库历史。后续人工操作引起的变化也会反映在误差中。

GET接口，前缀 `/api/v1/risk`：

| 路径 | 内容 |
|---|---|
| `/prediction?horizons=10,20,30` | 当前、物理/ML未来、差异与一致度 |
| `/model/status` | 模型版本、数据量、实际测试指标、推理耗时与存储状态 |
| `/prediction/explanation?minutes=30` | 支持10/20/30分钟的当前预测解释 |
| `/evaluation` | 当前场景已到期预测的真实MAE |
| `/predictions/{scenario_id}` | 历史预测与实际误差，最多300条 |

```bash
npm --prefix frontend run test:risk
npm --prefix frontend run build
(cd backend && .venv/bin/python -m pytest -q -W error)
```

当前仍使用简化物理模型和单worker内存引擎，不用于真实安全决策。详见 [M6架构](M6-architecture.md)、[M6验收](M6-verification.md)、[M6文件清单](M6-files.md)。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Vue Router、Pinia、Element Plus、Axios。
- 可视化：Three.js + OrbitControls + CSS2DRenderer + OutlinePass；ECharts 用于水位、设备趋势、健康仪表与偏离度贡献图。
- 后端：FastAPI、SQLAlchemy 2、Pydantic、psycopg、Uvicorn。
- 数据库：PostgreSQL 17（Docker Compose）；可连接现有 PostgreSQL。
- 仿真：Python asyncio、Pydantic 状态模型、FastAPI WebSocket；M3 使用 scikit-learn Isolation Forest；M6 使用六个 XGBoost 回归模型。

## 项目目录

```text
TwinCitySafe/
├── frontend/
│   ├── src/
│   │   ├── api/                  # Axios、Health 与实时状态/仿真控制 API
│   │   ├── assets/
│   │   ├── components/           # 三维容器、实时水位图、DEV 仿真控制
│   │   ├── three/                # 模块化 Web3D 引擎，详见 docs/M1-architecture.md
│   │   │   ├── core/
│   │   │   ├── building/
│   │   │   ├── pipeline/
│   │   │   ├── device/
│   │   │   ├── effects/
│   │   │   ├── interaction/
│   │   │   └── animation/
│   │   ├── views/                # Dashboard / Operation / Pipeline
│   │   │                        # Risk / Simulation / Review
│   │   ├── services/             # 单实例实时 WebSocket 客户端
│   │   ├── types/                # 实时 TypeScript 合同与运行时校验
│   │   ├── store/                # Health / Realtime Pinia store
│   │   ├── router/
│   │   ├── utils/
│   │   ├── App.vue
│   │   ├── main.ts
│   │   └── style.css
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── index.html
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── websocket/            # 消息封装、独立客户端队列与连接清理
│   │   ├── utils/
│   │   └── main.py
│   ├── simulator/               # Engine / Weather / Device / Flood / Pipeline
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── requirements.lock.txt
├── algorithm/                   # anomaly_detection / risk_prediction
│                                # graph_search / risk_engine
├── simulator/                   # M0 预留目录；M2 实现位于 backend/simulator
├── assets/                      # models / textures / mock_data
├── docs/
├── scripts/
│   ├── check-db.py
│   └── start-backend.py
├── .env.example
├── .gitignore
├── compose.yaml
├── start-dev.sh
└── README.md
```

## 系统要求

- Node.js 22.12+ 或 Node.js 24 LTS，npm。
- Python 3.11+，支持 `venv` 和 pip。
- Docker Engine/Desktop 和 Docker Compose v2，或已运行的 PostgreSQL。
- 自动启动脚本使用 Bash 4.3+、Linux `setsid`；macOS/Windows 请在两个终端分别启动服务。
- 首次安装需要网络。前端运行不依赖外部字体或在线模型资源。

以下命令均从 `TwinCitySafe/` 执行，除非命令包含 `cd`。

## 安装与环境变量

```bash
cp .env.example .env
cd frontend
npm ci
cd ..
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

本次验证环境为 Node.js 24、Python 3.13。`backend/requirements.lock.txt` 保存了本次验证的完整依赖版本，同类环境可用 `pip install -r backend/requirements.lock.txt` 复现；跨 Python 版本安装建议使用上面的范围依赖文件。

Windows 对应的 Python 路径为 `backend\.venv\Scripts\python.exe`。只运行服务时可安装 `requirements.txt`。

根目录 `.env` 是前后端共同配置源；不要提交本地 `.env`。后端按项目绝对路径加载它，操作系统环境变量优先。Vite 使用根目录作为 `envDir`，仅 `VITE_` 前缀的变量会暴露给浏览器。

| 变量 | 默认/示例 | 用途 |
|---|---|---|
| DATABASE_URL | 空 | 可选完整 SQLAlchemy URL；非空时优先于 POSTGRES_* |
| POSTGRES_HOST | 127.0.0.1 | 数据库主机 |
| POSTGRES_PORT | 5433 | 本机端口，避免与已有 5432 冲突 |
| POSTGRES_DB | twincitysafe | 数据库名 |
| POSTGRES_USER | twincity | 用户名 |
| POSTGRES_PASSWORD | twincity_local_dev | 仅供本机开发 |
| BACKEND_HOST / BACKEND_PORT | 127.0.0.1 / 8000 | 后端监听地址 |
| FRONTEND_PORT | 5173 | 前端端口 |
| CORS_ORIGINS | 本机 5173 两种地址的 JSON 数组 | 允许的前端源 |
| VITE_API_BASE_URL | /api/v1 | 浏览器请求 API 前缀 |
| VITE_API_PROXY_TARGET | http://127.0.0.1:8000 | Vite HTTP 与 WebSocket 开发代理目标 |
| VITE_WS_URL | 空 | 可选完整 ws:// 或 wss:// 地址；空时使用当前站点 /ws/realtime |

完整连接串格式：`postgresql+psycopg://USER:PASSWORD@HOST:PORT/DB`。密码有特殊字符时优先使用分项配置，程序负责转义。修改后端端口时同步修改代理目标；修改前端端口时同步修改 CORS。修改环境变量后重启服务。

默认 WebSocket 地址为 `ws://127.0.0.1:5173/ws/realtime`，由 Vite 的 `/ws` 代理转发到后端，代理开启 `ws: true` 并保留浏览器 Origin。HTTPS 页面自动使用 `wss:`。直接连接后端时可配置 `VITE_WS_URL=ws://127.0.0.1:8000/ws/realtime`，同时把真实前端源加入 `CORS_ORIGINS`。WebSocket 单独校验 Origin，只接受配置中的浏览器来源；不带 Origin 的命令行客户端允许连接。

## PostgreSQL 配置

### 使用项目 Docker 数据库

```bash
docker compose up -d --wait postgres
backend/.venv/bin/python scripts/check-db.py
```

成功输出 `PostgreSQL: Online (SELECT 1 passed)`。容器只绑定本机地址，使用具名卷持久化。`.env` 的 POSTGRES_* 用于首次创建数据库用户与数据库；已有卷不会因修改密码自动重置，请通过数据库管理操作更新用户信息。

停止数据库（保留数据）：

```bash
docker compose stop postgres
```

### 使用已有 PostgreSQL

由有权限的数据库管理员创建用户与数据库，然后将 `.env` 的 POSTGRES_* 设置为实际值。此时不需要运行 Docker Compose。M0/M2 未创建业务表；当前 M5 使用上方 Alembic 迁移，设备遥测和内涝快照分别每5秒采样。

## 启动方式

一键启动前后端：

```bash
./start-dev.sh
```

数据库不可用时会明确提示，前后端与 M2 内存仿真仍可启动。需要自动启动项目 Docker 数据库时：

```bash
START_POSTGRES=1 ./start-dev.sh
```

Ctrl+C 会停止该脚本启动的前后端，数据库保留运行。任一服务退出会清理另一项服务，避免遗留后台进程。

也可分两个终端启动：

```bash
# 终端 1：项目根目录
backend/.venv/bin/python scripts/start-backend.py
```

```bash
# 终端 2
cd frontend
npm run dev
```

默认页面：<http://127.0.0.1:5173/dashboard>，API 文档：<http://127.0.0.1:8000/docs>。

## Health API 与数据库验证

```bash
curl --fail http://127.0.0.1:8000/api/v1/health
curl --fail http://127.0.0.1:5173/api/v1/health
backend/.venv/bin/python scripts/check-db.py
```

两条 HTTP 请求都应返回：

```json
{"status":"ok","service":"TwinCitySafe","version":"2.0"}
```

第二条请求经过 Vite 代理，可检查前端到后端的通信链路。**Health 只表示 API 存活，不表示数据库就绪**；数据库独立使用 `SELECT 1` 检查，后端启动日志也会报告连接状态。

## M2 实时仿真与数据边界

后端在应用 lifespan 中创建一个 `SimulationEngine`，默认运行。仿真物理状态存在当前进程内存，重启后恢复初始值；M3 另有数据库采样与运行小时恢复。请以**单个 Uvicorn worker**运行，多个进程之间当前不共享状态。M2 不会每秒向 PostgreSQL 写入遥测。

- Weather：clear / cloudy / rain；数值向目标缓慢靠近，rain 的降雨目标约 14 mm/h。
- Device：P01、P02 默认 standby，P03 默认 running；温度、振动、电流、转速、效率连续变化。warning 是手动演示状态，不代表异常检测算法已接入。
- Water：B2 默认 0.8 cm，随进水与有效泵排水能力变化；M2 限制在 0.45–2.5 cm，属于低水位日常仿真。
- Pipeline：WS-001 给水、DS-001 排水、FS-001 消防，压力与流量平滑变化，状态维持 normal。
- System：在线数由 1265 个背景模拟设备与 3 台显式泵组成；warning/offline 泵计入当前告警，事件数为 0。

WebSocket 每秒发送一份完整状态，仿真速度范围为 0.25–10×，速度只改变模拟时间推进，推送频率保持 1 Hz。Stop 冻结模拟时间和遥测，连接与每秒心跳继续保留；Start 恢复推进。Reset 保留当前运行/暂停选择，恢复 clear、初始泵状态、0.8 cm 水位、模拟时间 0 和速度 1。

`sessionId` 标识后台引擎实例；`revision` 在心跳和控制操作后递增，Reset 不回退。前端据此拒绝过时响应。断线时保留最后一份数据，并显示 Disconnected；重连后恢复当前状态。App 统一管理一个连接，切换页面不会叠加 WebSocket。

## M2 API

| 方法 | 路径 | 请求 / 结果 |
|---|---|---|
| GET | `/api/v1/health` | 保留 M0 存活检测 |
| GET | `/api/v1/realtime/state` | 完整 `ParkRealtimeState` |
| GET | `/api/v1/simulation/status` | `running`、`speed`、`simulationTime` |
| POST | `/api/v1/simulation/start` | 恢复运行；重复调用幂等 |
| POST | `/api/v1/simulation/stop` | 暂停推进；重复调用幂等 |
| POST | `/api/v1/simulation/reset` | 恢复默认参数，保留运行状态 |
| POST | `/api/v1/simulation/weather` | `{"condition":"clear"}`；可选 clear/cloudy/rain |
| POST | `/api/v1/simulation/device/{device_id}/state` | `{"status":"running"}`；P01/P02/P03，支持 offline/standby/running/warning |
| POST | `/api/v1/simulation/speed` | `{"speed":2}`；数值范围 0.25–10 |
| WebSocket | `/ws/realtime` | 接入后立即发送快照，此后按 1 Hz 推送 |

所有仿真 POST 成功后返回完整状态；未知设备返回 404，无效参数返回 422。WebSocket 消息统一为：

```json
{
  "type": "REALTIME_STATE",
  "timestamp": "UTC ISO 8601 时间",
  "data": {
    "timestamp": "与消息时间相同",
    "sessionId": "本次引擎实例 UUID",
    "revision": 1,
    "simulationTime": 1,
    "running": true,
    "speed": 1,
    "weather": {},
    "environment": {},
    "devices": [],
    "pipelines": [],
    "system": {}
  }
}
```

上例仅展示消息结构；完整字段、单位和状态语义见 [M2 架构说明](M2-architecture.md) 与 `/docs`。

```bash
curl --fail http://127.0.0.1:8000/api/v1/realtime/state
curl --fail http://127.0.0.1:8000/api/v1/simulation/status
curl --fail -X POST http://127.0.0.1:8000/api/v1/simulation/weather \
  -H 'Content-Type: application/json' -d '{"condition":"rain"}'
curl --fail -X POST http://127.0.0.1:8000/api/v1/simulation/device/P03/state \
  -H 'Content-Type: application/json' -d '{"status":"warning"}'
curl --fail -X POST http://127.0.0.1:8000/api/v1/simulation/speed \
  -H 'Content-Type: application/json' -d '{"speed":2}'
```

## 页面验证与演示

1. 打开 `/`，跳转到 `/dashboard`。中央显示可交互园区；浏览器需支持 WebGL 2 并启用图形加速。
2. 右上角保留“后端服务：Online”，并新增“实时数据：Connected”。Dashboard 标识为“实时仿真数据”，天气、水位、P03 与管线读数持续更新。
3. 开发模式打开“仿真控制”，选择 Weather → Rain。观察降雨与湿度逐渐上升、灯光调整、雨粒子出现，以及低水位缓慢变化。
4. 切换地下模式，查看 P01/P02/P03。把 P03 从 running 改为 warning、offline，再恢复 running；卡片与三维设备分别显示绿、橙、灰色状态。standby 为蓝青色。
5. 点击给水/排水/消防管线，详情中显示对应的实时压力、流量、状态和稳定 ID。水面按厘米换算场景高度，薄水层变化较小，可结合数值读数查看。
6. Stop 后仍应保持 Connected，数值与模拟时间冻结；Start 后继续。改变速度时，消息保持每秒一次。Reset 恢复默认并保留当前启停状态。
7. 停止后端，实时状态会转为 Disconnected，面板保留上次数据；恢复后端后自动重连。Health 在 App 初次加载时检查，点击状态按钮可重新检测。
8. 切换其他五个页面再返回 Dashboard，连接保持单实例，三维场景会重新创建并应用当前状态。
9. 水位图只保留最近 60 个模拟时间发生变化的采样；暂停心跳不重复追加点，Reset 或后台新会话会清空旧序列。无事故时风险页显示暂无活动事故；M5 事故存在时显示明确标注的内涝场景风险。事件回放已在 M9 `/review` 接入，读取独立历史数据源。

“仿真控制”只在 `import.meta.env.DEV` 下显示，生产构建隐藏该面板；这不等同于给开发控制 API 添加身份认证。当前按本机开发配置运行。

## 构建与测试

```bash
cd frontend
npm run build
npm run test:web3d
npm run test:realtime
cd ../backend
.venv/bin/python -m pytest -q
```

构建执行严格 TypeScript 检查。`test:web3d` 复现 M1 三维交互回归；`test:realtime` 检查 M2 实时状态与场景联动，均需先启动前后端开发服务。浏览器配置见下文 M1 检查说明。后端测试覆盖 Health/CORS、实时 schema、控制 API、平滑性、暂停/重置、速度、水位边界、WebSocket 频率、多客户端、Origin 与断连清理。具体执行结果与环境限制见 [M2 验证记录](M2-verification.md)。`test:realtime` 可用 `M2_BASE_URL` 指定开发站点、`M2_SCREENSHOT_DIR` 指定截图目录，并支持同样的 `CHROME_PATH` 浏览器配置。

生产部署静态站点时，需要 SPA history 回退、`/api` HTTP 反向代理及 `/ws` WebSocket Upgrade 转发；Vite 代理仅用于开发。当前内存引擎应保持单 worker。M0 的工程与数据库验证保留在 [M0 验证记录](M0-verification.md)。

## 当前与后续 Milestone

| 阶段 | 内容 |
|---|---|
| M0（已完成） | Project Foundation |
| M1（已完成） | Web3D Digital Twin Foundation |
| M2（已完成） | Realtime Simulation Engine |
| M3（已完成） | Smart Equipment Operation |
| M4（已完成） | Underground Pipeline Digital Twin |
| M5（已完成） | Rainstorm & Flood Simulation |
| M6（已完成） | Risk Prediction Engine |
| M7（已完成） | Emergency Plan Simulation |
| M8（已完成） | Pipeline Leakage Scenario |
| M9（当前，已完成） | Timeline Replay & Incident Review |
| M10 | Competition Visual Optimization & Final Integration |

M0 提供工程与服务基础，M1 提供模块化场景，M2 接入连续软件仿真与实时联动。M3 已接入设备诊断与采样历史，M4 已完成管网拓扑数字底座，M5 已完成暴雨内涝演化、规则风险与水位外推。M6 已完成软件仿真分布下的 ML 预测、解释与真实后续观测对照。M7 已接入方案反事实推演与仿真执行。M8 已接入管网异常检测、定位、影响分析和确认隔离。M9 已接入工单闭环、正式关闭和持久化历史复盘。当前停止于 M9，等待新的指示后再进入 M10。

## 开发页面白屏排查

若 HTML 和 Health 正常但页面空白，检查浏览器模块请求是否出现 `504 Outdated Optimize Dep`。开发命令已使用 `vite --force` 在启动时重建依赖缓存；遇到旧页面缓存时重启开发服务并使用 Ctrl+Shift+R 刷新。服务运行期间不要删除 `frontend/node_modules/.vite`。浏览器实测截图见 `docs/M0-dashboard.png`。

## M1 三维场景操作

- 左键拖动旋转、滚轮缩放、右键拖动平移；相机角度和距离有限制。
- 悬停建筑显示淡青轮廓；点击选择，显示建筑信息并平滑聚焦；双击或详情里的“聚焦建筑”可再次聚焦。
- 点击另一栋建筑替换选择；点击空白或“关闭详情”取消选择；“恢复视角”回到园区全景。
- 地上：四栋主要建筑、道路、绿地、广场与景观。地下：地面和建筑半透明，显示 B2 停车场、给水/排水/消防示意管线和 P01/P02/P03。
- M2 地下模式可拾取管线与停车场，地上透明建筑不会阻挡管线选择。风险模式中其他建筑仍使用集中配置的示例等级；M5 活跃场景的 B2 改用实际 FloodRisk 染色。
- 自动巡游依次经过入口、办公楼、科研楼、实验楼和地下停车场，每次飞行约 1.1 秒、停留约 1.7 秒；停止按钮、手动操控或手动切换模式都会停止巡游。
- 右下角 FPS 为实测采样值，受显卡、浏览器图形加速、分辨率和选中轮廓影响。目标 45 FPS 以上需要在比赛设备上实测。
- 若出现场景加载错误，页面会显示提示与重新加载按钮。场景没有在线模型或外部纹理依赖。

M1 的结构、接口与稳定对象 ID 见 [架构说明](M1-architecture.md)，验证结果见 [验收记录](M1-verification.md)。

### 复现 M1 浏览器检查

先启动项目开发服务，再在 frontend/ 执行：

```bash
npm ci
# 若没有可用 Chrome：npx playwright install chromium
npm run test:web3d
```

可用 `CHROME_PATH=/path/to/chrome npm run test:web3d` 指定浏览器；默认使用本机 `/opt/google/chrome/chrome`，不存在时使用 Playwright 的 Chromium。该检查覆盖真实交互、相机、模式、巡游、重复进入页面、资源清理及 WebGL 丢失恢复，截图保存到 docs/。测试需要运行中的 Vite 开发服务；生产模式不暴露场景诊断属性。

## M7 应急方案推演

执行迁移 `adab6941d89a`（继承实际 M6 head `b655e1756d27`），再启动后端。启动会幂等补齐缺少的三个默认模板，不覆盖已有模板修改。新增四张表：`emergency_plan_templates`、`emergency_comparisons`、`emergency_executions`、`emergency_execution_steps`。

1. 打开 `/simulation`，选择“应急演示 · 暴雨后雨势回落”，确认软件仿真。此工况共 60 仿真分钟：沿用原极端暴雨至第 30 分钟，第 30–35 分钟从 100 回落到 20 mm/h。原 M5 持续暴雨按钮及工况保持可用。
2. DEV 选择 10×，到高风险后进入应急方案推演。建议先暂停：比较有效期为 30 **仿真秒**，10× 时约 3 墙钟秒。
3. 比较维持当前状态和 A（P01）、B（P01+P02）、C（双泵+东入口封控）的水位、风险、峰值、面积、阈值响应时间、资源指数与暴露。没有总评分或自动 Winner。
4. 选择卡片预览：蓝色泵轮廓、黄色拟封控入口；预览不改实时状态。确认“当前操作仅作用于软件仿真环境，不控制真实设备。”后提交执行。暂停时动作等待仿真时钟；点击继续后依次执行。
5. P01 启动、10 仿真秒后 P02 启动，各复用 M3 的 60 秒启动窗口；有效排量随进度增加。C 在第 20 秒封闭东入口，人员暴露按 300 秒时间常数渐减，现有车辆保留。取消仅停止未执行动作，不撤销已施加动作。
6. 观察水位增长放缓；在雨势回落后可观察水位与规则风险自然下降。Risk/Dashboard 显示活动方案；M5 物理和 M6 ML 随新状态刷新。动作完成不代表事件关闭。

**水量约束如实保留：** 100 mm/h × 12000 m² × 0.85 = 1020 m³/h 入流；既有 P01/P02/P03 额定各 120 m³/h，即使全部启动也不足以排空持续暴雨。因此原持续暴雨工况下 A/B 主要减缓上涨，响应时间可能 `>30 min`。雨势回落是显式、共用的环境边界条件，不能将全部风险降幅归因于泵或封控。C 与 B 在此模型中水位、积水面积相同，差别是人员暴露和资源指数；入口不是挡水闸。

成本为 `P01 运行分钟 + P02 运行分钟 + 新封控入口 10`，包含启动期间，不是人民币。响应时间是未来首次严格低于阈值的时刻，5 仿真秒采样；已低于阈值为 0，未达到为 null。曲线每分钟一个点，每分支 31 点。

API 前缀 `/api/v1/emergency`：GET `/plans?scenario_type=flood`、POST `/compare`（`plan_codes`, `horizon_minutes:30`）、POST `/preview`（`plan_code`, `horizon_minutes:30`）、POST `/execute`（`plan_code`, `comparison_id`, `confirmed_simulation:true`）、GET `/executions/{id}`、POST `/executions/{id}/cancel`、GET `/status`。另有 POST `/api/v1/simulation/flood/emergency-demo-start`。

执行必须引用本次服务保存的比较；场景、会话、入口、暴露、设备指令/故障/额定值改变，或超过 30 仿真秒、雨量差超过 5 mm/h、水位差超过 0.5 cm 时拒绝旧结果。后端再次校验模板、资源和状态。`BASELINE` 不可执行。阀门动作在统一枚举中预留，但 M7 验证器拒绝；当前模型没有逐段排水水力耦合，可继续在 M4 使用已有阀门控制。

**ML 边界：** 方案结果来自独立物理 rollout。XGBoost 不是因果决策模型，没有显式封控或待执行动作特征，不能用于评估方案干预。M6 已保存模型和历史训练报告保留；新雨势回落工况与 60 秒水力启动过渡未单独重新训练/认证，在线误差与模型差异需如实展示。物理预测会复制当前启动进度、封控状态和待执行动作。

`EMERGENCY_EVENT` 复用 `/ws/realtime`；每次完整快照也包含执行状态，断线后可恢复。执行日志单独异步写入数据库，开始动作前先持久化意图；存储失败不新启执行。重启将未完成记录标为失败，不自动恢复设备动作。

```bash
npm --prefix frontend run test:emergency
(cd backend && .venv/bin/python -m pytest -q -W error)
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
npm --prefix frontend run build
```

浏览器脚本操作同一仿真引擎，应顺序运行。`M7_OUTPUT_DIR` 可重定向 M7 截图和结果。详见 [M7 架构](M7-architecture.md)、[M7 验收记录](M7-verification.md)、[文件清单](M7-files.md)。


## M8 管网泄漏事故

先执行 `backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head`，M8 revision 为 `f6f65d1e093a`（M9 head 为 `9fdda90bd972`）。使用既有 M4 资产，不需要重置数据库或重新训练 M6 模型。

进入 `/pipeline` → **泄漏事故模式** → 启动软件演示 → DEV 选择 10× → 观察压力下降、流量异常、Top 3 排名和影响建筑 → 暂停后比较隔离候选 → 预览 → 确认“仅作用于软件仿真，不控制真实阀门。” → 继续观察泄漏流量和风险逐步下降。最终状态为 **CONTAINED / STABILIZING + INTERRUPTED**：泄漏受控，建筑仍停水，事件未关闭。

主演示 WS-003、severity 0.75 集中配置；定位结果由压力/流量与原 M4 图推断，不直接读取注入 ID。WS-003 的隔离候选关闭 V-W-03 / V-W-02 / V-W-01，影响 2/4/5 栋建筑；只比较，没有自动“最佳方案”。比较有效期 60 仿真秒，图、阀门、疑似位置或显著压力/流量变化会拒绝旧结果。暂停时指令改变阀门状态，流量过渡待时钟恢复。

Leak 与 Flood 不能同时存在（包括暂停），需先 Reset。Dashboard 显示当前管网事故，Risk 明确“当前 ML 预测模型仅适用于内涝场景”，不生成泄漏 ML 预测。

**模型边界：** 软件示范管网；简化泄漏与连续压力/流量传播，非真实水力模型；Localization 为未校准软件异常匹配，非真实概率或因果诊断；不用于真实城市安全决策。隔离后供水中断不会凭空消失。Reset 保留历史、恢复本次隔离阀门；服务重启不续演，也不自动重开已保存的阀门。

```bash
npm --prefix frontend run build
npm --prefix frontend run test:leak
npm --prefix frontend run test:leak-state
(cd backend && .venv/bin/python -m pytest -q -W error)
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
```

所有浏览器测试操作同一后端，应顺序运行。`M8_OUTPUT_DIR` / `M8_STATE_OUTPUT` 可重定向产物；默认 Chrome 路径可由 `CHROME_PATH` 指定。API、模型、事务和资源边界见 [M8 架构](M8-architecture.md)，实际测试数据见 [M8 验收](M8-verification.md)，[完成报告](M8-completion-report.md) 与 [文件清单](M8-files.md)。


## M9 事件复盘与工单中心

在项目根目录先迁移，并显式回填旧事故索引：

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python scripts/backfill-incidents.py
# 若已有早期 M9 开发派生记录，可显式整理确证重复；保留来源证据，不改 M5–M8 原表。
# backend/.venv/bin/python scripts/backfill-incidents.py --reconcile-derived
./start-dev.sh
```

打开 <http://127.0.0.1:5173/review>。列表支持事故类型、状态、日期和关键词。选择事故后，历史场景默认暂停；可用 0.5/1/2/5× 播放、拖动时间轴、点击关键节点或图表跳转。下方提供处置前后观测、当时方案、实际执行、本事件已到期预测误差、工单和模板复盘报告。

M9 使用独立 Replay Store 和同一 Three.js 场景的历史模式，不运行模拟器，不修改当前设备或阀门。原始快照和 M9 新增动态快照共同提供数据。旧 M5 设备/入口、旧 M8 阀门/泄漏流量等未保存字段保持“未记录”；缺口保留前次有效观测。最多 2000 个真实样本，按需下采样，不补造规则时间点。

完整闭环演示：启动 M7 暴雨后雨势回落工况 → 高风险 → 暂停比较 → 选择 B 并确认 → 恢复时钟 → STABILIZING 且风险低于 60 → 复盘页工单接单、处理、完成 → 填写关闭说明 → 人工确认关闭 → 回放及生成报告。泄漏同理，在隔离后达到 CONTAINED/STABILIZING 时完成工单并关闭。关闭确认文字为：**“确认关闭该软件仿真事件？关闭后事件将进入历史复盘，不再作为当前活动事故。”**

正式关闭冻结当前引擎并解除活动事故引用，保留泵、阀门、环境读数和供水影响；不会自动恢复正常。已关闭泄漏留下的阀门须在原 M4 控制中明确重开。开发 Reset/重启中断是 ABORTED，不能代替正常 CLOSED；回填和再次 Reset 不覆盖已关闭档案。

```bash
npm --prefix frontend run test:review-state
# 以下两个脚本顺序执行：前者产生完整 CLOSED 档案，后者使用其真实数据库历史。
npm --prefix frontend run test:incident-lifecycle
npm --prefix frontend run test:review
npm --prefix frontend run build
(cd backend && .venv/bin/python -m pytest -q -W error)
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
```

`M9_OUTPUT_DIR` 指定新截图和结果目录；状态 fixture 另用 `M9_STATE_OUTPUT`。所有真实事故浏览器脚本共用引擎，必须顺序运行。默认 Chrome 可由 `CHROME_PATH` 覆盖。详见 [M9 架构](M9-architecture.md)、[API 合同](M9-api-contract.md)、[验收记录](M9-verification.md)、[完成报告](M9-completion-report.md)。
