# M10 验收记录

Milestone 10 — Competition Visual Optimization & Final Integration。TwinCitySafe V1.0 比赛展示版本；基于 M1–M9 增量优化，未训练新模型或重写核心引擎。最终启动入口 <http://127.0.0.1:5173/dashboard?demo=1>。

## 复现

```bash
./prepare-demo.sh
./start-demo.sh
# 另一个终端；真实浏览器共享引擎，务必顺序运行
npm --prefix frontend run test:final-demo
backend/.venv/bin/python scripts/verify-final-state.py
```

开发回归使用显式 `VITE_ENABLE_DEV_CONTROLS=true ./start-dev.sh`；生产比赛构建使用 `VITE_ENABLE_DEV_CONTROLS=false`。完整历史回归入口 `python3 scripts/run-final-regression.py`，截图 `/tmp/m10-m*`，JSON与日志复制至 `docs/final`，原 M1–M9 产物未覆盖。回归中的缓存测试使用局部 fixture，真实事故闭环使用实际 REST、WebSocket、PostgreSQL 和 Three.js。

## 最终结果

| 项目 | 本轮实际结果 | 证据 |
|---|---|---|
| 后端完整 pytest | 145 passed，84.74s；warnings 作为错误 | [日志](final/M10-backend.log) |
| Alembic | No new upgrade operations detected | [日志](final/M10-migration-check.log) |
| 幂等准备与生产构建 | 通过，无自动训练、无删除历史 | [日志](final/M10-prepare-build.log) |
| 正式启动 | 生产后端 + 本地构建预览，实际服务就绪 | [日志](final/M10-start-demo.log) |
| Final Smoke | 12 组通过，errors=[] | [结果](final/M10-final-smoke-results.json) |
| 质量档位 | 4 组通过，errors=[] | [结果](final/M10-quality-results.json) |
| 十轮导航 | 60 次路由访问，单业务 WS，0 遗留 RAF / Canvas / WebGL | [结果](final/M10-navigation-results.json) |
| 独立故障恢复 | 5 组真实环境检查，应用 errors=[] | [结果](final/M10-recovery-results.json) |
| 布局 | 六页 × 1920 / 1440 / 1366；无横向溢出 | [检查](final/ui-check/layout-results.json) |
| 最终正常状态与档案 | 全部演示阀门开启，两类 CLOSED 及完成工单保留 | [只读核验](final/M10-final-state.json) |

## M1–M9 完整回归

| 脚本 | 结果 | 证据 |
|---|---|---|
| web3d | 通过，61.05s | [日志](final/M10-web3d-regression.log) |
| realtime | 通过，77.18s | [日志](final/M10-realtime-regression.log) |
| operation | 通过，40.52s | [日志](final/M10-operation-regression.log) |
| operation-state | 通过，1.58s | [日志](final/M10-operation-state-regression.log) |
| pipeline | 通过，52.73s | [日志](final/M10-pipeline-regression.log) |
| flood | 通过，196.43s | [日志](final/M10-flood-regression.log) |
| flood-state | 通过，2.18s | [日志](final/M10-flood-state-regression.log) |
| risk | 通过，118.36s | [日志](final/M10-risk-regression.log) |
| emergency | 通过，288.44s | [日志](final/M10-emergency-regression.log) |
| leak | 通过，138.20s | [日志](final/M10-leak-regression.log) |
| leak-state | 通过，2.47s | [日志](final/M10-leak-state-regression.log) |
| review-state | 通过，1.10s | [日志](final/M10-review-state-regression.log) |
| incident-lifecycle | 通过，329.25s | [日志](final/M10-incident-lifecycle-regression.log) |
| review | 通过，171.18s | [日志](final/M10-review-regression.log) |
| review-legacy | 通过，3.09s | [日志](final/M10-review-legacy-regression.log) |

合计 15 个历史浏览器脚本，包含 4 个局部缓存/状态 fixture；新增质量、导航、故障恢复、Final Demo 共 4 个浏览器验收脚本。脚本数量不等同单条断言数量或真实事故数量。M2 断网和独立故障注入预期网络错误单列，未作为正常业务错误忽略。

## 生产包真实闭环

Final Demo 在生产后端和最终 dist 中运行，通过可见 Demo 控件启动、暂停、继续、重置；所有方案比较、执行、工单流转、关闭均经真实 UI 与确认框。没有 `/src` 模块注入，没有伪造物理状态、跳到终帧或假 actual。正常页面不显示开发控件；真实 Fullscreen API 可用，外部 HTTP 请求被阻断时本地页面仍运行，未发现外部依赖请求。

Flood 使用原 M7 雨势回落工况：第30–35分钟100→20 mm/h。P03退化、泵启动过渡、雨量和水位来自原模型；不能把风险下降全部归因于双泵。Leak 根据真实观测定位 WS-003，人工执行 V-W-03，受控后仍保留两栋建筑供水中断。关闭与重置分别核验；前者保留物理末态，后者显式恢复演示状态。

| 类型 | 本轮档案 | 最终状态 | 观测 / 时间轴条目 |
|---|---|---|---|
| FLOOD | `ae4f9617-3568-5be0-9170-83f76971d53f` | CLOSED | 84 / 119 |
| PIPELINE_LEAK | `873f9e08-5e5d-5005-9cbb-6bea95c1081b` | CLOSED | 30 / 22 |

生产历史回放经实际 RAF 播放，游标从保存记录向后推进，实时物理状态保持不变。长时回放、100次拖动、设备/阀门离散边界和2000点限制另由本轮 M9 全回归验证。原模型指标保留，本轮事件预测误差见 Final Smoke 内 metrics，不以 M6 原始评估替代。

## 性能与资源

生产冷页面到实时状态与三维 Canvas 挂载实测 **1053.9 ms**，这是本机一次采样，非所有设备首帧承诺。HTTP端到端样本包含序列化与数据库时间，重复调用可能命中缓存；应急比较样本来自真实独立 rollout 并保存比较记录。

| API | 次数 | 平均 | P95 |
|---|---:|---:|---:|
| health | 20 | 4.98 ms | 6.78 ms |
| realtime state | 20 | 5.42 ms | 6.97 ms |
| pipeline topology | 20 | 11.45 ms | 12.77 ms |
| active risk prediction (5s cache) | 20 | 5.66 ms | 11.53 ms |
| flood status | 20 | 4.64 ms | 5.87 ms |
| four-branch emergency compare (persists comparisons) | 10 | 222.62 ms | 283.44 ms |
| flood persisted replay | 20 | 137.66 ms | 137.57 ms |
| leak localization | 20 | 4.92 ms | 6.25 ms |
| leak persisted replay | 20 | 57.47 ms | 62.76 ms |

三档质量与FPS、渲染器、draw calls和资源稳定性见 [性能报告](final/M10-performance.md)。SwiftShader软件渲染不能证明比赛显卡达到45FPS。24次档位切换不重建Canvas，十轮导航释放所有旧上下文；M5/M7与M9回归记录加速事故及历史回放的资源数量。雨池/水面/热区复用，未以裁剪关键业务内容掩盖资源增长。

## 发现与修正

初查清理首页旧复盘占位、固定汇总和固定状态灯，修正水位图3cm上限与开发控件默认可见。图表统一时纯拓扑图曾出现未使用grid模块警告，已移除无用默认配置。导航探针初次将Vite HMR算作业务连接，修为仅统计 `/ws/realtime`；严格单业务连接断言保留。旧首页告警和无事故文案变更相应更新测试选择器，保留业务含义。正式切换时端口探针曾将TIME_WAIT误判占用，改用与服务一致的SO_REUSEADDR并验证仍拒绝真实监听端口，见 [启动修正](final/M10-startup-fix.md)。其余验收期间的失败与修正见对应日志和最终完成报告。

模型缺失时不显示“0条训练样本”，改为训练信息不可用；无事故风险视图的建筑着色继续明确标记示例。默认比赛截图无FPS和开发参数。允许纵向滚动；不声称1366屏幕能将全部技术表格同时放入首屏。

## 最终状态与边界

最终无活动 Flood / Leak；晴天，P01/P02待机，P03正常运行；10个演示阀门开启、入口开放，1×动态监测，模型就绪，两类新 CLOSED 档案保留。启动服务不会自动产生事故。

仅软件模型；无真实IoT/工程控制/精确水力/真实城市泛化/LLM自动决策。单 worker 内存时钟，服务重启终止旧活动事故；归档有界重试，长时间断库可能丢中间记录。模型一致度不是置信区间，SHAP不是因果解释，模板报告不是自动工程安全结论。比赛GPU与正式投屏环境仍应复验。

[32节最终完成报告](M10-completion-report.md) · [演示脚本](DEMO_SCRIPT.md) · [技术说明](TECHNICAL_OVERVIEW.md) · [数据来源审计](M10-data-source-audit.md) · [功能审计](M10-feature-audit.md)

## 截图复核与冻结

首轮生产闭环通过，但风险页截图早于首次预测刷新。已加强三时距ML、物理对照和模型解释的真实DOM就绪断言，完整重跑后采用第二轮12组通过结果。正式1366风险截图已目视确认预测数值、解释与两组未来曲线完整；泄漏与历史页已检查。所有页面无横向溢出；小屏长页面需纵向滚动，回放三维浮动长标签可能在视口边缘裁切，对应数值仍在历史摘要完整显示。部分事件步骤保留动作枚举标识，未影响操作。核心功能已冻结。
