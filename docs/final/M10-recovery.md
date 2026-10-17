# M10 真实故障与恢复验证

本轮在独立环境执行，未停止或修改主 5173/8000 服务及比赛数据库。结果：[M10-recovery-results.json](M10-recovery-results.json)，执行日志：[M10-recovery.log](M10-recovery.log)。五组检查通过，应用 `pageerror` 与非故障阶段错误为零；八条受控断线期间的网络错误单独保存，没有伪称为始终在线。

## 环境与复现

使用本机已有 `postgres:17-alpine` 镜像，Docker 参数 `--pull never`，不下载镜像。临时数据库只开放本机 15433，专属生产模式 FastAPI 后端 18000（单 worker、无 reload），独立 Vite 前端 15173；数据库名 `recovery`，全程通过专用子进程环境指定。后端启用正式 `DEMO_MODE=true`，浏览器运行当前真实 Vue 应用与实时连接模块。此项使用开发前端便于独立代理；最终生产 bundle 闭环另由 Final Smoke 验证。

```bash
node frontend/scripts/verify-system-recovery.cjs --run-isolated
```

不带 `--run-isolated` 只打印说明。启动前拒绝端口占用，使用唯一临时容器名；完成或失败均清理自己创建的进程、容器、匿名数据卷与空模型目录。实际记录 `cleanedIsolatedContainer=true`，测试后 15433/18000/15173 均已释放。

## 实际结果

| 检查 | 操作与观测 |
|---|---|
| 初始就绪 | 对空临时库执行真实 migration 和幂等 seed；数据库、34 节点/32 管段/10 阀门、设备异常模型、六个风险模型均可用，真实浏览器单 WebSocket |
| 数据库中断与恢复 | 实际停止临时 PostgreSQL 进程，readiness 数据库项转不可用，设备资产 GET 返回 503；原 WebSocket 不断，内存仿真时间 2.024→3.036 秒，页面仍存在；重新启动数据库后，readiness 恢复，资产 GET 返回三台泵 |
| 后端实际重启 | 停止并重启临时生产后端；原 Vue 连接模块显示 Disconnected、保留旧 session 快照，自动重试共创建四次连接尝试，恢复后仅一条 OPEN 连接，并收到新 session 的真实状态；没有手工触发前端重连或伪造 socket 事件 |
| 模型文件真实缺失 | 重启子进程，将 `ANOMALY_MODEL_PATH` 和 `RISK_MODEL_DIR` 指向独立临时空路径，未替换项目模型；readiness 为 degraded、core_ready=true，两个模型组件明确不可用。真实启动 Flood 后，API 返回三个物理预测点与零个 ML 点；Risk 页面保留物理数值与趋势，显示“模型未加载，保留物理预测” |
| 恢复与历史中断 | 再次启动临时后端并恢复默认模型路径，readiness 全部 ready，浏览器单连接恢复；此前未关闭的真实 Flood 在数据库归档为 ABORTED，不伪装正式关闭 |

模型缺失真实页面已人工检查：[M10-model-missing-real.png](M10-model-missing-real.png)。加载失败使用真实文件路径检查，未使用 HTTP 响应 fixture；模型恢复不重新训练，未修改 M3/M6 的模型与训练报告。

## 配套日志与边界

- [隔离库迁移准备](M10-recovery-prepare.log)
- [生产后端启停](M10-recovery-backend.log)
- [真实缺失模型后端](M10-recovery-backend-models-missing.log)
- [独立前端与代理](M10-recovery-frontend.log)

受控中断可能记录连接拒绝、连接关闭与 Vite 代理错误，这些属于操作刻意造成的传输失败。此验证证明短时故障的分项降级与重连；不证明长期断库可以补齐全部中间历史，也不改变 M9 单 worker、有界存储重试及缺测不补造的边界。WebGL 丢失与恢复由 Three.js 回归单独验证。
