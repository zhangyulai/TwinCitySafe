from fastapi import HTTPException
from app.models.pipeline import Valve
from app.services.pipeline_graph_service import PipelineGraphService
class ValveService:
    @staticmethod
    def apply(session,changes):
        rows={id:session.get(Valve,id) for id in changes}
        for id,row in rows.items():
            if row is None:raise HTTPException(404,f"Valve {id} not found")
            if row.status=="fault":raise HTTPException(409,f"Valve {id} unavailable")
        for id,status in changes.items():
            if status not in ("open","closed"):raise HTTPException(422,"Invalid valve state")
            rows[id].status=status;rows[id].open_percentage=0 if status=="closed" else 100
        session.flush()
        return PipelineGraphService(session).graph
