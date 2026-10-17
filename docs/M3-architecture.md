# M3 Smart Equipment Operation

当前数据全部为软件仿真；异常检测模型也仅由仿真工况训练。M3 不实现 XGBoost、正式风险中心、暴雨事故、泄漏、应急方案或时间轴回放。

## 复用链路

```text
M2 SimulationEngine / DeviceSimulator（1 Hz）
  ├─ 正常与故障目标缓慢过渡，内部子步与倍速保持原有设计
  ├─ OperationService
  │   ├─ HealthService：规则加权 + 指数平滑
  │   ├─ AnomalyDetectionService：加载已训练 IF，不在启动时训练
  │   ├─ MaintenanceAdviceService：基于偏离度的模板解释与建议
  │   └─ AlarmService：按设备维护一个活动异常，滞回解除
  ├─ M2 REALTIME_STATE：设备字段扩展 analysis / fault / runtimeHours
  │   └─ App 单实例 WebSocket → Pinia → Dashboard + Operation + 现有 Three.js
  └─ TelemetrySamplingService：每 5 秒快照 → 线程池事务 → PostgreSQL
      ├─ devices 资产当前状态和累计运行时间
      ├─ device_telemetry 历史
      └─ device_alarms 去重告警
```

实时状态是唯一运行数据源。设备列表从数据库读资产资料，再用同一实时状态覆盖运行值；不另造模拟数据。资产初始化字段（日期、额定参数、既往运行小时）都是演示配置。

## 数据库与生命周期

Alembic revision `0001_equipment` 新增 `devices`、`device_telemetry`、`device_alarms`；启动不执行 create/drop。`scripts/seed-devices.py` 仅插入不存在的 P01/P02/P03，重复运行保留已积累运行小时。

历史表有 `(device_id, timestamp)` 索引以及 `(session_id, revision, device_id)` 唯一约束。告警表用 PostgreSQL 部分唯一索引保证同一设备和异常类型最多一条 active 记录。写入事务先更新已解除记录，再插入新的活动记录。

采样默认为每 5 个实际秒，最小配置值为 5，改变仿真速度不改变采样或 WebSocket 频率。同步 SQLAlchemy 操作在后台线程池执行，数据库失败会明确报告采样不可用并在下个采样周期重试，不停止实时仿真。正常关闭取消并等待 sampler、engine 和 WS writer；生产只使用单 worker。当前开发历史全部保留，没有自动清理 API。

后端重启后从资产表恢复累计运行小时；新仿真会话的物理参数恢复默认。旧会话未解除的仿真告警标为“会话重启结束”，新会话重新评估。Reset 恢复默认工况、清除实时趋势，保留数据库历史和累计运行小时，并将活动仿真告警标记结束。

## 设备与历史 API

REST 前缀 `/api/v1`。

| 方法 | 路径 | 参数 / 语义 |
|---|---|---|
| GET | `/devices` | `device_type`、`status`、`keyword`；normal 包含 running/standby |
| GET | `/devices/{id}` | 资产 + 实时状态、HI 和运行小时 |
| GET | `/devices/{id}/realtime` | 来自同一 M2 状态的设备快照 |
| GET | `/devices/{id}/health` | 当前 HI、目标值、等级和方法 |
| GET | `/devices/{id}/anomaly` | analysis，含模型可用性、分数、贡献、建议和活动告警 ID |
| GET | `/devices/{id}/maintenance-advice` | P0–P3 模板建议 |
| GET | `/devices/{id}/telemetry` | `range=1h/6h/24h` 或同时提供带时区 `start_time/end_time`；最多24小时 |
| GET | `/devices/{id}/alarms` | 最近100条已持久化的设备告警，可能比实时状态晚一个采样周期 |
| GET | `/telemetry/status` | 最近成功采样、周期与存储是否可用 |
| POST | `/simulation/device/{id}/fault` | `{"fault":"normal/bearing_degradation/overheat/low_efficiency"}` 中一个枚举值；仅 APP_ENV=development |

未知 ID 为 404，无效参数为 422，数据库查询失败为 503。历史查询按时间排序；超过600点均匀降采样并保留端点，返回原始总数与 downsampled 标识，不补造尚未积累的历史。生产环境故障注入路由返回404；前端 DEV 面板也在生产构建隐藏。

## 健康指数

权重与阈值集中在 `backend/app/services/health_config.py`。

`HI_target = 100 − 100 × Σ(w × clamp(deviation, 0, 1))`

| 项 | 权重 | 偏离度从0到1的范围 |
|---|---:|---|
| 温度 | 0.20 | 50 → 80 ℃ |
| 振动 | 0.30 | 2.8 → 6.5 mm/s |
| 电流 | 0.15 | 21.6 → 30 A |
| 效率 | 0.25 | 96 → 60 % |
| 累计运行 | 0.10 | 0 → 10000 h |

目标与当前 HI 通过20个模拟秒时间常数的指数响应平滑。待机/离线不把零效率当作故障扣分，保留已有 HI。等级边界为 ≥90优秀、≥80良好、≥60一般、≥30较差、其余严重。HI 是可解释演示规则，不是厂商认证寿命模型。

## 模型、训练与评分

`algorithm/anomaly_detection/train.py` 从现有 DeviceSimulator 的正常运行轨迹生成10000样本，涵盖三台泵并叠加小幅合成传感器噪声。训练特征仅为 temperature、vibration、current、rpm、efficiency；不含设备 ID 或故障标签。

Pipeline 为 StandardScaler + IsolationForest（200棵树、contamination=0.03、random_state=42）。保存模型、特征顺序、训练规模、版本、sklearn版本及归一化基准到 joblib。仅加载本项目生成的可信模型；环境复现以 requirements.lock.txt 为准。模型缺失、损坏或合同无效时启动继续，`modelAvailable=false`、score=null，页面显示“异常模型未加载”。

原始评分使用 `raw = -pipeline.score_samples(X)`，不是直接展示 decision_function。训练中位数映射0.12、模型训练得到的 cutoff 映射0.60；cutoff 以下线性归一化，高于 cutoff 时按 `0.60 + (raw − cutoff) × 0.40 / 0.25` 延展，并限制在0.02–0.99。在线再按12个模拟秒时间常数平滑。这是展示严重度刻度，不是故障概率。等级边界为0.35关注、0.60预警、0.80严重。

待机和离线不使用“运行工况模型”评估。正常启动/恢复运行的60个模拟秒为明确的过渡窗口（warming_up），HI保持且不作稳态模型判定；它不能解除已有活动告警。该窗口只由启停指令触发，注入或恢复故障不会重置窗口；若启动期间注入故障，将在启动窗口结束后开始评估。异常标签由测量特征推断，不由 fault 名称直接赋值。故障配置只改变原有模拟器的目标，90个模拟秒逐步进入故障目标，再经过各参数原有响应时间。

独立评估种子为20261002，训练种子42。测试集为1800正常样本和1764故障样本；故障标签仅统计注入45模拟秒之后的状态，早期过渡不计入这份静态分类指标。`evaluate.py` 输出混淆矩阵、Precision、Recall、F1、正常误报率和各故障召回率。该评估不证明跨真实设备泛化，也不是早期检出时延评估；在线检测和恢复另由集成测试验证。

官方语义参考：[IsolationForest 的 score_samples / decision_function](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)、[Alembic migration](https://alembic.sqlalchemy.org/en/latest/tutorial.html)。

## 贡献、建议与告警

贡献图使用集中配置的正常基线计算正向偏离，再除以总偏离。无偏离时全部为0；它既不是 IF 特征重要性，也不是 SHAP 或因果归因。解释为确定性模板，不调用 LLM，不断言轴承一定损坏。

建议基于 HI、异常等级、贡献特征与开发工况上下文：P3计划/关注、P2建议24小时内检查、P1建议2小时内检查、P0建议立即检查并确认备用泵。只给建议，不自动停机或启动备用设备。

score≥0.60 创建或更新同一设备的 ANOMALY_WARNING；持续异常只更新 updated_at/max_score。score<0.35 才解除，避免阈值附近反复生成告警；待机、离线或缺模型不能被当作已经恢复的证据。有活动异常的运行设备标为 warning，Dashboard 和 Three.js 使用同一状态。

## 前端与三维资源

Operation 页面按设备列表、资产详情、实时指标、健康仪表、异常解释、维护建议和趋势图拆分组件。5分钟趋势复用 App 级 Pinia 缓冲，每设备最多300点；1/6/24小时读数据库，每图最多600点。历史请求切换时取消旧请求并隔离迟到响应。图表一次初始化，更新 setOption，卸载 dispose 和 ResizeObserver。

`DigitalTwinScene` 新增 focusDeviceId 和 device-select；依然使用原 CameraManager/DeviceManager。设备聚焦时隐藏地上背景，降低近景透明层叠加；返回全景或切换模式恢复背景，不销毁/重建几何。支持地下设备真实射线选择和进入运维页链接。正常绿、关注黄、预警橙、严重红；异常脉冲环预先分配，仅异常时显示和更新，不在每秒消息中生成几何。

路由切换卸载当前场景和图表，再由同一组件创建下一个页面场景；任一时刻只保留当前视图一个 Three renderer。WebSocket 始终由 App 持有，页面不创建第二条业务连接。
