"""Reactive satellite booking: exact MILPs, validated incumbents and experiments."""
import argparse,csv,hashlib,json,math,platform,time
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import Bounds,LinearConstraint,milp
from scipy.sparse import coo_matrix

EPS=1e-6

def pairs(d):
    for p,v in enumerate(d['Passes']):
        for a in set(v['accessIds']):
            w=d['Accesses'][a];lo=max(v['start'],w['start']);hi=min(v['end'],w['end'])
            if hi-lo>=d['minVisiDuration']:yield p,a,lo,hi

def booking(d,p,s,e):
    v=d['Passes'][p]
    return dict(passId=int(p),passStart=v['start'],passEnd=v['end'],bookingStart=float(s),bookingEnd=float(e))

def evaluate(d,sol,budget=None):
    covered=set();seen=set();duration=0.;minimum=d['minVisiDuration']
    for b in sol['Bookings']:
        p=b['passId']
        if type(p) is not int or not 0<=p<len(d['Passes']) or p in seen:raise ValueError('Invalid/duplicate pass')
        seen.add(p);v=d['Passes'][p];s=b['bookingStart'];e=b['bookingEnd']
        if not all(math.isfinite(t) for t in (s,e)) or s<v['start']-EPS or e>v['end']+EPS or e-s<minimum-EPS:raise ValueError('Invalid interval')
        for k in ('passStart','passEnd'):
            if k in b and b[k]!=v['start' if k=='passStart' else 'end']:raise ValueError('Inconsistent pass bounds')
        duration+=e-s
        for a in v['accessIds']:
            w=d['Accesses'][a]
            if min(e,w['end'])-max(s,w['start'])>=minimum-EPS:covered.add(a)
    available={a for _,a,_,_ in pairs(d)};reqs=d['ObservationRequests']
    sat=[r for r,v in enumerate(reqs) if covered.intersection(v['accessIds'])]
    unreachable=[r for r,v in enumerate(reqs) if not available.intersection(v['accessIds'])]
    cost=d['fixedPassCost']*len(seen)+d['passCostPerTimeUnit']*duration
    if budget is not None and cost>budget+EPS*max(1,budget):raise ValueError('Budget exceeded')
    return dict(cost=cost,satisfied=len(sat),total=len(reqs),n_bookings=len(seen),seconds=duration,
        satisfied_ids=sat,unreachable_ids=unreachable,
        by_priority={str(p):sum(reqs[r].get('priority',1)==p for r in sat) for p in (1,2,3)})

def trim(d,sol):
    result=[];minimum=d['minVisiDuration']
    for b in sol['Bookings']:
        p=b['passId'];v=d['Passes'][p];spans=[]
        for a in v['accessIds']:
            w=d['Accesses'][a]
            if min(b['bookingEnd'],w['end'])-max(b['bookingStart'],w['start'])>=minimum-EPS:
                spans.append((max(v['start'],w['start']),min(v['end'],w['end'])))
        if spans:
            s=min(hi-minimum for lo,hi in spans);e=max(s+minimum,max(lo+minimum for lo,hi in spans))
            result.append(booking(d,p,s,e))
    return {'Bookings':result}

def greedy(d,partial=False,seed=None,deadline=float('inf'),budget=None):
    reverse=[0]*len(d['Accesses'])
    for r,v in enumerate(d['ObservationRequests']):
        for a in v['accessIds']:reverse[a]|=1<<r
    options=[];rng=np.random.default_rng(seed)
    for p,v in enumerate(d['Passes']):
        if time.monotonic()>deadline:break
        bits=0
        for a in v['accessIds']:
            w=d['Accesses'][a]
            if min(v['end'],w['end'])-max(v['start'],w['start'])>=d['minVisiDuration']:bits|=reverse[a]
        if bits:
            b=booking(d,p,v['start'],v['end'])
            if partial:b=trim(d,{'Bookings':[b]})['Bookings'][0]
            cost=d['fixedPassCost']+d['passCostPerTimeUnit']*(b['bookingEnd']-b['bookingStart'])
            options.append((b,bits,cost,rng.random()))
    selected=[];covered=0;spent=0.
    while options and time.monotonic()<deadline:
        candidates=[((noise if seed is not None else (bits&~covered).bit_count()/max(cost,1e-12)),-i,i)
            for i,(b,bits,cost,noise) in enumerate(options)
            if bits&~covered and (budget is None or spent+cost<=budget+EPS)]
        if not candidates:break
        b,bits,cost,_=options.pop(max(candidates)[-1]);selected.append(b);covered|=bits;spent+=cost
    sol={'Bookings':selected};target=set(evaluate(d,sol)['satisfied_ids'])
    for b in list(selected):
        if time.monotonic()>deadline:break
        candidate={'Bookings':[v for v in sol['Bookings'] if v is not b]}
        if target.issubset(evaluate(d,candidate)['satisfied_ids']):sol=candidate
    return sol

class Model:
    def __init__(self):self.ub=[];self.integer=[];self.rows=[];self.lo=[];self.hi=[]
    def var(self,upper=1,integer=True):
        i=len(self.ub);self.ub.append(upper);self.integer.append(int(integer));return i
    def row(self,c,lo=-np.inf,hi=np.inf):self.rows.append(c);self.lo.append(lo);self.hi.append(hi)
    def optimize(self,c,deadline,backend):
        if backend=='docplex':
            from docplex.mp.model import Model as CplexModel
            with CplexModel() as m:
                vs=[m.binary_var() if b else m.continuous_var(lb=0,ub=u) for b,u in zip(self.integer,self.ub)]
                for i,u in enumerate(self.ub):
                    if self.integer[i] and u==0:m.add_constraint(vs[i]==0)
                for row,lo,hi in zip(self.rows,self.lo,self.hi):
                    expr=m.sum(v*vs[i] for i,v in row.items())
                    if np.isfinite(lo):m.add_constraint(expr>=lo)
                    if np.isfinite(hi):m.add_constraint(expr<=hi)
                m.minimize(m.sum(v*vs[i] for i,v in c.items()));m.parameters.timelimit=max(.001,deadline-time.monotonic());m.parameters.mip.tolerances.mipgap=0
                sol=m.solve(log_output=False);info=m.solve_details
                return (np.array([sol.get_value(v) for v in vs]) if sol else None,dict(bound=float(info.best_bound) if sol else None,gap=float(info.mip_relative_gap) if sol else None,proven=bool(sol) and 'optimal' in info.status.lower() and info.mip_relative_gap<=1e-9,status=info.status))
        objective=np.zeros(len(self.ub))
        for i,v in c.items():objective[i]=v
        rr=[];cc=[];vv=[]
        for r,row in enumerate(self.rows):
            for i,v in row.items():rr.append(r);cc.append(i);vv.append(v)
        a=coo_matrix((vv,(rr,cc)),shape=(len(self.rows),len(self.ub))).tocsc()
        res=milp(objective,integrality=np.array(self.integer),bounds=Bounds(np.zeros(len(self.ub)),self.ub),constraints=LinearConstraint(a,self.lo,self.hi),options={'time_limit':max(.001,deadline-time.monotonic()),'mip_rel_gap':0})
        def number(k):
            v=getattr(res,k,None);return float(v) if v is not None and np.isfinite(v) else None
        gap=number('mip_gap')
        return res.x,dict(bound=number('mip_dual_bound'),gap=gap,proven=res.status==0 and (gap is None or gap<=1e-9),status=res.message)

def solve(d,partial=True,budget=None,priorities=False,limit=110,incumbent=None,backend='scipy'):
    if not math.isfinite(limit) or not 0<limit<=120:raise ValueError('Limit must be in (0,120]')
    if budget is not None and (not math.isfinite(budget) or budget<0):raise ValueError('Invalid budget')
    if backend not in ('scipy','docplex'):raise ValueError('Invalid backend')
    if not math.isfinite(d['minVisiDuration']) or d['minVisiDuration']<=0 or any(not math.isfinite(d[k]) or d[k]<0 for k in ('fixedPassCost','passCostPerTimeUnit')):raise ValueError('Invalid costs/duration')
    start=time.monotonic();deadline=start+limit;stages=[]
    best=greedy(d,partial,deadline=min(deadline,start+min(2,limit*.1)),budget=budget)
    def rank(sol):
        r=evaluate(d,sol,budget);counts=tuple(r['by_priority'][str(p)] for p in (1,2,3)) if priorities and budget is not None else (r['satisfied'],)
        return counts+(-r['cost'],)
    if incumbent is not None:
        evaluate(d,incumbent,budget)
        if not partial and any(b['bookingStart']!=d['Passes'][b['passId']]['start'] or b['bookingEnd']!=d['Passes'][b['passId']]['end'] for b in incumbent['Bookings']):raise ValueError('Partial incumbent in full model')
        if rank(incumbent)>rank(best):best=incumbent
    def finish(status):
        r=evaluate(d,best,budget);r.update(status=status,elapsed=time.monotonic()-start,partial=partial,budget=budget,priorities=priorities,stages=stages,incumbent_supplied=incumbent is not None)
        return {'solution':best,'report':r}
    if not d['Passes'] or not d['ObservationRequests']:best={'Bookings':[]};return finish('optimal')
    m=Model();x=[m.var() for p in d['Passes']];s={};e={};cost={};minimum=d['minVisiDuration'];rate=d['passCostPerTimeUnit']
    for p,v in enumerate(d['Passes']):
        length=v['end']-v['start'];cost[x[p]]=d['fixedPassCost']
        if partial:
            s[p]=m.var(length,False);e[p]=m.var(length,False)
            m.row({s[p]:1,x[p]:-length},hi=0);m.row({e[p]:1,x[p]:-length},hi=0);m.row({e[p]:1,s[p]:-1,x[p]:-minimum},lo=0)
            cost[s[p]]=-rate;cost[e[p]]=rate
        else:
            cost[x[p]]+=rate*length
            if length<minimum:m.ub[x[p]]=0
    links={}
    for p,a,lo,hi in pairs(d):
        if time.monotonic()>deadline:return finish('construction_timeout')
        if partial:
            z=m.var();v=d['Passes'][p];length=v['end']-v['start'];l=lo-v['start'];u=hi-v['start']
            m.row({z:1,x[p]:-1},hi=0);m.row({s[p]:1,z:length-u+minimum,x[p]:-length},hi=0);m.row({e[p]:1,z:-(l+minimum)},lo=0)
        else:z=x[p]
        links.setdefault(a,set()).add(z)
    groups={}
    for r in d['ObservationRequests']:
        support=frozenset(v for a in r['accessIds'] for v in links.get(a,()))
        if support:groups.setdefault(support,[0,0,0])[r.get('priority',1)-1]+=1
    if budget is None:
        minimal=[]
        for support in sorted(groups,key=lambda q:(len(q),tuple(sorted(q)))):
            if time.monotonic()>deadline:return finish('construction_timeout')
            if not any(v.issubset(support) for v in minimal):minimal.append(support);m.row({v:1 for v in support},lo=1)
        r=evaluate(d,best)
        if r['satisfied']==r['total']-len(r['unreachable_ids']):m.row(cost,hi=r['cost']+EPS)
        objectives=[('cost',cost)]
    else:
        m.row(cost,hi=budget);weights={}
        for support,w in groups.items():
            y=m.var(integer=False);weights[y]=w;m.row({y:1,**{v:-1 for v in support}},hi=0)
        objectives=([('P'+str(p+1),{y:-w[p] for y,w in weights.items() if w[p]}) for p in range(3)] if priorities else [('coverage',{y:-sum(w) for y,w in weights.items()})])
        objectives=[(k,v) for k,v in objectives if v]+[('cost',cost)]
    for label,c in objectives:
        if deadline-time.monotonic()<.01:return finish('feasible_not_proven')
        vector,info=m.optimize(c,deadline,backend);stages.append(dict(stage=label,**info))
        if vector is None:return finish('feasible_not_proven')
        sol={'Bookings':[booking(d,p,v['start']+vector[s[p]] if partial else v['start'],v['start']+vector[e[p]] if partial else v['end']) for p,v in enumerate(d['Passes']) if vector[x[p]]>.5]}
        try:evaluate(d,sol,budget)
        except ValueError:return finish('validation_fallback')
        if rank(sol)>rank(best):best=sol
        if not info['proven']:return finish('feasible_not_proven')
        if label!='cost':m.row({i:-v for i,v in c.items()},lo=int(round(-sum(v*vector[i] for i,v in c.items()))))
    return finish('optimal')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('--output',default='mySolution.json');p.add_argument('--full',action='store_true');p.add_argument('--budget',type=float);p.add_argument('--priorities',action='store_true');p.add_argument('--limit',type=float,default=110);p.add_argument('--backend',choices=['scipy','docplex'],default='scipy');a=p.parse_args()
    result=solve(json.loads(Path(a.input).read_text()),partial=not a.full,budget=a.budget,priorities=a.priorities,limit=a.limit,backend=a.backend)
    Path(a.output).write_text(json.dumps(result['solution'],indent=2)+'\n');Path(a.output+'.report.json').write_text(json.dumps(result['report'],indent=2)+'\n')
