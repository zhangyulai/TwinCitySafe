# M6 验收记录

## 范围和复现

Risk Prediction Engine：真实生成数据、训练六个XGBoost模型、独立场景评估、在线预测、TreeSHAP/近似降级、物理对照、真实后续观测回测、Risk页与Dashboard。停止在M6，不执行M7应急操作。

```bash
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m alembic -c backend/alembic.ini check
# 模型已保留；需要重新生成时执行：
backend/.venv/bin/python algorithm/risk_prediction/generate_dataset.py
backend/.venv/bin/python algorithm/risk_prediction/train.py
backend/.venv/bin/python algorithm/risk_prediction/evaluate.py
backend/.venv/bin/python algorithm/risk_prediction/benchmark.py
# 启动服务后，浏览器脚本应顺序执行
npm --prefix frontend run build
npm --prefix frontend run test:risk
npm --prefix frontend run test:web3d
npm --prefix frontend run test:realtime
npm --prefix frontend run test:operation
npm --prefix frontend run test:operation-state
npm --prefix frontend run test:pipeline
npm --prefix frontend run test:flood
(cd backend && .venv/bin/python -m pytest -q -W error)
```

浏览器默认Chrome `/opt/google/chrome/chrome`，支持CHROME_PATH。各脚本操作同一后端，不能同时跑事故控制。M1/M2截图目录变量不变；M3/M4/M5新增或保留对应M*_OUTPUT_DIR，保护原里程碑历史记录。

## 最终检查

| 检查 | 实际结果 | 记录 |
|---|---|---|
| 完整后端pytest | **66 passed，22.56s**，warnings视为错误 | [日志](M6-backend.log) |
| TypeScript / 生产构建 | **通过，6.74s** | [日志](M6-build.log) |
| Alembic一致性 | **No new upgrade operations detected** | [日志](M6-migration-check.log) |
| M6真实网络浏览器 | **7组通过，errors=[]** | [结果](M6-browser-results.json) |
| M1 Web3D回归 | **16组通过，errors=[]** | [结果](M6-m1-results.json) |
| M2实时回归 | **12组通过，errors=[]** | [结果](M6-m2-results.json) |
| M3设备运维回归 | **8组通过，errors=[]** | [结果](M6-m3-results.json) |
| M3缓存/缺模型界面 | **通过** | [结果](M6-operation-state-results.json) |
| M4管网回归 | **6组通过，errors=[]** | [结果](M6-m4-results.json) |
| M5完整30分钟事故 | **6组通过，errors=[]** | [结果](M6-m5-results.json) |
| M5缓存边界 | **通过** | [结果](M6-flood-state-results.json) |

M1–M5本轮截图单独存放于各结果记录的 `/tmp/m6-m*` 目录，原里程碑产物保留。M6截图在本目录。最后对非有限模型输出增加了降级保护，完整后端66项包含该分支；最终浏览器回归使用相同的六个模型与页面实现。

## 数据与模型证据

- 60000样本、30特征、250独立场景、10类工况，每类25个。
- 170/40/40场景分别用于训练/验证/测试，40800/9600/9600行；无场景交叉。
- seed42，独立场景种子、划分与分布全部保存。
- 所有标签来自M5模型前推，不是比例或常量；按单条样本独立克隆进行horizon对照测试。
- 六个原生JSON模型、metadata校验和、特征版本、训练参数与真实metrics均保存；启动不训练。
- 深度4/6/8三组验证比较后选4；测试集未参与选择。

详细指标见 [M6-model-report.md](M6-model-report.md) 和 [metrics.json](../algorithm/risk_prediction/reports/metrics.json)。水位测试MAE为0.2916/0.4818/0.7330cm；风险MAE为0.9964/1.3904/1.4198分。高R²只说明对当前仿真分布的拟合，不证明真实城市能力。

## 新增后端验证

18项（含参数化）覆盖：

- 数据可复现、场景无泄漏、30维合同、全工况有限值、标签精确horizon。
- 六模型真实加载和有效输出；缺失模型、版本不符、校验失败降级；原生输出NaN/Inf在裁剪前拒绝，保留物理预测。
- TreeSHAP bias+全部贡献与原始预测相加一致，近似fallback明确区分。
- 一致度小/中/大差异及边界。
- 缓存命中与响应隔离、控制变化失效、预测和解释均不推进真实状态。
- 真实引擎运行至horizon、actual匹配、误差计算、数据库保存与Reset中断剩余预测。
- Prediction/Status/Explanation API、无场景、非法horizon、模型不可用时保留物理结果。

## 真实浏览器演示

M6浏览器脚本通过真实API启动Extreme Rain、10×推进，通过WebSocket获取同一实时状态。7组检查全部通过，errors=[]。等待P03退化、水位上升，验证ML未来水位随实际输入变化，检查两张ECharts中的物理/ML系列、模型一致度、TreeSHAP和Dashboard入口。

到期误差通过真实后续引擎状态匹配；模型缺失界面测试使用响应fixture，实际文件缺失路径另由后端pytest验证。暂停后请求预测/解释，设备、水位、仿真时间保持不变。1440窗口从1920动态缩小检查无横向溢出；离开至/review检查全部canvas释放。

历史实线表示已经发生的仿真观测，未来物理虚线/ML点线是预测；两个不同单位使用独立图表。界面将规则贡献与ML解释分开，并显示预测/解释各自基准时刻，避免把不同刷新周期的数据误认为同一时刻。

本轮事故观测：当前水位 12.546 cm、当前规则风险 66.256。已有 5 个到期预测匹配真实观测，水位MAE 0.2543 cm、风险MAE 0.6548分；数据库保存 30 条预测。该短演示误差不替代独立测试集指标。

资源在超过10个仿真分钟的比较中保持 geometry 34、material 95、texture 1；单WebSocket。此轮Risk场景采样点约 36 FPS，在线ML调用平均 1.950 ms。镜头与视口改变可能降低软件渲染帧率，该采样点不是全程性能下限。

## 性能

[性能JSON](../algorithm/risk_prediction/reports/performance.json) 来自独立M5副本的真实模型调用：

| 调用 | 次数 | 平均耗时 | P95 |
|---|---:|---:|---:|
| 六模型合计预测 | 200 | 0.884 ms | 1.280 ms |
| +30min原生TreeSHAP | 100 | 0.840 ms | 0.890 ms |

Python3.13.9、XGBoost CPU3.4.1、单推理线程。以上不含HTTP和M5物理rollout。后端预测刷新约5秒、解释约10秒、预测DB采样10秒；原实时WebSocket仍1Hz。

浏览器使用Headless Chrome / ANGLE SwiftShader软件渲染，FPS不能证明实际GPU达到45FPS目标。三维复用M1/M5，图表更新setOption，未每次预测重建实例。具体场景FPS及geometry/material/texture数量以本轮浏览器JSON为准。

## 页面截图

- [无活动事故](M6-risk-idle.png)
- [事故预测与解释](M6-risk-active.png)
- [1440布局](M6-risk-1440.png)
- [模型缺失保留物理预测](M6-model-fallback.png)

已检查无事故和活跃事故截图。初次验收发现ECharts容器最小宽度导致1920→1440溢出，已将图表网格改为可收缩的minmax列，并重新验证scrollWidth=1440。回归脚本的无canvas离开目标改为实际“事件复盘”，因为/risk已从占位升级为正式三维页。

## 演示流程

进入/simulation → 启动并确认软件暴雨场景 → 10× → 进入/risk → 观察当前规则风险、两种未来水位/风险预测和一致度 → 查看+30min模型贡献 → 超过10仿真分钟后查看第一批实际到期误差 → 返回Dashboard查看轻量未来风险。

## 当前边界

- 全部训练/验证/测试来自同一个M5模型族；ML拟合仿真分布，不能代表真实城市泛化。
- 物理模型简化，ML预测以已知雨量计划和当前泵/故障趋势继续为假设；人为干预会改变实际结果。
- 模型一致度不是统计置信区间。SHAP是模型贡献，不是因果解释；近似fallback不可加和。
- 仅训练10/20/30分钟，其他MLhorizon返回422。水位非负、风险0–100裁剪不保证全域单调性。
- 到期actual用相邻真实观测插值，保留采样跨度；超过演示终点的预测不造actual。Reset/重启中断未完成预测，历史保留。
- 单worker内存引擎；断库存储使用有界重试，不保证全部中间记录补齐。
- 前端GPU性能需比赛设备实测；未实现自动操作设备/阀门、应急方案比较、泄漏与事故复盘。

## 完成清单

- [x] 独立M5数据生成、多样场景、随机种子、精确horizon标签。
- [x] 场景级训练/验证/测试划分，无交叉；60000样本、30维共享特征。
- [x] 六个水位/风险XGBoost模型、三组验证比较、原生JSON与校验和。
- [x] 实际MAE/RMSE/R²/等级一致率、分布、全局gain和metadata报告。
- [x] 模型缺失/版本不符/推理异常降级，启动不训练。
- [x] 物理预测保留、ML预测、Gap与非概率模型一致度。
- [x] +30min原生TreeSHAP和明确标记的近似fallback。
- [x] Risk页面、当前规则与未来ML区分、历史实线与未来虚线。
- [x] Dashboard轻量联动、预测/状态/解释/误差/历史API。
- [x] 无副作用、5秒缓存、10秒解释缓存及10秒数据库预测采样。
- [x] 真实后续状态对齐、误差计算/保存、未到期不伪造actual。
- [x] 生产构建、迁移、完整pytest、M1–M5回归与资源稳定验证。

Milestone 6 已完成，当前停止开发，等待进入 Milestone 7。
