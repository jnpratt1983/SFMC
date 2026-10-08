#!/usr/bin/env python3
"""Read-only collector for an SFMC health audit: published journeys (+ event definitions), automations (+ SQL),
data extensions (+ row counts for referenced DEs), triggered-send definitions/summaries, journey history rejections.
Writes audit/*.json. Uses only GET and SOAP Retrieve (journeyhistory/search is a POST-bodied read)."""
import sys, json, re, time, collections, urllib.request, urllib.error, datetime as dt
sys.path.insert(0, '/Users/jennifer.pratt/Desktop/c360-sfdx/scripts'); import lifecycle_watch as lw
OUT = sys.argv[1]
mc = lw.MC(lw.load_env()); mc.auth()
def post_read(path, body):
    mc.auth(); req = urllib.request.Request(mc.rest + path, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {mc.token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r: return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return {"_error": e.code, "_body": e.read().decode()[:300]}
def save(name, obj): json.dump(obj, open(f"{OUT}/{name}.json", "w"), indent=0, default=str); print(f"saved {name}", file=sys.stderr)
t0 = time.time()
# 1. journeys
import os
if os.path.exists(f'{OUT}/journeys_published.json'):
    items = json.load(open(f'{OUT}/journeys_list.json')); details = json.load(open(f'{OUT}/journeys_published.json')); eventdefs = json.load(open(f'{OUT}/eventdefs.json')); pub = [i for i in items if i.get('status') == 'Published']
else:
  items, page = [], 1
  while True:
    j = mc.get(f"/interaction/v1/interactions?$page={page}&$pageSize=100"); items += j.get('items', [])
    if not j.get('items') or len(items) >= j.get('count', 0): break
    page += 1
  save("journeys_list", items)
  pub = [i for i in items if i.get('status') == 'Published']
  details = {}; eventdefs = {}
  for i in pub:
    d = mc.get(f"/interaction/v1/interactions/{i['id']}?extras=all"); details[i['id']] = d
    for t in d.get('triggers', []):
        k = (t.get('metaData') or {}).get('eventDefinitionKey')
        if k and k not in eventdefs: eventdefs[k] = mc.get(f"/interaction/v1/eventDefinitions/key:{k}")
  save("journeys_published", details); save("eventdefs", eventdefs)
print(f"journeys done {time.time()-t0:.0f}s", file=sys.stderr)
# 2. automations + queries
auts = mc.get("/automation/v1/automations?$page=1&$pageSize=500").get('items', [])
adet = {}; queries = {}
for a in auts:
    d = mc.get(f"/automation/v1/automations/{a['id']}"); adet[a['id']] = d
    for s in d.get('steps', []):
        for act in s.get('activities', []):
            qid = act.get('activityObjectId')
            if act.get('objectTypeId') == 300 and qid and qid not in queries:
                queries[qid] = mc.get(f"/automation/v1/queries/{qid}")
save("automations", adet); save("queries", queries)
print(f"automations done {time.time()-t0:.0f}s", file=sys.stderr)
# 3. data extensions (all)
props = ["Name", "CustomerKey", "ObjectID", "IsSendable", "SendableSubscriberField.Name", "SendableDataExtensionField.Name", "DataRetentionPeriodLength", "DataRetentionPeriodUnitOfMeasure", "RowBasedRetention", "ResetRetentionPeriodOnImport", "DeleteAtEndOfRetentionPeriod", "RetainUntil", "ModifiedDate", "CreatedDate", "CategoryID"]
st, rid, rows = mc.retrieve("DataExtension", props, lw.simple("Name", "like", ["%"])); des = list(rows)
while st == "MoreDataAvailable": st, rid, rows = mc.retrieve("DataExtension", [], "", request_id=rid); des += rows
save("data_extensions", des); print(f"DEs {len(des)} {time.time()-t0:.0f}s", file=sys.stderr)
# 4. referenced DEs: entry DEs + query targets + DEs named in SQL -> fields + row counts
by_name = {d['Name']: d for d in des}; by_key = {d['CustomerKey']: d for d in des}
ref = set()
for k, e in eventdefs.items():
    if e.get('dataExtensionName'): ref.add(e['dataExtensionName'])
for q in queries.values():
    tn = (q.get('targetName') or (q.get('targetDataExtensions') or [{}])[0].get('name'))
    if tn: ref.add(tn)
    for m in re.findall(r'(?:from|join|into)\s+(?:ent\.)?\[?([A-Za-z0-9_\-\. ]+?)\]?(?:\s|$|\))', (q.get('queryText') or ''), re.I): ref.add(m.strip())
for d in details.values():
    for a in d.get('activities', []):
        ca = a.get('configurationArguments') or {}
        for key in ('dataExtensionName', 'targetDataExtensionName'):
            if ca.get(key): ref.add(ca[key])
        for o in a.get('outcomes', []):
            for m in re.findall(r'Key="([^".]+)\.', (o.get('arguments') or {}).get('criteria', '') or ''): ref.add(m)
    for e in d.get('exits', []):
        for m in re.findall(r'Key="([^".]+)\.', (e.get('configurationArguments') or {}).get('criteria', '') or ''): ref.add(m)
ref = {r for r in ref if r in by_name}
de_info = {}
for n in sorted(ref):
    d = by_name[n]
    st, rid, f = mc.retrieve("DataExtensionField", ["Name", "FieldType", "IsPrimaryKey", "IsRequired"], lw.simple("DataExtension.CustomerKey", "equals", [d['CustomerKey']]))
    cnt = mc.get(f"/data/v1/customobjectdata/key/{urllib.request.quote(d['CustomerKey'])}/rowset?$page=1&$pageSize=1")
    de_info[n] = {"fields": [(x['Name'], x['FieldType'], x.get('IsPrimaryKey')) for x in f], "rows": cnt.get('count') if isinstance(cnt, dict) else None, "rows_error": cnt.get('_error') if isinstance(cnt, dict) else None}
save("de_referenced", de_info); print(f"referenced DEs {len(de_info)} {time.time()-t0:.0f}s", file=sys.stderr)
# 5. triggered sends: all since 2023 + summaries for Active ones
st, rid, rows = mc.retrieve("TriggeredSendDefinition", ["ObjectID", "Name", "CustomerKey", "CreatedDate", "ModifiedDate", "TriggeredSendStatus"], lw.simple("CreatedDate", "greaterThan", ["2024-01-01T00:00:00"])); tsds = list(rows)
while st == "MoreDataAvailable": st, rid, rows = mc.retrieve("TriggeredSendDefinition", [], "", request_id=rid); tsds += rows
save("tsds", tsds)
st, rid, rows = mc.retrieve("TriggeredSendSummary", ["CustomerKey", "Sent", "NotSent", "Queued", "Bounces", "Errors"], lw.simple("Sent", "greaterThan", ["-1"])); summ = list(rows)
while st == "MoreDataAvailable": st, rid, rows = mc.retrieve("TriggeredSendSummary", [], "", request_id=rid); summ += rows
save("tsd_summary", summ); print(f"TSDs {len(tsds)} summaries {len(summ)} {time.time()-t0:.0f}s", file=sys.stderr)
# 6. journey history: rejections and failures, last 24h server time (small windows, 10k cap)
now = dt.datetime.utcnow() - dt.timedelta(hours=6); hist = []
for h in range(0, 24, 4):
    a = (now - dt.timedelta(hours=h+4)).strftime('%Y-%m-%dT%H:%M:%S'); b = (now - dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M:%S')
    for statuses in (["Rejected"], ["Failed", "Error"]):
        j = post_read("/interaction/v1/interactions/journeyhistory/search?$page=1&$pageSize=5000", {"start": a, "end": b, "statuses": statuses})
        if isinstance(j, dict) and j.get('items'): hist += [{k: it.get(k) for k in ('definitionName', 'activityType', 'activityName', 'status', 'result', 'message', 'transactionTime', 'definitionId')} for it in j['items']]
save("journey_history_24h", hist); print(f"history rows {len(hist)} {time.time()-t0:.0f}s", file=sys.stderr)
# 7. mobile keywords / sms assets referenced
print("collect complete", file=sys.stderr)
