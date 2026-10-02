from __future__ import annotations
import math,random,statistics

def wilson_interval(successes,total,z=1.959963984540054):
    if total<=0: return (0.0,1.0)
    p=successes/float(total); denom=1.0+z*z/total
    center=(p+z*z/(2.0*total))/denom
    half=z*math.sqrt((p*(1.0-p)+z*z/(4.0*total))/total)/denom
    return (max(0.0,center-half),min(1.0,center+half))

def zero_event_upper_bound(total,alpha=0.05):
    if total<=0: return 1.0
    return 1.0-math.pow(alpha,1.0/total)

def mcnemar_exact_p(b,c):
    n=b+c
    if n==0: return 1.0
    k=min(b,c)
    tail=sum(math.comb(n,i) for i in range(0,k+1))/float(2**n)
    return min(1.0,2.0*tail)

def paired_binary(records,left_arm,right_arm,field):
    by={}
    for r in records:
        by.setdefault(r["pair_id"],{})[r["arm"]]=bool(r["outcome"].get(field,False))
    pairs=[v for v in by.values() if left_arm in v and right_arm in v]
    diffs=[int(p[right_arm])-int(p[left_arm]) for p in pairs]
    b=sum(1 for p in pairs if p[left_arm] and not p[right_arm])
    c=sum(1 for p in pairs if not p[left_arm] and p[right_arm])
    return {"n":len(pairs),"mean_delta":sum(diffs)/float(len(diffs)) if diffs else 0.0,"left_only_success":b,"right_only_success":c,"mcnemar_exact_p":mcnemar_exact_p(b,c),"deltas":diffs}

def bootstrap_paired_delta(values,seed=1729,reps=4000,alpha=0.05):
    if not values: return {"median_delta":0.0,"mean_delta":0.0,"ci":[0.0,0.0]}
    rng=random.Random(seed); n=len(values); means=[]
    for _ in range(reps):
        sample=[values[rng.randrange(n)] for __ in range(n)]; means.append(sum(sample)/float(n))
    means.sort(); lo=means[int((alpha/2.0)*reps)]; hi=means[min(reps-1,max(0,int((1.0-alpha/2.0)*reps)-1))]
    return {"median_delta":statistics.median(values),"mean_delta":sum(values)/float(n),"ci":[lo,hi]}

def paired_condition(records,left_condition,right_condition,field):
    by={}
    for r in records:
        condition=r.get("outcome",{}).get("handoff_condition") or r.get("environment",{}).get("handoff_condition")
        by.setdefault(r["pair_id"],{})[condition]=bool(r["outcome"].get(field,False))
    pairs=[v for v in by.values() if left_condition in v and right_condition in v]
    diffs=[int(p[right_condition])-int(p[left_condition]) for p in pairs]
    return {"n":len(pairs),"mean_delta":sum(diffs)/float(len(diffs)) if diffs else 0.0,"deltas":diffs}

def median_ratio(records,numerator_arm="A2",denominator_arm="A0",field="total_tokens"):
    by={}
    for r in records: by.setdefault(r["pair_id"],{})[r["arm"]]=r.get("usage",{}).get(field)
    ratios=[]
    for pair in by.values():
        a=pair.get(denominator_arm); b=pair.get(numerator_arm)
        if isinstance(a,(int,float)) and isinstance(b,(int,float)) and a>0: ratios.append(b/float(a))
    return statistics.median(ratios) if ratios else None
