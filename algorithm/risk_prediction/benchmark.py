"""Measure real loaded-model latency on an independent active M5 state."""
import sys,time,json,platform
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(PROJECT),str(PROJECT/'backend')]
import numpy as np
from simulator.engine import SimulationEngine
from app.services.flood_service import FloodService
from app.schemas.flood import FloodScenarioRequest
from algorithm.risk_prediction.inference import RiskModels
from algorithm.risk_prediction.features import build_features
from algorithm.risk_prediction.config import REPORT_DIR

def benchmark():
    engine=SimulationEngine();FloodService(engine).start(FloodScenarioRequest(),True);engine.set_speed(10)
    for _ in range(90):engine.tick()
    models=RiskModels();row=build_features(engine)
    models.predict(row);models.explain(row)
    results={}
    for name,call,count in [('six_model_prediction',lambda:models.predict(row),200),('risk_30m_native_treeshap',lambda:models.explain(row),100)]:
        times=[]
        for _ in range(count):
            start=time.perf_counter();call();times.append((time.perf_counter()-start)*1000)
        results[name]={'samples':count,'mean_ms':float(np.mean(times)),'p95_ms':float(np.quantile(times,.95)),'max_ms':float(max(times))}
    results['environment']={'python':platform.python_version(),'platform':platform.platform(),'xgboost':models.xgb.__version__,'inference_threads':1,'scope':'CPU loaded-model calls; excludes HTTP and M5 physical rollout'}
    (REPORT_DIR/'performance.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
if __name__=='__main__':benchmark()
