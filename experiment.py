"""Reproduce comparisons. A supplied seed is explicitly audited and labeled."""
import csv,json,hashlib,platform,time
from pathlib import Path
import scipy
from solution import booking,evaluate,greedy,solve,trim
out=Path('results');out.mkdir(exist_ok=True);rows=[];plans={}
seeds=json.loads((out/'seeds.json').read_text()) if (out/'seeds.json').exists() else {}
for k in (12,4,2):
 d=json.loads(Path(f'data/data{k}.json').read_text());name=f'data{k}'
 def record(method,partial,sol,report,seed=None):
  evaluate(d,sol,report.get('budget'));row={key:report.get(key) for key in ('cost','satisfied','total','n_bookings','elapsed','status','budget','priorities')}
  row.update(dataset=name,method=method,partial=partial,seed=seed)
  stages=report.get('stages',[]);row.update(bound=stages[-1]['bound'] if stages else None,gap=stages[-1]['gap'] if stages else None,bound_stage=stages[-1]['stage'] if stages else None)
  rows.append(row)
  with (out/'summary.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(row));w.writeheader();w.writerows(rows)
  print(name,method,partial,row['cost'],row['satisfied'],row['status'],flush=True)
 for partial in (False,True):
  for seed in (None,0,1,2):
   t=time.monotonic();sol=greedy(d,partial,seed);report=evaluate(d,sol);report.update(elapsed=time.monotonic()-t,status='heuristic')
   record('greedy' if seed is None else 'random',partial,sol,report,seed)
  initial=seeds.get(name)
  if initial is None and partial:initial=trim(d,full['solution'])
  result=solve(d,partial=partial,limit=12,incumbent=initial if partial else None)
  record('milp_seeded' if partial and initial is not None else 'milp',partial,result['solution'],result['report'])
  if not partial:full=result
  else:
   report=result['report'];plans[name]=dict(solution=result['solution'],cost=report['cost'],satisfied=report['satisfied'],status=report['status'],stages=report['stages'],sha256=hashlib.sha256(Path(f'data/data{k}.json').read_bytes()).hexdigest())
   (out/'plans.json').write_text(json.dumps(plans,separators=(',',':'))+'\n')
 for fraction in (.5,.75):
  result=solve(d,partial=False,budget=full['report']['cost']*fraction,priorities=True,limit=3)
  record('budget_milp',False,result['solution'],result['report'])
(out/'environment.json').write_text(json.dumps(dict(python=platform.python_version(),scipy=scipy.__version__,platform=platform.platform()),indent=2)+'\n')
