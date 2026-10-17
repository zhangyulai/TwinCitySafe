import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from sqlalchemy import select
from app.models.pipeline import PipelineNode, PipelineEdge, Valve as ValveModel
from algorithm.graph_search.types import Node, Edge, Valve
from algorithm.graph_search.graph import PipelineGraph
from algorithm.graph_search.traversal import trace, nearby_valves, affected
from algorithm.graph_search.isolation import isolation_options

class PipelineGraphService:
    def __init__(self, session):
        self.nodes=list(session.scalars(select(PipelineNode).order_by(PipelineNode.id)))
        self.edges=list(session.scalars(select(PipelineEdge).order_by(PipelineEdge.id)))
        self.valves=list(session.scalars(select(ValveModel).order_by(ValveModel.id)))
        self.graph=self.build_graph()
    def build_graph(self):
        return PipelineGraph([Node(n.id,n.node_type,n.building_id,n.name,n.attributes.get("criticality","normal")) for n in self.nodes],
            [Edge(e.id,e.start_node_id,e.end_node_id,e.pipeline_type,e.length,e.status) for e in self.edges],
            [Valve(v.id,v.node_id,v.status) for v in self.valves])
    def get_upstream(self,id):return trace(self.graph,id,"upstream")
    def get_downstream(self,id):return trace(self.graph,id,"downstream")
    def get_connected_nodes(self,kind):return self.graph.connected(kind)[0]
    def get_connected_edges(self,kind):return self.graph.connected(kind)[1]
    def get_valves_for_edge(self,id):return {"upstream":nearby_valves(self.graph,id,"upstream"),"downstream":nearby_valves(self.graph,id,"downstream")}
    def get_affected_buildings(self,id):return affected(self.graph,id)
    def find_isolation_options(self,id):return isolation_options(self.graph,id)
    def serialize(self):
        return {"nodes":[{"id":n.id,"nodeCode":n.node_code,"nodeType":n.node_type,"name":n.name,"x":n.x,"y":n.y,"z":n.z,"buildingId":n.building_id,"areaId":n.area_id,"metadata":n.attributes} for n in self.nodes],
                "edges":[{"id":e.id,"pipelineCode":e.pipeline_code,"pipelineType":e.pipeline_type,"startNodeId":e.start_node_id,"endNodeId":e.end_node_id,
                "diameter":e.diameter,"length":e.length,"depth":e.depth,"material":e.material,"installDate":e.install_date,"designPressure":e.design_pressure,
                "healthScore":e.health_score,"status":e.status} for e in self.edges],
                "valves":[{"id":v.id,"valveCode":v.valve_code,"nodeId":v.node_id,"valveType":v.valve_type,"status":v.status,"openPercentage":v.open_percentage,"lastMaintenance":v.last_maintenance} for v in self.valves]}
