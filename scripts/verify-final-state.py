#!/usr/bin/env python3
"""Read-only final-state and archived-incident checks against the running demo."""
import json, os, sys, hashlib
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ.get('M10_API_URL','http://127.0.0.1:8000/api/v1')
OUTPUT=ROOT/'docs/final/M10-final-state.json'
def get(path):
    with urlopen(BASE+'/'+path,timeout=20) as response:return json.load(response)
def fingerprint(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def main():
    result={'readOnly':True}
    smoke=json.loads((ROOT/'docs/final/M10-final-smoke-results.json').read_text())
    assert smoke['success'], 'Final Smoke must pass first'
    readiness=get('system/readiness');assert readiness['ready'] and readiness['demo_enabled']
    state=get('realtime/state')
    assert state['running'] and state['speed']==1
    assert not state['flood']['scenarioId'] and not state['leak']['scenarioId'] and not state['emergency']
    assert state['weather']['condition']=='clear' and state['weather']['rainfall']==0
    assert not state['flood']['entranceClosed']
    assert len(state['devices'])==3
    assert {d['id']:d['status'] for d in state['devices']}=={'P01':'standby','P02':'standby','P03':'running'}
    assert all(d['fault']=='normal' for d in state['devices'])
    assert len(state['valves'])==10 and all(v['status']=='open' for v in state['valves'])
    assert len(state['pipelines'])==32 and all(p['status']=='normal' for p in state['pipelines'])
    records=[]
    for key in ['floodIncidentId','leakIncidentId']:
        identity=smoke[key];before=get('incidents/'+identity)
        assert before['status']=='CLOSED'
        assert len(before['work_orders'])==1 and before['work_orders'][0]['status']=='COMPLETED'
        timeline=get(f'incidents/{identity}/timeline');replay=get(f'incidents/{identity}/replay');report=get(f'incidents/{identity}/review')
        assert sum(item['event_type']=='INCIDENT_CLOSED' for item in timeline['items'])==1
        assert len(replay['snapshots'])>10 and report['report']
        after=get('incidents/'+identity);assert fingerprint(before)==fingerprint(after)
        records.append({'id':identity,'type':before['incident_type'],'status':before['status'],'snapshotCount':len(replay['snapshots']),'timelineCount':len(timeline['items']),'workOrder':before['work_orders'][0]['status'],'detailUnchangedByGet':True,'detailHash':fingerprint(after)})
    result.update(readiness=readiness,normalState=state,archives=records,success=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('PASS final normal monitoring, all demo valves open, two CLOSED archives and completed work orders retained')
if __name__=='__main__':main()
