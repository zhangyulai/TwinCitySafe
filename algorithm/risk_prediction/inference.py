"""Native JSON models, validated feature contract, optional native TreeSHAP."""
import json,hashlib,logging,time
import numpy as np
from .config import MODEL_DIR,FEATURE_VERSION,TARGETS,HORIZONS
from .features import FEATURE_NAMES,LABELS

class RiskModels:
    def __init__(self,directory=MODEL_DIR):
        self.models={};self.metadata={};self.error='';self.directory=directory
        try:
            import xgboost as xgb
            self.xgb=xgb
            meta=json.loads((directory/'metadata.json').read_text())
            if meta['feature_version']!=FEATURE_VERSION or meta['feature_names']!=list(FEATURE_NAMES):
                raise ValueError('feature version or names mismatch')
            for name in TARGETS:
                file=directory/(name+'.json')
                if hashlib.sha256(file.read_bytes()).hexdigest()!=meta['sha256'][name]:raise ValueError('model checksum mismatch')
                model=xgb.Booster(params={'nthread':1});model.load_model(file);model.set_param({'nthread':1})
                if model.num_features()!=len(FEATURE_NAMES) or model.feature_names!=list(FEATURE_NAMES):raise ValueError('model feature mismatch')
                self.models[name]=model
            self.metadata=meta
        except Exception as error:
            self.models={};self.error=str(error) if isinstance(error,ValueError) else '模型文件或 XGBoost 依赖不可用'
            logging.getLogger('uvicorn.error').warning('Risk models unavailable: %s; physical forecast remains available',self.error)
    @property
    def available(self):return len(self.models)==6
    def status(self):
        m=self.metadata
        return {'available':self.available,'model':'XGBoost','version':m.get('version'),'featureVersion':m.get('feature_version'),
                'trainedAt':m.get('trained_at'),'datasetSize':m.get('dataset_size',0),'scenarioCounts':m.get('scenario_counts',{}),
                'metrics':m.get('metrics',{}),'message':self.error or '使用软件仿真数据训练；仅用于比赛软件演示'}
    def predict(self,row):
        if not self.available:return []
        result=[]
        for h in HORIZONS:
            water=float(self.models[f'water_{h}m'].inplace_predict(row.reshape(1,-1))[0])
            risk=float(self.models[f'risk_{h}m'].inplace_predict(row.reshape(1,-1))[0])
            if not np.isfinite([water,risk]).all():raise ValueError('Non-finite prediction')
            water=max(0,water);risk=max(0,min(100,risk))
            result.append({'minute':h,'waterLevel':water,'riskScore':risk,'riskLevel':risk_level(risk)})
        return result
    def explain(self,row,minutes=30,force_fallback=False):
        if not self.available:return {'available':False,'method':'unavailable','minutes':minutes,'topFeatures':[],'message':'模型未加载'}
        start=time.perf_counter();name=f'risk_{minutes}m';model=self.models[name]
        try:
            if force_fallback:raise RuntimeError('Explicit fallback test')
            matrix=self.xgb.DMatrix(row.reshape(1,-1),feature_names=list(FEATURE_NAMES),nthread=1)
            contributions=model.predict(matrix,pred_contribs=True)[0]
            values=contributions[:-1].astype(float);base=float(contributions[-1]);method='native_tree_shap'
            message='原生 TreeSHAP 对当前风险预测的有符号贡献；不是因果关系，百分比为绝对贡献占比。'
        except Exception:
            gain={p['feature']:p['importance'] for p in self.metadata['global_importance'][name]}
            deviation=(row-np.asarray(self.metadata['feature_median']))/np.asarray(self.metadata['feature_std'])
            values=np.abs(deviation)*np.array([gain.get(key,0) for key in FEATURE_NAMES]);base=None;method='importance_deviation'
            message='全局增益×当前标准化偏离度的近似相关性排序；无方向、不可加和，不是SHAP或因果解释。'
        total=float(np.abs(values).sum()) or 1
        entries=[{'feature':key,'label':LABELS[key],'value':float(row[i]),'contribution':float(values[i]),
                  'share':float(abs(values[i])/total*100)} for i,key in enumerate(FEATURE_NAMES)]
        entries.sort(key=lambda p:-abs(p['contribution']))
        return {'available':True,'method':method,'minutes':minutes,'baseValue':base,
                'rawPrediction':float(model.inplace_predict(row.reshape(1,-1))[0]),'topFeatures':entries[:8],
                'otherContribution':float(sum(p['contribution'] for p in entries[8:])),
                'latencyMs':(time.perf_counter()-start)*1000,'message':message}

def risk_level(score):return ('low','general','elevated','high','extreme')[sum(score>=x for x in (20,40,60,80))]
def agreement(water_gap,risk_gap):
    a=0 if water_gap<2 else 1 if water_gap<=5 else 2
    b=0 if risk_gap<8 else 1 if risk_gap<=15 else 2
    return ('high','medium','low')[max(a,b)]
