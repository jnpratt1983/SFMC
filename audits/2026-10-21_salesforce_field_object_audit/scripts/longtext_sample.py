import json, glob
from sfh import *
SAMPLE=20000
res={}
for p in sorted(glob.glob('pop_*.json')):
    obj=p[4:-5]; d=json.load(open(p))
    lt=[k for k,v in d.items() if v.get('note')=='long text: not filterable']
    if not lt: continue
    for i in range(0,len(lt),8):
        chunk=lt[i:i+8]
        try:
            recs=q(f"SELECT CreatedDate, {', '.join(chunk)} FROM {obj} ORDER BY CreatedDate DESC LIMIT {SAMPLE}")
        except Exception as e:
            print(obj,'err',str(e)[:150]); continue
        for f in chunk:
            vals=[r for r in recs if r.get(f) not in (None,'')]
            res[f"{obj}.{f}"]={'sampled':len(recs),'populated_in_sample':len(vals),'last_new_value':vals[0]['CreatedDate'][:10] if vals else None,'oldest_in_sample':recs[-1]['CreatedDate'][:10] if recs else None}
    print(obj,len(lt),'long-text fields sampled',flush=True)
json.dump(res,open('longtext_sample.json','w'),indent=1)
for k,v in res.items(): print(k,v)
