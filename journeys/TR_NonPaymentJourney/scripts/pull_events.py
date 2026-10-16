# Read-only. Requires ~/.config/sfmc/env and c360-sfdx/scripts/lifecycle_watch.py (MC client). Run from this folder; outputs land in the working directory.
import json, sys, time, mc
m = mc.client()
tsds = json.load(open('tsds.json'))
ids = [t['ObjectID'] for t in tsds if t['Name'].startswith('TR_')]
print(len(ids), 'TR_ tsds', file=sys.stderr)
props = {"SentEvent":["SubscriberKey","EventDate","TriggeredSendDefinitionObjectID","SendID","BatchID"],
         "OpenEvent":["SubscriberKey","EventDate","TriggeredSendDefinitionObjectID","SendID","BatchID"],
         "ClickEvent":["SubscriberKey","EventDate","TriggeredSendDefinitionObjectID","SendID","URL"],
         "BounceEvent":["SubscriberKey","EventDate","TriggeredSendDefinitionObjectID","SendID","BounceCategory"]}
out = {}
for obj, pr in props.items():
    rows_all = []
    f = mc.complex_(mc.simple("TriggeredSendDefinitionObjectID","IN",ids), mc.simple("EventDate","greaterThan",["2026-01-31T00:00:00"]))
    st, rid, rows = m.retrieve(obj, pr, f)
    rows_all += rows
    while st == "MoreDataAvailable":
        st, rid, rows = m.retrieve(obj, pr, "", request_id=rid)
        rows_all += rows
    print(obj, len(rows_all), file=sys.stderr)
    out[obj] = rows_all
    json.dump(out, open('events.json','w'))
print('done', file=sys.stderr)
