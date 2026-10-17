# M5 验收记录

## 范围与复现

Milestone 5 — Rainstorm & Flood Simulation。仅实现事故演化、场景规则风险与模型外推；未进入 M6/M7/M8/M9。开发服务入口：<http://127.0.0.1:5173/simulation>。

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
npm --prefix frontend run build
npm --prefix frontend run test:flood
npm --prefix frontend run test:flood-state
npm --prefix frontend run test:web3d
npm --prefix frontend run test:realtime
npm --prefix frontend run test:operation
npm --prefix frontend run test:operation-state
npm --prefix frontend run test:pipeline
(cd backend && .venv/bin/python -m pytest -q -W error)
```

浏览器测试需要前后端开发服务和已迁移的数据库，默认 Chrome `/opt/google/chrome/chrome`，可用 `CHROME_PATH` 指定。顺序运行各浏览器脚本，因为它们操作同一仿真引擎。M1/M2 支持 `M1_SCREENSHOT_DIR`、`M2_SCREENSHOT_DIR`，M3/M4 支持 `M3_OUTPUT_DIR`、`M4_OUTPUT_DIR`，可保护原里程碑产物。

## 实际结果

| 检查 | 结果 | 记录 |
|---|---|---|
| 后端 pytest（含13项M5测试） | **48 passed，19.61s**，warnings视为错误 | [日志](M5-backend.log) |
| Vue/TypeScript生产构建 | **通过，6.74s** | [日志](M5-build.log) |
| Alembic迁移一致性 | **No new upgrade operations detected** | [日志](M5-migration.log) |
| M5真实网络E2E | **6组通过，errors=[]** | [结果](M5-browser-results.json) |
| M5趋势缓存边界 | **全部通过** | [结果](M5-state-results.json) |
| M1 Web3D回归 | **16组通过，errors=[]** | [结果](M5-m1-results.json) |
| M2实时回归 | **12组通过，errors=[]** | [结果](M5-m2-results.json) |
| M3运维回归 | **8组通过，errors=[]** | [结果](M5-m3-results.json) |
| M3缓存/模型缺失展示 | **全部通过** | [结果](M5-operation-state-results.json) |
| M4管网回归 | **6组通过，errors=[]** | [结果](M5-m4-results.json) |

M5后端新增13项测试，原有35项保持通过。覆盖零雨/正常雨/强雨/极端雨、泵启停/故障、守恒/边界、增长率/非线性面积、风险单调性/分解、无副作用预测和前向校准、暂停/恢复/重置、快照与告警去重、API输入/生产限制/资产额定值、非整数墙钟步长的完成边界。

M5缓存实测：2001条输入最多保留1800点；暂停仍1800；跨过60分钟窗口后只剩新点；新场景/会话清空旧序列，断线保留，Reset为0。M2人工模拟断网期间记录的网络失败属于预期，恢复后单连接、遥测继续；其余浏览器errors均为空。M1–M4本轮截图位于各结果中的`/tmp/m5-m*`目录，正式M5截图保存在本目录。

## 真实网络事故演示

[浏览器结果](M5-browser-results.json) 来自真实 REST、WebSocket、数据库和 Three.js，未伪造物理状态或跳到预设终帧。10×覆盖30仿真分钟，期间执行暂停/预测/继续；控制成功、单 WebSocket、六组综合断言全部通过，页面 errors 为空。

| 观测时点 | 雨量 mm/h | P03 效率 | 水位 cm | 规则风险 |
|---|---:|---:|---:|---:|
| 启动初期 | 8.77 | 正常向既有模型演化 | 0.793 | 11.46 |
| 故障发展阶段 | 65.12 | 76.005% | 2.795 | 38.07 |
| 高风险阶段 | 接近100 | 约76% | 12.313 | 65.85 |
| 30分钟末 | 100 | 76% | 25.888 | 82.8 |

结束时 +10/+20/+30 分钟模型外推为 36.15/46.41/56.67 cm。该数值假设计划降雨和当前设备演化继续，不受演示时长截断；不是实际工程预测。完成状态冻结事故，不代表恢复。

本次记录 39 条实际快照，事件保持同一 UUID，告警保持同一 ID。Reset 后：P03 normal、clear、日常低水位、事件0、趋势清空、热区隐藏；快照保留，32条管网资产仍存在。

## 验收清单

- [x] Flood V2 通过体积守恒计算，无前端写死水位动画。
- [x] Weather 单一雨量真值；P03 效率来自既有 M3 状态。
- [x] 额定泵能力读取 Device 资产，活动泵能力×效率，无 HI 重复扣减。
- [x] 正常、强降雨、极端暴雨及 P03 故障联动。
- [x] 水位、体积非负，面积不超过有效面积，风险0–100。
- [x] 非线性积水面积、60仿真秒窗口回归上涨速度。
- [x] 参数化风险分解、Stage、人员和车辆暴露。
- [x] 水面高度/面积实时联动、软边、波纹、连续扩张。
- [x] 固定雨粒子池、雨量驱动密度/速度/透明度；光照/天空/雾联动。
- [x] B2 热区颜色/面积变化，高风险脉冲，低风险不闪烁。
- [x] 场景启动镜头引导和动态水位/风险标签。
- [x] 三栏 Simulation 参数、风险、预测和事件展示。
- [x] 四个趋势 Tab 分开单位。
- [x] 无副作用 +10/+20/+30 预测、既有泵指令与计划雨量外推。
- [x] 5墙钟秒数据库采样、同事件告警更新、历史保留。
- [x] Dashboard 使用明确标注的内涝场景风险、B2风险染色。
- [x] 演示确认、DEV控制、Pause/Continue/Reset、30分钟完成冻结。
- [x] M5完整演示无 JS error，1440/1920布局可读、无横向溢出。
- [x] 趋势1800点上限、60仿真分钟窗口、暂停/场景/会话/断线/Reset边界。
- [x] M1、M2、M3、M4完整浏览器回归通过，既有设备/管网资产保留。
- [x] Alembic一致性、生产构建和完整后端测试通过。

## 性能与资源

使用 Headless Chrome / ANGLE SwiftShader 软件渲染，本轮暴雨终态实测约 **30 FPS**，1440截图约36 FPS；这不证明比赛机器达到45 FPS目标，仍应在实际GPU设备验收。

故障发展→高风险阶段覆盖超过10个仿真分钟，直到30分钟末：geometry **100→100**、material **95→95**、texture **1→1**。雨池、水面和热区复用对象，没有随每秒状态创建额外几何或纹理。低风险透明环提前预热，避免首次高风险才分配GPU geometry被误判为持续增长。

前端趋势上限1800点/60仿真分钟；数据库固定5秒采样与1HzWebSocket独立。M1/M2回归另有上下文释放、连接频率与重连检查。

## 页面截图

- [正常页面](M5-simulation-normal.png)
- [暴雨发展](M5-flood-developing.png)
- [极高风险](M5-flood-extreme.png)
- [Dashboard联动](M5-dashboard-flood.png)
- [1440布局](M5-flood-1440.png)

1920极高风险与1440页面截图已人工检查：三维水面和热区局限于B2，标签与参数可读，趋势显示连续发展过程，未发生文字截断或横向溢出。1920终态截图中的预测可能比最终REST快照早一个10秒轮询周期，1440返回页面后已重新获取最终预测。

## 演示流程

打开 `/simulation` → 启动并确认软件仿真 → DEV选择10× → 观察雨量增加 → 第3仿真分钟P03轴承退化 → 水位和积水面积上升 → 风险热区黄/橙/红 → +10/+20/+30外推变化 → 风险≥60提示M7待接入。可启动备用泵观察有效排水增加，或重置后重新演示。到此停止，不执行应急处置或事故恢复。

## 当前边界

- 简化有效面积/径流/泵排量模型，非地形淹没求解、CFD或防洪设计，不用于真实安全决策。
- P03轴承退化沿用M3约76%的效率标定，没有另造55%的效率数据。
- 规则风险不是XGBoost或AI综合预测。其他建筑的基础风险仍是示例，B2事故风险有独立来源标注。
- 内存引擎为单worker；重启不会恢复旧事故，历史running记录转stopped。断库存储重试仅保留每场景最新状态，不补造缺失历史。
- 告警去重和等级更新已实现；确认/关闭工单、应急方案执行、事件回放与最终恢复不在M5。
- 模型没有逐段排水拓扑水力耦合；预测为延续假设，可能超过演示时长和物理建筑适用深度。
- 实际GPU性能仍需比赛设备验收；软件渲染数据已如实记录。
