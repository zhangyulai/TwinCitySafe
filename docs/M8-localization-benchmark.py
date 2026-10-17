import sys,asyncio,json,time,platform,statistics
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'));sys.path.insert(0,str(root))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models import Base
from app.services.pipeline_seed import seed_pipelines
from app.services.pipeline_leak_service import PipelineLeakService
from app.services.leak_detection_service import LeakLocalizationService
from app.websocket.manager import ConnectionManager
from app.schemas.leak import LeakStart
from simulator.engine import SimulationEngine
async def main():
 db=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(db);factory=sessionmaker(bind=db,expire_on_commit=False)
 with factory() as session:seed_pipelines(session)
 e=SimulationEngine();s=PipelineLeakService(e,factory,ConnectionManager());await s.start_scenario(LeakStart());e.set_speed(10)
 for _ in range(60):e.tick(1)
 values=[]
 for _ in range(500):
  start=time.perf_counter();r=LeakLocalizationService.rank(e._state.pipelines,s.baseline,e.pipelines.graph);values.append((time.perf_counter()-start)*1000)
 results={'environment':platform.platform(),'python':platform.python_version(),'scope':'Observation-only Top 3 on seeded M4 graph, isolated SQLite setup. No HTTP/database time included. Real compare latency is in browser results.','count':len(values),'meanMs':statistics.mean(values),'p95Ms':sorted(values)[int(.95*len(values))-1],'ranking':r}
 (root/'docs/M8-localization-performance.json').write_text(json.dumps(results,indent=2));print(results)
 db.dispose()
asyncio.run(main())
