# M1 Web3D 数字孪生底座

## 边界

M1 替换 Dashboard 中央占位区；左右数据面板、顶部导航、Health API 与数据库保持 M0 功能。所有建筑属性和风险颜色来自示例元数据。不实现 WebSocket 业务、仿真、预测、泄漏、应急方案或事件回放。

## 模块及职责

```text
frontend/src/
├── components/digital-twin/
│   ├── DigitalTwinScene.vue      挂载、按钮、详情、错误恢复、向 Dashboard 发事件
│   └── digital-twin.css          场景 UI 与 CSS2D 标签
└── three/
    ├── index.ts                 DigitalTwin 生命周期与模块编排
    ├── types/scene.ts           元数据、选择事件、模式、统计及风险图例
    ├── utils/dispose.ts         几何、材质、纹理、实例网格与标签清理
    ├── core/
    │   ├── SceneManager.ts      Scene、Fog、环境/半球/方向光及场景对象
    │   ├── CameraManager.ts     PerspectiveCamera、构图、聚焦、复位
    │   ├── RendererManager.ts   WebGLRenderer、CSS2DRenderer、DPR、释放
    │   └── ControlsManager.ts   OrbitControls 与距离/俯仰约束
    ├── interaction/InteractionManager.ts  Raycaster、Hover、Click、DoubleClick
    ├── animation/CameraTween.ts           相机与 target 同步缓动
    ├── building/
    │   ├── BuildingManager.ts   建筑、停车场、窗户、标签与材质模式
    │   └── metadata.ts          集中管理示例建筑属性
    ├── environment/ParkEnvironment.ts    地面、道路、草地、广场、景观
    ├── pipeline/PipelineManager.ts       地下静态管线 Demo
    ├── device/DeviceManager.ts           P01/P02/P03 静态设备
    ├── effects/EffectManager.ts          RenderPass、OutlinePass、OutputPass
    └── loaders/ModelLoader.ts            可选 GLTF/GLB 加载入口（本阶段不调用）
```

CSS 标签采用 [CSS2DRenderer](https://threejs.org/docs/pages/CSS2DRenderer.html)，关闭标签指针事件以免遮挡射线交互。选中优先使用 [OutlinePass](https://threejs.org/docs/pages/OutlinePass.html)，悬停使用较弱轮廓与 emissive；选中保持时另一建筑的 Hover 通过 emissive 区分。没有高亮时直接渲染，避免不必要的后处理。管线不做流动动画。

## 场景与稳定标识

坐标系采用 Three.js Y 向上，地面约为 y=0，示范底盘 114 × 92 个场景单位。坐标只是程序化空间布局，不是测绘或 BIM 数据；示例建筑面积是独立业务字段，不由低精度几何体计算。

| 标识 | 名称 | 位置 | 演示风险 |
|---|---|---|---|
| A-OFFICE | 办公楼 A | 西北，高层与附楼 | 低 |
| B-RESEARCH | 科研楼 B | 东北，双翼建筑 | 一般 |
| C-LAB | 实验楼 C | 西南，实验楼与附楼 | 较高 |
| D-SERVICE | 综合服务楼 | 东南，低层服务建筑 | 低 |
| B2-PARKING | B2 地下停车场 | (0, -6, 10)，开放顶面 | 高 |

停车场对象名为 `underground-parking-b2`，metadata 包含 `id/name/type/level`，其中 type 为 parking、level 为 -2。P01、P02、P03 位于停车場前缘的排水设施区，userData.id 使用大写稳定 ID，Three 对象名分别为 device-p01/p02/p03。后续 M5 可通过稳定 ID 定位故障泵，不依赖数组位置。

地下管线分给水（水蓝）、排水（青绿）、消防（暗红），不同高度位于地表以下。它们是静态视觉示意，不代表正式的流体或网络拓扑模型。

## Vue 接口

```vue
<DigitalTwinScene @building-select="selectedBuilding = $event" />
```

选择事件为 `BuildingSelection | null`，包含 `buildingId/buildingName/buildingType`，以及元数据中的面积、楼层、设备数量、告警、安全指数、风险等级、状态等。所有数值集中在 `building/metadata.ts`。关闭选择、跨模式隐藏当前对象、重新加载场景时发送 null。

## 生命周期与性能

- 由组件挂载后创建 DigitalTwin，ResizeObserver 观察真实容器，不依赖全窗口宽高。
- 只有一个 RAF 循环；相机缓动和巡游共享它，没有巡游 setInterval 或独立动画循环。
- 离开 Dashboard 时取消 RAF、事件监听、Controls、ResizeObserver；释放后处理目标、几何、材质、纹理、实例化缓冲、标签和 WebGL context。
- 页面隐藏时暂停渲染，取消镜头动画和巡游；返回时恢复，避免后台持续占用 GPU。
- 窗户、树木、路灯、车位线、标线使用 InstancedMesh；建筑主体按材质合并，轮廓按建筑合并。
- DPR 最大 2；后处理像素比最大 1.5；阴影 1024²，只在场景模式改变时重新计算。
- Three 核心和渲染/插件独立构建分包，Dashboard 路由按需加载。
- `__twinDebug` 仅开发环境挂在场景容器上，提供只读相机/对象/渲染数据供浏览器验收。生产构建不挂载该属性。

## 扩展点

M2 可通过稳定对象 ID 与明确的更新方法接入有状态仿真数据。M4 才建立正式管网拓扑与流动效果；M5 才实现积水演化；M6 才接入风险预测。当前 ModelLoader 可加载未压缩的 glTF/GLB；DRACO/KTX 等压缩资源尚未配置解码器。
