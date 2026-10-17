# Milestone 0 验证记录

## 已完成

- 独立 TwinCitySafe monorepo、前后端分离、六个页面路由和深色 Dashboard 骨架。
- Pinia 管理后端连接状态，Dashboard 挂载时调用真实 Health API，提供手动重试。
- FastAPI schema/model/service/api 分层；PostgreSQL SQLAlchemy 连接、环境变量和本地 CORS。
- PostgreSQL 17 Docker Compose、数据库检查脚本、一键启动脚本及完整 README。
- Three.js / ECharts 依赖已安装，但未初始化场景和图表引擎；算法和仿真目录仅预留。

## 实际验证结果

| 检查 | 结果 |
|---|---|
| npm install | 成功，生成 package-lock.json |
| npm run build | 成功，严格 TypeScript 检查通过；无大包警告 |
| 后端依赖安装 | 成功，生成 requirements.lock.txt |
| pytest | 3 passed，无警告 |
| PostgreSQL 容器 | healthy，绑定 127.0.0.1:5433 |
| 数据库真实连接 | SELECT 1 成功，后端启动日志确认连接成功 |
| 8000 Health API | HTTP 200，JSON 与需求一致 |
| 5173 前端代理 Health API | HTTP 200，JSON 与需求一致 |
| 六个页面 URL | 全部 HTTP 200，返回应用入口 |
| 六个 Vue 页面开发编译 | 全部成功 |
| 一键启动 | 前后端成功启动 |
| 启动脚本清理 | SIGTERM 后两个应用端口均释放 |

生产构建主 JS 约 205.38 kB（gzip 78.74 kB），CSS 约 45.49 kB（gzip 7.81 kB）。

## 验证边界与已知限制

- 补充使用独立无头 Chrome 完成真实页面渲染、六个导航点击与刷新、Online/Offline 及恢复验证；正常加载阶段无 JavaScript 或控制台错误。截图见 `M0-dashboard.png`。
- Health 检查 API 存活；数据库连接必须单独使用 check-db.py 检查。
- Dashboard 指标为明确标注的 UI 示例数据。其余五页为待开发占位页，回放按钮禁用。
- 一键启动脚本面向 Linux Bash；其他平台分别启动前后端。
- 未实现 M1 及后续功能，未修改原有设计说明书和赛事材料。

## 下一阶段建议

确认 M0 后再进入 M1，实现 SceneManager、CameraManager、RendererManager、InteractionManager、ModelLoader、EffectManager 与基础园区场景。

## 白屏问题修复

复现时主文档与 Health API 正常，但 Vue、Pinia、Element Plus 模块请求返回 `504 Outdated Optimize Dep`，开发服务器引用的预构建依赖文件缺失。重启服务并重建缓存后恢复。`npm run dev` 改为 `vite --force`，每次开发启动重新优化依赖。补充本地图标，消除 favicon 404。

修改：`frontend/package.json`、`frontend/index.html`、本验证记录、README。新增：`docs/M0-dashboard.png`。未进入 M1。
