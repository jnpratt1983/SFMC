#!/usr/bin/env python3
"""Forward read of the Einstein lead score against two outcomes: purchase and "back to quote".

Back to quote = a Quote_Session_Key__c / Max_Quote_Step__c change on the lead (only in its first 24 hours, sync tails to 48)
OR a new Lead with the same email or cookie ID (optimizely_dna__Visitor_Id__c) created after the snapshot: the quote flow
only updates a Lead for 24 hours, a later return is a new quote and a new Lead.
Purchase = first purchased__c -> true in LeadHistory (the flag flaps on ~1 in 5 purchasers), else Purchased_Date__c.

Usage: venv/bin/python -I scripts/lead_score_return_read.py [--org blueowl-prod] [--since 2026-11-09]
       [--history-since 2026-10-25] [--window-days 7] [--outdir /tmp/lsrr]
Emails are hashed on the way in and never written to disk.
"""
import argparse, hashlib, io, os, subprocess, sys
import numpy as np, pandas as pd

def soql(org, q, limit=200000):
    env = dict(os.environ, SF_ORG_MAX_QUERY_LIMIT=str(limit))
    r = subprocess.run(['sf', 'data', 'query', '-o', org, '--result-format', 'csv', '-q', q], capture_output=True, text=True, env=env)
    if r.returncode: sys.exit(r.stderr)
    return pd.read_csv(io.StringIO(r.stdout), dtype=str)

def auc(score, y):
    d = pd.DataFrame({'s': score, 'y': y}).dropna()
    if d.y.nunique() < 2 or len(d) < 20: return np.nan
    r = d.s.rank(); n1 = d.y.sum(); n0 = len(d) - n1
    return (r[d.y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--org', default='blueowl-prod'); ap.add_argument('--since', default='2026-11-09')
    ap.add_argument('--history-since', default='2026-10-25'); ap.add_argument('--window-days', type=float, default=7)
    ap.add_argument('--outdir', default='/tmp/lsrr'); a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    pd.set_option('display.width', 200)
    s = soql(a.org, f"SELECT Lead_Id__c, Snapshot_Date__c, Einstein_Score__c, Previous_Score__c, Max_Quote_Step__c, Lead_Age_Days__c, Is_First_Snapshot__c, CreatedDate FROM Lead_Score_Snapshot__c WHERE Snapshot_Date__c >= {a.since}")
    l = soql(a.org, f"SELECT Id, Email, optimizely_dna__Visitor_Id__c, CreatedDate, Status, purchased__c, Purchased_Date__c FROM Lead WHERE CreatedDate >= {a.history_since}T00:00:00Z")
    h = soql(a.org, f"SELECT LeadId, Field, OldValue, NewValue, CreatedDate FROM LeadHistory WHERE CreatedDate >= {a.history_since}T00:00:00Z AND Field IN ('Max_Quote_Step__c','purchased__c','Quote_Session_Key__c','Declined__c')")
    l['ek'] = l.Email.fillna('').str.lower().str.strip().map(lambda e: hashlib.sha1(e.encode()).hexdigest()[:16] if e else None)
    l['ck'] = l.optimizely_dna__Visitor_Id__c.where(l.optimizely_dna__Visitor_Id__c.str.len() > 0)
    l = l.drop(columns=['Email', 'optimizely_dna__Visitor_Id__c'])
    for d, c in ((s, 'CreatedDate'), (l, 'CreatedDate'), (h, 'CreatedDate')): d[c] = pd.to_datetime(d[c], utc=True)
    l['pd'] = pd.to_datetime(l.Purchased_Date__c, utc=True, errors='coerce')
    s['Einstein_Score__c'] = pd.to_numeric(s.Einstein_Score__c); s['Previous_Score__c'] = pd.to_numeric(s.Previous_Score__c, errors='coerce')
    s['age'] = pd.to_numeric(s.Lead_Age_Days__c); s['step'] = pd.to_numeric(s.Max_Quote_Step__c, errors='coerce')
    s.to_csv(f'{a.outdir}/snapshots.csv', index=False); l.to_csv(f'{a.outdir}/leads_hashed.csv', index=False); h.to_csv(f'{a.outdir}/leadhistory.csv', index=False)
    NOW = h.CreatedDate.max(); W = pd.Timedelta(days=a.window_days)
    hp = h[h.Field == 'purchased__c']; first_true = hp[hp.NewValue == 'true'].groupby('LeadId').CreatedDate.min()
    flappers = set(hp[(hp.OldValue == 'true') & (hp.NewValue == 'false')].LeadId)
    hr = h[h.Field.isin(['Max_Quote_Step__c', 'Quote_Session_Key__c'])]
    hr = hr[~((hr.Field == 'Max_Quote_Step__c') & ((hr.OldValue == '7.0') | (hr.NewValue == '7.0')))]
    hr = hr[~hr.LeadId.isin(flappers) | (hr.Field == 'Quote_Session_Key__c')]
    hd = h[(h.Field == 'Declined__c') & (h.NewValue == 'true')].groupby('LeadId').CreatedDate.min()
    print(f'snapshots {a.since}..: {len(s)} rows; history to {NOW}; purchasers {hp.LeadId.nunique()}, flapping {len(flappers)}; window {a.window_days}d')

    # one row per lead: its first snapshot on/after --since, so the score is the earliest new-model score
    b = s.sort_values('CreatedDate').drop_duplicates('Lead_Id__c').merge(l[['Id', 'ek', 'ck', 'pd', 'Status']], left_on='Lead_Id__c', right_on='Id', how='left')
    b['snap_t'] = b.CreatedDate; b['end_t'] = (b.snap_t + W).clip(upper=NOW)
    b['purch_t'] = b.Lead_Id__c.map(first_true).fillna(b.pd); dt = b.Lead_Id__c.map(hd)
    pre = (b.purch_t.notna() & (b.purch_t <= b.snap_t)) | (b.Status == 'Converted') | (dt.notna() & (dt <= b.snap_t))
    b = b[~pre & (b.snap_t + pd.Timedelta(hours=4) <= NOW)].copy()
    b['y_purch'] = (b.purch_t.notna() & (b.purch_t > b.snap_t) & (b.purch_t <= b.end_t)).astype(int)
    e = hr.merge(b[['Lead_Id__c', 'snap_t', 'end_t']], left_on='LeadId', right_on='Lead_Id__c'); e = e[(e.CreatedDate > e.snap_t) & (e.CreatedDate <= e.end_t)]
    n = pd.concat([b[['Lead_Id__c', k, 'snap_t', 'end_t']].dropna(subset=[k]).merge(l[[k, 'Id', 'CreatedDate']].dropna(subset=[k]), on=k) for k in ('ek', 'ck')])
    n = n[(n.Id != n.Lead_Id__c) & (n.CreatedDate > n.snap_t) & (n.CreatedDate <= n.end_t)]
    b['y_hist'] = b.Lead_Id__c.isin(e.LeadId).astype(int); b['y_newlead'] = b.Lead_Id__c.isin(n.Lead_Id__c).astype(int)
    b['y_back'] = ((b.y_hist == 1) | (b.y_newlead == 1)).astype(int)
    b['fwd_h'] = (b.end_t - b.snap_t).dt.total_seconds() / 3600
    b.drop(columns=['ek', 'ck']).to_csv(f'{a.outdir}/cohort.csv', index=False)
    print(f'\ncohort: {len(b)} open leads; mean forward window {b.fwd_h.mean():.0f}h (capped by now); back {b.y_back.sum()} (hist {b.y_hist.sum()}, new lead {b.y_newlead.sum()}), purchases {b.y_purch.sum()}')
    for name, g in [('fresh 0-3d', b[b.age <= 3]), ('older 4-30d', b[b.age > 3]), ('all', b)]:
        print(f'\n== {name}: n={len(g)} back {g.y_back.sum()} ({g.y_back.mean()*100:.1f}%) purch {g.y_purch.sum()} ({g.y_purch.mean()*100:.2f}%)')
        for y in ['y_back', 'y_purch']:
            print(f'   AUC {y:8s} score {auc(g.Einstein_Score__c, g[y]):.3f} | step {auc(g.step, g[y]):.3f} | age(younger) {auc(-g.age, g[y]):.3f} | old score {auc(g.Previous_Score__c, g[y]):.3f}')
        g = g.assign(band=pd.cut(g.Einstein_Score__c, [0, 20, 40, 60, 80, 90, 95, 100], labels=['1-20', '21-40', '41-60', '61-80', '81-90', '91-95', '96-99']))
        t = g.groupby('band', observed=True).agg(n=('Lead_Id__c', 'size'), age=('age', 'mean'), step=('step', 'mean'), back=('y_back', 'mean'), purch=('y_purch', 'mean'))
        t[['back', 'purch']] *= 100; print(t.round(1).to_string())
    g = b[b.age <= 3]
    print('\n== fresh leads, within quote step: back-to-quote rate below / at-or-above the median score')
    for st, gg in g.groupby('step'):
        if len(gg) < 40: continue
        med = gg.Einstein_Score__c.median(); lo = gg[gg.Einstein_Score__c < med]; hi = gg[gg.Einstein_Score__c >= med]
        print(f'   step {st}: n={len(gg)} <{med:.0f}: back {lo.y_back.mean()*100:.1f}% purch {lo.y_purch.mean()*100:.1f}% | >={med:.0f}: back {hi.y_back.mean()*100:.1f}% purch {hi.y_purch.mean()*100:.1f}% | AUC back {auc(gg.Einstein_Score__c, gg.y_back):.2f}')

if __name__ == '__main__': main()
