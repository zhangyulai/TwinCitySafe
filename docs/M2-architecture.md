# M2 Realtime Simulation Engine 架构

M2 在 M0 服务骨架和 M1 Web3D 场景上增加实时数据链路。所有状态来自软件仿真，既不是实际传感器采集，也不是正式事故、风险预测或异常检测结果。三维几何沿用 M1，实时消息只驱动现有对象与新增雨效、水面。

## 数据链路与时钟

```text
FastAPI lifespan
  └─ RealtimeService
      ├─ SimulationEngine：每 1 秒墙上时间一次 tick
      │   ├─ WeatherSimulator
      │   ├─ DeviceSimulator
      │   ├─ FloodSimulator
      │   └─ PipelineSimulator
      └─ ConnectionManager：每客户端独立最新状态队列
          └─ /ws/realtime：REALTIME_STATE 全量状态
              └─ App 级 RealtimeSocket
                  └─ useRealtimeStore
                      ├─ Dashboard 数值与 ECharts 最近采样
                      └─ DigitalTwinScene props/watch
                          └─ DigitalTwin.applyRealtimeState
                              ├─ SceneManager / RainEffect
                              ├─ DeviceManager
                              ├─ WaterSurface
                              └─ PipelineManager
```

业务状态以 1 Hz 更新，Three.js 用独立 RAF 渲染和移动已有雨粒子，二者不会相互创建计时器或场景。仿真速度为 0.25–10×，只改变每次 tick 的模拟 `dt`；内部最大子步为 0.25 个模拟秒。进程长时间卡顿后的墙上时间追赶限制为 5 秒，避免一次大幅跳变。

暂停只冻结模拟时间与遥测，后台仍发送 1 Hz 心跳，时间戳和 revision 继续推进。相机交互和表现层动画仍由场景渲染循环管理，暂停不等于断开连接。

## 后端职责

| 文件 | 职责 |
|---|---|
| `backend/app/main.py` | lifespan 创建一个服务、启动后台任务、退出时清理任务/连接；保留数据库启动检查 |
| `app/schemas/realtime.py` | Pydantic 状态、枚举、字段范围、单位与控制请求；camelCase 序列化 |
| `app/api/realtime.py` | REST 查询与控制、WebSocket 路由、设备 404/请求 422、WebSocket Origin 校验 |
| `app/services/realtime_service.py` | 连接引擎与消息发布，统一启动及关闭 |
| `app/websocket/messages.py` | `REALTIME_STATE` envelope；为后续消息类型保留名称 |
| `app/websocket/manager.py` | 独立发送任务、容量 1 最新状态队列、超时与断开清理 |
| `simulator/engine.py` | 当前状态、快照副本、启停/重置/速度、固定墙上时间发布与子步推进 |
| `simulator/state.py` | clear、0.8 cm、三台泵、三条管线的初始状态 |
| `simulator/config.py` | 发布周期、最大子步、低水位上限、平滑响应函数 |
| `simulator/weather_simulator.py` | 天气目标、温湿度、风速与降雨渐变 |
| `simulator/device_simulator.py` | 泵状态对应目标、连续遥测与有效排水能力 |
| `simulator/flood_simulator.py` | 日常进水、泵排水、被动排水与低水位约束 |
| `simulator/pipeline_simulator.py` | 正常管线压力和流量；排水流量与降雨/泵能力关联 |

后端模块表中 `app/` 与 `simulator/` 均相对 `backend/`。项目根目录原有 `simulator/` 是 M0 预留目录；当前实际实现只有 `backend/simulator/`。

状态仅在进程内存保存，不按秒插入 PostgreSQL。每个应用 lifespan 有独立引擎，因此当前部署使用单个 Uvicorn worker；多 worker 不会自动共享或同步状态。

## 状态合同与单位

REST 与 WebSocket 复用 `ParkRealtimeState`；前端对应 `frontend/src/types/realtime.ts`，网络边界由 `realtimeValidation.ts` 检查结构、枚举与数值有效性。

| 字段 | 含义 |
|---|---|
| `timestamp` | 当前快照的 UTC ISO 8601 时间，JSON 序列化带 `Z` |
| `sessionId` | 本次引擎 UUID；后台重启会变化，Reset 不变 |
| `revision` | 会话内单调递增版本；心跳和有效控制操作更新，Reset 不回退 |
| `simulationTime` | Reset 以来的模拟秒数 |
| `running` / `speed` | 是否推进、模拟速度 |
| `weather` | condition、rainfall（mm/h）、temperature（℃）、humidity（%）、windSpeed（m/s） |
| `environment` | b2WaterLevel（cm）、b2WaterArea（m²）、smoke、airQuality（模拟指标） |
| `devices` | id、name、status、temperature（℃）、vibration（mm/s）、current（A）、rpm、efficiency（%）、health（模拟指标） |
| `pipelines` | id、type、pressure（MPa）、flow（m³/h）、status |
| `system` | onlineDevices、alerts、eventCount |

枚举固定为：天气 `clear/cloudy/rain`；设备 `offline/standby/running/warning`；管线 `water/drain/fire`，M2 管线状态均为 `normal`。稳定 ID 为 P01/P02/P03 与 WS-001/DS-001/FS-001。

Weather 采用目标值、一阶响应和小幅确定性正弦扰动；切换 condition 即时生效，数值逐渐靠近目标。clear/cloudy 的降雨目标为 0，rain 约 14 mm/h；没有暴雨事故模式。

P01/P02 默认待机，P03 默认运行：42 ℃、1.8 mm/s、18 A、1450 rpm、96% 效率、94 健康指标。状态控制立即更新状态标签，遥测缓慢过渡。warning 是手动演示工况，仍提供随转速与效率下降的排水能力；standby/offline 不贡献有效排水。

水位使用“渗入＋降雨输入－有效泵排水－被动排水”，默认 0.8 cm，限制在 0.45–2.5 cm。该上限用于控制 M2 日常演示范围，不能用于工程水文计算。三条管线维持正常状态，排水流量随降雨和泵能力变化，不模拟泄漏。

在线数为 1265 个背景模拟设备加未离线的三台显式泵。warning/offline 泵各计一条当前告警；eventCount 为 0。health 与 airQuality 是模拟指标，不是正式风险得分。

## 接口与控制语义

| 方法 | 路径 | Body / 响应 |
|---|---|---|
| GET | `/api/v1/realtime/state` | 完整状态快照 |
| GET | `/api/v1/simulation/status` | running、speed、simulationTime |
| POST | `/api/v1/simulation/start` | 无 Body；完整状态，重复 Start 幂等 |
| POST | `/api/v1/simulation/stop` | 无 Body；完整状态，重复 Stop 幂等 |
| POST | `/api/v1/simulation/reset` | 无 Body；完整状态 |
| POST | `/api/v1/simulation/weather` | `{ "condition": "rain" }` |
| POST | `/api/v1/simulation/device/{device_id}/state` | `{ "status": "warning" }` |
| POST | `/api/v1/simulation/speed` | `{ "speed": 2 }`；数值 0.25–10 |
| WebSocket | `/ws/realtime` | 首次立即发快照，之后 1 Hz 全量状态 |

所有成功控制响应均为完整 `ParkRealtimeState`，使 UI 可立即展示后台确认后的状态。未知设备为 404；无效枚举、速度范围或多余请求字段为 422。Reset 保留调用前 running，恢复模拟时间 0、速度 1、clear、默认泵与管线及 0.8 cm 水位；不会修改 sessionId 或降低 revision。

WebSocket envelope 为 `{ "type": "REALTIME_STATE", "timestamp": "...", "data": ParkRealtimeState }`，外层与 data 时间一致。其余预留消息类别在 M2 不发送。

连接管理器接入时把当前快照入队；每客户端队列容量为 1，积压时覆盖旧状态。每条连接独立发送，默认 2 秒发送超时后关闭，其他客户端及仿真不等待慢连接。断连异常视为正常退出，服务关闭会取消并回收全部引擎/写任务和连接。

Origin 必须与 `CORS_ORIGINS` 中一个前端源完全一致；无 Origin 的 CLI 客户端可用。HTTP CORS 中间件不代替 WebSocket 的独立握手校验。Vite 的 `/ws` 代理启用 WebSocket 转发并保留浏览器 Origin；`VITE_WS_URL` 可指定独立完整地址。

## 前端状态、重连与顺序

`App.vue` 在挂载时连接、应用卸载时断开，连接由 Pinia store 内单个 `RealtimeSocket` 持有。Dashboard 页面进入与离开只影响场景和图表，不创建额外 WebSocket。

每次建立连接时并行获取 REST 快照和进行 WebSocket 握手。首条有效流消息后，迟到的初始 REST 数据不再覆盖流；每次连接有 generation 标识，旧连接回调和已取消请求不再影响当前状态。握手或心跳无有效消息超过 6 秒会重连，退避为 1、2、5 秒，之后保持 5 秒；成功接收有效消息后重置退避。

`useRealtimeStore` 用 shallowRef 保存完整状态，派生天气、环境、设备、管网、统计与更新时间。同一 session 只接受更高 revision；已有会话只能由新的实时流切换，跨会话迟到 REST 不回滚状态。断开只标记连接状态并保留数据；显式 store.reset 才断开并清空本地缓存。

最近水位序列最多 60 个采样，只有模拟时间变化时追加。后台 Reset 导致时间回退，或 sessionId 变化时清空旧序列。ECharts 图表按模拟时间标记，速度改变后“60 点”不等于固定 60 模拟秒；图表不做未来预测，也不提供历史回放。

DEV 模式才挂载 `SimulationControls.vue`。控制请求期间防止重复提交，确认响应后更新 store，失败时显示提示；面板包含天气、三台泵状态、速度与启停/重置。生产隐藏面板不构成 API 权限控制。

## Web3D 与 Vue 的边界

```vue
<DigitalTwinScene
  :realtime-state="realtime.state"
  @building-select="selectedBuilding = $event"
/>
```

`DigitalTwinScene.vue` 只在挂载或错误重建时创建 `DigitalTwin`，每份新状态通过 watch 调用 `applyRealtimeState()`，场景重建后立即重放当前快照。THREE.Scene、Mesh、Material 仍完全由普通 manager 实例持有，不放入深度 reactive。

| 更新接口 | 行为 |
|---|---|
| `DigitalTwin.applyRealtimeState(state)` | 分发天气、设备、水位、管线，保存当前快照 |
| `SceneManager.updateWeather(weather)` | 设置光照目标；在 RAF 中平滑靠近 |
| `RainEffect.updateWeather(weather)` | 调整固定池的雨量密度、速度、风偏；不按消息创建几何 |
| `DeviceManager.updateDeviceState(device)` | 按稳定 ID 更新材质、emissive、指示器和 CSS 标签 |
| `WaterSurface.updateLevel(cm)` | 以 `cm / 100` 更新 B2 水面高度；仅地下/风险模式可见 |
| `PipelineManager.updatePipelineState(pipeline)` | 更新管线对象绑定的当前状态，不重建管网 |

RainEffect 预分配 900 条线段粒子，改变 drawRange 控制密度，RAF 只更新已有顶点。水面为一个可复用半透明平面，高度按真实厘米换算，不放大水深；0.8 cm 等低水位主要结合读数观察。

地下管线与停车场均可拾取，地上透明建筑不会参与地下选择。选中管线保存稳定 ID，Vue 详情从当前 realtimeState 派生，因而每秒显示最新压力/流量。设备颜色为 standby 蓝青、running 绿、warning 橙、offline 灰。风险模式继续使用 M1 示例建筑风险颜色，与实时天气/设备控制不混为风险算法结果。

## 清理、测试与边界

App 卸载清理 WebSocket、重连/心跳定时器和 REST AbortController。Dashboard 卸载继续执行 M1 的 RAF、Observer、事件、controls、材质、几何、后处理与 WebGL context 清理，并增加雨效/水面清理。ECharts 卸载断开 ResizeObserver 并 dispose 图表。后台 lifespan 退出回收引擎和全部客户端写任务。

后端测试在 `backend/tests/test_simulation.py`、`test_realtime_api.py`、`test_realtime_websocket.py`；WebSocket 测试直接运行 ASGI 通道，无需旧版 TestClient。前端使用严格构建、`npm run test:web3d` 与 `npm run test:realtime`。执行结果、截图、性能与环境限制统一记录在 [M2-verification.md](M2-verification.md)。

M2 不实现 Isolation Forest、XGBoost、正式风险得分、暴雨事故、泄漏定位、应急方案或时间轴回放。M3 设备运维功能须等待新的用户指示。
