"""Editable scientific workflow figure; reflects current incident/work-order semantics."""
from pathlib import Path
from html import escape
ROOT=Path(__file__).resolve().parents[2]
N='#183B56';B='#347BA8';T='#358E8A';O='#D59450';R='#BC6460';G='#738592';L='#D5E0E8'
parts=[]
def text(x,y,v,size=16,c=N,w=400,anchor='start'):
 parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{c}" font-weight="{w}" text-anchor="{anchor}">{escape(str(v))}</text>')
def box(x,y,w,h,fill='white',stroke=L,rx=9):parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>')
def path(d,c=L,w=1,arrow=False,dash=''):
 parts.append(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}" stroke-dasharray="{dash}"'+(' marker-end="url(#arrow)"' if arrow else '')+'/>')
def icon(x,y,kind,c):
 common=f'fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
 shapes={
 'pulse':'<path d="M-13 0h6l4-9 5 18 4-9h7"/>',
 'bell':'<path d="M-10 5h20l-3-5v-5a7 7 0 0 0-14 0v5z M-3 9q3 5 6 0"/>',
 'pin':'<path d="M0 12s10-10 10-16a10 10 0 1 0-20 0c0 6 10 16 10 16z"/><circle cy="-4" r="3"/>',
 'doc':'<path d="M-9-12h12l6 6v18h-18z M3-12v6h6 M-5 0h10 M-5 5h8"/>',
 'fork':'<path d="M-12 0h10 M-2 0l8-8h7 M-2 0l8 8h7 M9-11l4 3-4 3 M9 5l4 3-4 3"/>',
 'check':'<circle r="12"/><path d="M-6 0l4 4 8-9"/>',
 'tool':'<path d="M-10 10l12-12 M2-2a7 7 0 0 0 9-9l-5 5-4-4 5-5a7 7 0 0 0-9 9l-12 12z"/>',
 'sync':'<path d="M-10-3a10 10 0 0 1 18-4 M8-12v5h-5 M10 3a10 10 0 0 1-18 4 M-8 12v-5h5"/>',
 'archive':'<path d="M-12-8h24v7h-24z M-9-1v13h18v-13 M-3 4h6"/>',
 'chart':'<path d="M-12-12v24h24 M-6 6v-5 M0 6v-10 M6 6v-17"/>',
 'book':'<path d="M0-8q-6-5-12-2v22q6-3 12 2 6-5 12-2v-22q-6-3-12 2v22"/>'}
 parts.append(f'<g transform="translate({x} {y})" {common}>{shapes[kind]}</g>')
box(0,0,1600,900,'#FAFCFE','none',0)
text(55,58,'孪城智安 TwinCitySafe',14,B,700)
text(55,105,'事件处置与复盘闭环流程',34,N,700)
text(55,137,'异常发现 → 分析决策 → 工单处置 → 事件关闭 → 证据复盘 → 人工优化回流',17,G)
text(1545,62,'INCIDENT LIFECYCLE / EVIDENCE & REVIEW',12,G,400,'end')
path('M55 160H1545')
phases=[('a','感知发现','监测与事件定位',B,'#EDF4FA',[
 ('异常发现','设备遥测 · 水位 / 压力 / 流量','pulse'),('实时告警','记录时间、来源与异常状态','bell'),('风险识别与定位','风险趋势 · 建筑 / 管段 / 区域','pin')]),
 ('b','分析决策','任务与方案协同',B,'#EDF4FA',[
 ('工单生成','关联事件 · 明确任务与负责班组','doc'),('处置方案推荐','同基线推演 · 效果与资源比较','fork'),('人工确认 / 调度','确认方案并记录操作人','check')]),
 ('c','执行处置','操作、回传与任务完成',T,'#EEF6F5',[
 ('现场处置记录 / 仿真执行','泵站启动 · 阀门隔离 · 入口封控','tool'),('状态回传与持续监测','跟踪风险、水位、供水与设备','sync'),('工单完成','填写处理结果 · 保留责任与时间','check')]),
 ('d','复盘优化','人工关闭与经验沉淀',T,'#EEF6F5',[
 ('事件关闭','稳定状态 + 关闭结果 + 人工确认','archive'),('复盘分析','时间轴回放 · 指标评估 · 报告','chart'),('经验沉淀 / 知识回流','记录改进建议 · 人工评估落实','book')])]
xs=[55,440,825,1210]
for i,(letter,title,sub,c,bg,nodes) in enumerate(phases):
 x=xs[i]
 box(x,185,335,431,bg,L,12)
 text(x+20,220,letter,24,c,700);text(x+55,220,title,22,N,700);text(x+55,249,sub,13,G)
 for j,(title,sub,k) in enumerate(nodes):
  y=279+j*104
  box(x+18,y,299,82,'white',('#E0B6AA' if i==0 and j==1 else L),7)
  icon(x+45,y+33,k,R if i==0 and j==1 else c)
  text(x+72,y+33,title,15,N,700)
  text(x+31,y+62,sub,12,G)
  if j<2:path(f'M{x+167} {y+82}v22',c,1.8,True)
 if i<3:
  # Follow each stage top-to-bottom, then connect through the inter-stage gutter.
  path(f'M{x+317} 528H{x+360}V320H{xs[i+1]+18}',B,1.6,True)
text(55,649,'贯穿全流程的证据链',18,N,700)
text(1545,648,'统一事件索引 · 时间戳 · 操作来源 · 状态变更',13,G,400,'end')
labels=[('告警与定位记录','何时发生 · 位于何处'),('三维状态快照','场景状态 · 实时采样'),('方案与执行日志','比较结果 · 操作步骤'),('工单与关闭记录','责任班组 · 结果说明'),('复盘指标与报告','响应时长 · 影响 · 预测误差')]
for i,(label,sub) in enumerate(labels):
 x=55+i*302
 box(x,665,282,66,'white',L,7)
 text(x+18,692,label,15,B,700);text(x+18,716,sub,12,G)
# Feedback supports human-led improvement; it does not imply automatic model retraining.
box(433,758,734,47,'#EDF5F4','#B6D4CE',7)
text(800,787,'人工评估与优化：监测规则 / 风险模型 / 应急预案 / 巡检流程',16,T,700,'middle')
path('M1377 616V629H1562V781H1172',T,1.8,True,'6 5')
path('M427 781H36V400H53',T,1.8,True,'6 5')
path('M55 825H1545')
text(55,850,'流程口径：工单完成与事件关闭分别记录；事件关闭条件为稳定状态、填写关闭结果并人工确认。工单可手动创建或在应急响应时自动关联。',12,G)
text(55,874,'实现边界：当前执行面向软件仿真；关闭事件不自动恢复积水、阀门或供水状态。复盘形成改进建议，规则、模型及预案的优化由人工落实。',12,G)
svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><title>TwinCitySafe事件处置与复盘闭环流程</title><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10" fill="#347BA8"/></marker></defs><g font-family="Noto Sans CJK SC,Microsoft YaHei,Arial,sans-serif">'+''.join(parts)+'</g></svg>'
name='TwinCitySafe-事件处置与复盘流程-科研风格'
(ROOT/(name+'.svg')).write_text(svg,encoding='utf-8')
(ROOT/(name+'.html')).write_text('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;width:1600px;height:900px;overflow:hidden}svg{display:block}</style></head><body>'+svg+'</body></html>',encoding='utf-8')
print(ROOT/(name+'.svg'))
