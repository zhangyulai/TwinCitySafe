# M2 验证记录

验证日期：2026-10-01（Asia/Shanghai）。当前交付范围仅为 Realtime Simulation Engine，全部运行数据为软件仿真。

## 环境与复验命令

- Node.js 24、Python 3.13、Chrome headless、Playwright；开发前端 5173、后端 8000。
- PostgreSQL 启动连接检查通过。M2 状态保存于单进程内存，没有每秒遥测插入。
- 浏览器 WebGL 2 渲染器：ANGLE / Vulkan / SwiftShader Device (Subzero)，属于软件渲染。

从项目根目录启动 `./start-dev.sh`，再在另一终端执行：

```bash
npm --prefix frontend run build
(cd backend && .venv/bin/python -m pytest -q -W error)
npm --prefix frontend run test:realtime
npm --prefix frontend run test:web3d
```

浏览器脚本默认寻找 `/opt/google/chrome/chrome`，否则使用 Playwright Chromium；可设置 `CHROME_PATH`。测试依赖开发模式的场景诊断属性，运行时会控制共享内存中的仿真状态；M2 脚本结束恢复晴天、默认泵状态、1×、运行中。

## 构建与后端

- `npm run build`：通过，含严格 TypeScript 构建检查，未产生大分包警告；按需使用的 ECharts 与 zrender 分包为约 319.74 / 175.92 kB，Three.js renderer 约 374.04 kB（均未 gzip）。
- `pytest -q -W error`：12 passed，4.85 秒。覆盖原有 Health/CORS 及新增模型、API 和 WebSocket。
- 模型：共享 schema、默认值、快照隔离、停止冻结、Reset 保留启停、版本单调、速度子步等价、天气/设备/水位连续性、低水位边界、泵能力影响排水。
- API：完整状态、状态摘要、全部控制、枚举/范围/多余字段校验、未知设备 404、无效请求 422、Start/Stop 幂等。
- WebSocket：首个快照、1 Hz、10× 时频率不变、暂停心跳、多客户端一致性、单客户端退出不影响其他客户端、Origin 拒绝、慢/坏连接隔离、队列只保留最新状态、退出无遗留任务。

## M2 浏览器验收

`npm run test:realtime` 的 11 组检查全部通过。机器可读原始结果保存在 [M2-browser-results.json](M2-browser-results.json)。

| 检查 | 结果与证据 |
|---|---|
| 初次自动连接 | Health Online、Realtime Connected；页面内只有 1 条实时 WebSocket，REST 与流使用同一状态结构 |
| UI 更新 | 时间戳、P03 参数和 Dashboard 数据持续刷新 |
| Cloudy 灯光 | 实际 ambient 从 0.8 平滑降至采样时约 0.740；sun 和 hemisphere 同步变暗 |
| Clear / Cloudy / Rain | 控件触发真实 API；Rain 粒子可见，降雨逐步增加；采样时约 3.11 mm/h、234 条可见雨粒子 |
| 设备联动 | P03 running 绿色 `#52b890`、warning 橙色 `#d59547`、offline 灰色 `#687887`；P01 材质没有随 P03 被误改；P01/P02 可启停 |
| 水面高度 | 水位从约 0.81448 到 0.81782 cm，实际 mesh y 从 -5.664855 到 -5.664822 m；换算系数为 cm / 100 |
| 连续 30 次推送 | 平均间隔 1000.42 ms；降雨、水位、泵温度无无规律巨大跳变；同一个 canvas，33 个 geometry、1 个 texture 保持不变（雨效首次上传后采样） |
| 地下管线点击 | 实际射线点击 WS-001 打开详情，压力/流量文本随后更新 |
| 路由来回 3 次 | 保持 App 单条 WebSocket，每次 Dashboard 仅 1 个 Three canvas |
| Stop / Reset / Start | Stop 冻结模拟时间；Reset 恢复 clear、默认泵、time=0；Start 恢复推进 |
| 掉线与恢复 | 模拟离线 8.5 秒，卡片与最后更新时间不被清空；3 次延迟重试，后两次间隔约 2.15 / 5.14 秒；恢复后只有 1 条连接并继续更新 |

未出现意外 JavaScript、Vue、Three.js 或控制台错误。人为断网时 Chrome 报告 `ERR_INTERNET_DISCONNECTED`，验收单独记录这些预期网络错误，不将其伪称为无错误联网状态。

### 补充屏幕与速度检查

1440×900 视口下 scrollWidth 为 1440，无水平溢出；开发面板边界 x=1070、y=230、宽=340、高≈421.69，完全位于视口内。通过原生下拉把模拟速度改为 2×，后台确认 speed=2；Reset + Start 后恢复 speed=1、running=true。

另一次短断网检查测得首次重试约 1042.4 ms，随后间隔约 2137.3 / 5139.2 ms，符合 1/2/5 秒退避。完整 M2、完整 M1 与这些补充段分别执行通过；补充断言已并入持久脚本并通过语法检查，没有重复运行整套长检查。最终服务恢复为晴天、默认泵状态、运行中、1×。

## M1 回归

`npm run test:web3d` 的 16 组检查全部通过，原始结果见 [M2-web3d-regression-results.json](M2-web3d-regression-results.json)。覆盖旋转/平移/缩放、实际建筑 hover/click、镜头 tween、详情聚焦、空白取消、地下透明与风险示例模式、自动巡游、1440×900 布局、三次重进，以及 WebGL context loss 后恢复。

退出 Dashboard 后：待执行 RAF 为 0，canvas 为 0，活动 WebGL context 为 0，旧诊断入口被删除；重建后仅 1 个 Three canvas/context。晴天地上空闲仍为 59 draw calls / 17652 triangles。新增水位图有独立的 2D canvas，因此回归脚本的三维 canvas 断言限定到场景容器。

## 性能与范围

相同 1920×1080 浏览器视口、同一地上视角、鼠标移离场景时测得：

| 状态 | 平均 RAF 帧率 |
|---|---:|
| Clear | 33.58 FPS |
| Rain | 34.03 FPS |

本轮未见雨效果导致明显帧率下降。M1 该软件渲染环境也约为 35 FPS；本结果不能证明比赛硬件上满足 >45 FPS。正式显卡、浏览器图形加速、屏幕分辨率与复杂选中状态下仍需现场测量。

1 Hz 消息只更新现有对象属性，雨效固定预分配 900 条线段；水面和设备几何不会随消息重建。THREE 对象由 manager 普通实例持有，Pinia shallowRef 仅持有业务快照。ECharts 最多显示 60 个近期水位采样，不做未来预测或回放。

## 截图与演示

- [晴天实时总览](M2-clear.png)
- [雨天与实时天气](M2-rain.png)
- [地下管线详情、水面与设备](M2-underground.png)
- [1440×900 屏幕布局](M2-1440.png)

打开 <http://127.0.0.1:5173/dashboard>，确认实时 Connected。打开“仿真控制”：先选 Rain 并等待数值渐变，再切“地下”点击管线；把 P03 设为 warning，观察卡片与泵变橙，再切 running 恢复绿色。Stop 用于暂停数值，Reset 恢复基线，Start 恢复运行；水位变化很小时可使用 2×/5×，但推送仍为 1 Hz。

## 当前边界

内存状态在后端重启后恢复初始值，当前按单 worker 部署。手动 warning/offline 计数是模拟状态汇总，风险模式沿用 M1 示例着色；没有正式风险计算、暴雨事故、泄漏、应急方案或历史回放。M2 停止于本阶段，未进入 M3。
