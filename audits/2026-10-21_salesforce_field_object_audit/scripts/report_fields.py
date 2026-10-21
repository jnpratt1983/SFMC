from sfh import *
import json, re
reps=json.load(open('reports.json'))
out={}
for i,r in enumerate(reps):
    try:
        d=get(f"/services/data/{V}/analytics/reports/{r['Id']}/describe")
        md=d['reportMetadata']
        cols=set(md.get('detailColumns',[]))
        for g in md.get('groupingsDown',[])+md.get('groupingsAcross',[]): cols.add(g.get('name'))
        for f in md.get('reportFilters',[]): cols.add(f.get('column'))
        for a in md.get('aggregates',[]): cols.add(a)
        if md.get('scope'): pass
        out[r['Id']]={'name':r['Name'],'folder':r['FolderName'],'lastRun':(r['LastRunDate'] or '')[:10],'type':md.get('reportType',{}).get('type'),'columns':sorted(c for c in cols if c)}
    except Exception as e:
        out[r['Id']]={'name':r['Name'],'folder':r['FolderName'],'lastRun':(r['LastRunDate'] or '')[:10],'err':str(e)[:150]}
    if i%50==0: print(i,flush=True)
json.dump(out,open('report_fields.json','w'),indent=1)
print('done',len(out),'errors',sum(1 for v in out.values() if 'err' in v))
