# 孪城智安 TwinCitySafe

基于 Web3D 数字孪生与智能风险研判的智慧园区运维安全平台。

构建监测—预测—推演—处置—复盘一体化园区安全闭环。V1.0 比赛展示版本已完成，核心功能冻结。后端145项测试、M1–M9共15项回归及最终生产闭环12组检查通过。详见 [M10验收记录](docs/M10-verification.md) 和 [32节最终完成报告](docs/M10-completion-report.md)。

当前前端采用深蓝科技风工作台：统一六大业务入口、蓝色发光控件与数字孪生三维园区。启用 `VITE_ENABLE_ONLINE_GIS=true` 时，三维园区将 OpenStreetMap 在线真实道路、地名与建筑轮廓绘制为 GIS 地面纹理，再叠加项目的可交互三维建筑、道路、设备、管网和风险资产，全部使用同一地理坐标系；网络不可用时自动保留本地公开 GIS 底座。场景工具栏的“二维 GIS”可单独查看底图。配置高德 Web JS API 后二维查看器会自动优先使用高德三维地图。仿真泵、管网与风险标记仍是软件资产映射，不是实际园区的测绘或 BIM 数据。M10 历史记录和此前的视频保留原版界面。

已有 Python 虚拟环境、Node 依赖和 PostgreSQL 时，在项目根目录执行：

```bash
cp .env.example .env  # 已有 .env 时保留原配置，不要覆盖
./prepare-demo.sh
./start-demo.sh
```

访问 <http://127.0.0.1:5173/dashboard?demo=1>。正式启动使用生产后端和本地构建产物，无自动事故、无启动训练。关闭终端前按 Ctrl+C；数据库及历史档案保留。可用 `OPEN_BROWSER=1 ./start-demo.sh` 尝试打开系统浏览器。

六大页面：综合态势、智慧运维、地下管网、风险研判、应急推演、事件复盘。首页或演示控制栏选择暴雨 / 泄漏并启动，默认 10×；通过暂停、比较、人工确认处置完成闭环。演示重置保留历史；正式事件关闭保留积水、阀门和供水影响。

设备、地下管网、内涝、泄漏与应急方案均为软件仿真资产，页面已明确标注其空间位置仅用于业务联动，不能作为实际园区的地下基础设施测绘资料。

## 首次准备

环境：Linux、Python 3.13、Node.js 24、PostgreSQL 17；以依赖锁定文件为准。默认离线 GIS 演示不使用 CDN、外部字体或在线模型；启用“真实 GIS”时需要访问 OpenStreetMap 或高德地图在线服务。

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
cp .env.example .env
# 配置本地 PostgreSQL；使用项目容器时：
docker compose up -d --wait postgres
./prepare-demo.sh
./start-demo.sh
```

`prepare-demo.sh` 幂等迁移、初始化缺少的资产、检查已保存模型并构建前端，不重新训练、不清理档案、不复位运行事故。已有 `.env` 请直接编辑而非复制覆盖。数据库准备与安全备份见 [DEMO_DATABASE.md](docs/DEMO_DATABASE.md)。比赛机器需提前完成依赖和数据准备。

## 比赛运行

- 三维质量默认“精细”；可选“均衡 / 性能”，按比赛设备实测选择。`?debug=1` 显示 FPS；全屏展示隐藏调试信息。
- 顶部“系统状态 / 系统自检”分别检查服务、数据库、模型、管网与浏览器连接。缺失风险模型时保留物理预测。
- `start-demo.sh` 显式以 `DEMO_MODE=true` 启用比赛控制。普通生产环境默认关闭该新控制接口。
- 开发参数默认隐藏。仅需要研发回归时用 `VITE_ENABLE_DEV_CONTROLS=true ./start-dev.sh`；正式构建使用 `VITE_ENABLE_DEV_CONTROLS=false npm --prefix frontend run build`。
- 前后端默认端口 5173 / 8000，数据库默认 5433。通过 `.env` 配置；不要同时运行开发版和比赛版占用相同端口。
- 真实 GIS 需要在根目录 `.env` 填写 `VITE_AMAP_KEY` 与 `VITE_AMAP_SECURITY_JS_CODE`，然后重新运行 `./start-demo.sh` 使前端重新构建。高德控制台中创建的 Web 端（JS API）Key 需要与安全密钥配套；未配置时系统自动保留离线 GIS 底座。
- 可手动分别启动，脚本入口见 [项目结构](docs/final/PROJECT_STRUCTURE.md)。不向公网公开未经认证的演示控制。

## 验证与资料

```bash
npm --prefix frontend run build
(cd frontend && npm run test:web3d)
(cd backend && .venv/bin/python -m pytest -q -W error)
# 真实浏览器脚本共用同一仿真引擎，必须顺序运行
npm --prefix frontend run test:final-demo
```

浏览器验收默认 `/opt/google/chrome/chrome`，支持 `CHROME_PATH`。Final Demo 会启动真实软件事故、操作工单并保存关闭档案，结束恢复正常监测。全部 M1–M9 回归与异常恢复证据见 [M10 验收](docs/M10-verification.md)，历史验收从未覆盖。

- [5 分钟 / 8 分钟操作脚本](docs/DEMO_SCRIPT.md)
- [技术说明](docs/TECHNICAL_OVERVIEW.md) · [竞赛事实](docs/COMPETITION_FACTS.md)
- [数据来源审计](docs/M10-data-source-audit.md) · [功能审计](docs/M10-feature-audit.md)
- [性能记录](docs/final/M10-performance.md) · [开发历史](docs/DEVELOPMENT_HISTORY.md)

本平台数据来自软件仿真和保存的历史记录。Isolation Forest 用于设备异常，XGBoost 学习内涝仿真分布，图搜索用于管网拓扑，物理副本用于方案比较；未使用大模型决策。模型一致度不是置信区间，SHAP 不是因果解释，软件演示不能用于真实安全决策。
