# Read-only. Requires ~/.config/sfmc/env and c360-sfdx/scripts/lifecycle_watch.py (MC client). Run from this folder; outputs land in the working directory.
import csv, json, collections, datetime as dt, statistics, math
rows = list(csv.DictReader(open('bills_raw.csv')))
ev = json.load(open('events.json')); tsds = {t['ObjectID']: t for t in json.load(open('tsds.json'))}
STEP = lambda oid: 'T-5' if 'T-5' in tsds[oid]['Name'] else 'T+3' if 'T+3' in tsds[oid]['Name'] else 'T+7'
VARIANT = {'111622':'E','111625':'E','111697':'E','113707':'ES','113705':'ES','113706':'ES'}
P = lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=None) if s else None
# SOAP EventDate is server time (CST, UTC-6); convert to UTC
SRV = lambda s: dt.datetime.fromisoformat(s[:19]) + dt.timedelta(hours=6)
# ---- episodes: one per contact x notice date
ep = {}
for r in rows:
    pol = r['Policy_Number__c']
    if pol.endswith('R'): continue             # journey excludes renters
    n = P(r['Nonpay_Cancel_Notice_Created_At__c']); k = (r['Contact__c'], n.date())
    e = ep.setdefault(k, {'contact': r['Contact__c'], 'notice': n, 'due': dt.date.fromisoformat(r['Invoice_Due_Date__c']), 'cancel_date': r['Non_Pay_Cancel_Date__c'],
                          'cleared': None, 'cancelled': None, 'state': pol[:2], 'bills': 0})
    e['bills'] += 1
    c = P(r['Nonpay_Cleared_At__c']); x = P(r['Nonpay_Cancelled_At__c'])
    if c and (e['cleared'] is None or c < e['cleared']): e['cleared'] = c
    if x and (e['cancelled'] is None or x < e['cancelled']): e['cancelled'] = x
eps = sorted(ep.values(), key=lambda e: (e['contact'], e['notice']))
# first-time vs repeat (no notice in prior 120 days)
last = {}
for e in eps:
    p = last.get(e['contact']); e['first_time'] = (p is None) or (e['notice'] - p).days > 120; last[e['contact']] = e['notice']
for e in eps:
    e['outcome'] = 'cleared' if e['cleared'] and not e['cancelled'] else 'cancelled' if e['cancelled'] and not e['cleared'] else 'cleared' if (e['cleared'] and e['cancelled'] and e['cleared'] < e['cancelled']) else 'cancelled' if e['cancelled'] else 'open'
    e['month'] = e['notice'].strftime('%Y-%m')
# ---- events per contact
sends = collections.defaultdict(list); opens = collections.defaultdict(set); clicks = collections.defaultdict(set); bounces = collections.defaultdict(set)
for s in ev['SentEvent']: sends[s['SubscriberKey']].append((SRV(s['EventDate']), STEP(s['TriggeredSendDefinitionObjectID']), VARIANT.get(tsds[s['TriggeredSendDefinitionObjectID']].get('ID'),'?'), s['SendID']))
for s in ev['OpenEvent']: opens[s['SubscriberKey']].add((STEP(s['TriggeredSendDefinitionObjectID']), s['SendID'], SRV(s['EventDate'])))
for s in ev['ClickEvent']: clicks[s['SubscriberKey']].add((STEP(s['TriggeredSendDefinitionObjectID']), s['SendID']))
for s in ev['BounceEvent']: bounces[s['SubscriberKey']].add((STEP(s['TriggeredSendDefinitionObjectID']), s['SendID']))
# attach sends to episode: T-5 in [due-7, due-3], T+3 in [due+1, due+6], T+7 in [due+5, due+10]
WIN = {'T-5': (-7, -3), 'T+3': (1, 6), 'T+7': (5, 10)}
for e in eps:
    e['sent'] = {}; e['open'] = {}; e['click'] = {}; e['variant'] = None
    for (t, step, var, sid) in sends.get(e['contact'], []):
        lo, hi = WIN[step]; d = (t.date() - e['due']).days
        if lo <= d <= hi and step not in e['sent']:
            e['sent'][step] = t; e['variant'] = e['variant'] or var
            e['open'][step] = min([o[2] for o in opens[e['contact']] if o[0]==step and o[1]==sid], default=None)
            e['click'][step] = any(c[0]==step and c[1]==sid for c in clicks[e['contact']])
json.dump([{k: (v.isoformat() if isinstance(v,(dt.datetime,dt.date)) else v) for k,v in e.items() if k not in ('sent','open','click')} | {'sent': {k: v.isoformat() for k,v in e['sent'].items()}, 'open': {k: (v.isoformat() if v else None) for k,v in e['open'].items()}, 'click': e['click']} for e in eps], open('episodes.json','w'))
def pct(a,b): return f"{a/b:.1%}" if b else '-'
def se(p,n): return math.sqrt(p*(1-p)/n) if n else 0
# ---- monthly table 2024-2026
print("\n== monthly cure rate (contact-episodes, renters excluded) ==")
mon = collections.defaultdict(list)
for e in eps: mon[e['month']].append(e)
for m in sorted(mon):
    L = mon[m]; n=len(L); cl=sum(e['outcome']=='cleared' for e in L); ft=[e for e in L if e['first_time']]; rp=[e for e in L if not e['first_time']]
    cov = {s: sum(s in e['sent'] for e in L) for s in WIN}
    print(m, f"n={n:5d} cleared={pct(cl,n)} first-time n={len(ft)} {pct(sum(e['outcome']=='cleared' for e in ft),len(ft))} repeat n={len(rp)} {pct(sum(e['outcome']=='cleared' for e in rp),len(rp))}",
          f"| got T-5 {pct(cov['T-5'],n)} T+3 {pct(cov['T+3'],n)} T+7 {pct(cov['T+7'],n)}")
json.dump({m: {'n': len(L), 'cleared': sum(e['outcome']=='cleared' for e in L), 'cancelled': sum(e['outcome']=='cancelled' for e in L), 'open': sum(e['outcome']=='open' for e in L),
               'first_n': sum(e['first_time'] for e in L), 'first_cleared': sum(e['first_time'] and e['outcome']=='cleared' for e in L),
               'sent': {s: sum(s in e['sent'] for e in L) for s in WIN}} for m,L in mon.items()}, open('monthly.json','w'), indent=1)
# ---- treated window: notices 2026-06-12 .. 2026-09-30 (mature, full sequence live)
T = [e for e in eps if dt.date(2026,6,12) <= e['notice'].date() <= dt.date(2026,9,30)]
print(f"\n== treated window Jun 12-Sep 30 2026: n={len(T)} cleared {pct(sum(e['outcome']=='cleared' for e in T),len(T))}")
for s in WIN:
    got=[e for e in T if s in e['sent']]; print(f"  {s}: sent to {len(got)} ({pct(len(got),len(T))}); opened {pct(sum(bool(e['open'][s]) for e in got),len(got))}; clicked {pct(sum(e['click'][s] for e in got),len(got))}")
# why no T+3? cleared before T+3 would be sent (due+3 12:00 UTC)
noT3=[e for e in T if 'T+3' not in e['sent']]
t3_time=lambda e: dt.datetime.combine(e['due']+dt.timedelta(days=3), dt.time(12,0))
print("  no T+3:", len(noT3), "of which cleared before T+3 time:", sum(1 for e in noT3 if e['cleared'] and e['cleared']<t3_time(e)), "cancelled before:", sum(1 for e in noT3 if e['cancelled'] and e['cancelled']<t3_time(e)), "had T-5:", sum('T-5' in e['sent'] for e in noT3))
# at-risk at T+3: not cleared/cancelled before T+3 send time
AR=[e for e in T if not (e['cleared'] and e['cleared']<t3_time(e)) and not (e['cancelled'] and e['cancelled']<t3_time(e))]
got=[e for e in AR if 'T+3' in e['sent']]; not_=[e for e in AR if 'T+3' not in e['sent']]
print(f"  at risk at T+3: {len(AR)}; got T+3 {len(got)} cleared {pct(sum(e['outcome']=='cleared' for e in got),len(got))}; no T+3 {len(not_)} cleared {pct(sum(e['outcome']=='cleared' for e in not_),len(not_))}")
for ft in (True, False):
    g=[e for e in got if e['first_time']==ft]; nn=[e for e in not_ if e['first_time']==ft]
    print(f"    first_time={ft}: got {len(g)} {pct(sum(e['outcome']=='cleared' for e in g),len(g))} | not {len(nn)} {pct(sum(e['outcome']=='cleared' for e in nn),len(nn))}")
op=[e for e in got if e['open']['T+3']]; nop=[e for e in got if not e['open']['T+3']]
print(f"  among T+3 recipients at risk: openers {len(op)} cleared {pct(sum(e['outcome']=='cleared' for e in op),len(op))}; non-openers {len(nop)} {pct(sum(e['outcome']=='cleared' for e in nop),len(nop))}")
ck=[e for e in got if e['click']['T+3']]; print(f"  clickers {len(ck)} cleared {pct(sum(e['outcome']=='cleared' for e in ck),len(ck))}")
for v in ('ES','E'):
    g=[e for e in got if e['variant']==v]; print(f"  path {v}: n={len(g)} cleared {pct(sum(e['outcome']=='cleared' for e in g),len(g))} opened {pct(sum(bool(e['open']['T+3']) for e in g),len(g))}")
# ---- hazard: clears per hour relative to T+3 send, manual hours only (exclude 7,9,10 UTC batch)
print("\n== clears per 1,000 at-risk per hour, relative to T+3 send (manual-hour clears only) ==")
buckets=collections.Counter(); risk=collections.Counter()
for e in got:
    t0=e['sent']['T+3']
    end = e['cleared'] or e['cancelled'] or (t0+dt.timedelta(hours=96))
    for h in range(-48, 72):
        ts=t0+dt.timedelta(hours=h)
        if ts>=end: break
        if ts.hour in (7,9,10): continue
        risk[h]+=1
    if e['cleared'] and e['cleared'].hour not in (7,9,10):
        h=int((e['cleared']-t0).total_seconds()//3600)
        if -48<=h<72: buckets[h]+=1
for lo,hi in [(-48,-24),(-24,-12),(-12,0),(0,6),(6,12),(12,24),(24,48),(48,72)]:
    c=sum(buckets[h] for h in range(lo,hi)); r=sum(risk[h] for h in range(lo,hi)); print(f"  h {lo:+d}..{hi:+d}: {c} clears / {r} at-risk-hours = {1000*c/r if r else 0:.2f}")
# same for T+7
got7=[e for e in T if 'T+7' in e['sent']]
buckets=collections.Counter(); risk=collections.Counter()
for e in got7:
    t0=e['sent']['T+7']; end = e['cleared'] or e['cancelled'] or (t0+dt.timedelta(hours=96))
    for h in range(-48, 72):
        ts=t0+dt.timedelta(hours=h)
        if ts>=end: break
        if ts.hour in (7,9,10): continue
        risk[h]+=1
    if e['cleared'] and e['cleared'].hour not in (7,9,10):
        h=int((e['cleared']-t0).total_seconds()//3600)
        if -48<=h<72: buckets[h]+=1
print("  T+7:")
for lo,hi in [(-48,-24),(-24,-12),(-12,0),(0,6),(6,12),(12,24),(24,48),(48,72)]:
    c=sum(buckets[h] for h in range(lo,hi)); r=sum(risk[h] for h in range(lo,hi)); print(f"  h {lo:+d}..{hi:+d}: {c} clears / {r} at-risk-hours = {1000*c/r if r else 0:.2f}")
# ---- open-to-clear lag for T+3 openers who cleared after opening
lags=[(e['cleared']-e['open']['T+3']).total_seconds()/3600 for e in op if e['cleared'] and e['cleared']>e['open']['T+3']]
print(f"\nT+3 openers who cleared after opening: {len(lags)} of {len(op)}; median lag h {statistics.median(lags) if lags else '-'}; within 1h {sum(l<=1 for l in lags)}, within 6h {sum(l<=6 for l in lags)}, within 24h {sum(l<=24 for l in lags)}")
