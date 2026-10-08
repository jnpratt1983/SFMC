#!/usr/bin/env python3
"""Run bug checks over the audit JSON produced by sfmc_audit_collect.py and print findings (aggregates only)."""
import sys, json, re, collections, datetime as dt
A = sys.argv[1]
L = lambda n: json.load(open(f"{A}/{n}.json"))
jl = L("journeys_list"); J = L("journeys_published"); EV = L("eventdefs"); AU = L("automations"); Q = L("queries"); DE = L("data_extensions"); DI = L("de_referenced"); TS = L("tsds"); SUM = L("tsd_summary"); H = L("journey_history_24h")
by_name = {d['Name']: d for d in DE}; by_key = {d['CustomerKey']: d for d in DE}; by_oid = {d['ObjectID']: d for d in DE}
now = dt.datetime.utcnow() - dt.timedelta(hours=6)   # SFMC server time
F = collections.defaultdict(list)                   # severity -> findings
def add(sev, area, name, msg): F[sev].append((area, name, msg))
TEST = re.compile(r'^(test|uat|zz|z_|copy)|\(copy\)|\btest\b|\buat\b', re.I)
# ---------- journeys ----------
tsd_by_day = collections.defaultdict(list)
for t in TS: tsd_by_day[t['CreatedDate'][:10]].append(t)
summ = {s['CustomerKey']: s for s in SUM}
aut_journey_targets = collections.defaultdict(list)   # journey name -> automations injecting it
for a in AU.values():
    for s in a.get('steps', []):
        for act in s.get('activities', []):
            if act.get('objectTypeId') == 952: aut_journey_targets[act.get('name')].append(a['name'])
for jid, d in J.items():
    name = d.get('name', '?'); pub = str(d.get('lastPublishedDate') or '')[:10]; acts = d.get('activities', [])
    if TEST.search(name): add('high', 'journey', name, f"published test/copy journey (v{d.get('version')}, published {pub}); sends to real contacts if its entry source fills")
    # entry source
    trig = (d.get('triggers') or [{}])[0]; ttype = trig.get('type'); ek = (trig.get('metaData') or {}).get('eventDefinitionKey'); ev = EV.get(ek, {})
    dename = ev.get('dataExtensionName'); de = by_name.get(dename) if dename else None
    if ttype == 'AutomationAudience':
        feeders = aut_journey_targets.get(name) or [an for jn, lst in aut_journey_targets.items() for an in lst if jn and jn.split('_')[0:2] == name.split('_')[0:2]]
        if not feeders: add('high', 'journey', name, f"AutomationAudience entry but no automation has a journey-entry activity for it (entry DE {dename})")
        for an in feeders:
            a = [x for x in AU.values() if x['name'] == an][0]
            if a.get('status') in ('Error', 'BuildingError', 'Paused', 'PausedSchedule', 'Stopped', 'InactiveTrigger', 'Building'): add('high', 'journey', name, f"feeder automation {an} is {a.get('status')} (last run {str(a.get('lastRunTime'))[:16]})")
            lr = a.get('lastRunTime')
            if lr and (now - dt.datetime.fromisoformat(lr[:19])).days >= 2 and a.get('status') in ('Scheduled', 'Running'): add('medium', 'journey', name, f"feeder automation {an} last ran {lr[:10]} although {a.get('status')}")
    if dename and not de: add('high', 'journey', name, f"entry data extension '{dename}' not found")
    if dename and de:
        info = DI.get(dename, {}); rows = info.get('rows')
        if rows == 0: add('medium', 'journey', name, f"entry DE '{dename}' is empty right now")
        if de.get('DeleteAtEndOfRetentionPeriod') == 'true' and de.get('DataRetentionPeriodLength'): add('low', 'journey', name, f"entry DE '{dename}' deletes rows after {de.get('DataRetentionPeriodLength')} {de.get('DataRetentionPeriodUnitOfMeasure')}")
        if de.get('IsSendable') == 'false': add('medium', 'journey', name, f"entry DE '{dename}' is not sendable")
    # activities
    emails = [a for a in acts if a.get('type') == 'EMAILV2']; live = [t for t in tsd_by_day.get(pub, []) if any(t['Name'].startswith(a['name'][:29]) for a in emails if a.get('name'))]
    if emails and not live: add('high', 'journey', name, f"{len(emails)} email steps but no triggered-send definition created on publish date {pub}; emails may not be sending")
    inactive = [t['Name'][:40] for t in live if t.get('TriggeredSendStatus') != 'Active']
    if inactive: add('high', 'journey', name, f"live triggered sends not Active: {inactive[:3]}")
    errs = sum(int(float(summ.get(t['CustomerKey'], {}).get('NotSentDueToUndeliverable') or 0)) for t in live); sent = sum(int(float(summ.get(t['CustomerKey'], {}).get('Sent') or 0)) for t in live); queued = sum(int(float(summ.get(t['CustomerKey'], {}).get('Queued') or 0)) for t in live)
    if live and sent == 0 and (now - dt.datetime.fromisoformat(pub)).days > 14: add('medium', 'journey', name, f"published {pub}, live email definitions have 0 sends ever")
    if errs and sent and errs / max(sent, 1) > 0.05: add('medium', 'journey', name, f"triggered-send errors {errs} vs sent {sent} ({100*errs/sent:.0f}%)")
    if queued > 50: add('medium', 'journey', name, f"{queued} messages queued on live triggered sends")
    for a in acts:
        ca = a.get('configurationArguments') or {}
        if 'DECISION' in a.get('type', ''):
            outs = a.get('outcomes', []); non_rem = [o for o in outs if (o.get('metaData') or {}).get('label') and 'remainder' not in str((o.get('metaData') or {}).get('label')).lower() and not (o.get('metaData') or {}).get('isDefault')]
            empty = [str((o.get('metaData') or {}).get('label')) for o in non_rem if not ((o.get('arguments') or {}).get('criteria') or '').strip() and not (o.get('metaData') or {}).get('criteriaDescription')]
            if empty: add('high', 'journey', name, f"decision split '{a.get('name') or a.get('key')}' has outcomes with EMPTY criteria (catch-all): {empty}")
            # criteria referencing DE fields not present
            crit = ' '.join(((o.get('arguments') or {}).get('criteria') or '') for o in outs)
            for src, fld in set(re.findall(r'Key="(?:Event\.)?([^".]+)\.([^"]+)"', crit)):
                sde = None
                if src.startswith('DEAudience') or src == ek: sde = dename
                elif src in by_name: sde = src
                if sde and sde in DI and fld.lower() not in {f[0].lower() for f in DI[sde]['fields']} and not fld.startswith('poli'):
                    add('medium', 'journey', name, f"split '{a.get('name') or a.get('key')}' references field '{fld}' not in DE '{sde}'")
        if a.get('type') == 'RANDOMSPLIT': add('medium', 'journey', name, f"random split present: {[(str((o.get('metaData') or {}).get('label')), (o.get('arguments') or {}).get('percentage')) for o in a.get('outcomes', [])]}")
        if a.get('type', '').startswith('WAIT'):
            dur = ca.get('waitDuration'); unit = (ca.get('waitUnit') or '').lower()
            if dur is not None and ((unit.startswith('day') and dur > 120) or (unit.startswith('minute') and dur == 0)): add('low', 'journey', name, f"wait of {dur} {unit}")
        if a.get('type') == 'SMSSYNC' and not ca.get('assetId'): add('high', 'journey', name, f"SMS step '{a.get('name')}' has no message asset")
        if a.get('type') == 'EMAILV2' and not (ca.get('triggeredSend') or {}).get('emailId'): add('medium', 'journey', name, f"email step '{a.get('name')}' has no email asset id in config")
        # activities with no outgoing path that are not terminal types
        outs = a.get('outcomes') or []
        if a.get('type') in ('EMAILV2', 'SMSSYNC', 'PUSHNOTIFICATIONACTIVITY') and outs and not any(o.get('next') for o in outs): pass
    # re-entry mode vs feeder cadence
    mode = d.get('entryMode') or (d.get('defaults') or {}).get('entryMode') or '?'
    if mode == 'OnceAndDone' and ttype == 'AutomationAudience':
        rej = [h for h in H if h.get('definitionName') == name and h.get('status') == 'Rejected']
        if len(rej) >= 50: add('medium', 'journey', name, f"OnceAndDone with {len(rej)} rejections in the last 24h ({collections.Counter(h.get('result') for h in rej).most_common(2)})")
    fails = [h for h in H if h.get('definitionName') == name and h.get('status') in ('Failed', 'Error')]
    if fails: add('high', 'journey', name, f"{len(fails)} failed activity executions in the last 24h: {collections.Counter((h.get('activityType'), str(h.get('message') or h.get('result'))[:60]) for h in fails).most_common(3)}")
    # exits referencing DEs
    for e in d.get('exits', []):
        for src in set(re.findall(r'Key="([^".]+)\.', (e.get('configurationArguments') or {}).get('criteria', '') or '')):
            if src not in by_name and not src.startswith('Event.') and src != 'Event': add('medium', 'journey', name, f"exit criteria references '{src}' which is not a data extension")
            elif src in by_name and (DI.get(src, {}).get('rows') == 0): add('medium', 'journey', name, f"exit DE '{src}' is empty, exit never fires")
# ---------- automations ----------
pub_names = {d.get('name') for d in J.values()}
for a in AU.values():
    name = a['name']; st = a.get('status'); lr = a.get('lastRunTime'); sched = a.get('schedule') or {}
    jsteps = [act.get('name') for s in a.get('steps', []) for act in s.get('activities', []) if act.get('objectTypeId') == 952]
    if st in ('Error', 'BuildingError'): add('high', 'automation', name, f"status {st} (last run {str(lr)[:16]})")
    if st in ('Scheduled', 'Running') and sched.get('scheduleStatus') == 'active' and lr and (now - dt.datetime.fromisoformat(lr[:19])).days >= 3: add('high', 'automation', name, f"scheduled but last ran {lr[:10]}")
    for jn in jsteps:
        if jn and jn not in pub_names:
            near = [p for p in pub_names if p and p.split('_')[:2] == jn.split('_')[:2]]
            if not near: add('high', 'automation', name, f"injects into '{jn}' which is not a published journey")
            else: add('low', 'automation', name, f"journey-entry activity named '{jn}' while published version is '{near[0]}' (name drift, usually harmless)")
    if st in ('PausedSchedule', 'InactiveTrigger', 'Stopped') and jsteps and any(jn in pub_names for jn in jsteps): add('high', 'automation', name, f"{st} but feeds published journey(s) {jsteps}")
    for s in a.get('steps', []):
        for act in s.get('activities', []):
            if act.get('objectTypeId') == 300:
                q = Q.get(act.get('activityObjectId'), {}); txt = q.get('queryText') or ''; tgt = q.get('targetName') or (q.get('targetDataExtensions') or [{}])[0].get('name')
                if tgt and tgt not in by_name: add('high', 'automation', name, f"query '{act.get('name')}' targets missing DE '{tgt}'")
                for m in set(re.findall(r'(?:from|join)\s+(?:ent\.)?\[?([A-Za-z0-9_\-]+)\]?', txt, re.I)):
                    if m.lower().startswith(('_', 'ent')) or m.lower() in ('select',): continue
                    if m not in by_name and not m.lower().endswith('_salesforce') and not m.lower().startswith('lead_salesforce'): add('medium', 'automation', name, f"query '{act.get('name')}' reads '{m}' which is not a DE in this BU (shared/synced objects excepted)")
                if re.search(r'getdate\(\)\s*-\s*\d+', txt, re.I) and st in ('Scheduled', 'Running'): pass
# ---------- data extensions ----------
names = collections.Counter(d['Name'] for d in DE)
for n, c in names.items():
    if c > 1: add('low', 'data extension', n, f"{c} data extensions share this name")
for d in DE:
    if d.get('IsSendable') == 'true' and not d.get('SendableSubscriberField.Name'): add('medium', 'data extension', d['Name'], "sendable but no subscriber relationship field")
# ---------- journey list hygiene ----------
pub_test = [i['name'] for i in jl if i.get('status') == 'Published' and TEST.search(i.get('name', ''))]
print(json.dumps({sev: F[sev] for sev in ('high', 'medium', 'low')}, indent=1))
print("\nSUMMARY: published", len(J), "| high", len(F['high']), "| medium", len(F['medium']), "| low", len(F['low']), file=sys.stderr)
