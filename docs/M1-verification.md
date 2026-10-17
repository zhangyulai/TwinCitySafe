# Milestone 1 验收记录

本阶段仅实现 Web3D Digital Twin Foundation，未进入 M2。使用本机独立 Chrome 无头浏览器执行真实页面交互与截图，同时完成 TypeScript 检查和生产构建。

## 验收结果

| 要求 | 结果 |
|---|---|
| 中央真实 Three.js WebGL 2 场景 | 通过，Canvas 实际渲染 |
| 至少四栋主要建筑 | 通过，办公/科研/实验/综合服务楼 |
| 道路、草地、广场、景观 | 通过，截图检查 |
| 地下停车场 | 通过，B2-PARKING / underground-parking-b2 |
| 至少三类地下管线 | 通过，给水/排水/消防 |
| P01 / P02 / P03 | 通过，设备对象与标签 |
| 鼠标旋转、滚轮缩放、右键平移 | 通过，实际鼠标输入及相机状态检查 |
| Hover 与 pointer 光标 | 通过，真实 Raycaster 拾取 |
| 点击高亮与元数据卡片 | 通过，实际点击不同建筑 |
| 新选择替换旧选择 | 通过，保持选择并缩放后点击另一建筑 |
| 点击空白或关闭卡片取消选择 | 通过 |
| 点击/聚焦按钮与平滑 Camera Tween | 通过，多次采样捕获 5–6 个动画中间状态 |
| 恢复默认视角 | 通过，相机位置与全景基准一致 |
| 地上/地下/风险模式 | 通过，切换状态及截图检查 |
| 地下建筑透明、停车场/管线显示 | 通过，主体透明度 0.13，地面 0.075 |
| 风险颜色 | 通过，低/一般/较高/高四级示例颜色 |
| 自动巡游 | 通过，飞行、停留、到达地下停车场、手动停止 |
| 1920×1080 / 1440×900 | 通过，无水平溢出；1440 三维视口约 836×543，页面可纵向滚动 |
| 离开页面清理 | 通过，0 个遗留 RAF、0 个 Canvas、0 个活动 WebGL context |
| 连续重新进入三次 | 通过，每次恰好 1 个 Canvas 与 1 个活动 WebGL context |
| WebGL context 丢失后重试 | 通过，错误提示正常，重建后仅一个 Canvas，旧 context 已释放且选中项清空 |
| JavaScript/Three.js 错误 | 正常验收流程 0 个 page/console error，无 Three.js 资源/重复 context 警告 |
| npm run build | 通过，TypeScript 检查成功，无大包警告 |
| npm run lint | 未配置 lint 脚本，未执行 |
| M0 联调 | Health 经前端代理返回正确 JSON；PostgreSQL SELECT 1 成功 |

## 性能实测与边界

- 环境：1920×1080、deviceScaleFactor=1、独立无头 Chrome，ANGLE Vulkan SwiftShader 软件渲染。
- 优化前地上全景 125 draw calls；建筑几何合并后 **59 draw calls**，三角形仍为 **17,652**。
- 渲染器当前记录 32 个几何资源、1 个纹理资源。合并几何增加独立 geometry 数量，同时减少 draw calls，属于预期取舍。
- 软件渲染采样约 2.5 秒、89 个帧间隔，平均 **35.37 FPS**。不能据此宣称普通 GPU 或比赛机器稳定达到 45 FPS；需在目标设备开启硬件加速后验证，尤其是选中轮廓和地下透明模式。
- 浏览器出现 GPU ReadPixels 性能诊断（截图/软件渲染环境），没有持续应用错误、未处理 Promise 或资源泄漏告警。
- DPR≤2、后处理 DPR≤1.5、阴影 1024²；静态阴影按模式更新；窗户/树木/路灯/标线采用实例化，建筑与轮廓已合并。
- 生产分包：Three core 约 185.62 kB、Three renderer/addons 约 374.04 kB、Dashboard 约 40.49 kB（均为压缩前产物大小）。

## 截图

- [地上全景](M1-above.png)
- [地下空间](M1-underground.png)
- [示例风险分级](M1-risk.png)
- [1440 桌面布局](M1-1440.png)

## 已知范围限制

程序化园区不代表真实场地；建筑属性、风险等级均为示例数据。地下管线只是视觉 Demo，没有流动、拓扑或泄漏计算。三维依赖 WebGL 2；浏览器不支持时有明确错误与重试提示。ModelLoader 预留未压缩 GLB/glTF 入口，本阶段不加载外部模型。

Milestone 1 已完成，当前停止开发，等待进入 Milestone 2。

## 复现浏览器验收

保持开发服务运行，在 frontend/ 下执行 `npm run test:web3d`。浏览器路径可通过 CHROME_PATH 指定；本机优先使用已安装 Chrome，其他环境可用 `npx playwright install chromium` 下载测试浏览器。该测试依赖开发环境只读诊断接口，不面向生产预览站点。

最终复核：`npm run test:web3d` 整体退出码为 0；WebGL 已丢失时不再重复调用丢失扩展，恢复测试无 Three.js 警告。`npm run build` 再次通过，无大包警告。
