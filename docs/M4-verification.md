# M4 验收记录

验证日期：2026-10-03（Asia/Shanghai）。服务：本地 PostgreSQL / FastAPI / Vite；浏览器：Headless Chrome，ANGLE SwiftShader 软件渲染。

## 实际数据与迁移

- Alembic upgrade head 成功；revision `2cae9fa70c8f`，前置 `0001_equipment`。
- Alembic check：`No new upgrade operations detected.`
- 首次 Seed：34 节点、32 管段、10 阀门；重复 Seed：0 / 0 / 0。
- 给水 12 节点，排水 12 节点，消防 10 节点。
- 拓扑 validate：孤立节点、无效边、重复 ID 均为空；两个供给水源与一个排水出口。
- 真实入库，不是前端硬编码的三组管道；管网总长由资产长度汇总约 0.71 km。

## 测试结果

| 验证 | 结果 | 证据 |
|---|---|---|
| 后端全套 pytest -q -W error | 35 passed | backend/tests，含原 M2/M3 和新增管网测试 |
| 前端生产 build | 通过 | vue-tsc + Vite，无 chunk 体积警告 |
| M4 test:pipeline | 6 组完整场景通过，0 应用错误 | [结果](M4-browser-results.json) |
| M1 test:web3d | 16 组通过，0 应用错误 | [结果](M4-m1-results.json) |
| M2 test:realtime | 12 组通过，0 应用错误 | [结果](M4-m2-results.json) |
| M3 test:operation | 8 组通过，0 应用错误 | [结果](M4-m3-results.json) |
| M3 状态补充 | 300 点上限、暂停过期清理、模型缺失 UI 通过 | [结果](M4-state-results.json) |

后端新增覆盖：Seed 幂等、资产更新保留、图构建、边/节点上下游、建筑影响、最近阀门、三组候选、阀门关闭与重开、Reset 保留阀门、API 筛选与无效输入、生产模式禁用控制。纯算法覆盖简单路径、支路、多阀、多源、断连、关闭阀门、水源缺失、环、重复路径与无效边。

验收时发现高负载下手动采样与定时采样重叠的既有竞态，给采样入口增加 asyncio.Lock，确保检查 revision 与数据库写入串行；新增 8 个并发 sample 调用只生成 3 条设备遥测的测试。修复后全套 35 项通过。

旧浏览器测试的“无 canvas 占位页”从 /pipeline 改为仍是占位页的 /risk；M2 正式管段数从 3 更新为 32。保留镜头、实时变化、去重、资源释放等原断言。M3 的历史验收截图保留，M4 回归结果另存。

## M4 实际浏览器流程

自动地下模式；11 条给水分类与编号搜索；实时压力/流量；Shader offset 推进；上游水源追踪；下游科研楼 B 与实验楼 C；影响分析；WS-003 三个隔离候选；ECharts 实际边/节点鼠标点击联动 Three.js；实际三维 Raycaster 管段点击反向选中二维图；阀门关闭、灰色隔离、平滑流量与重开；50 次选择资源稳定；1440 布局无横向溢出；页面卸载无残留 canvas；重进仅一个实时 WebSocket。

关闭 V-W-02 的实测流量：27.898 → 控制刚返回 27.898 → 衰减后 2.867 m³/h；重开恢复到 25.366 m³/h。为缩短验收等待，阶段性使用 10× 模拟时间，结束恢复 1×。不是 28 → 0 瞬变。

WS-003 默认候选：V-W-03 / V-W-02 / V-W-01；影响 2 / 4 / 5 栋建筑。点击候选只预览，API 返回 executed=false。输出阀门、隔离边、影响节点、建筑和长度；不标注“最佳方案”。

## 资源与性能

50 次选择前后：geometry 67 → 67，material 93 → 93，texture 0 → 0。每帧无新建 geometry、material、texture，流动只推进 uniform。

管网页面最终记录约 33 FPS（1920×1080 浏览器视口）。M1 全园区本次帧采样约 28.8 FPS，M2 晴/雨约 30 FPS；M3 设备聚焦约 60 FPS。它们是软件渲染下不同场景的观测值，不代表桌面独立显卡结果；未声称完成真实显卡 45 FPS 验收。

优化保留地下建筑半透明外轮廓，关闭地下不可见阴影采样；地上/风险模式恢复详细建筑与阴影。地下场景初次近距离约 13 FPS，拉开镜头并减少背景绘制后达到上述结果。未重写 SceneManager。

## 截图

- [管网正常场景](M4-pipeline-normal.png)
- [追踪与三个隔离候选](M4-pipeline-options.png)
- [关闭阀门](M4-valve-closed.png)
- [1440 布局](M4-pipeline-1440.png)

## 演示步骤

1. 启动前执行 Alembic upgrade head 与 scripts/seed-pipelines.py，再运行 ./start-dev.sh。
2. 打开 http://127.0.0.1:5173/pipeline，选择给水、WS-003。
3. 查看资产字段与实时参数；点击上游追踪、下游追踪、影响分析。
4. 点击隔离方案，比较三种范围，点击卡片预览。
5. 点击二维边/阀门，观察三维镜头；点击三维管段，查看二维同步。
6. 开发阀门 V-W-02 改为 Closed，观察灰色管段和下降流量；改回 Open。
7. 切换 Dashboard / Operation，验证原运维功能。

## 已知边界

软件示范管网，不是真实城市地下管网。压力/流量是既有 M2 动态的拓扑调制，不是 EPANET/CFD 或真实水力分配。基础健康分是资产展示值，不是新模型。

候选搜索范围最多三层阀门、十个阀候选、三阀组合；返回的是有限候选，不保证全局组合最小。部分水源邻接管段或已断连管段可返回空集合。受影响长度指失去设计运行连通性的管段范围，不能作为真实检修卸压证明。

当前单 worker；阀门状态持久化、重启保留。没有正式管网资产管理 CRUD UI，也未实现泄漏事件、概率、爆管动画、工单或应急决策。开发控制不是生产鉴权体系。

Milestone 4 已完成，当前停止开发，等待进入 Milestone 5。
