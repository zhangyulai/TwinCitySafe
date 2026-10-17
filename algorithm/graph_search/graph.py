from collections import defaultdict, deque
from .types import Node, Edge, Valve

class PipelineGraph:
    def __init__(self, nodes: list[Node], edges: list[Edge], valves: list[Valve]):
        self.nodes = {n.id:n for n in nodes}
        self.edges = {e.id:e for e in edges}
        self.valves = {v.id:v for v in valves}
        self.duplicates = sorted({x.id for xs in (nodes,edges,valves) for x in xs if sum(y.id==x.id for y in xs)>1})
        self.adjacency = defaultdict(list)
        self.reverse = defaultdict(list)
        for e in edges:
            if e.start in self.nodes and e.end in self.nodes:
                self.adjacency[e.start].append((e.end,e.id,e.weight))
                self.reverse[e.end].append((e.start,e.id,e.weight))

    def walk(self, starts, direction="downstream", closed=(), removed=(), kind=None, physical=False):
        blocked = {v.node for v in self.valves.values() if v.status == "closed" or v.id in closed}
        seen, found = set(), set()
        queue=deque(starts)
        while queue:
            node=queue.popleft()
            if node in seen or node in blocked or node not in self.nodes: continue
            seen.add(node)
            links = (self.reverse[node] if direction == "upstream" else self.adjacency[node])
            if direction == "undirected": links = self.adjacency[node]+self.reverse[node]
            for nxt,eid,_ in links:
                e=self.edges[eid]
                if eid in removed or e.status in ("offline","isolated") or kind and e.kind != kind: continue
                if nxt in blocked: continue
                found.add(eid)
                if nxt not in seen: queue.append(nxt)
        return seen,found

    def terminals(self, kind):
        # Drainage is operational when connected downstream to an outlet.
        desired="sink" if kind=="drainage" else "source"
        used={x for e in self.edges.values() if e.kind==kind for x in (e.start,e.end)}
        return [n.id for n in self.nodes.values() if n.kind==desired and n.id in used]

    def connected(self, kind, closed=(), removed=(), physical=False):
        direction="undirected" if physical else "upstream" if kind=="drainage" else "downstream"
        return self.walk(self.terminals(kind),direction,closed,removed,kind)

    def buildings(self, node_ids):
        return [{"buildingId":n.building_id,"buildingName":n.name,"connectionNode":n.id,"criticality":n.criticality}
                for n in self.nodes.values() if n.id in node_ids and n.building_id]

    def validate(self):
        used={x for e in self.edges.values() for x in (e.start,e.end)}
        return {"nodeCount":len(self.nodes),"edgeCount":len(self.edges),"isolatedNodes":sorted(set(self.nodes)-used),
                "invalidEdges":[e.id for e in self.edges.values() if e.start not in self.nodes or e.end not in self.nodes or e.start==e.end],
                "duplicateIds":self.duplicates,"sourceNodes":[n.id for n in self.nodes.values() if n.kind=="source"],
                "sinkNodes":[n.id for n in self.nodes.values() if n.kind=="sink"]}
