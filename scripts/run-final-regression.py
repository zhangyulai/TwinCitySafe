"""Sequential browser regressions: one shared engine, preserved historical outputs."""
import json, os, subprocess, time, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
output = root / 'docs/final'
output.mkdir(exist_ok=True)
env = os.environ.copy()
for n in range(1,10):
    path=Path(f'/tmp/m10-m{n}');path.mkdir(exist_ok=True)
    env[f'M{n}_OUTPUT_DIR']=str(path)
    env[f'M{n}_SCREENSHOT_DIR']=str(path)
for n in [3,5,8,9]:env[f'M{n}_STATE_OUTPUT']=str(output/f'M10-m{n}-state-results.json')
tasks=['web3d','realtime','operation','operation-state','pipeline','flood','flood-state','risk','emergency','leak','leak-state','review-state','incident-lifecycle','review','review-legacy']
if len(sys.argv)>1:tasks=sys.argv[1:]
record=output/'M10-regression-results.json'
result=json.loads(record.read_text()) if record.exists() else []
for task in tasks:
    started=time.monotonic()
    log=output/f'M10-{task}-regression.log'
    with log.open('w') as stream:
        proc=subprocess.run(['npm','--prefix','frontend','run',f'test:{task}'],cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT)
    row={'test':task,'exitCode':proc.returncode,'seconds':round(time.monotonic()-started,2),'log':log.name}
    result=[old for old in result if old['test']!=task]
    result.append(row)
    (output/'M10-regression-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(row,ensure_ascii=False),flush=True)
    if proc.returncode:raise SystemExit(proc.returncode)
