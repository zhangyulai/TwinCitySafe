"""Bounded valve-boundary enumeration; candidates, never automatic actuation."""
from itertools import combinations
from .traversal import nearby_valves

def isolation_options(graph, edge_id):
    edge=graph.edges[edge_id]
    candidates=sorted(set(nearby_valves(graph,edge_id,"upstream",3)+nearby_valves(graph,edge_id,"downstream",3)))
    candidates=[v for v in candidates if graph.valves[v].status=="open"][:10]
    base_nodes,base_edges=graph.connected(edge.kind)
    options=[];seen=set()
    for size in range(1,min(3,len(candidates))+1):
        for valves in combinations(candidates,size):
            # A supply path in either direction can still pressurize the target.
            physical,_=graph.connected(edge.kind,closed=valves,physical=True)
            if edge.start in physical or edge.end in physical:continue
            nodes,edges=graph.connected(edge.kind,closed=valves)
            isolated=sorted(base_edges-edges)
            if edge_id not in isolated:continue
            key=(tuple(isolated),tuple(sorted(base_nodes-nodes)))
            if key in seen:continue
            seen.add(key)
            buildings=graph.buildings(base_nodes-nodes)
            options.append({"valves":list(valves),"isolatedEdges":isolated,"affectedBuildings":buildings,
                "affectedNodes":sorted(base_nodes-nodes),"estimatedScope":{"buildingCount":len(buildings),"edgeCount":len(isolated),
                "length":round(sum(graph.edges[e].weight for e in isolated),2)}})
    options.sort(key=lambda o:(len(o["affectedBuildings"]),o["estimatedScope"]["length"],len(o["valves"])))
    return [{"id":f"option-{i+1}",**o} for i,o in enumerate(options[:5])]
