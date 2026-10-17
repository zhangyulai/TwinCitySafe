import sys
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(PROJECT),str(PROJECT/"backend")]
import json,time
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error,root_mean_squared_error,r2_score
from algorithm.risk_prediction.config import DATA_DIR,MODEL_DIR,REPORT_DIR,TARGETS

def evaluate():
    data=np.load(DATA_DIR/'training.npz');dataset=json.loads((DATA_DIR/'metadata.json').read_text())
    metadata=json.loads((MODEL_DIR/'metadata.json').read_text());report={}
    for split in ('validation','test'):
        mask=np.isin(data['scenario_id'],dataset['groups'][split]);x,y=data['X'][mask],data['Y'][mask];metrics={}
        for i,name in enumerate(TARGETS):
            booster=xgb.Booster(params={'nthread':1});booster.load_model(MODEL_DIR/(name+'.json'))
            predicted=booster.inplace_predict(x);predicted=np.clip(predicted,0,100 if name.startswith('risk') else np.inf)
            metrics[name]={'mae':float(mean_absolute_error(y[:,i],predicted)),
                           'rmse':float(root_mean_squared_error(y[:,i],predicted)),'r2':float(r2_score(y[:,i],predicted))}
            if name.startswith('risk'):metrics[name]['risk_level_accuracy']=float(np.mean(np.digitize(y[:,i],[20,40,60,80])==np.digitize(predicted,[20,40,60,80])))
        report[split]=metrics
    report['scope']=metadata['scope'];report['dataset_size']=metadata['dataset_size'];report['scenario_counts']=metadata['scenario_counts']
    (REPORT_DIR/'metrics.json').write_text(json.dumps(report,indent=2)+'\n')
    metadata['metrics']=report['test'];(MODEL_DIR/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':evaluate()
