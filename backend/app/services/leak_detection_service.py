"""Observation-only detection/localization. No access to injected target or severity."""
from math import isfinite
from simulator.leak_config import DETECTION_WEIGHTS

def unit(value):return max(0.,min(1.,value))
class LeakDetectionService:
    @staticmethod
    def score(observation,baseline,previous,dt):
        p=observation.pressure;q=observation.flow
        dp=(previous[0]-p)/dt*60 if previous and dt>0 else 0
        dq=(q-previous[1])/dt*60 if previous and dt>0 else 0
        factors={"pressure_deviation":unit((baseline[0]-p)/.20),"flow_deviation":unit(abs(q-baseline[1])/25),
                 "pressure_trend":unit(dp/.04),"flow_trend":unit(dq/10),
                 "imbalance":unit(max(0,observation.inlet_flow-observation.outlet_flow)/25)}
        return sum(factors[k]*w for k,w in DETECTION_WEIGHTS.items()),factors,dp,dq

class LeakLocalizationService:
    @staticmethod
    def rank(observations,baseline,graph,top_k=3):
        water=[p for p in observations if p.type=="water" and p.status not in ("isolated","offline") and p.id in baseline]
        residual={p.id:unit((baseline[p.id][0]-p.pressure)/.2) for p in water}
        ranking=[]
        for p in water:
            edge=graph.edges.get(p.id)
            if not edge:continue
            neighbors=[e.id for e in graph.edges.values() if e.kind=="water" and e.id!=p.id and (e.start==edge.end or e.end==edge.start)]
            consistency=sum(residual.get(id,0) for id in neighbors)/max(1,len(neighbors))
            downstream=[e.id for e in graph.edges.values() if e.kind=="water" and e.start==edge.end]
            pattern=sum(residual.get(id,0) for id in downstream)/max(1,len(downstream))
            balance=unit(max(0,p.inlet_flow-p.outlet_flow)/25)
            pressure_gradient=unit(max(0,p.inlet_pressure-p.outlet_pressure)/.15)
            flow_residual=unit(abs(p.flow-baseline[p.id][1])/25)
            score=.35*balance+.25*pressure_gradient+.20*residual[p.id]+.10*flow_residual+.05*consistency+.05*pattern
            ranking.append({"pipeline_id":p.id,"score":unit(score),"pressure_residual":residual[p.id],"flow_residual":flow_residual,"imbalance":balance,"topology_consistency":consistency})
        return sorted(ranking,key=lambda x:(-x["score"],x["pipeline_id"]))[:top_k]
