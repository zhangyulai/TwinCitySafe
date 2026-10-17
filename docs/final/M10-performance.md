# M10 性能与资源实测

## 浏览器与测量口径

质量及导航验收使用本机 Headless Chrome、ANGLE Vulkan SwiftShader 软件渲染。1920×1080、1440×900性能采样为 DPR1；另用DPR2浏览器核验质量上限。没有实际比赛独显的45FPS保证，不将本次Renderer表述为RTX。

质量测试每个分辨率/档位使用真实RAF约5秒，给出平均FPS及P95帧间隔。无事故正常场景在各档均为59 draw calls、17,652 triangles；无选中时既有实现本就跳过后处理。因此正常场景三档差异较小，本机采样波动不能用于声称显著提速。

## 真实三档质量

| 分辨率 | 实际场景尺寸 | 档位 | 平均FPS | P95帧间隔ms |
|---|---|---|---:|---:|
| 1920×1080 | 1022×600 | high | 24.56 | 50.10 |
| 1920×1080 | 1022×600 | medium | 20.47 | 83.20 |
| 1920×1080 | 1022×600 | low | 20.73 | 83.30 |
| 1440×900 | 870×591 | high | 22.85 | 83.30 |
| 1440×900 | 870×591 | medium | 22.80 | 83.40 |
| 1440×900 | 870×591 | low | 23.68 | 83.40 |

证据：[质量结果](M10-quality-results.json)、[执行日志](M10-quality.log)、[Profile审查](M10-three-profile.md)。

DPR上限high/medium/low为2/1.5/1，已在DPR2真实浏览器验证。地上静态阴影1024²/512²/关闭，地下各档关闭。固定1800雨池仅改变绘制数量，最多1800/1000/450。普通标签按距离和数量精简，异常/选中/事故核心标签保留。low跳过Outline，但真实选中的办公楼及其标签保留。

优化前基线为1256×615场景、FPS计数27/26/28/27/27；新Dashboard已改变三维视口尺寸。因此只保留原始证据，不计算不公平的前后速度提升百分比。

## 质量切换资源

真实地下模式和办公楼Outline预热后，连续24次画质切换使用同一Canvas；geometry/material/texture保持 **100/98/10→100/98/10**。GPU geometry/texture增加只发生在第一次显示地下及第一次使用后处理，预热后比较没有持续增长。

独立雨效视觉fixture验证1800→1000→450→1800绘制数量，始终复用同一个geometry和position buffer。这是视觉预算单元检查，未修改实时状态、未用fixture替代真实事故演化证据。

## 导航、RAF与WebSocket

真实UI按Dashboard→Operation→Pipeline→Risk→Simulation→Review连续10轮。共创建50个三维上下文，旧上下文全部释放；每个有场景的页面恰好1个活动WebGL上下文，Review默认未选档案时为 **0 Canvas、0 RAF、0活动上下文**。

整个浏览器标签页仅创建 **1条 `/ws/realtime` 业务连接**，导航后保持open；Vite自己的开发HMR通道单独排除。初次脚本把HMR算入而超时，修正探针口径后重跑成功，没有放宽业务单连接断言。

证据：[导航结果](M10-navigation-results.json)、[日志](M10-navigation.log)。`errors=[]`、`warnings=[]`。

## 三分辨率页面

1920×1080、1440×900、1366×768各六页，共18张实际全页截图：`screenshots/layout-{width}-{route}.png`。全部页面无横向溢出，导航和三维工具栏可访问；小高度允许纵向滚动。已目视1366六页的主要卡片、图表、资产列表和工具栏，主要内容未截断。

这些导航截图为正常运行状态。事故页、方案比较、历史回放的正式演示截图与资源测试由完整Final Smoke补充。

## API、模型和事故长时资源

最终生产浏览器首次打开到实时状态与Canvas挂载为 **1053.9 ms**（本机单次测量）。最终构建6.87秒；六路由懒加载，无大chunk警告。

以下为同源HTTP端到端计时，包含传输和序列化；风险预测重复请求可能命中5秒缓存，不能等同纯模型计算。应急比较每次执行实际四分支rollout并保存比较。

| API | 次数 | Mean ms | P95 ms |
|---|---:|---:|---:|
| health | 20 | 4.98 | 6.78 |
| realtime state | 20 | 5.42 | 6.97 |
| pipeline topology | 20 | 11.45 | 12.77 |
| active risk prediction (5s cache) | 20 | 5.66 | 11.53 |
| flood status | 20 | 4.64 | 5.87 |
| four-branch emergency compare (persists comparisons) | 10 | 222.62 | 283.44 |
| flood persisted replay | 20 | 137.66 | 137.57 |
| leak localization | 20 | 4.92 | 6.25 |
| leak persisted replay | 20 | 57.47 | 62.76 |

本轮M6回归在线模型内部调用平均 **2.372 ms**，软件渲染采样 **35 FPS**；这与上表完整HTTP请求计时不同，未复用旧M6性能报告。

| 长时检查 | 实际资源或结果 |
|---|---|
| M5完整30仿真分钟 | geometry/material/texture 103/98/1稳定；极端雨采样29 FPS |
| M7跨超过10仿真分钟 | 104/98/10稳定；采样30 FPS |
| M8第8.5至19.4仿真分钟 | 36/98/9稳定；采样30 FPS |
| M9连续100次scrub | 74/98/0保持不变 |
| M9真实5×播放 | 120.69墙钟秒推进601.226历史秒，74/98/0保持不变，采样32 FPS |

最终生产双事故闭环12组通过，单业务WebSocket，页面errors=[]；截图覆盖活动预测、方案比较、泄漏与历史回放。两类新CLOSED档案均保留，结束恢复正常监测。

首轮截图早于风险页首次刷新，增加三条ML预测、物理对照和模型解释的真实DOM就绪断言后完整重跑；以上生产数据与正式截图均采用第二轮结果。首轮记录保存在first-production-run，未修改业务代码或模型。

证据：[API计时](M10-api-performance.json)、[最终闭环](M10-final-smoke-results.json)、[最终状态](M10-final-state.json)、[本轮M6](M10-M6-browser-results.json)、[M7](M10-M7-browser-results.json)、[M8](M10-M8-browser-results.json)、[M9](M10-M9-browser-results.json)。
