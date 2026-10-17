# M8 验收记录

## 范围与复现

Pipeline Leakage Scenario：渐进压力/流量异常、观测检测与 Top 3 定位、M4 影响范围、隔离比较/预览/过期校验、人工确认仿真阀门执行、自然风险回落与停水保留。只到 STABILIZING，不进入 M9 事件关闭或回放。

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
npm --prefix frontend run build
npm --prefix frontend run test:leak
npm --prefix frontend run test:leak-state
npm --prefix frontend run test:web3d
npm --prefix frontend run test:realtime
npm --prefix frontend run test:operation
npm --prefix frontend run test:operation-state
npm --prefix frontend run test:pipeline
npm --prefix frontend run test:flood
npm --prefix frontend run test:flood-state
npm --prefix frontend run test:risk
npm --prefix frontend run test:emergency
(cd backend && .venv/bin/python -m pytest -q -W error)
backend/.venv/bin/python docs/M8-localization-benchmark.py
```

浏览器使用真实开发服务 5173/8000、PostgreSQL 和 Chrome `/opt/google/chrome/chrome`，可用 CHROME_PATH 指定。测试必须顺序执行，避免并发控制同一引擎。M8_OUTPUT_DIR / M8_STATE_OUTPUT 重定向新产物；M1–M7 本轮截图位于 `/tmp/m8-m*`，旧里程碑证据保留。

## 检查结果

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 完整后端 pytest | **107 passed，54.37s**，warnings 视为错误 | [日志](M8-backend.log) |
| TypeScript / 生产构建 | **通过，6.77s** | [日志](M8-build.log) |
| Alembic 一致性 | **No new upgrade operations detected** | [日志](M8-migration-check.log) |
| M8 缓存边界 | **通过** | [JSON](M8-state-results.json) |
| M8 真实网络事故 | **通过，138.83s** | [日志](M8-leak-regression.log) |
| M1 Web3D | **通过，63.37s** | [日志](M8-web3d-regression.log) |
| M2 实时 | **通过，76.52s** | [日志](M8-realtime-regression.log) |
| M3 设备运维 | **通过，40.43s** | [日志](M8-operation-regression.log) |
| M3 缓存/缺模型 | **通过，1.64s** | [日志](M8-operation-state-regression.log) |
| M4 管网 | **通过，52.68s** | [日志](M8-pipeline-regression.log) |
| M5 暴雨事故 | **通过，196.42s** | [日志](M8-flood-regression.log) |
| M5 趋势缓存 | **通过，2.18s** | [日志](M8-flood-state-regression.log) |
| M6 预测 | **通过，119.06s** | [日志](M8-risk-regression.log) |
| M7 应急方案 | **通过，289.03s** | [日志](M8-emergency-regression.log) |


## 新增后端测试

20 项（含参数化），原 87 项保持通过。覆盖零泄漏正常微波动、渐进严重度、五种严重度下压力/泄漏流量/检测/风险的合理关系、四根不同注入管段的独立观测定位、注入真值改写不影响定位、Graph 影响等于 M4、三种真实候选、只读比较、确认要求、即时状态不变与后续渐进衰减、停水保留、人工重新开阀重新检测、持久化和去重、七种过期原因、双向事故冲突、无效资产、存储失败不施加阀门动作、采样恢复重试、200 条事件有界、重启中断、API 合同及暂停变速冻结。

M8 事件/告警是场景持久化 JSON，状态等级变化更新同一个 ID；没有另建真实生产告警系统。设备运维 M3 告警模型不用于管网检测。

## 真实事故数据

[浏览器 JSON](M8-browser-results.json) 来自真实 REST / 单 WebSocket / 仿真引擎 / Three.js / PostgreSQL，未向实际事故注入前端状态 fixture。最终 7 组综合检查通过，errors=[]。

第 340.293 仿真秒：上游/下游局部观测压力 0.3428 / 0.2162 MPa，管段流量 43.195 m³/h，估算泄漏 20.966 m³/h，异常匹配度 0.6748，规则风险 61.988。排名由观测产生：WS-003 **0.8342**、WS-008 **0.2294**、WS-009 **0.2294**。没有将需求示例中的后两名硬编码为结果。

| 关闭候选 | 阀门数 | 影响建筑 | 隔离长度 m | 服务损失指数 |
|---|---:|---:|---:|---:|
| V-W-03 | 1 | 2 | 86.92 | 0.4 |
| V-W-02 | 1 | 4 | 185.51 | 0.8 |
| V-W-01 | 1 | 5 | 224.39 | 1.0 |

暂停后比较/预览，压力、流量、阀门及仿真时间保持不变。预览第二种再切第一种，Three 与二维拓扑同步换范围；不自动选择方案。实际人工改变 V-W-01 后旧比较执行返回 409 STALE_ISOLATION，再恢复阀门、重新比较。

用户确认 V-W-03：指令提交后阀门关闭，压力/流量/风险即时保持原值。恢复时钟后，观测连续衰减，实际事件流进入 ISOLATING → STABILIZING。第 1167.399 仿真秒泄漏流量约 7.43×10⁻²² m³/h（UI 显示 0.00），风险 **6.000**，CONTAINED / INTERRUPTED，科研楼 B 与实验楼 C 继续停水；服务损失 0.4。告警仍 active，事件不关闭。隔离初期服务损失项增加，风险可能短时略升（本轮峰值 63.57），随后随泄漏衰减下降，不伪造每一点严格单调。

隔离后的定位卡片明确显示保留最后确认的位置证据；当前强度另由实时残余流量表示。人工重新开阀的后端验证会重新出现显著泄漏，避免永久锁定“受控”。

## 数据库与重置

[PostgreSQL 核验](M8-database-results.json)：同一事故 1 条事件、27 条真实快照、3 次比较和 1 次实际执行；比较 hash 与浏览器完全一致。7 条 PIPELINE_LEAK_EVENT 通过原连接到达。Reset 后本次关闭的 V-W-03 恢复、场景与趋势清空，事件/快照/比较/执行仍存在。数据库事件记为 reset，不冒充已完成正式事件关闭。

迁移 head `f6f65d1e093a`（父 `adab6941d89a`），Alembic check 无差异。34 节点、32 管段、10 阀门、3 个 M7 模板、3 台各 120 m³/h 泵资产保留。M6 保存的六模型未重训。

## 缓存与页面

[缓存结果](M8-state-results.json) 使用明确标注的本地状态 fixture，与上述真实网络验收分开。2001 次输入最多 1800 点，暂停仍 1800，跨 60 仿真分钟仅保留新点；新场景/新会话清空、断线保留、Reset 清零。

实际点击四个趋势 Tab，分别展示压力 MPa、流量 m³/h、检测 0–1、风险 0–100。Dashboard 显示当前泄漏事件；Risk 显示规则和影响，注明“当前 ML 预测模型仅适用于内涝场景”，隐藏 Flood ML 展示并停用轮询。1440 宽无横向溢出，离开到事件复盘后所有 canvas 释放，整个导航过程只有一条实时 WebSocket。

M3 回归初次在缩小视口后立即断言发生失败；单独检查重排后 scrollWidth=1440、无溢出元素。将原断言前增加等待 ResizeObserver 完成的有界检查，不删减原宽度和控制面板检查。初次记录保留于 [日志](M8-operation-resize-first-attempt.log)。

## 性能与资源

[定位基准](M8-localization-performance.json)：Python 3.13.9，500 次真实 Top 3 计算平均 **0.0598 ms**、P95 **0.0737 ms**，不含 HTTP/数据库。采用独立 SQLite 仅用于载入同一 M4 图，不改演示数据库。

本轮真实比较计时 **6.690 ms**，包括图读取、候选枚举和签名，不含比较写库及 HTTP 返回。在线实际定位采样 **0.0942 ms**。这些只代表当前 32 管段示范图。

从第 515.969 到 1167.399 仿真秒，超过 10 仿真分钟：geometry **36→36**、material **98→98**、texture **9→9**。资源在常用预览/选择后预热；Outline 首用可能分配纹理，不是持续泄漏。120 粒子固定池，没有按实时消息新建 geometry 或 texture。

Headless Chrome / ANGLE SwiftShader 软件渲染，最终 1920 采样 **31 FPS**；1440 截图时约 40 FPS。不能证明比赛 GPU 达到 45 FPS，需要实际比赛机器验收。

## 页面截图

- [启动初期](M8-normal.png)
- [观测确认与定位](M8-confirmed.png)
- [隔离预览](M8-preview.png)
- [隔离后稳定](M8-stabilizing.png)
- [1440 布局](M8-1440.png)
- [Dashboard](M8-dashboard.png)
- [Risk 场景边界](M8-risk.png)

已人工检查 1920 确认阶段和 1440 稳定阶段截图：疑似与隔离颜色可辨，影响建筑着色，停水状态保留，图表有连续过程，未出现横向溢出。

## 当前边界

- 软件示范图、简化压力/流量传播与残余衰减，不是真实水力求解或工程安全工具。
- 定位分数未经概率校准；模拟观测包含清晰局部不平衡，不证明真实传感器噪声或城市网络上的准确率。
- Risk 是场景专用规则分解，M3 设备模型和 M6 Flood 模型均不用于泄漏诊断/预测。
- 单 worker 内存引擎；数据库提交与进程内应用不是跨崩溃原子事务，重启不恢复旧事故，已持久化阀门关闭需人工恢复。
- 采样失败仅保留每场景最新状态，无法补造丢失中间轨迹；事件缓存有界，数据库历史不保证完整回放。
- 每事件只接受一次 M8 隔离执行，人工重新开阀会重新检测但需 Reset 后再演示隔离。
- 阀门为离散软件指令，连续过渡的是压力和流量；暂停不会推进过渡。
- CONTAINED 不代表供水恢复，STABILIZING 不代表事件关闭；未实现 M9 回放、正式复盘或最终工单关闭。


## 完成清单

- [x] 独立 Leak Scenario、状态模型、默认 ID 和集中参数。
- [x] 原 PipelineSimulator 增量实现，severity/pressure/flow 连续演化。
- [x] 五因素检测、集中阈值与非概率分数说明。
- [x] 观测/拓扑 Localization、Top 3 和多注入点验证，不读取目标真值。
- [x] Leak Risk、分项解释和服务损失保留。
- [x] M4 影响建筑、节点、管段与隔离候选复用。
- [x] 固定粒子池、脉冲、红橙黄、影响建筑高亮、隔离灰化。
- [x] 全网启动镜头、确认后首位聚焦、2D/3D 联动。
- [x] 四趋势 Tab、不同单位及 1800 点/60 分钟缓存。
- [x] 事件/告警去重、5 秒采样、比较和执行持久化。
- [x] 比较无副作用、预览阀门/管段/建筑、无自动 Winner。
- [x] 状态签名、七类过期条件与服务端再次验证。
- [x] 显式软件确认、共享 ValveService、存储失败不施加动作。
- [x] 阀门指令后的压力/流量连续过渡与自然风险变化。
- [x] STABILIZING、停水保留、人工重开后重新检测。
- [x] Dashboard / Risk 当前来源、Flood ML 隔离和双场景冲突。
- [x] 单 WebSocket、完整快照恢复与有界事件缓存。
- [x] 超过 10 仿真分钟资源稳定、1440 布局、canvas 释放。
- [x] Alembic check、生产构建、107 项后端、M8 浏览器和缓存通过。
- [x] M1–M7 全部回归通过，既有资产和历史报告保留。

Milestone 8 已完成，当前停止开发，等待进入 Milestone 9。
