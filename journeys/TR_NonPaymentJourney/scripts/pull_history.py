# Read-only. Requires ~/.config/sfmc/env and c360-sfdx/scripts/lifecycle_watch.py (MC client). Run from this folder; outputs land in the working directory.
import json, mc, collections, datetime as dt, sys
m = mc.client()
end = dt.datetime.utcnow().replace(microsecond=0); start = end - dt.timedelta(days=29)
rows=[]; cur=start
while cur < end:
    nxt=min(cur+dt.timedelta(days=1), end)
    body={"definitionIds":["2bac7420-5e84-4e59-b657-cfb05359ca3b"],"start":cur.strftime("%Y-%m-%dT%H:%M:%SZ"),"end":nxt.strftime("%Y-%m-%dT%H:%M:%SZ")}
    page=1; n=0
    while True:
        r=m.search_history(body,page=page); items=r.get('items',[]); rows+=items; n+=len(items)
        if len(items)<5000: break
        page+=1
    print(cur.date(), n, 'count', r.get('count'), file=sys.stderr)
    cur=nxt
json.dump(rows, open('history29.json','w'))
print('total', len(rows))
c=collections.Counter((i.get('activityType'),i.get('activityName'),i.get('status')) for i in rows)
for k,v in sorted(c.items(), key=lambda x:-x[1])[:45]: print(v,k)
byday=collections.defaultdict(collections.Counter)
for i in rows:
    d=i['transactionTime'][:10]
    if i.get('status')=='ContactAttempted': byday[d]['attempted']+=1
    if i.get('activityType')=='Trigger' and i.get('status')=='MetCriteria': byday[d]['entered']+=1
    if i.get('activityType')=='Other' and i.get('status')=='Failed': byday[d]['failed']+=1
    if i.get('activityType')=='EMAILV2' and i.get('status')=='Complete': byday[d]['email']+=1
    if i.get('activityType')=='SMSSYNC' and i.get('status')=='Complete': byday[d]['sms']+=1
for d in sorted(byday): print(d, dict(byday[d]))
msgs=collections.Counter(i.get('message','')[:120] for i in rows if i.get('status') in ('Failed','ContactAttempted'))
print(msgs.most_common(10))
