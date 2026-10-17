import sys
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(PROJECT),str(PROJECT/"backend")]
import json,hashlib
from datetime import datetime,UTC
import numpy as np
import xgboost as xgb
from sklearn.metrics import root_mean_squared_error
from algorithm.risk_prediction.config import DATA_DIR,MODEL_DIR,REPORT_DIR,PARAMETERS,TARGETS,MODEL_VERSION,FEATURE_VERSION,GENERATOR_VERSION,SEED
from algorithm.risk_prediction.features import FEATURE_NAMES

def train():
    data=np.load(DATA_DIR/'training.npz');meta=json.loads((DATA_DIR/'metadata.json').read_text())
    if meta['feature_version']!=FEATURE_VERSION or meta['feature_names']!=list(FEATURE_NAMES):raise ValueError('Dataset feature contract mismatch')
    x,y,ids=data['X'],data['Y'],data['scenario_id']
    train=np.isin(ids,meta['groups']['train']);validation=np.isin(ids,meta['groups']['validation'])
    MODEL_DIR.mkdir(exist_ok=True);REPORT_DIR.mkdir(exist_ok=True)
    trials=[]
    for depth in (4,6,8):
        errors=[]
        for target in (2,5):
            reg=xgb.XGBRegressor(**{**PARAMETERS,'max_depth':depth},early_stopping_rounds=35)
            reg.fit(x[train],y[train,target],eval_set=[(x[validation],y[validation,target])],verbose=False)
            rmse=float(root_mean_squared_error(y[validation,target],reg.predict(x[validation])))
            errors.append(rmse)
        trial={'max_depth':depth,'water_30m_validation_rmse':errors[0],'risk_30m_validation_rmse':errors[1],
               'selection_score':sum(e/float(y[train,j].std()) for e,j in zip(errors,(2,5)))/2}
        trials.append(trial);print('Validation trial',trial,flush=True)
    depth=min(trials,key=lambda t:t['selection_score'])['max_depth'];parameters={**PARAMETERS,'max_depth':depth}
    importance={};hashes={};iterations={}
    for i,name in enumerate(TARGETS):
        reg=xgb.XGBRegressor(**parameters,early_stopping_rounds=35)
        reg.fit(x[train],y[train,i],eval_set=[(x[validation],y[validation,i])],verbose=False)
        booster=reg.get_booster()[:reg.best_iteration+1]
        booster.feature_names=list(FEATURE_NAMES)
        file=MODEL_DIR/(name+'.json');booster.save_model(file)
        hashes[name]=hashlib.sha256(file.read_bytes()).hexdigest();iterations[name]=reg.best_iteration+1
        gains=booster.get_score(importance_type='gain');total=sum(gains.values()) or 1
        importance[name]=sorted([{'feature':k,'gain':v,'importance':v/total} for k,v in gains.items()],key=lambda a:-a['importance'])
        print('Saved',name,'trees',reg.best_iteration+1,flush=True)
    metadata={'version':MODEL_VERSION,'feature_version':FEATURE_VERSION,'dataset_generator_version':GENERATOR_VERSION,
              'trained_at':datetime.now(UTC).isoformat(),'dataset_size':len(x),'training_seed':SEED,'feature_names':FEATURE_NAMES,
              'dataset_sha256':hashlib.sha256((DATA_DIR/'training.npz').read_bytes()).hexdigest(),
              'scenario_counts':{k:len(v) for k,v in meta['groups'].items()},'row_counts':{k:int(np.isin(ids,v).sum()) for k,v in meta['groups'].items()},
              'parameters':parameters,'trees':iterations,'sha256':hashes,'xgboost_version':xgb.__version__,
              'feature_median':np.median(x[train],axis=0).tolist(),'feature_std':x[train].std(axis=0).clip(.001).tolist(),
              'feature_min':x[train].min(axis=0).tolist(),'feature_max':x[train].max(axis=0).tolist(),
              'metrics':{},'scope':'Trained and tested on independent software simulation scenarios; no real-city generalization validation'}
    (REPORT_DIR/'training_trials.json').write_text(json.dumps(trials,indent=2)+'\n')
    (REPORT_DIR/'feature_importance.json').write_text(json.dumps(importance,indent=2)+'\n')
    metadata['global_importance']=importance
    (MODEL_DIR/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')

if __name__=='__main__':train()
