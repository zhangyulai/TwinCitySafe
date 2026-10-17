# M9 验收记录

## 范围与复现

Milestone 9 — Timeline Replay & Incident Review。覆盖 Flood/Leak 统一档案、时间轴、历史三维回放、指标、工单、关闭及模板报告；不进入 M10。开发入口：<http://127.0.0.1:5173/review>。

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python scripts/backfill-incidents.py
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
npm --prefix frontend run build
npm --prefix frontend run test:review-state
npm --prefix frontend run test:incident-lifecycle
npm --prefix frontend run test:review
# 已有旧 Leak 档案时，可复现未知天气隔离检查：
npm --prefix frontend run test:review-legacy
backend/.venv/bin/python scripts/verify-incident-archives.py
(cd backend && .venv/bin/python -m pytest -q -W error)
```

浏览器脚本共用真实 5173/8000 服务与 PostgreSQL，应顺序执行。Chrome 默认 `/opt/google/chrome/chrome`，支持 `CHROME_PATH`。M9_OUTPUT_DIR 控制闭环和回放结果；M9_STATE_OUTPUT 控制状态 fixture。数据库核验脚本读取默认 docs/M9-lifecycle-results.json。测试结束保留已关闭档案，并通过原 M4 API 明确重开演示阀门；这些清理动作与业务关闭分开。

## 最终检查

| 检查 | 结果 | 证据 |
|---|---|---|
| 完整后端 pytest | **134 passed，65.11s**，warnings 视为错误；原有107项 + M9新增27项 | [日志](M9-backend.log) |
| Vue / TypeScript 生产构建 | 通过，6.93s | [日志](M9-build.log) |
| Alembic | head 9fdda90bd972；No new upgrade operations detected | [日志](M9-migration-check.log) |
| 真实两类事故闭环 | 7组通过，errors=[] | [结果](M9-lifecycle-results.json)、[日志](M9-lifecycle.log) |
| 真实历史浏览器回放 | 7组通过，errors=[] | [结果](M9-browser-results.json)、[日志](M9-review.log) |
| Replay Store 边界 | 通过，局部状态 fixture 与真实网络证据分开 | [结果](M9-state-results.json) |
| 旧天气跨事件隔离 | 真实 Leak→Flood→Leak，无天气字段倒填、同Canvas、errors=[] | [结果](M9-weather-isolation.json) |
| 历史回填及派生去重 | 两次均未新建事故；首次合并9个别名，第二次0；9张原表 count/hash不变 | [日志](M9-backfill.log)、[数据库](M9-backfill-database.json) |
| 档案数据库核验 | 两类CLOSED、各一张完成工单和一条关闭事件，GET前后档案表hash不变，32管段/3台泵保留 | [结果](M9-database-results.json) |

### M1–M8 回归

| 检查 | 实际结果 | 证据 |
|---|---|---|
| web3d | 通过，64.60s | [日志](M9-web3d-regression.log) |
| realtime | 通过，76.47s | [日志](M9-realtime-regression.log) |
| operation | 通过，40.67s | [日志](M9-operation-regression.log) |
| operation-state | 通过，1.80s | [日志](M9-operation-state-regression.log) |
| pipeline | 通过，52.09s | [日志](M9-pipeline-regression.log) |
| flood | 通过，196.60s | [日志](M9-flood-regression.log) |
| flood-state | 通过，2.17s | [日志](M9-flood-state-regression.log) |
| risk | 通过，118.18s | [日志](M9-risk-regression.log) |
| emergency | 通过，288.28s | [日志](M9-emergency-regression.log) |
| leak | 通过，138.40s | [日志](M9-leak-regression.log) |
| leak-state | 通过，2.58s | [日志](M9-leak-state-regression.log) |

M1–M8 本轮截图与原JSON在 `/tmp/m9-m*`，各日志和 [统一结果](M9-regression-results.json) 保存在 docs。原里程碑验收产物未覆盖。M2 人工断网产生的预期错误单独记录；恢复后单连接。上述回归之后仅收紧了 M9 关闭、历史天气、采样/时间轴边界，最终完整 pytest、M9真实闭环与回放使用修复后的代码。

## 后端和状态边界

27项后端检查覆盖来源聚合、反复回填、GET不写历史、时间轴顺序与语义去重、旧历史缺失、真实峰值和到期预测、报告、工单状态机、非法关闭/重复关闭、Reset与CLOSED区分、当前与旧事故隔离，以及真实 Flood C/Leak 关闭后的物理保留。

4108个输入观测的限量测试保留不超过2000个真实点；范围和步长校验通过。同一暂停时刻操作前后保留，关闭→重开→再关闭不当成重复重试，只有timestamp改变的重试不新增。正常10×下每5墙钟秒采样不误报缺口，真正缺测才提示。

Replay Store 检查连续插值、按ID对齐设备/管段、阀门/泵/入口离散边界、乱序输入、显式null、不借未来字段、跨缺口保留前值、速度/暂停/末尾停止、单RAF、切事件与dispose。旧 M5/M8 缺少的设备、入口、阀门、估算泄漏流量不会从终态补齐。旧 Leak 缺天气时使用静态光照基准，未写入任何weather观测。

## 真实 Flood 闭环

[直接查看本次档案](http://127.0.0.1:5173/review?incident=fdf4ffe4-caee-56c2-9769-93b4c65c6ec8)。事件 `fdf4ffe4-caee-56c2-9769-93b4c65c6ec8`，真实 M7 暴雨后雨势回落工况，10×推进；高风险时暂停比较四分支，人工选择B，恢复时钟。达到 T+41.76min、STABILIZING且风险低于60后，经UI接单→处理→完成→准确确认文字关闭。

| 观测 | 首次执行前 | 关闭前最后观测 |
|---|---:|---:|
| 规则风险 | 82.734 | 47.000 |
| 水位 cm | 24.946 | 26.641 |
| 有效泵能力 m³/s | 0.025333 | 0.089490 |
| 雨量 mm/h | 100.000 | 20.000 |

峰值水位 27.582cm，峰值风险 82.734。后期水位已从峰值下降，但高于执行前水位；不能描述成“方案立即排空”。雨量回落与泵排水共同作用。关闭保存 102 个合并观测（其中 56 个完整M9动态帧）、103 条时间轴，保留比较、执行和报告。

本事件实际到期样本 **39** 个：ML水位MAE **2.1955cm**、风险MAE **13.6647分**；物理水位MAE 0.7014cm、风险MAE 3.7012分。后续人工干预及雨势回落使误差明显，不能以M6原始独立测试集高精度代替这次实际误差，不把ML当作因果方案评价模型。

## 真实 Leak 闭环

[直接查看本次档案](http://127.0.0.1:5173/review?incident=c6f2a669-ec95-5cc0-ace6-5df329a9b847)。事件 `c6f2a669-ec95-5cc0-ace6-5df329a9b847`。真实推进到疑似定位WS-003并确认，暂停比较后执行V-W-03隔离，再继续到 T+10.15min。泄漏流量从 20.939m³/h 衰减到 0.00000074m³/h，规则风险从 61.888降至6.000。供水状态仍 **INTERRUPTED**，科研楼B、实验楼C两栋建筑仍受影响。

工单经UI完整流转后人工关闭，保存 31 个合并观测（22 个完整M9帧）、23 条时间轴。关闭前后泵、阀门、管段、环境读数、入口和场景物理字段相等；V-W-03仍关闭。重复关闭不改变说明、不新增Timeline。Leak没有调用内涝ML，不生成泄漏预测误差。

## Replay 实测与资源

进入历史档案默认暂停，播放/暂停/停止、0.5/1/2/5×、关键节点、四个单独单位图表、游标、报告和完成工单均经真实UI验证。Flood水位/热区随真实历史变化；Leak压力、流量、排名、粒子、隔离灰化和历史阀门状态正确。回放中历史V-W-03显示closed，当前M4 V-W-03仍open；实时state各物理字段和事故引用全程不变。

| 检查 | 实测 |
|---|---|
| Flood Replay服务耗时 | 36.254ms，102点 |
| Leak Replay服务耗时 | 18.08ms，31点 |
| 100次scrub | geometry 74→74，material 98→98，texture 0→0 |
| 真实RAF播放 | 5×，120.872墙钟秒，推进601.476历史秒 |
| 播放后资源 | geometry 74、material 98、texture 0，与预热后相等 |
| 场景切换 | Flood→Leak→Flood沿用同一个Three Canvas、一个ECharts实例 |
| 退出页面 | 全部Canvas释放，待执行RAF=0；App保持单WebSocket |
| 布局 | 1920与1440可读，无页面横向溢出 |

初次脚本的异步等待谓词不能证明实际播放时长，已改为同步状态等待，并额外断言历史推进≥600秒、墙钟≥110秒；本报告只采用重新运行后的结果。播放期间采样约 **28 FPS**，[渲染器实测](M9-renderer.json)为Headless Chrome/ANGLE SwiftShader软件渲染，不证明比赛GPU达到45 FPS目标。资源计数为当前已渲染对象的实测值，未把首次分配和持续增长混淆。

## 页面截图

- [Flood峰值回放](M9-flood-peak.png)
- [Leak异常回放](M9-leak-active.png)
- [Leak关闭末态](M9-leak-closed.png)
- [1440时间轴布局](M9-review-1440.png)
- [完整历史曲线](M9-timeline-chart.png)
- [Flood模板报告](M9-flood-report.png)
- [Leak模板报告](M9-leak-report.png)

已检查1920 Flood、Leak及1440截图：历史模式标识、三维对象、摘要、时间轴可读，未发生页面溢出。报告基于数据库事实，不调用LLM。Unknown数据灰化；新的静态天气回退不作为历史观测。

## 当前边界

- 回放是持久化软件仿真记录，不是重新仿真；显示插值不代表新增实测点。旧缺失不可恢复，超出2000个必须离散边界时metadata明确提示裁减。
- 响应时间为原始墙钟差值，图表/回放为事故相对仿真秒；缺少时间或actual返回null。
- Close解除活动引用并冻结，保留入口封控、积水、设备、阀门和供水影响。Reset/服务重启为ABORTED，已CLOSED不被覆盖。
- 单worker内存引擎；归档队列128条且有界重试，长时间断库不能保证全部中间历史补齐。报告保留最新一次生成版本。
- 字符串班组，无复杂权限、真实人员调度、LLM Agent、移动端或PDF导出。软件模型和规则复盘不能用于真实安全决策。

Milestone 9 已完成，当前停止开发，等待进入 Milestone 10。
