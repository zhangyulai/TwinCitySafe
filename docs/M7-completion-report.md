# Milestone 7 完成报告

## 1. 已完成内容

完成四分支方案比较、人工选择和软件仿真执行；保留 M0–M6。

## 2. Emergency Plan 架构

模板/校验 → 同一状态副本 → 四个独立物理 rollout → 比较快照 → 确认执行 → 原实时引擎/数据库/单WebSocket。详见 [架构](M7-architecture.md)。

## 3. Plan Templates

FLOOD-A 启动P01；FLOOD-B 启动P01+P02；FLOOD-C 双泵+封控B2东入口，均存数据库。

## 4. Emergency Actions

统一类型、目标、参数、延迟、持续等待与优先级。支持泵、入口和人员暴露动作；阀门枚举预留并明确拒绝未耦合的M7推演。

## 5. Plan Matching

按活动内涝、风险阶段、可用资源匹配；正式模式≥60，DEV可提前比较。

## 6. Plan Validation

服务端检查模板、设备/入口、离线故障、冲突与参数，存储await后再次复验。

## 7. Counterfactual Simulation

四个分支复制同一基线；内部5秒、曲线每分钟采样，不推进实时引擎，不用XGBoost推导干预结果。

## 8. Baseline

维持当前状态，不施加新增动作，不可执行；保存完整模型基线SHA256。

## 9. A/B/C 对比结果

| 分支 | +30水位 cm | +30规则风险 | 面积 m² | 风险<60 | 资源指数 | 人员/车辆 |
|---|---:|---:|---:|---|---:|---|
| BASELINE | 31.803 | 53.590 | 1500.0 | 5.33 min | 0.00 | 32 / 48 |
| FLOOD-A | 28.021 | 47.000 | 1425.2 | 4.25 min | 30.00 | 32 / 48 |
| FLOOD-B | 24.261 | 46.094 | 1279.2 | 3.92 min | 59.83 | 32 / 48 |
| FLOOD-C | 24.261 | 41.444 | 1279.2 | 3.50 min | 69.83 | 1 / 48 |

以上采用明确的30–35分钟雨势回落计划。C不改变水量，因此与B水位/面积相同。

## 10. Response Time / Resource Cost

首次低于60/40；未达返回null。P01/P02每运行分钟各1指数，新封控10指数，不是金额。

## 11. Plan Availability

P02离线或故障时B/C不可用；UI禁用并解释，后端重新校验。

## 12. Plan Preview

复用单个蓝色Outline标记泵，黄色入口预览；切换清理，真实状态不变。

## 13. Execution Engine

确认指定软件仿真提示后，先保存pending再由原tick执行；复用DeviceSimulator.set_state及60秒过渡。取消仅取消后续动作。

## 14. Emergency Timeline

保存比较基线、选择确认、步骤施加/完成与风险回落；EMERGENCY_EVENT复用原socket，完整快照可恢复日志。

## 15. Three.js 联动

泵启动环和状态色、红色入口闸门/已封控标签，水面和热区沿用原对象。

## 16. Flood 状态联动

真实B执行风险 82.67→47.00；水位先升至27.57cm再降至26.64cm，来自泵与雨势回落共同作用。告警保留。

## 17. M6 Prediction 联动

新执行/泵/入口状态触发刷新；物理副本包含待执行动作，ML按当前特征更新，新工况差异如实显示。

## 18. Dashboard / Risk 联动

显示活动方案与执行/回落状态，无新增socket。

## 19. API

GET plans/status/executions/{id}；POST compare/preview/execute/executions/{id}/cancel；执行要求comparison_id及confirmed_simulation。另有显式雨势回落演示入口。

## 20. Migration / Database

实际revision adab6941d89a←b655e1756d27；四张应急表，迁移一致性通过。operator=demo-user；重启不自动控制设备。

## 21. 新增文件

新增动作/执行DTO、四表、迁移、三服务、API、Pinia、面板、摘要、闸门及浏览器验收。详见 [文件清单](M7-files.md)。

## 22. 修改文件

扩展原设备启动、Flood状态、共享副本、缓存失效、单WS、Simulation/Risk/Dashboard与三维生命周期；M6模型产物保留。

## 23. 测试结果

87 passed in 54.00s；构建/迁移通过；M7真实网络7组、M1–M6及缓存回归均通过。详见 [验收记录](M7-verification.md)。

## 24. 性能情况

四分支比较204.55ms；资源102/97/10稳定；软件渲染采样30FPS，实际GPU另验。

## 25. 演示步骤

/simulation → 应急演示·暴雨后雨势回落 → 10×到高风险 → 暂停 → 进入推演 → 比较 → 选B → 确认 → 继续 → 观察启动/水位/风险/M6；可随后比较执行C观察封控。

## 26. 当前边界

持续100mm/h入流大于既有泵能力，仅启泵不能保证下降。回落计划对所有分支相同；比较不代替人工决策，资源非金额，ML非因果；不控制真实设备，不提供工程安全保证。无M8/M9。

## 27. M8 建议

获新指示后再设计泄漏场景、拓扑与压力流量耦合、数据标注和独立验证；本轮未实施。

Milestone 7 已完成，当前停止开发，等待进入 Milestone 8。
