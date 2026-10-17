"""Stable software demonstration assets. Not surveyed municipal infrastructure."""
from datetime import date
from math import dist
from app.models.pipeline import PipelineNode, PipelineEdge, Valve

BUILDINGS = [("A-OFFICE", "办公楼 A", -27, -22), ("B-RESEARCH", "科研楼 B", 25, -22),
             ("C-LAB", "实验楼 C", -29, 20), ("D-SERVICE", "综合服务楼", 29, 20),
             ("B2-PARKING", "B2 地下车库", 0, 23)]

def seed_pipelines(session):
    counts = {"nodes": 0, "edges": 0, "valves": 0}
    for prefix, kind, depth, pressure, flow, offset, valve_count in [
        ("WS", "water", 2.3, .42, 28, -7, 3),
        ("DS", "drainage", 4.1, .08, 20, 6, 3),
        ("FS", "fire", 3, .48, 2, 15, 4)]:
        # Water/drainage: 12 nodes each. Fire: 10 nodes with a parallel branch.
        nodes = []
        def node(code, typ, x, z, building=None, name=None):
            d = dict(id=code, node_code=code, node_type=typ, name=name or code, x=x, y=-depth,
                     z=z, building_id=building, area_id="PARK-UNDERGROUND", attributes={"pipelineType": kind, "criticality": "high" if building in ("C-LAB", "B2-PARKING") else "normal"})
            nodes.append(d);return code
        root = node(prefix+"-"+("OUTLET-01" if kind == "drainage" else "SOURCE-01"), "sink" if kind == "drainage" else "source", offset, -46)
        sequence = [root]
        valves = []
        for i in range(valve_count):
            vid = f"V-{prefix[0]}-{i+1:02}"
            sequence.append(node(vid, "valve", offset, -35+i*18))
            valves.append(vid)
            if kind != "fire": sequence.append(node(f"{prefix}-J-{i+1:02}", "junction", offset, -28+i*18))
        connections = [node(f"{prefix}-BC-{i+1:02}", "building_connection", x, z, bid, name) for i,(bid,name,x,z) in enumerate(BUILDINGS)]
        pairs = list(zip(sequence, sequence[1:]))
        pairs = pairs[:2] + pairs[-1:] + pairs[2:-1]
        for i, target in enumerate(connections):
            origin = sequence[2] if i == 0 else sequence[4] if kind != "fire" and i >= 3 else sequence[-1]
            pairs.append((origin, target))
        if kind == "fire": pairs.append((sequence[2], sequence[-1]))
        for d in nodes:
            existing = session.get(PipelineNode, d["id"])
            if existing is None:
                session.add(PipelineNode(**d)); counts["nodes"] += 1
            else:
                # Seed labels are stable backend fixture data. The frontend
                # applies the Caohejing presentation mapping by building ID.
                existing.name = d["name"]
        session.flush()
        by_id = {n["id"]: n for n in nodes}
        for i,(a,b) in enumerate(pairs):
            if kind == "drainage": a,b=b,a
            eid=f"{prefix}-{i+1:03}"
            if session.get(PipelineEdge, eid) is None:
                n,m=by_id[a],by_id[b]
                session.add(PipelineEdge(id=eid,pipeline_code=eid,pipeline_type=kind,start_node_id=a,end_node_id=b,
                    diameter=300 if kind == "drainage" else 200,length=round(dist((n['x'],n['y'],n['z']),(m['x'],m['y'],m['z'])),2),
                    depth=depth,material="球墨铸铁" if kind != "drainage" else "HDPE",install_date=date(2025,3,12),
                    design_pressure=pressure,current_pressure=pressure,current_flow=flow,health_score=96,status="normal")); counts["edges"]+=1
        for vid in valves:
            if session.get(Valve,vid) is None:
                session.add(Valve(id=vid,valve_code=vid,node_id=vid,valve_type="检修闸阀",status="open",open_percentage=100,last_maintenance=date(2026,9,18)));counts["valves"]+=1
    session.commit()
    return counts
