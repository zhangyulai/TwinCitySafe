# M5 暴雨内涝仿真架构

本阶段完成事故演化、规则风险与模型外推。所有数据为软件仿真；不用于真实安全决策。没有 CFD、M6 XGBoost、M7 应急动作或 M9 复盘。

## 状态与时间

唯一 `SimulationEngine` 继续驱动 Weather、Device、Flood、Pipeline；WebSocket `/ws/realtime` 仍以 1 Hz 广播完整 `ParkRealtimeState`，新增 `flood`。App 持有唯一连接，Simulation、Dashboard、Three.js 共用 Pinia 状态。速度只改变仿真时间；物理积分子步最多 0.25 秒，单次墙钟增量最多 5 秒。

`FloodService` 管理场景 UUID、启停、重置和暴露量。生命周期使用异步锁，先冻结、归档旧场景，再开始新场景。手动 Start 使用当前设备工况；正式 Demo 从默认设备状态开始，180 个仿真秒后调用既有 M3 轴承退化工况。演示时长默认 30 分钟，到期冻结事故状态，不表示事故恢复。

暂停冻结天气、设备、积水、场景时间；WebSocket 心跳继续。继续使用原 Start API。Flood Reset 归档旧场景并恢复日常运行、晴天、默认泵、0.8 cm 初始水位、1×速度、空趋势；资产、阀门配置和历史采样保留。无内涝事故时，普通 M2 Reset 保留原启停选择。场景存在时普通 Weather API 返回 409，避免两个控制源争用雨量。

## 配置与守恒

参数集中于 [flood_config.py](../backend/simulator/flood_config.py)：汇水面积 12000 m²、径流系数 0.85、车库有效面积 1500 m²、自然排水 0.0015 m³/s、初始水位 0.8 cm。三台泵额定值从 Device 资产读取，缺省均为 120 m³/h。

```text
Qin = rainfall(mm/h) / 1000 / 3600 × catchment_area × runoff_coefficient
Qpump = Σ[rated_capacity(m³/h) / 3600 × efficiency / 100]
       仅统计 running / warning 设备
Qout = min(V / dt + Qin, natural_drainage + Qpump)
Vnext = max(0, V + (Qin - Qout) × dt)
h(cm) = V / effective_area × 100
water_area = effective_area × clamp(h / 30, 0, 1)^0.75
```

待机、离线泵排水贡献为零；HI 不再乘入排水量，避免效率与健康重复扣减。面积为非线性展示估计，不是额外的体积扣除项。水位使用有效面积换算，三维 B2 示意占地按面积比例映射。上涨速度使用最近 60 个仿真秒的多点线性回归，单位 cm/min。

## 天气和设备

WeatherSimulator 为唯一雨量来源，既有 12 秒时间常数平滑追随场景目标。正常降雨保持 8 mm/h，强降雨升至 55 mm/h，极端暴雨目标经 8→35→55→72→86→100 mm/h 的时间节点连续插值，到末节点后保持。

P03 直接复用 M3 `bearing_degradation`：振动、温度、效率和 HI 来自同一设备状态。既有标定的稳定效率约 76%，没有为了演示强制改写为 55%。P01/P02 启动后增加真实模型出流。管网压力/流量继续使用原管网模型，但 M5 尚未把车库出流逐段注入具有水力求解的排水拓扑。

## 规则风险

`Flood scenario risk score · 场景规则模型` 明确区别于 M6 预测模型。

| 因子 | 权重 | 归一化 |
|---|---:|---|
| 水位 | 0.35 | 0/3/8/15/25 cm 对应 0/0.1/0.3/0.65/1，分段线性 |
| 降雨 | 0.20 | rainfall / 100，限制 0–1 |
| 泵能力损失 | 0.20 | 1 − 有效能力 / (120÷3600)，限制 0–1 |
| 上涨速度 | 0.15 | 正向 cm/min / 1，限制 0–1 |
| 人员车辆暴露 | 0.10 | 0.6×people/40 + 0.4×vehicles/60，限制 0–1 |

风险为加权和×100，范围 0–100；每项返回归一化值、权重、得分点数和占总风险百分比。人员/车辆默认 32/48，可调。风险分级边界 20/40/60/80；场景 Stage 取水位阈值 3/8/15/25 cm 与风险等级映射中的更高者。风险≥60 提示 M7 待接入，无工单或应急动作。

## 预测

`FloodForecastService` 深复制当前状态、天气目标、设备命令/故障年龄、泵额定能力与水位历史，独立按 5 秒步长向前计算。默认 +10/+20/+30 分钟，可指定 1–60 分钟内最多 6 个不同整数 horizon。

使用已计划降雨曲线以及设备故障继续演化的假设，保留已设置的备用泵工况，也包含尚未触发的计划 P03 故障。预测不受演示停止时长截断，不表示事故已恢复；不修改真实引擎。响应包含计算基准 revision、时间和假设。页面每 10 秒请求，切页取消；过时场景结果不覆盖当前页面，断线保留上次结果并标记。

## 三维与图表

- WaterSurface 固定 geometry/material，uniform 波纹、透明软边；面积驱动连续缩放、业务 cm 换算实际高度，从 B2 局部低洼点扩展。
- RainEffect 预分配最大 1800 粒子，动态 draw range、速度和透明度；雨量增加时光照略降、背景变暗、雾增强。
- FloodRiskEffect 在 B2 使用固定热区平面和环；颜色由风险决定，面积由积水决定。风险≥60 显示脉冲，≥80 增强，低风险无闪烁。透明环预热后复用 GPU 资源。
- 场景启动一次切地下并聚焦 B2，随后保持手动相机控制；水位/风险 CSS2D 标签实时更新。仅 B2 使用实际 FloodRisk 染色，其他建筑保留明确的示例风险。
- 四个 ECharts Tab 分别显示雨量、水位、有效泵能力、风险，单位分开。实时缓存最多 1800 点、最近 60 仿真分钟，暂停心跳不新增点；切场景/会话或 Reset 清空。

## 事件、告警与存储

`flood_scenarios` 保存事件、配置、峰值、当前 stage/status 和一个告警 JSON；`flood_snapshots` 每 5 个墙钟秒记录实际状态。唯一键 `(scenario_id, simulation_time)` 避免暂停重复写入。start/stop/reset 额外保存边界状态。快照 API 至多返回 600 个均匀抽取的真实行并保留端点，返回原始 total，不生成虚构历史。

每个场景固定一个 `FLOOD-<UUID>` 告警，WATCH/WARNING/HIGH/EXTREME 对应 Info/Warning/Major/Critical；更新同一告警而非每秒新增。当前级别可以变化，峰值保留；Reset 归档为 `ended_by_reset`。这不是已完成处置。场景记录和快照保留，M7 的确认/关闭告警流程尚未实现。

存储故障不会停止仿真，页面显示存储状态，采样器保留每个场景的最新待写快照并重试；断库期间不保证保留每个中间点。进程重启将数据库中遗留 running 场景标为 stopped，内存仿真重新初始化，不会自动接续事故。

迁移版本 `04ac9081f4fe`，前置 `2cae9fa70c8f`。仅保留中央 `DEMO_EXTREME_RAIN` 模板，不 Seed 大量事故历史。

## API

前缀 `/api/v1/simulation/flood`，成功控制请求返回完整 ParkRealtimeState。

| 方法 | 路径 | 内容 |
|---|---|---|
| POST | `/start` | scenario、durationMinutes(1–120)、peopleCount、vehicleCount；仅 development |
| POST | `/demo-start` | 统一极端暴雨模板、软件仿真按钮 |
| POST | `/stop` | 暂停，保留事故 |
| POST | `/reset` | 归档并恢复日常初始状态 |
| POST | `/exposure` | peopleCount(0–500)、vehicleCount(0–300)；仅 development |
| GET | `/status` | FloodSimulationState |
| GET | `/forecast?horizons=10,20,30` | 当前及未来水位、面积、风险 |
| GET | `/storage` | 数据库存储状态、采样周期、最近采样 |
| GET | `/scenarios` | 最近 30 条实际场景记录 |
| GET | `/snapshots/{scenario_id}` | 实际快照，总量和抽样点 |

DEV 隐藏不等于身份认证；正式部署仍需原有单 worker、HTTP/WS 代理和访问控制。生产前端只保留正式演示启动按钮，启动前确认“将启动软件仿真事故场景，不影响真实设备。”
