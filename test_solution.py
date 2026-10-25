import itertools,json,subprocess,sys
import numpy as np
import pytest
from solution import evaluate,solve,trim

def toy():
 return dict(fixedPassCost=5,passCostPerTimeUnit=1,minVisiDuration=2,Accesses=[dict(start=1,end=4),dict(start=6,end=9)],Passes=[dict(start=0,end=10,accessIds=[0,1]),dict(start=1,end=4,accessIds=[0]),dict(start=6,end=9,accessIds=[1])],ObservationRequests=[dict(accessIds=[0],priority=1),dict(accessIds=[1],priority=2)])
def oracle(d,partial,budget):
 choices=[]
 for p,v in enumerate(d['Passes']):
  choices.append([None]+[dict(passId=p,bookingStart=s,bookingEnd=e) for s in range(v['start'],v['end']) for e in range(s+d['minVisiDuration'],v['end']+1) if partial or (s==v['start'] and e==v['end'])])
 keys=[]
 for combo in itertools.product(*choices):
  r=evaluate(d,{'Bookings':[b for b in combo if b]})
  if budget is None and r['satisfied']!=r['total']-len(r['unreachable_ids']):continue
  if budget is not None and r['cost']>budget:continue
  keys.append((r['satisfied'],-r['cost']))
 return max(keys)
@pytest.mark.parametrize('partial',[False,True])
@pytest.mark.parametrize('budget',[None,0,7,12,30])
def test_oracle(partial,budget):
 d=toy();r=solve(d,partial,budget,limit=3)['report'];assert (r['satisfied'],-round(r['cost'],6))==oracle(d,partial,budget);assert r['status']=='optimal'
@pytest.mark.parametrize('seed',range(8))
def test_random(seed):
 rng=np.random.default_rng(seed);d=toy();d['minVisiDuration']=1;d['Accesses']=[];d['Passes']=[]
 for p in range(2):
  ids=[]
  for j in range(2):
   s=int(rng.integers(0,4));e=int(rng.integers(s+1,6));ids.append(len(d['Accesses']));d['Accesses'].append(dict(start=s,end=e))
  d['Passes'].append(dict(start=0,end=5,accessIds=ids))
 d['ObservationRequests']=[dict(accessIds=[0,2],priority=1),dict(accessIds=[1,3],priority=2)]
 for budget in (None,6,12):
  r=solve(d,budget=budget,limit=3)['report'];assert (r['satisfied'],-round(r['cost'],6))==oracle(d,True,budget)
@pytest.mark.parametrize('p,s,e',[(0,3,1),(0,-1,5),(0,0,11),(-1,0,3),(True,0,3),(0,float('nan'),4),(0,0,1)])
def test_invalid(p,s,e):
 with pytest.raises(ValueError):evaluate(toy(),{'Bookings':[dict(passId=p,bookingStart=s,bookingEnd=e)]})
def test_geometry():
 d=toy();b=dict(passId=0,bookingStart=2,bookingEnd=4);assert evaluate(d,{'Bookings':[b]})['satisfied']==1
 with pytest.raises(ValueError):evaluate(d,{'Bookings':[b,b]})
 with pytest.raises(ValueError):evaluate(d,{'Bookings':[b]},budget=6)
 assert evaluate(d,{'Bookings':[dict(passId=0,bookingStart=3,bookingEnd=5)]})['satisfied']==0
 assert evaluate(d,trim(d,{'Bookings':[dict(passId=0,bookingStart=0,bookingEnd=10)]}))['cost']==11

def test_priority():
 d=toy();d['ObservationRequests']=[dict(accessIds=[0],priority=1),dict(accessIds=[0],priority=3)]+[dict(accessIds=[1],priority=2)]*3
 assert solve(d,budget=7,priorities=True,limit=3)['report']['by_priority']=={'1':1,'2':0,'3':1}
@pytest.mark.parametrize('key',['fixedPassCost','passCostPerTimeUnit'])
def test_cost(key):
 d=toy();d[key]=-1
 with pytest.raises(ValueError):solve(d,limit=3)
@pytest.mark.parametrize('key',['Passes','ObservationRequests'])
def test_empty(key):
 d=toy();d[key]=[];assert solve(d,limit=3)['solution']=={'Bookings':[]}
@pytest.mark.parametrize('shift',[0,1000000000])
def test_fraction(shift):
 d=toy();d['minVisiDuration']=.5;d['Accesses']=[dict(start=shift+.25,end=shift+1.25)];d['Passes']=[dict(start=shift,end=shift+2,accessIds=[0])];d['ObservationRequests']=[dict(accessIds=[0],priority=1)]
 assert solve(d,limit=3)['report']['cost']==pytest.approx(5.5)
@pytest.mark.parametrize('kwargs',[dict(budget=-1),dict(budget=float('nan')),dict(limit=0),dict(limit=121),dict(limit=float('nan')),dict(backend='bad')])
def test_options(kwargs):
 with pytest.raises(ValueError):solve(toy(),**kwargs)
def test_incumbent():
 with pytest.raises(ValueError):solve(toy(),partial=False,incumbent={'Bookings':[dict(passId=0,bookingStart=1,bookingEnd=3)]},limit=3)
def test_unreachable():
 d=toy();d['Accesses'][0]=dict(start=-20,end=1);d['Passes']=[dict(start=0,end=10,accessIds=[0])];assert solve(d,limit=3)['report']['unreachable_ids']==[0,1]
def test_timeout():
 d=toy();r=solve(d,limit=.00001,budget=12);evaluate(d,r['solution'],12);assert r['report']['status']!='optimal'
def test_cli(tmp_path):
 p=tmp_path/'input.json';p.write_text(json.dumps(toy()));out=tmp_path/'plan.json';r=subprocess.run([sys.executable,'solution.py',str(p),'--output',str(out),'--limit','3'],capture_output=True,text=True);assert r.returncode==0,r.stderr;assert json.loads(out.read_text())['Bookings']
@pytest.mark.parametrize('minimum',[0,float('inf')])
def test_minimum(minimum):
 d=toy();d['minVisiDuration']=minimum
 with pytest.raises(ValueError):solve(d,limit=3)
