# M6 模型实际评估报告

数据来源：独立M5软件仿真场景。指标不证明真实城市泛化能力。

- 60000样本，30特征，250场景；训练170/验证40/测试40场景。
- 训练40800行，验证9600行，测试9600行；按场景分组，集合间无场景交叉。
- 模型版本 risk-xgb-v1；特征版本 m6-v1；训练时间 2026-10-03T13:52:36.760399+00:00。
- 比较深度4/6/8，实际选择4；学习率0.05，最多600树，验证早停35轮。

## 独立测试集

| 目标 | MAE | RMSE | R² | 风险等级一致率 |
|---|---:|---:|---:|---:|
| water_10m | 0.2916 | 0.3736 | 0.99899 | — |
| water_20m | 0.4818 | 0.6339 | 0.99801 | — |
| water_30m | 0.7330 | 0.9526 | 0.99685 | — |
| risk_10m | 0.9964 | 1.3377 | 0.99606 | 96.53% |
| risk_20m | 1.3904 | 1.8154 | 0.99263 | 95.66% |
| risk_30m | 1.4198 | 1.8880 | 0.99167 | 96.48% |

水位误差单位cm，风险误差单位分（0–100）。预测与评估均执行输出裁剪。

## 原始报告

- [完整验证/测试指标](../algorithm/risk_prediction/reports/metrics.json)
- [参数比较](../algorithm/risk_prediction/reports/training_trials.json)
- [样本分布与场景分组](../algorithm/risk_prediction/reports/dataset_report.json)
- [全局gain importance](../algorithm/risk_prediction/reports/feature_importance.json)
- [模型元数据](../algorithm/risk_prediction/models/metadata.json)
- [实际性能测量](../algorithm/risk_prediction/reports/performance.json)

标签是仿真器产生的未来状态；当前风险目标沿用M5规则模型。ML是在逼近该仿真分布，不能由高R²推断真实防洪预测能力。未来已知计划雨量属于发出预测时的输入假设，不使用未来真实观测作为特征。
