# M3 验证记录

执行日期：2026-10-02 至 2026-10-03（Asia/Shanghai）。范围仅为 Smart Equipment Operation。

## 环境和复验

Node.js 24、Python 3.13、PostgreSQL 17、Chrome headless / Playwright；scikit-learn 1.9.1，依赖锁文件为 `backend/requirements.lock.txt`。WebGL 渲染器是 ANGLE / Vulkan / SwiftShader 软件渲染，不代表比赛 GPU。

从项目根目录按 README 完成迁移、seed 和训练，启动 `./start-dev.sh` 后：

```bash
npm --prefix frontend run build
(cd backend && .venv/bin/python -m pytest -q -W error)
npm --prefix frontend run test:operation
npm --prefix frontend run test:operation-state
npm --prefix frontend run test:realtime
npm --prefix frontend run test:web3d
```

浏览器脚本默认使用本机 `/opt/google/chrome/chrome`，不存在时使用 Playwright Chromium；可通过 `CHROME_PATH` 指定。测试会操作开发仿真状态，完成后恢复默认运行基线。

## 数据库与后端

- Alembic `upgrade head` 成功，revision 为 `0001_equipment`；`alembic check` 返回 `No new upgrade operations detected`。
- P01/P02/P03 正式入库；seed 幂等，已有累计运行值保留。
- 实际 PostgreSQL 的 `/telemetry/status` 返回 available=true，周期5秒；运维页的1h/6h/24h查询读到了实际采样，不是补造历史。
- 最终后端测试 **25 passed，14.17秒**。所有测试使用独立临时 SQLite，不修改运行中的 PostgreSQL。
- 覆盖 Health/CORS、M2协议/引擎/WS、资产筛选查询、时间范围和600点降采样、HI公式与平滑、真实模型分数、模型缺失降级、三种故障、模板建议、告警创建/去重/解除、采样事务/故障/任务清理、生产故障接口禁用。
- 正常备用泵启动有60个模拟秒的明确过渡窗口；新增回归证明 P01 正常启动不会产生活动告警，P02故障在过渡后仍可检出。Fault切换本身不会重置启动窗口。

## 模型评估

结果由 [metrics.json](../algorithm/anomaly_detection/reports/metrics.json) 实际生成。

| 项目 | 结果 |
|---|---:|
| 正常训练样本 | 10000 |
| 独立测试样本 | 3564 |
| Precision | 0.967636 |
| Recall | 1.000000 |
| F1 | 0.983552 |
| 正常样本误报率 | 0.032778 |
| 真正常 / 误报 | 1741 / 59 |
| 漏报 / 真异常 | 0 / 1764 |

轴承退化、过热、低效率各588个测试样本，召回率均为1.0。训练与测试采用不同随机种子，但均来自同一软件仿真器；测试故障只统计注入45模拟秒之后的数据。这些数字不能证明真实设备泛化，也不是早期检测时间评估。模型的原始分数映射与UI平滑规则见 [M3架构](M3-architecture.md)。

## M3 浏览器实测

`test:operation` 的8组主要检查通过，原始结果见 [M3-browser-results.json](M3-browser-results.json)。

| 检查 | 证据 |
|---|---|
| 默认P03与数据来源 | 资产来自数据库，实时参数来自同一WS；Health Online，IF可用，默认HI大于90 |
| 设备筛选与聚焦 | 类别、搜索、状态过滤有效；P01待机不误作运行故障；点击列表驱动同一相机聚焦 |
| 趋势图 | 温度/振动/电流/效率四Tab，5min与1h/6h/24h切换通过；图表canvas不重新创建，历史最多600点 |
| 真实故障链 | 10×加速下实际采样达到温度66.40℃、振动5.19mm/s、HI56.68、score0.912；P03变warning、红色脉冲、P0建议 |
| 资源稳定 | 故障更新仍是同一个Three canvas；异常环上传后28个geometry、1个texture保持稳定 |
| 告警与Dashboard | 多次采样只有同一个active告警ID；Dashboard同步warning和告警计数，链接返回P03运维 |
| 正常恢复 | HI恢复95.61、score约0.024；同一数据库告警resolved，红色脉冲关闭 |
| 页面与生命周期 | 1440×900无水平溢出、DEV面板在视口内；离开运维页后所有canvas清除，重复进入只有一个Three canvas和一条实时WS |

截图在不同时间点拍摄，因此退化截图中的最终HI约50.1、温度68℃、振动5.20mm/s，较上述首次达到验收条件时更严重；属于同一连续仿真过程。

- [运维正常状态](M3-operation-normal.png)
- [轴承退化与建议](M3-operation-fault.png)
- [Dashboard联动告警](M3-dashboard-alarm.png)
- [1440×900布局](M3-operation-1440.png)

### 缓存与模型缺失的补充页面检查

`test:operation-state` 通过：用有效的本地状态夹具验证305次更新后缓存上限为300点；暂停且时间推进超过5分钟后缓存过期为0，但设备最后读数仍保留。注入与后端缺模型合同一致的状态后，页面显示“异常模型未加载”，HI和三维场景继续存在，没有JavaScript错误。此段是UI状态夹具测试；实际缺失模型文件的降级另由后端pytest验证。结果见 [M3-state-results.json](M3-state-results.json)。

最终M2回归在启动过渡修复与缓存过期处理后执行，12组全部通过。M1完整回归和M3真实网络故障闭环也分别通过；各套件证据如实独立记录。

## M1/M2 回归

M1 的16组检查通过，详见 [M3-m1-results.json](M3-m1-results.json)。保留建筑交互、镜头聚焦、风险示例、巡游、地下模式、窗口缩放、重复进入、RAF与context释放，以及WebGL丢失恢复。

M2 的完整12组检查通过，详见 [M3-m2-results.json](M3-m2-results.json)。保留天气灯光、雨效、水面、设备状态隔离、真实管线点击、30次连续推送资源稳定、暂停/重置、倍速、单连接与断线退避。

旧测试改用仍为空间占位的管网页面检查“无场景基线”，因为Operation已经变成真实场景页；同时适配App级自动Health初始化。没有删掉原有场景或连接断言。人工断网产生的网络错误与Chrome软件渲染驱动提示在结果中单独记录；没有意外应用错误。

## 性能

1920×1080视口、鼠标移离场景后，运维设备近景实测正常 **60.00 FPS**，故障脉冲 **60.00 FPS**。ECharts持续setOption，未见故障或图表引入明显下降。

首次近景检查约12 FPS；原因是地上透明场景在近距离下叠加绘制。设备聚焦现在临时隐藏地上背景，恢复视角/切换模式时恢复，复用现有对象而非新建引擎。

Dashboard整园区在同一软件渲染环境仍约33 FPS，不能把运维近景60 FPS推广为所有场景都达到45 FPS。正式比赛显卡、屏幕和浏览器加速条件仍需实机验证。

## 演示与当前边界

打开 <http://127.0.0.1:5173/operation>，默认P03。打开仿真控制，选择“轴承退化”，可设5×/10×加速观察HI和异常分数逐渐变化；切回“正常工况”观察恢复。Reset恢复仿真参数，不删除历史数据。首次运行只能显示已经积累的历史，未满24小时不会伪造24小时样本。

当前为三个演示泵、单worker、内存物理状态和数据库采样记录。模型训练与规则阈值均面向软件演示；未接生产传感器、工单执行或后续风险/事故模块。当前停止在M3，不进入M4。
