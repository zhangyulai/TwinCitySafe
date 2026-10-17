import sys,json,hashlib,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from sqlalchemy import select,func,text
from app.core.database import SessionLocal
from app.models.incident import Incident,IncidentSnapshot,IncidentTimelineEvent,WorkOrder,ReviewReport
from app.models import Device,PipelineEdge
from app.services.incident_service import IncidentService
from app.services.incident_replay_service import IncidentReplayService,row_dict
j=json.loads((root/'docs/M9-lifecycle-results.json').read_text());assert j['success']
def hashes(db):
 result={}
 for model in [Incident,IncidentTimelineEvent,IncidentSnapshot,WorkOrder,ReviewReport]:
  rows=[row_dict(r) for r in db.scalars(select(model).order_by(model.id))]
  result[model.__tablename__]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()}
 return result
with SessionLocal() as db:
 before=hashes(db);records=[]
 for key in ['floodIncidentId','leakIncidentId']:
  id=j[key];service=IncidentService(SessionLocal);record=service.detail(db,id);assert record['status']=='CLOSED'
  timeline=service.timeline(db,id)['items'];assert sum(e['event_type']=='INCIDENT_CLOSED' for e in timeline)==1
  assert len({(e['event_type'],e['source_id']) for e in timeline})==len(timeline)
  assert len(record['work_orders'])==1 and record['work_orders'][0]['status']=='COMPLETED'
  replay=IncidentReplayService().replay(db,id);assert replay['snapshots'] and not replay['metadata']['gaps']
  assert any(p['scene_state'].get('recordedAt') for p in replay['snapshots'])
  for suffix in ['', '/timeline','/replay','/metrics','/review']:
   with urllib.request.urlopen('http://127.0.0.1:8000/api/v1/incidents/'+id+suffix) as response:assert response.status==200
  report=db.scalar(select(ReviewReport).where(ReviewReport.incident_id==id));assert report
  records.append({'incident_id':id,'type':record['incident_type'],'status':record['status'],'closed_at':record['closed_at'],'snapshots':replay['metadata']['snapshot_count'],'source_snapshots':replay['metadata']['source_snapshot_count'],'full_m9_snapshots':db.scalar(select(func.count()).select_from(IncidentSnapshot).where(IncidentSnapshot.incident_id==id)),'timeline_events':len(timeline),'comparisons':len(record['comparisons']),'executions':len(record['executions']),'work_orders':len(record['work_orders']),'report_id':report.id,'replay_latency_ms':replay['metadata']['latency_ms']})
 after=hashes(db);assert after==before
 assets={'pipelines':db.scalar(select(func.count()).select_from(PipelineEdge)), 'pump_ratings':[{ 'id':d.id,'rated_capacity':d.rated_capacity} for d in db.scalars(select(Device).where(Device.device_type=='pump').order_by(Device.id))]}
 assert assets['pipelines']==32 and len(assets['pump_ratings'])==3
 version=db.execute(text('select version_num from alembic_version')).scalar()
result={'records':records,'read_apis_unchanged_database':before==after,'archive_hashes':after,'assets':assets,'alembic_head':version}
(root/'docs/M9-database-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({'records':records,'read_only':True,'head':version},ensure_ascii=False,default=str))
