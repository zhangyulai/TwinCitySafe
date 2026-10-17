from collections import deque

def trace(graph, edge_id, direction):
    edge=graph.edges.get(edge_id)
    if edge:
        start=edge.start if direction=="upstream" else edge.end
        kind=edge.kind
    else:
        if edge_id not in graph.nodes: raise KeyError(edge_id)
        start=edge_id
        incident=next((e for e in graph.edges.values() if start in (e.start,e.end)),None)
        kind=incident.kind if incident else None
    nodes,edges=graph.walk([start],direction,kind=kind)
    nodes.add(start)
    if edge:
        nodes.update((edge.start,edge.end));edges.add(edge_id)
    return {"nodes":sorted(nodes),"edges":sorted(edges),"valves":[v.id for v in graph.valves.values() if v.node in nodes],
            "sources":[n for n in nodes if graph.nodes[n].kind=="source"],"buildings":graph.buildings(nodes)}

def nearby_valves(graph, edge_id, direction, layers=1):
    edge=graph.edges[edge_id];start=edge.start if direction=="upstream" else edge.end
    queue=deque([(start,0)]);seen=set();found=[];by_node={v.node:v for v in graph.valves.values()}
    while queue:
        node,depth=queue.popleft()
        if (node,depth) in seen:continue
        seen.add((node,depth))
        if node in by_node:
            found.append(by_node[node].id);depth+=1
            if depth>=layers:continue
        links=graph.reverse[node] if direction=="upstream" else graph.adjacency[node]
        for nxt,eid,_ in links:
            if eid!=edge_id and graph.edges[eid].kind==edge.kind:queue.append((nxt,depth))
    return sorted(set(found))

def affected(graph, edge_id):
    edge=graph.edges[edge_id]
    before,_=graph.connected(edge.kind)
    after,_=graph.connected(edge.kind,removed=[edge_id])
    return graph.buildings(before-after)
