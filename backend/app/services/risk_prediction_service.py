import asyncio,time,logging
from copy import deepcopy
from collections import deque
from contextlib import suppress
from datetime import datetime,UTC
from uuid import uuid4
from starlette.concurrency import run_in_threadpool
from app.core.config import PROJECT_ROOT
import sys
if str(PROJECT_ROOT) not in sys.path:sys.path.insert(0,str(PROJECT_ROOT))
from algorithm.risk_prediction.inference import RiskModels,agreement
from algorithm.risk_prediction.features import build_features
from algorithm.risk_prediction.simulation import SimulationCopy
from app.services.flood_forecast_service import FloodForecastService
from app.services.prediction_evaluation_service import PredictionEvaluationService

class RiskPredictionService:
    def __init__(self,engine,factory,model_dir=None):
        self.engine=engine;self.models=RiskModels(model_dir) if model_dir is not None else RiskModels()
        self.evaluation=PredictionEvaluationService(factory)
        self.lock=asyncio.Lock();self.explanation_lock=asyncio.Lock();self.cached=None;self.frame=None
        self.signature=None;self.cached_at=-100.;self.explanations={};self.latencies=deque(maxlen=100)
        self.task=None;self.last_sample=-100.
    @staticmethod
    def feature_signature(frame):
        s=frame._state;f=s.flood
        return (s.session_id,f.scenario_id,f.entrance_closed,f.rainfall_recession,s.emergency.id if s.emergency else None,int(f.water_level),int(s.weather.rainfall/5),f.people_count,f.vehicle_count,
                tuple((d.id,frame.devices.commanded.get(d.id,d.status),d.fault,round(d.efficiency/5),round(d.startup_progress,1),frame.flood.rated_capacities[d.id]) for d in s.devices))
    def calculate(self,frame):
        s=frame._state;f=s.flood;row=build_features(frame);start=time.perf_counter()
        ml=[]
        if f.scenario_id:
            try:ml=self.models.predict(row)
            except Exception:
                self.models.models={};self.models.error='模型推理失败，已保留物理预测'
                logging.getLogger('uvicorn.error').warning('Risk inference unavailable; physical forecast retained')
        latency=(time.perf_counter()-start)*1000
        physical=FloodForecastService.forecast(frame,[10,20,30]).model_dump(mode='json',by_alias=True)['points'] if f.scenario_id else []
        comparison=[{'minute':m['minute'],'waterGap':abs(m['waterLevel']-p['waterLevel']),
                     'riskGap':abs(m['riskScore']-p['riskScore']),
                     'agreement':agreement(abs(m['waterLevel']-p['waterLevel']),abs(m['riskScore']-p['riskScore']))} for p,m in zip(physical,ml)]
        return {'id':str(uuid4()),'scenarioId':f.scenario_id,'sessionId':s.session_id,'basedOnRevision':s.revision,
                'simulationTime':f.elapsed_simulation_seconds,'generatedAt':datetime.now(UTC).isoformat(),
                'current':{'waterLevel':f.water_level,'riskScore':f.risk_score,'riskLevel':f.risk_level},
                'physicalForecast':physical,'mlForecast':ml,'comparison':comparison,'modelStatus':self.models.status(),
                'inferenceMs':latency,'cacheHit':False,
                'assumption':'物理预测延续降雨计划、泵启动与待执行动作；ML 只读当前特征，不编码封控/待执行动作，雨势回落为扩展工况。ML 非因果模型，一致度不是置信概率。'}
    async def prediction(self):
        async with self.lock:
            # All live objects are cloned on the event loop; worker threads never read the real engine.
            frame=SimulationCopy(self.engine);signature=self.feature_signature(frame);now=time.monotonic()
            if self.cached and now-self.cached_at<5 and signature==self.signature:
                value=deepcopy(self.cached);value['cacheHit']=True;return value
            value=await run_in_threadpool(self.calculate,frame)
            self.cached=value;self.frame=frame;self.signature=signature;self.cached_at=time.monotonic()
            if value['mlForecast']:self.latencies.append(value['inferenceMs'])
            return deepcopy(value)
    async def explanation(self,minutes=30):
        await self.prediction()
        async with self.explanation_lock:
            frame=SimulationCopy(self.frame);key=(minutes,self.feature_signature(frame));now=time.monotonic()
            previous=self.explanations.get(minutes)
            if previous and previous[0]==key and now-previous[1]<10:return deepcopy(previous[2])
            if not frame._state.flood.scenario_id:
                return {'available':False,'method':'unavailable','minutes':minutes,'topFeatures':[],'message':'暂无活动事故场景'}
            result=await run_in_threadpool(self.models.explain,build_features(frame),minutes)
            result.update(scenarioId=frame._state.flood.scenario_id,simulationTime=frame._state.flood.elapsed_simulation_seconds,
                          generatedAt=datetime.now(UTC).isoformat(),basedOnRevision=frame._state.revision)
            self.explanations[minutes]=(key,now,result)
            return deepcopy(result)
    def status(self):
        return {**self.models.status(),'averageInferenceMs':sum(self.latencies)/len(self.latencies) if self.latencies else None,
                'cacheSeconds':5,'explanationCacheSeconds':10,'storageAvailable':self.evaluation.available,'storageMessage':self.evaluation.message}
    async def flush(self):
        records=list(self.evaluation.dirty.values())
        if not records:return
        if await run_in_threadpool(self.evaluation.persist,records):
            for record in records:
                if self.evaluation.dirty.get(record['id']) is record:self.evaluation.dirty.pop(record['id'],None)
        # Bounded retry memory during prolonged storage outages.
        while len(self.evaluation.dirty)>5000:self.evaluation.dirty.pop(next(iter(self.evaluation.dirty)))
    async def sample(self):
        result=await self.prediction();now=time.monotonic()
        if now-self.last_sample>=10 and result['scenarioId']:
            self.evaluation.register(result,result['sessionId']);self.last_sample=now
        await self.flush()
    async def _run(self):
        while True:
            await asyncio.sleep(5)
            try:await self.sample()
            except Exception:
                logging.getLogger('uvicorn.error').exception('Risk prediction refresh failed; realtime simulation continues')
    async def start(self):
        await run_in_threadpool(self.evaluation.restart)
        self.task=asyncio.create_task(self._run(),name='risk-prediction-cache')
    async def shutdown(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):await self.task
        await self.flush()
