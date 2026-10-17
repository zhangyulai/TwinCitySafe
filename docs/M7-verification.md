# M7 验收记录

## 范围与复现

Emergency Plan Simulation：同一基线的四分支物理推演、模板与资源校验、比较持久化、过期拒绝、人工确认仿真执行、启动过渡、入口封控、事件流、三维与 M6 联动。停止在 M7，不执行 M8/M9。

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
npm --prefix frontend run build
npm --prefix frontend run test:emergency
npm --prefix frontend run test:web3d
npm --prefix frontend run test:realtime
npm --prefix frontend run test:operation
npm --prefix frontend run test:operation-state
npm --prefix frontend run test:pipeline
npm --prefix frontend run test:flood
npm --prefix frontend run test:flood-state
npm --prefix frontend run test:risk
(cd backend && .venv/bin/python -m pytest -q -W error)
```

浏览器脚本顺序运行，使用 Chrome `/opt/google/chrome/chrome`（可用 CHROME_PATH），开发服务 5173/8000 与真实 PostgreSQL。M7_OUTPUT_DIR 控制新验收产物，其他 M*_OUTPUT_DIR/SCREENSHOT_DIR 和 *_STATE_OUTPUT 保留。M1–M6 本轮截图 `/tmp/m7-m*`，结果复制到 M7 前缀文件；旧里程碑产物保留。

## 实际检查

| 检查 | 结果 | 证据 |
|---|---|---|
| 完整后端 pytest | **87 passed in 54.00s**，warnings 视为错误 | [日志](M7-backend.log) |
| TypeScript / 生产构建 | 通过 | [日志](M7-build.log) |
| Alembic upgrade / check | head adab6941d89a；No new upgrade operations detected | [日志](M7-migration-check.log) |
| M7 浏览器 | 通过 | [M7-emergency-regression.log](M7-emergency-regression.log) |
| M1 浏览器 | 通过 | [M7-web3d-regression.log](M7-web3d-regression.log) |
| M2 浏览器 | 通过 | [M7-realtime-regression.log](M7-realtime-regression.log) |
| M3 浏览器 | 通过 | [M7-operation-regression.log](M7-operation-regression.log) |
| M3-state 浏览器 | 通过 | [M7-operation-state-regression.log](M7-operation-state-regression.log) |
| M4 浏览器 | 通过 | [M7-pipeline-regression.log](M7-pipeline-regression.log) |
| M5 浏览器 | 通过 | [M7-flood-regression.log](M7-flood-regression.log) |
| M5-state 浏览器 | 通过 | [M7-flood-state-regression.log](M7-flood-state-regression.log) |
| M6 浏览器 | 通过 | [M7-risk-regression.log](M7-risk-regression.log) |

[真实网络浏览器结果](M7-browser-results.json) 中 7 组综合检查，errors=[]。新增 21 项后端测试覆盖：四分支独立基线、守恒/资源/暴露关系、持续强入流无法排空、缺失/离线/故障/冲突/入口/不支持动作、无副作用、确认与过期、启动坡度、自然风险变化、预测刷新、日志保存、取消、重启、存储失败、提交期间资源改变和重新开放入口。原 M2 精确字段集合断言更新以接纳 emergency/startupProgress，未删除原测试。

[PostgreSQL 核验](M7-database-results.json)：比较哈希与浏览器记录一致；B/C 两次真实执行及全部步骤均已保存，B 为 STABILIZING；3 个模板、三台 120 m³/h 泵和 32 条管网资产保留。

## 真实比较数据

基准：第 29.034 仿真分钟，雨量 100.00 mm/h，水位 24.896 cm，规则风险 82.673。基线 hash `8d32eb6b4b790121bbf9c850d124c3c1feafd9c6de62ace23b5763d7969b894a`。30–35 min 雨势从 100 回落到 20 mm/h。所有分支共用此显式环境计划，不能将全部下降归因于处置。

| 分支 | +30水位 cm | +30规则风险 | 面积 m² | 风险<60 | 资源指数 | 人员/车辆 |
|---|---:|---:|---:|---|---:|---|
| BASELINE | 31.803 | 53.590 | 1500.0 | 5.33 min | 0.00 | 32 / 48 |
| FLOOD-A | 28.021 | 47.000 | 1425.2 | 4.25 min | 30.00 | 32 / 48 |
| FLOOD-B | 24.261 | 46.094 | 1279.2 | 3.92 min | 59.83 | 32 / 48 |
| FLOOD-C | 24.261 | 41.444 | 1279.2 | 3.50 min | 69.83 | 1 / 48 |

这些是后端实际 rollout，非前端常量。每分支31个分钟点，内部5秒积分；C 与 B 水位/面积相同，入口只降低人员暴露，保留现有车辆。未达风险40均如实返回 null（UI >30min），不输出总分或赢家。P02 延迟10秒，因此双泵资源指数小于60；新封控增加10。

原 M5 持续100mm/h的入流为1020m³/h，大于三台各120m³/h的能力。此工况下双泵减缓上涨，不能声称必然下降；后端测试专门防止伪造这种结果。原 M5 默认曲线、额定值和无备用泵轨迹保留。

## 执行与真实观测

暂停时 compare / preview 保持 flood、devices、simulationTime 不变。真实改变暴露后旧执行返回409；P02离线时B/C禁用并有原因。选择B后出现指定确认文字，先持久化pending，暂停时不执行，恢复时钟后泵按原 M3 的60仿真秒过渡，P02错峰10秒。

本轮：执行前风险 82.673，水位峰值 27.574 cm；后续风险 47.000、水位 26.642 cm、增长率 -0.1371 cm/min。逐步下降由泵有效能力和雨势回落共同产生；事件和告警ID不变，告警仍active。

原 socket 收到 8 条应急事件（含比较基线、选择确认、P01/P02施加与已运行、动作完成、风险回落），全程只有一条 WebSocket。后续实际执行C，入口出现红色闸门和“已封控”，人员逐渐减少、车辆保持48。Dashboard/Risk显示活动方案，离开至事件复盘页所有canvas释放。

## M6 联动与边界

本轮后续+30min物理水位 22.518 cm、规则风险 43.959；ML 水位 17.582 cm、风险 31.403。二者均响应当前状态，但差距明显；雨势回落及新启动过渡不是已单独训练验证的分布。M6模型不编码封控和待执行动作，所以不把它当作因果方案比较依据。模型和旧训练报告没有重新训练或覆盖；后续数据生成版本更新为 m7-simulator-v2-startup，特征维度仍30。

物理预测复制待执行步骤、startup_progress、入口状态与显式降雨计划，无副作用。在线ML继续当前特征预测、原到期actual回测与存储；不伪造精度。

## 性能与资源

四分支真实比较耗时 **204.55 ms**（包括副本rollout，不含HTTP/DB写入）。真实场景跨度超过10仿真分钟，geometry/material/texture 保持 **102 / 97 / 10**；采样FPS **30**。Outline首用会分配已有后处理纹理，后续选择/执行不持续增长。闸门预建并透明预热。

浏览器为 Headless Chrome 软件渲染；这些采样不证明比赛实际GPU达到45FPS。compare在线程池，无三维对象；图表setOption复用实例。数据库执行前保存意图，步骤后台异步写入；内存比较限30次、事件展示限100条、有界待写达到100拒绝新增执行。原实时推送仍1Hz。

## 页面与交互

- [四分支比较](M7-compare.png)
- [C预览](M7-preview.png)
- [B执行后风险回落](M7-stabilizing.png)
- [Risk联动](M7-risk-linked.png)
- [入口实际封控](M7-entrance-closed.png)
- [1440布局](M7-1440.png)

已检查实际截图。方案由用户主动选择，四曲线图例与轴分离；两图单位独立，1440无横向溢出。旧比较标明过期，不能直接执行。暂停比较是用户显式控制，不在compare内部偷偷暂停引擎。

## 当前边界

- 简化模型、软件反事实推演、资源指数非金额；不控制真实泵/阀门/入口，不替代人工应急决策，不提供工程安全保证。
- 阀门动作枚举预留，但M7校验拒绝；M4控制仍可用，不伪造逐段排水水力耦合。
- 原车辆为固定存量，封控阻止新增进入（rate=0），不会让已停车辆消失；人员为指数减少的演示模型。
- 60秒启动会影响短暂水力过程；雨势回落需与处置贡献分开解释。ML不是因果模型，新工况需要后续独立校准。
- 单worker内存引擎。取消不撤销已施加动作；重启不自动重放，Reset保留已保存历史。断库不保证中间日志全量写入。
- STABILIZING不等于事件结束；不执行M8泄漏、M9关闭事件或最终复盘。

Milestone 7 已完成，当前停止开发，等待进入 Milestone 8。
