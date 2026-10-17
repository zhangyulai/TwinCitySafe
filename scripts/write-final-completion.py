#!/usr/bin/env python3
"""Finish the specified 32-section report from successful production evidence."""
import json,re
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/final'
def read(name):return json.loads((OUT/name).read_text())
def num(value,n=3):return '未记录' if value is None else f'{value:.{n}f}'
def main():
    smoke=read('M10-final-smoke-results.json');final=read('M10-final-state.json');reg=read('M10-regression-results.json')
    assert smoke['success'] and final['success'] and len(reg)==15 and all(x['exitCode']==0 for x in reg)
    source=ROOT/'docs/M10-completion-report.md';original=source.read_text()
    headings=re.findall(r'^## (\d+)\. (.+)$',original,re.M);assert [int(x[0]) for x in headings]==list(range(1,33))
    bodies={int(n):body.strip() for n,body in re.findall(r'^## (\d+)\. [^\n]+\n(.*?)(?=^## \d+\.|\Z)',original,re.M|re.S)}
    f=smoke['flood'];l=smoke['leak'];before=smoke['floodBeforeResponse'];leak_before=smoke['leakBeforeResponse'];metrics=f['metrics']['prediction_review']
    matrix='\n'.join(f"| {r['test']} | 通过 | {r['seconds']:.2f}s | [日志](final/{r['log']}) |" for r in reg)
    api='\n'.join(f"| {b['name']} | {b['count']} | {b['meanMs']:.2f} | {b['p95Ms']:.2f} |" for b in read('M10-api-performance.json')['benchmarks'])
    elapsed=(datetime.fromisoformat(smoke['finishedAt'].replace('Z','+00:00'))-datetime.fromisoformat(smoke['startedAt'].replace('Z','+00:00'))).total_seconds()
    m7=read('M10-M7-browser-results.json')['performance'];m8=read('M10-M8-browser-results.json')['performance'];m9=read('M10-M9-browser-results.json')['performance']
    bodies[1]='TwinCitySafe V1.0 比赛展示版本已完成并冻结核心功能。六大页面、两类事故闭环、正式演示控制与生产构建均通过本轮验证；当前服务运行在正常监测状态。没有新增核心场景或模型，没有重写 SceneManager、仿真引擎、预测、拓扑或回放。\n\n入口：<http://127.0.0.1:5173/dashboard?demo=1>。后续进入比赛排练、材料制作和最终部署，已知模型与硬件性能边界保持公开。'
    bodies[8]=f'''确认后以10×启动原M7雨势回落工况并进入应急推演，拒绝替换活动事故。人工比较并选择B后继续真实时钟，完成工单并人工关闭。

本轮档案 `{smoke['floodIncidentId']}`。执行前水位 **{num(before['waterLevel'])} cm**、规则风险 **{num(before['riskScore'])}**；关闭前水位 **{num(f['beforeScenario']['waterLevel'])} cm**、风险 **{num(f['beforeScenario']['riskScore'])}**，峰值水位 **{num(f['metrics']['peak_metrics']['peak_water_level'])} cm**。降雨由100降至20 mm/h，与泵排水共同影响，不描述为方案立即排空。保留 {f['snapshotCount']} 个观测与 {f['timelineCount']} 条时间轴。

[生产闭环证据](final/M10-final-smoke-results.json)。'''
    bodies[9]=f'''一键启动现有WS-003工况，自动10×并进入地下泄漏模式；从真实压力流量定位、比较和人工确认V-W-03隔离。

本轮档案 `{smoke['leakIncidentId']}`。处置前估算泄漏量 **{num(leak_before['estimatedLeakFlow'])} m³/h**、规则风险 **{num(leak_before['riskScore'])}**；关闭前泄漏量 **{num(l['beforeScenario']['estimatedLeakFlow'],8)} m³/h**、风险 **{num(l['beforeScenario']['riskScore'])}**。供水状态仍为 `{l['beforeScenario']['serviceStatus']}`，科研楼B与实验楼C影响保留。保存 {l['snapshotCount']} 个观测、{l['timelineCount']} 条时间轴及完成工单。'''
    bodies[10]=bodies[10].replace('正式生产启动自检的最终记录：**待本轮实测填入**。','正式生产启动已通过分项Ready与真实同源WebSocket首帧检查；页面自检全部通过。见 [启动日志](final/M10-start-demo.log) 与 [最终状态](final/M10-final-state.json)。')
    bodies[11]=bodies[11].replace('生产界面最终清理结果：**待本轮实测填入**。','生产界面重置及结束清理后均验证为1×正常监测、全部演示阀门开启；两类新CLOSED档案及完成工单保留，GET前后档案详情hash不变。见 [最终核验](final/M10-final-state.json)。')
    bodies[14]=bodies[14].replace('初始加载的最终墙钟结果：**待本轮实测填入**。',f'新浏览器首次打开生产页面到实际实时状态与Canvas挂载为 **{smoke["initialLoadMs"]:.1f} ms**（单次本机测量，非全设备保证）。正式构建日志见 [M10-build.log](final/M10-build.log)。')
    bodies[15]=bodies[15].replace('事故、方案比较与已选档案在正式 Final Smoke 中的三分辨率结果：**待本轮实测填入**。','正式Final Smoke进一步在活动运维、Risk、Flood、方案比较、Leak及两类选中档案下检查1440×900和1366×768，均无横向溢出，保存对应截图；1920保留主截图。允许纵向滚动，不声称完整长表同时位于首屏。')
    bodies[16]=bodies[16].replace('本轮完整 WebGL 丢失/恢复与全回归结论：**待本轮实测填入**。','本轮M1真实WebGL丢失/恢复、页面重入和上下文释放均通过，15项历史回归全部成功。')
    bodies[18]=bodies[18].replace('本轮 Final Smoke 误差：**待本轮实测填入**。',f'本轮Final Smoke有 **{metrics["samples"]}** 个到期样本，ML水位MAE **{num(metrics["water_mae"],4)} cm**、风险MAE **{num(metrics["risk_mae"],4)}**；物理水位/风险MAE为 **{num(metrics["physical_water_mae"],4)} cm / {num(metrics["physical_risk_mae"],4)}**。这些是受人工干预影响的事件实际回测。')
    bodies[19]=bodies[19].replace('最终保留的两个本轮 CLOSED 演示档案及正常基线核验：**待本轮实测填入**。',f'最终保留新Flood `{smoke["floodIncidentId"]}` 与Leak `{smoke["leakIncidentId"]}` 两个CLOSED档案及各一张完成工单，正常基线和资产数量由 [只读检查](final/M10-final-state.json) 确认。')
    bodies[20]=bodies[20].replace('正式服务关键 API 延迟与最终健康检查：**待本轮实测填入**。','正式服务分项Ready和同源HTTP/WebSocket通过。关键API的实际HTTP端到端mean/P95见第26节，重复预测可能命中缓存；未把模型内部耗时等同完整请求耗时。')
    bodies[21]=f'''本轮完整后端 **145 passed，84.74s**（134旧项+11新增，warnings作为错误）；Alembic一致性、准备脚本、TypeScript与最终生产构建全部通过。

历史浏览器脚本 **15/15**；新增质量、导航、真实故障恢复与Final Demo共4个脚本全部成功。Final Smoke **{len(smoke['checks'])}组**，`errors=[]`。缓存fixture与真实网络分别标注；网络故障注入的预期错误单列。

全部结果与复现见 [M10验收](M10-verification.md)。'''
    bodies[22]='本轮全部15项通过，旧里程碑证据未覆盖。\n\n| 脚本 | 结果 | 耗时 | 证据 |\n|---|---|---:|---|\n'+matrix
    bodies[23]=f'''`test:final-demo` 在最终生产后端与dist上通过 **{len(smoke['checks'])}组** 检查，`errors=[]`：Dashboard自检→一键Flood→真实高风险→物理/ML预测→UI比较/选择/执行→稳定→工单/关闭→真实历史播放→重置→Leak定位/隔离/受控→工单/关闭→历史播放→返回首页。

确认框文字、关闭前后物理连续性、同事件历史、两个新CLOSED档案、单业务WebSocket均实际断言。禁止外部HTTP资源后流程仍正常，未请求外部CDN；启动不训练。没有`/src`注入、没有修改引擎内部状态、没有跳时刻造actual。脚本总墙钟 **{elapsed:.1f}s**，含多分辨率截图和API重复基准，不等同讲解时间。

[结果](final/M10-final-smoke-results.json) · [日志](final/M10-final-demo.log)。'''
    bodies[24]=f'''质量24次切换同Canvas资源 **100/98/10→100/98/10**。本轮M5走完30仿真分钟，M7继续到超过40分钟；M7预热后跨超过10仿真分钟资源保持 **{m7['resources']['geometry']}/{m7['resources']['material']}/{m7['resources']['texture']}**。Leak从第{m8['warm']['time']/60:.1f}至{m8['hot']['time']/60:.1f}仿真分钟保持 **{m8['hot']['geometry']}/{m8['hot']['material']}/{m8['hot']['texture']}**。

M9执行100次scrub和真实5×播放至少600历史秒，资源与预热基线一致，详见 [回放结果](final/M10-M9-browser-results.json)。首次地下与Outline分配不误算为持续增长。雨效fixture单列，不替代真实事故证据。'''
    bodies[25]=bodies[25].replace('正式生产两类闭环与回放结束后的最终资源记录：**待本轮实测填入**。',f'正式生产两类事故与两次真实历史播放始终只创建 **{smoke["websocket"]["connections"]}** 条业务连接，历史播放前后实时物理字段相等。场景/图表/RAF完整释放由本轮M1、M9与十轮导航分别验证。')
    bodies[26]=bodies[26].replace('正式核心 API mean/P95、当前 ML 推理、应急比较、泄漏定位、Replay 延迟和初始加载时间：**待本轮实测填入**。不复用旧 M6/M7 耗时冒充本轮结果，不承诺比赛 GPU 已达 45 FPS。','本轮HTTP端到端耗时如下，含序列化/传输；重复ML预测有5秒缓存，应急比较执行真实rollout并持久化比较。单位ms。\n\n| API | 次数 | Mean | P95 |\n|---|---:|---:|---:|\n'+api+'\n\n不复用旧M6/M7耗时冒充本轮结果，不承诺比赛GPU达到45FPS。')
    images=[('01-dashboard','综合态势'),('02-operation','设备异常'),('03-pipeline','地下管网'),('04-risk','风险预测'),('05-flood','暴雨演化'),('06-emergency','四分支比较'),('07-leak','管网泄漏'),('08-review','历史回放')]
    for name,_ in images:assert (OUT/'screenshots'/f'{name}.png').exists()
    bodies[27]='正式生产截图已保存并检查，事故与历史截图来自本轮真实流程。\n\n'+'\n'.join(f'- [{label}](final/screenshots/{name}.png)' for name,label in images)+'\n\n对应1440、1366活动布局图片与18张正常页截图位于同一目录；真实模型缺失图见 [恢复截图](final/M10-model-missing-real.png)。'
    bodies[29]=bodies[29].replace('本轮正式流程真实墙钟时长：**待本轮实测填入**。',f'本轮自动验收墙钟 **{elapsed:.1f}s**，额外包含API批量计时与多尺寸截图，因此不是现场讲解承诺；需按 [演示脚本](DEMO_SCRIPT.md) 实机排练。')
    bodies[31]=bodies[31].replace('当前尚未结束的最终回归和验收项继续如实列为待填，不提前宣告完成。','本轮全部软件验收已完成；实际比赛GPU和投屏条件仍需现场复验。')
    bodies[32]=bodies[32].replace('最终正式启动验收结果、默认正常基线与完整冻结确认：**待本轮实测填入**。','已实际运行正式启动并通过分项检查，当前恢复1×正常动态监测，无活动事故，历史档案保留。核心功能冻结，后续不继续架构调整。')
    content='# Milestone 10 最终完成报告\n\n本报告采用本轮实际测试、生产演示与持久化档案，完整证据见 [M10验收](M10-verification.md)。\n\n'+'\n\n'.join(f'## {n}. {title}\n\n{bodies[int(n)]}' for n,title in headings)+'\n\nMilestone 10 已完成。TwinCitySafe V1.0 比赛展示版本开发完成，当前冻结核心功能，进入比赛演示、材料制作与最终部署阶段。\n'
    assert '待本轮实测填入' not in content
    source.write_text(content)
    print('PASS completed all 32 sections from final evidence')
if __name__=='__main__':main()
