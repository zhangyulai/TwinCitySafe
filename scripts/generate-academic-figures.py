#!/usr/bin/env python3
"""Generate editable 16:9 SVG figures for the TwinCitySafe presentation."""
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figures"
W, H = 1600, 900

# Restrained academic palette: navy, teal, blue-green, pale gray, amber, red.
NAVY = "#173A5E"
TEAL = "#187B8D"
MINT = "#4D9C93"
PALE = "#EEF3F6"
LINE = "#B8CAD5"
INK = "#1F2D3D"
MUTED = "#66798B"
AMBER = "#D98A3A"
RED = "#C95757"
WHITE = "#FFFFFF"
FONT = "Noto Sans CJK SC, Microsoft YaHei, Arial, sans-serif"


def svg_body(title: str, body: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">TwinCitySafe 学术风格可编辑示意图</desc>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9 z" fill="{TEAL}"/></marker>
    <marker id="arrowGray" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 0 1 L 9 5 L 0 9 z" fill="{MUTED}"/></marker>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="130%"><feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#173A5E" flood-opacity=".11"/></filter>
  </defs>
  <rect width="1600" height="900" fill="#FBFCFD"/>
  <rect x="0" y="0" width="1600" height="10" fill="{TEAL}"/>
  {body}
</svg>\n'''


def title_block(kicker: str, title: str, sub: str) -> str:
    return f'''<text x="74" y="66" font-family="{FONT}" font-size="14" font-weight="700" letter-spacing="2.2" fill="{TEAL}">{escape(kicker)}</text>
<text x="74" y="112" font-family="{FONT}" font-size="32" font-weight="700" fill="{INK}">{escape(title)}</text>
<text x="74" y="145" font-family="{FONT}" font-size="16" fill="{MUTED}">{escape(sub)}</text>
<line x1="74" y1="174" x2="1526" y2="174" stroke="{LINE}" stroke-width="1"/>'''


def footer(label: str) -> str:
    return f'''<line x1="74" y1="842" x2="1526" y2="842" stroke="{LINE}" stroke-width="1"/>
<text x="74" y="871" font-family="{FONT}" font-size="13" fill="{MUTED}">TwinCitySafe · 智慧园区运维安全协同平台</text>
<text x="1526" y="871" text-anchor="end" font-family="{FONT}" font-size="13" fill="{MUTED}">{escape(label)}</text>'''


def text(x, y, value, size=16, color=INK, weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(value)}</text>'


def card(x, y, w, h, heading, lines, color=TEAL, icon=None, heading_size=18):
    result = [f'<g filter="url(#shadow)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{WHITE}" stroke="{LINE}" stroke-width="1.2"/>',
              f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{color}"/>']
    if icon:
        result.append(f'<circle cx="{x+30}" cy="{y+30}" r="14" fill="{color}" opacity=".14"/>{text(x+30, y+36, icon, 16, color, 700, "middle")}')
        hx = x + 54
    else:
        hx = x + 22
    result.append(text(hx, y+33, heading, heading_size, INK, 700))
    for i, line in enumerate(lines): result.append(text(x+22, y+62+i*22, line, 13, MUTED))
    result.append('</g>')
    return ''.join(result)


def architecture() -> str:
    body = [title_block("FIG. 01 · SYSTEM ARCHITECTURE", "TwinCitySafe 智慧园区安全闭环总体架构", "以空间孪生为底座，贯通监测、研判、推演、处置与复盘")]
    # left vertical spatial foundation
    body += [f'<rect x="74" y="220" width="255" height="545" rx="14" fill="#E8F3F4" stroke="{TEAL}" stroke-width="1.3"/>',
             text(104, 260, "1", 42, TEAL, 700), text(158, 252, "园区数字孪生底座", 20, INK, 700),
             text(104, 290, "地上建筑 · 地下空间 · GIS", 13, MUTED),
             '<path d="M106 380 h175 M106 440 h175 M106 500 h175 M106 560 h175 M106 620 h175" stroke="#9FC5CD" stroke-width="1"/>',
             '<path d="M130 660 l35 -60 35 60 M187 660 l30 -100 30 100 M245 660 l24 -45 24 45" fill="none" stroke="#187B8D" stroke-width="2"/>',
             text(201, 710, "统一空间坐标与资产索引", 13, TEAL, 700, "middle")]
    # 5 modules
    modules = [(400,"园区总览","实时状态 · 告警汇总","01"),(580,"设备运维","健康诊断 · 维护建议","02"),(760,"风险预测","物理 / ML 预测对照","03"),(940,"应急推演","方案比较 · 人工执行","04"),(1120,"事件复盘","时间轴 · 工单 · 报告","05")]
    for x, name, sub, num in modules:
        body.append(f'<g filter="url(#shadow)"><rect x="{x}" y="225" width="150" height="124" rx="10" fill="{WHITE}" stroke="{LINE}"/><text x="{x+18}" y="255" font-family="{FONT}" font-size="12" font-weight="700" fill="{TEAL}">{num}</text><text x="{x+18}" y="289" font-family="{FONT}" font-size="18" font-weight="700" fill="{INK}">{name}</text><text x="{x+18}" y="316" font-family="{FONT}" font-size="12" fill="{MUTED}">{sub}</text></g>')
        body.append(f'<path d="M{x+75} 350 V365" stroke="{TEAL}" stroke-width="1.5" marker-end="url(#arrow)"/>')
    body.append(text(400, 204, "5 个业务应用模块", 15, TEAL, 700))
    body.append(f'<rect x="400" y="368" width="970" height="38" rx="8" fill="{NAVY}"/><text x="885" y="393" text-anchor="middle" font-family="{FONT}" font-size="16" font-weight="700" fill="{WHITE}">TwinCitySafe 智慧园区运维安全平台</text>')
    # engines
    body.append(text(400, 414, "4 个核心能力", 15, TEAL, 700))
    engines = [(400,"Web3D 时空建模","地上地下、资产与空间映射"),(650,"多源感知接入","设备、气象、管网与状态"),(900,"风险分析与智能预警","物理模型 · ML · 异常诊断"),(1150,"可视化交互与辅助决策","图表、拓扑、方案与回放")]
    for x, name, sub in engines:
        body.append(card(x, 432, 220, 103, name, [sub], NAVY, "◌", 15))
    # incident and archive
    body.append(text(400, 586, "2 个支撑引擎 + 1 个安全闭环", 15, TEAL, 700))
    body.append(card(400, 605, 305, 116, "风险预测引擎", ["融合实时输入、物理模型与机器学习", "形成分时风险预测与预警结果"], AMBER, "△"))
    body.append(card(735, 605, 305, 116, "仿真推演引擎", ["同基线比较处置方案与影响范围", "支持泵站、阀门与入口等操作推演"], RED, "!"))
    body.append('<path d="M705 663 H735" stroke="#66798B" stroke-width="1.5" marker-end="url(#arrowGray)"/>')
    body.append('<path d="M1040 663 H1130" stroke="#66798B" stroke-width="1.5" marker-end="url(#arrowGray)"/>')
    body.append(card(1130, 605, 340, 116, "监测 → 预测 → 推演 → 处置 → 复盘", ["异常触发、人工确认、工单协同与历史归档", "复盘结论反哺规则库、模型库与预案库"], MINT, "✓"))
    body.append('<path d="M1300 721 V757 H201 V728" fill="none" stroke="#187B8D" stroke-width="1.5" stroke-dasharray="6 5" marker-end="url(#arrow)"/>')
    body.append(text(748, 790, "历史档案反哺监测与风险研判", 14, TEAL, 700, "middle"))
    body.append(footer("系统总体架构图"))
    return svg_body("TwinCitySafe 系统总体架构图", ''.join(body))


def digital_twin() -> str:
    body=[title_block("FIG. 02 · DIGITAL TWIN", "园区地上—地下—风险一体化数字孪生界面", "统一三维场景承载建筑、道路、设备点位、地下管线与风险信息")]
    # main scene panel
    body += [f'<rect x="74" y="212" width="1010" height="572" rx="12" fill="#F3F7F9" stroke="{LINE}"/>',
             f'<rect x="74" y="212" width="1010" height="44" rx="12" fill="{NAVY}"/><rect x="74" y="244" width="1010" height="12" fill="{NAVY}"/>',
             text(100, 241, "数字孪生园区 · 空间与资产联动", 15, WHITE, 700),
             text(1055, 241, "地上 / 风险 / 管网 / 应急", 12, "#D7EDF1", 400, "end"),
             '<path d="M160 674 L516 470 L954 625 L594 755 Z" fill="#D9E8E8" stroke="#77A7AF" stroke-width="1.5"/>',
             '<path d="M208 650 L536 497 M280 690 L615 536 M363 729 L696 574 M440 764 L778 611" stroke="#B4CFD0" stroke-width="2"/>',
             '<path d="M250 610 L680 744 M340 554 L812 701 M445 494 L928 646" stroke="#B4CFD0" stroke-width="2"/>']
    # buildings isometric-ish
    buildings=[(370,467,74,128,"办公楼 A",NAVY),(565,470,80,109,"科研楼 B",TEAL),(765,525,86,76,"实验楼 C",NAVY),(603,610,112,54,"综合服务楼",MINT)]
    for x,y,w,h,name,c in buildings:
        body.append(f'<g><path d="M{x} {y} l{w} -34 l{w} 26 l-{w} 34 z" fill="#D8EEF0" stroke="{c}"/><path d="M{x} {y} v{h} l{w} 27 v-{h} z" fill="{c}"/><path d="M{x+w} {y-8} l{w} 26 v{h} l-{w} 27 z" fill="#245A77"/>')
        for row in range(max(2,h//23)):
            body.append(f'<path d="M{x+13} {y+19+row*19} h{w-25} M{x+w+14} {y+5+row*19} l{w-26} 8" stroke="#8FE0E2" stroke-width="3"/>')
        body.append(f'<rect x="{x+w//2-42}" y="{y-h//8-44}" width="84" height="25" rx="4" fill="#FFFFFF" stroke="{c}"/><text x="{x+w//2}" y="{y-h//8-27}" text-anchor="middle" font-family="{FONT}" font-size="12" fill="{INK}">{name}</text></g>')
    # risk, assets, pipes
    body += ['<circle cx="552" cy="625" r="56" fill="#D98A3A" opacity=".24"/><circle cx="552" cy="625" r="30" fill="#C95757" opacity=".34"/>',
             '<path d="M214 694 C360 628 465 738 610 690 S830 625 963 676" fill="none" stroke="#3186B8" stroke-width="7" stroke-linecap="round"/>',
             '<path d="M250 706 C390 647 488 753 642 706 S842 645 930 688" fill="none" stroke="#C95757" stroke-width="5" stroke-linecap="round"/>']
    for x,y,shape,c,label in [(306,610,'●',TEAL,'环境传感器'),(500,690,'✚',RED,'消防栓'),(858,622,'◉',NAVY,'摄像头')]:
        body.append(f'<circle cx="{x}" cy="{y}" r="14" fill="{WHITE}" stroke="{c}" stroke-width="2"/><text x="{x}" y="{y+5}" text-anchor="middle" font-family="{FONT}" font-size="15" fill="{c}">{shape}</text><text x="{x+20}" y="{y+5}" font-family="{FONT}" font-size="11" fill="{MUTED}">{label}</text>')
    # right interpretation panels
    body += [text(1135, 244, "空间图层", 16, INK, 700)]
    body.append(card(1120,276,405,104,"地上园区",["建筑群、道路、景观与设备点位","点击资产查看状态与基础信息"],NAVY,"①"))
    body.append(card(1120,402,405,104,"地下管网",["给水（蓝）· 消防（红）· 电力（黄）","透明地面减少遮挡，支持管段追踪"],TEAL,"②"))
    body.append(card(1120,528,405,104,"风险与应急",["热力层：低风险—高风险","事故建筑、救援路线与疏散提示"],AMBER,"③"))
    body.append('<g><rect x="1120" y="659" width="405" height="93" rx="10" fill="#E9F3F3" stroke="#A8CBC9"/><text x="1143" y="690" font-family="'+FONT+'" font-size="14" font-weight="700" fill="'+INK+'">图例与数据边界</text><circle cx="1150" cy="718" r="6" fill="'+TEAL+'"/><text x="1165" y="723" font-family="'+FONT+'" font-size="12" fill="'+MUTED+'">实时状态 / 软件仿真</text><circle cx="1337" cy="718" r="6" fill="'+RED+'"/><text x="1352" y="723" font-family="'+FONT+'" font-size="12" fill="'+MUTED+'">异常 / 风险强调</text></g>')
    body.append(footer("数字孪生界面图"))
    return svg_body("TwinCitySafe 数字孪生界面图", ''.join(body))


def flood_comparison() -> str:
    body=[title_block("FIG. 03 · FLOOD SCENARIO", "暴雨内涝推演与应急方案比较", "同一初始状态下，对比不同处置方案的水位、风险与资源消耗")]
    # left chart
    body += [f'<rect x="74" y="214" width="715" height="555" rx="12" fill="{WHITE}" stroke="{LINE}" filter="url(#shadow)"/>', text(106,253,"a  暴雨过程与风险演化",19,INK,700),text(106,282,"实时仿真与未来 30 分钟风险预测",13,MUTED),
             '<line x1="142" y1="674" x2="734" y2="674" stroke="#8BA2B0"/><line x1="142" y1="338" x2="142" y2="674" stroke="#8BA2B0"/>']
    for y,label in [(674,'0'),(590,'20'),(506,'40'),(422,'60'),(338,'80')]: body.append(f'<line x1="142" y1="{y}" x2="734" y2="{y}" stroke="#DFE8ED"/><text x="130" y="{y+4}" text-anchor="end" font-family="{FONT}" font-size="12" fill="{MUTED}">{label}</text>')
    for x,label in [(142,'0'),(290,'10'),(438,'20'),(586,'30'),(734,'40')]: body.append(f'<line x1="{x}" y1="674" x2="{x}" y2="681" stroke="#8BA2B0"/><text x="{x}" y="704" text-anchor="middle" font-family="{FONT}" font-size="12" fill="{MUTED}">{label}</text>')
    body += ['<path d="M142 654 C220 640 250 615 290 570 S375 465 438 420 S548 394 586 426 S671 480 734 515" fill="none" stroke="#187B8D" stroke-width="5"/>',
             '<path d="M142 666 C220 660 250 642 290 614 S375 526 438 474 S548 428 586 451 S671 510 734 555" fill="none" stroke="#D98A3A" stroke-width="5" stroke-dasharray="10 7"/>',
             '<path d="M142 650 C225 629 262 599 304 557 S381 468 438 442" fill="none" stroke="#4D9C93" stroke-width="5"/>',
             '<line x1="438" y1="324" x2="438" y2="681" stroke="#C95757" stroke-width="1.5" stroke-dasharray="5 5"/><rect x="385" y="306" width="106" height="26" rx="13" fill="#FBEAEA"/><text x="438" y="324" text-anchor="middle" font-family="'+FONT+'" font-size="12" font-weight="700" fill="'+RED+'">启动应急处置</text>',
             text(170,325,"风险指数 / 水位归一化",12,MUTED),text(734,735,"仿真时间（min）",12,MUTED,400,"end"),
             '<path d="M154 748 h25" stroke="#187B8D" stroke-width="4"/><text x="186" y="752" font-family="'+FONT+'" font-size="12" fill="'+MUTED+'">基线</text><path d="M255 748 h25" stroke="#D98A3A" stroke-width="4" stroke-dasharray="7 4"/><text x="287" y="752" font-family="'+FONT+'" font-size="12" fill="'+MUTED+'">方案 A</text><path d="M356 748 h25" stroke="#4D9C93" stroke-width="4"/><text x="388" y="752" font-family="'+FONT+'" font-size="12" fill="'+MUTED+'">方案 B</text>']
    # right cards
    body += [text(850,245,"b  同基线方案比较",19,INK,700),text(850,273,"操作人员比较后人工确认执行",13,MUTED)]
    plans=[("方案 A","启动 P01 排水能力","风险下降有限","#EEF3F6",NAVY),("方案 B","双泵协同 · 10 秒错峰","峰值水位更低","#EAF4F2",MINT),("方案 C","双泵 + 入口封控","人员暴露最小","#FDF3EA",AMBER)]
    for i,(name,action,effect,bg,c) in enumerate(plans):
        y=304+i*131; selected=i==1
        stroke=MINT if selected else LINE; width=2.5 if selected else 1
        body.append(f'<g filter="url(#shadow)"><rect x="850" y="{y}" width="675" height="108" rx="10" fill="{bg}" stroke="{stroke}" stroke-width="{width}"/>')
        if selected: body.append(f'<rect x="1363" y="{y+15}" width="136" height="25" rx="12" fill="{MINT}"/><text x="1431" y="{y+33}" text-anchor="middle" font-family="{FONT}" font-size="12" font-weight="700" fill="white">推荐执行</text>')
        body.append(f'<text x="876" y="{y+35}" font-family="{FONT}" font-size="18" font-weight="700" fill="{c}">{name}</text><text x="1004" y="{y+34}" font-family="{FONT}" font-size="15" fill="{INK}">{action}</text><text x="1004" y="{y+63}" font-family="{FONT}" font-size="13" fill="{MUTED}">{effect}</text><line x1="876" y1="{y+82}" x2="1494" y2="{y+82}" stroke="#D6E1E7"/><text x="876" y="{y+101}" font-family="{FONT}" font-size="12" fill="{MUTED}">比较指标：峰值水位 · 峰值风险 · 影响面积 · 人员暴露 · 资源消耗</text></g>')
    body += ['<path d="M1187 707 V752" stroke="#187B8D" stroke-width="2" marker-end="url(#arrow)"/>', '<rect x="946" y="758" width="478" height="44" rx="8" fill="#173A5E"/><text x="1185" y="786" text-anchor="middle" font-family="'+FONT+'" font-size="15" font-weight="700" fill="white">人工确认执行 → 实时状态、事件时间轴与工单同步更新</text>']
    body.append(footer("暴雨内涝推演与方案对比图"))
    return svg_body("TwinCitySafe 暴雨内涝推演与方案对比图", ''.join(body))


def lifecycle() -> str:
    body=[title_block("FIG. 04 · INCIDENT LIFECYCLE", "事件处置与复盘闭环流程", "从异常发现到人工关闭，所有关键状态、处置证据与复盘结果均可追溯")]
    body += ['<rect x="74" y="220" width="1452" height="472" rx="15" fill="#F6F9FA" stroke="#D5E1E7"/>']
    stages=[("01","发现异常","实时遥测 / 告警",NAVY),("02","研判定位","风险预测 / 拓扑追踪",TEAL),("03","方案推演","多方案比较",AMBER),("04","人工执行","泵站 / 阀门 / 封控",TEAL),("05","工单处置","接单 · 处理 · 完成",MINT),("06","确认关闭","稳定判定与人工确认",RED),("07","复盘归档","时间轴 · 指标 · 报告",NAVY)]
    startx=110; gap=198
    for i,(num,name,sub,c) in enumerate(stages):
        x=startx+i*gap
        body.append(f'<g filter="url(#shadow)"><circle cx="{x+64}" cy="354" r="58" fill="white" stroke="{c}" stroke-width="3"/><circle cx="{x+64}" cy="354" r="42" fill="{c}" opacity=".12"/><text x="{x+64}" y="347" text-anchor="middle" font-family="{FONT}" font-size="13" font-weight="700" fill="{c}">{num}</text><text x="{x+64}" y="371" text-anchor="middle" font-family="{FONT}" font-size="16" font-weight="700" fill="{INK}">{name}</text><text x="{x+64}" y="438" text-anchor="middle" font-family="{FONT}" font-size="12" fill="{MUTED}">{sub}</text></g>')
        if i<len(stages)-1: body.append(f'<path d="M{x+123} 354 H{x+gap-12}" stroke="#7C9AA8" stroke-width="2" marker-end="url(#arrowGray)"/>')
    # data evidence lane
    body.append(text(106,514,"事件证据持续写入",15,TEAL,700))
    chips=[("实时状态快照",NAVY),("告警与操作记录",TEAL),("应急执行步骤",AMBER),("工单状态变更",MINT),("关闭说明与报告",RED)]
    for i,(label,c) in enumerate(chips):
        x=108+i*276
        body.append(f'<rect x="{x}" y="538" width="238" height="44" rx="22" fill="white" stroke="{c}"/><circle cx="{x+23}" cy="560" r="7" fill="{c}"/><text x="{x+43}" y="565" font-family="{FONT}" font-size="14" fill="{INK}">{label}</text>')
    # closing loop
    body += ['<path d="M1410 646 C1410 736 180 736 180 646" fill="none" stroke="#187B8D" stroke-width="2" stroke-dasharray="7 6" marker-end="url(#arrow)"/>', text(795,734,"复盘结论反哺风险模型、应急预案与日常巡检",15,TEAL,700,"middle"),
             '<g><rect x="74" y="770" width="1452" height="45" rx="8" fill="#EAF2F4"/><text x="102" y="799" font-family="'+FONT+'" font-size="13" fill="'+INK+'">闭环边界：</text><text x="178" y="799" font-family="'+FONT+'" font-size="13" fill="'+MUTED+'">平台执行软件仿真与信息协同；真实设备控制、工程处置与安全决策须由具备资质的人员及系统完成。</text></g>']
    body.append(footer("事件处置与复盘流程图"))
    return svg_body("TwinCitySafe 事件处置与复盘流程图", ''.join(body))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "01-system-architecture.svg": architecture(),
        "02-digital-twin-interface.svg": digital_twin(),
        "03-flood-scenario-comparison.svg": flood_comparison(),
        "04-incident-lifecycle.svg": lifecycle(),
    }
    for name, content in files.items(): (OUT / name).write_text(content, encoding="utf-8")
    (OUT / "README.md").write_text("""# TwinCitySafe 学术风格示意图

本目录包含四张可编辑 SVG，均为 1600×900（16:9）横版构图，适合导入 PowerPoint、Figma、Illustrator 或 Inkscape 后继续调整文字、色彩与布局。

| 文件 | 建议放置位置 | 表达内容 |
|---|---|---|
| `01-system-architecture.svg` | 项目创新内容—总体思路 | 1+5+4+2+1 体系与模块关系 |
| `02-digital-twin-interface.svg` | 实施方案—时空建模 | 地上、地下、风险与应急空间图层 |
| `03-flood-scenario-comparison.svg` | 实施方案—应急推演 | 暴雨风险演化与三种处置方案比较 |
| `04-incident-lifecycle.svg` | 实施方案—闭环实现 | 异常发现到归档复盘的全流程 |

图中使用内置矢量形状、路径和文字，不依赖外部图片。字体为无衬线中文回退栈；在目标电脑安装「Noto Sans CJK SC」或「Microsoft YaHei」可获得一致字形。
""", encoding="utf-8")
    print("Generated", ", ".join(files))


if __name__ == "__main__": main()
