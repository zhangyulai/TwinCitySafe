"""Run with the project's backend virtualenv from any working directory."""
import sys
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(PROJECT),str(PROJECT/"backend")]
import argparse,json,csv
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from algorithm.risk_prediction.config import DATA_DIR,REPORT_DIR,SEED,FEATURE_VERSION,GENERATOR_VERSION,TARGETS
from algorithm.risk_prediction.features import FEATURE_NAMES
from algorithm.risk_prediction.dataset import scenario_rows,scenario_split,FAMILIES

def generate(scenarios=250,samples=240,workers=4,seed=SEED):
    DATA_DIR.mkdir(exist_ok=True);REPORT_DIR.mkdir(exist_ok=True)
    seeds=np.random.SeedSequence(seed).generate_state(scenarios).astype('uint32')
    tasks=[(i,int(seeds[i]),samples) for i in range(scenarios)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        parts=[]
        for i,part in enumerate(pool.map(scenario_rows,tasks,chunksize=2)):
            parts.append(part)
            if (i+1)%25==0:print(f"Generated {i+1}/{scenarios} independent scenarios",flush=True)
    x=np.concatenate([p[0] for p in parts]);y=np.concatenate([p[1] for p in parts]);ids=np.repeat(np.arange(scenarios),samples)
    groups=scenario_split(scenarios,seed)
    metadata=dict(seed=seed,feature_version=FEATURE_VERSION,generator_version=GENERATOR_VERSION,feature_names=FEATURE_NAMES,
                  targets=TARGETS,size=len(x),scenarios=scenarios,samples_per_scenario=samples,sample_step_seconds=10,
                  integration_step_seconds=5,scenario_seeds=seeds.tolist(),groups=groups,families=FAMILIES,
                  label_source="Exact future states of an independent copied M5 trajectory; overlapping rollout suffixes reused")
    np.savez_compressed(DATA_DIR/'training.npz',X=x,Y=y,scenario_id=ids)
    (DATA_DIR/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    with (DATA_DIR/'sample.csv').open('w') as file:
        writer=csv.writer(file);writer.writerow(['scenario_id',*FEATURE_NAMES,*TARGETS])
        for index in np.linspace(0,len(x)-1,200,dtype=int):writer.writerow([ids[index],*x[index],*y[index]])
    distributions={}
    for key in ('rainfall_current','water_level','p03_efficiency','current_risk_score'):
        values=x[:,FEATURE_NAMES.index(key)]
        hist,bins=np.histogram(values,bins=12)
        distributions[key]={'min':float(values.min()),'max':float(values.max()),'mean':float(values.mean()),
                            'quantiles':np.quantile(values,[.05,.25,.5,.75,.95]).tolist(),'histogram':hist.tolist(),'bins':bins.tolist()}
    (REPORT_DIR/'dataset_report.json').write_text(json.dumps({'metadata':metadata,'distributions':distributions},indent=2)+'\n')
    print(f"Saved {len(x)} rows, {len(FEATURE_NAMES)} features; groups: "+str({k:len(v) for k,v in groups.items()}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scenarios',type=int,default=250);p.add_argument('--samples',type=int,default=240);p.add_argument('--workers',type=int,default=4);p.add_argument('--seed',type=int,default=SEED)
    args=p.parse_args();generate(**vars(args))
