"""Match forecasts to later real engine observations; never forecast the 'actual'."""
from collections import OrderedDict,deque
from datetime import datetime
from sqlalchemy import select,update
from sqlalchemy.exc import SQLAlchemyError
from app.models.risk_prediction import RiskPredictionRecord
from app.models.flood import FloodScenarioRecord

class PredictionEvaluationService:
    def __init__(self,factory):
        self.factory=factory;self.pending=OrderedDict();self.dirty={};self.previous=None
        self.recent=deque(maxlen=600);self.available=False;self.message="等待预测采样";self.last_persisted_time={}
    def restart(self):
        try:
            with self.factory() as db:
                db.execute(update(RiskPredictionRecord).where(RiskPredictionRecord.evaluation_status=="pending").values(evaluation_status="interrupted"));db.commit()
            self.available=True;self.message=""
        except SQLAlchemyError:self.message="预测存储未就绪，请执行 M6 migration"
    def register(self,prediction,session_id):
        id=prediction['scenarioId'];origin=prediction['simulationTime']
        if not id or self.last_persisted_time.get(id)==origin:return
        self.last_persisted_time={id:origin}
        ml={p['minute']:p for p in prediction['mlForecast']};gaps={p['minute']:p for p in prediction['comparison']}
        for p in prediction['physicalForecast']:
            h=p['minute'];m=ml.get(h,{})
            record=dict(id=prediction['id']+f'-{h}',scenario_id=id,session_id=session_id,
                generated_at=datetime.fromisoformat(prediction['generatedAt']),origin_time=origin,target_time=origin+h*60,horizon_minutes=h,
                model_version=prediction['modelStatus']['version'],predicted_water=m.get('waterLevel'),predicted_risk=m.get('riskScore'),
                physical_water=p['waterLevel'],physical_risk=p['riskScore'],agreement=gaps.get(h,{}).get('agreement'),evaluation_status='pending')
            self.pending[record['id']]=record;self.dirty[record['id']]=dict(record)
        while len(self.pending)>4000:
            key,record=self.pending.popitem(last=False);record['evaluation_status']='expired';self.dirty[key]=dict(record)
    def observe(self,state):
        f=state.flood
        current=(f.scenario_id,f.elapsed_simulation_seconds,f.water_level,f.risk_score)
        previous=self.previous;self.previous=current
        for key,record in list(self.pending.items()):
            if record['scenario_id']!=current[0]:
                record['evaluation_status']='interrupted'
            elif previous and previous[0]==current[0] and previous[1]<=record['target_time']<=current[1] and current[1]>previous[1]:
                span=current[1]-previous[1]
                if span>60:record['evaluation_status']='unmatched'
                else:
                    fraction=(record['target_time']-previous[1])/span
                    water=previous[2]+(current[2]-previous[2])*fraction;risk=previous[3]+(current[3]-previous[3])*fraction
                    record.update(evaluation_status='evaluated',actual_water=water,actual_risk=risk,sample_span_seconds=span,
                        water_error=water-record['predicted_water'] if record['predicted_water'] is not None else None,
                        risk_error=risk-record['predicted_risk'] if record['predicted_risk'] is not None else None,
                        physical_water_error=water-record['physical_water'],physical_risk_error=risk-record['physical_risk'])
                    self.recent.append(dict(record))
            elif record['target_time']<current[1]:record['evaluation_status']='unmatched'
            else:continue
            self.pending.pop(key,None);self.dirty[key]=dict(record)
    def persist(self,records):
        try:
            with self.factory() as db:
                for item in records:
                    if db.get(FloodScenarioRecord,item['scenario_id']) is None:continue
                    record=db.get(RiskPredictionRecord,item['id'])
                    if record is None:
                        existing=db.scalar(select(RiskPredictionRecord.id).where(RiskPredictionRecord.scenario_id==item['scenario_id'],RiskPredictionRecord.origin_time==item['origin_time'],RiskPredictionRecord.horizon_minutes==item['horizon_minutes']))
                        if existing:continue
                        db.add(RiskPredictionRecord(**item))
                    else:
                        for key,value in item.items():setattr(record,key,value)
                db.commit()
            self.available=True;self.message="";return True
        except SQLAlchemyError:
            self.available=False;self.message="预测采样暂不可用，稍后重试";return False
    def summary(self,scenario_id):
        values=[r for r in self.recent if r['scenario_id']==scenario_id and r['water_error'] is not None]
        return {'samples':len(values),'waterMae':sum(abs(r['water_error']) for r in values)/len(values) if values else None,
                'riskMae':sum(abs(r['risk_error']) for r in values)/len(values) if values else None,
                'physicalWaterMae':sum(abs(r['physical_water_error']) for r in values)/len(values) if values else None,
                'physicalRiskMae':sum(abs(r['physical_risk_error']) for r in values)/len(values) if values else None,
                'pending':sum(r['scenario_id']==scenario_id for r in self.pending.values()),
                'source':'real_engine_observations','message':'相邻真实观测线性插值到预测时刻；包含后续人工操作带来的差异。'}
