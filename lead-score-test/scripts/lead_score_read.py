"""Point-in-time read of Einstein Lead Scoring using Lead_Score_Snapshot__c.

Exports every snapshot row plus current Lead outcomes from blueowl-prod, then reports:
  * snapshot rows per day and days where scores changed (re-score / retrain detection)
  * 7-day purchase rate and AUC by score band, point-in-time (lead not yet purchased at
    snapshot), for snapshot dates old enough to have a full 7-day follow-up window
  * baselines: quote step and lead age AUC on the same rows
  * what the latest score correlates with among open leads (step, age)

Usage (needs pandas; `python3 -m venv venv && venv/bin/pip install pandas`):
    venv/bin/python -I scripts/lead_score_read.py [--org blueowl-prod] [--since 2026-09-25] [--outdir /tmp/lsr]
First run on 2026-11-09: old clumped-at-83 model AUC 0.55 (7-day purchase) vs quote step 0.74 /
lead age 0.83; model re-scored between 2026-11-08 and 2026-11-09 snapshots (7,420 leads changed).
"""
import argparse, os, subprocess, sys
import numpy as np, pandas as pd

pd.set_option('display.width', 220); pd.set_option('display.max_columns', 40)
SNAP_Q = ("SELECT Lead_Id__c, Snapshot_Date__c, Einstein_Score__c, Previous_Score__c, Score_Segment_Id__c, "
          "Is_First_Snapshot__c, Is_Converted__c, Lead_Age_Days__c, Lead_Created_Date__c, Lead_Status__c, "
          "Max_Quote_Step__c FROM Lead_Score_Snapshot__c ORDER BY Lead_Id__c, Snapshot_Date__c")
LEAD_Q = ("SELECT Id, CreatedDate, Status, IsConverted, ConvertedDate, purchased__c, Purchased_Date__c, "
          "Max_Quote_Step__c, ScoreIntelligence.Score FROM Lead WHERE RecordType.Name = 'Auto' "
          "AND CreatedDate >= {since}T00:00:00Z")

def export(org, soql, path):
    with open(path, 'w') as f:
        subprocess.run(['sf', 'data', 'query', '-o', org, '-q', soql, '--result-format', 'csv'],
                       stdout=f, stderr=subprocess.DEVNULL, check=True)

def auc(score, y):
    d = pd.DataFrame({'s': score, 'y': y}).dropna()
    if d.y.nunique() < 2: return np.nan
    r = d.s.rank(); n1 = d.y.sum(); n0 = len(d) - n1
    return (r[d.y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)

def band(x):
    return pd.cut(x, [0, 10, 30, 50, 70, 82.5, 83.5, 90, 100],
                  labels=['1-10', '11-30', '31-50', '51-70', '71-82', '83', '84-90', '91-99'])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--org', default='blueowl-prod'); ap.add_argument('--since', default='2026-09-25')
    ap.add_argument('--outdir', default='/tmp/lsr'); ap.add_argument('--window', type=int, default=7)
    a = ap.parse_args(); os.makedirs(a.outdir, exist_ok=True)
    sp, lp = os.path.join(a.outdir, 'snapshots.csv'), os.path.join(a.outdir, 'leads.csv')
    export(a.org, SNAP_Q, sp); export(a.org, LEAD_Q.format(since=a.since), lp)
    s = pd.read_csv(sp, dtype={'Max_Quote_Step__c': str}); l = pd.read_csv(lp, dtype={'Max_Quote_Step__c': str})
    s['Snapshot_Date__c'] = pd.to_datetime(s['Snapshot_Date__c'])
    for c in ['CreatedDate', 'ConvertedDate', 'Purchased_Date__c']:
        l[c] = pd.to_datetime(l[c], utc=True).dt.tz_localize(None)
    print(f"snapshots {len(s)}  leads {s.Lead_Id__c.nunique()}  matched {s.Lead_Id__c.isin(l.Id).mean():.1%}")
    chg = s[s.Previous_Score__c.notna() & (s.Previous_Score__c != s.Einstein_Score__c)]
    print("\nrows per day / changed scores per day:")
    print(pd.concat([s.groupby('Snapshot_Date__c').size().rename('rows'),
                     chg.groupby('Snapshot_Date__c').size().rename('changed')], axis=1).fillna(0).astype(int).to_string())

    r = s.merge(l[['Id', 'Purchased_Date__c', 'ConvertedDate']], left_on='Lead_Id__c', right_on='Id', how='inner')
    r['snap_dt'] = r.Snapshot_Date__c + pd.Timedelta(hours=12)        # 05:00 Pacific flow run
    r = r[~(r.Purchased_Date__c <= r.snap_dt) & ~(r.ConvertedDate <= r.snap_dt)]   # not yet bought
    r['y'] = ((r.Purchased_Date__c > r.snap_dt) &
              (r.Purchased_Date__c <= r.snap_dt + pd.Timedelta(days=a.window))).astype(int)
    r['step'] = pd.to_numeric(r.Max_Quote_Step__c, errors='coerce'); r['age'] = r.Lead_Age_Days__c
    cutoff = s.Snapshot_Date__c.max() - pd.Timedelta(days=a.window)
    m = r[r.Snapshot_Date__c <= cutoff]
    print(f"\n== point-in-time rows with full {a.window}-day window (snapshot <= {cutoff.date()}): {len(m)}, buyers {m.y.sum()}")
    print(m.groupby(band(m.Einstein_Score__c), observed=False).agg(n=('y', 'size'), buy=('y', 'sum'), rate=('y', 'mean')).round(4).to_string())
    print(f"null-score rows {m.Einstein_Score__c.isna().sum()} rate {m[m.Einstein_Score__c.isna()].y.mean():.4f}")
    print(f"AUC einstein {auc(m.Einstein_Score__c, m.y):.3f}  quote step {auc(m.step, m.y):.3f}  lead age(neg) {auc(-m.age, m.y):.3f}")
    print("\nAUC by snapshot date (n, buyers, einstein, step):")
    for d, sub in m.groupby('Snapshot_Date__c'):
        print(f"  {d.date()} {len(sub):5d} {sub.y.sum():3d} {auc(sub.Einstein_Score__c, sub.y):.3f} {auc(sub.step, sub.y):.3f}")
    # which rows were scored by the post-2026-11-09 model
    new = m[m.Snapshot_Date__c >= '2026-11-09']
    if len(new):
        print(f"\n== NEW model rows (snapshot >= 2026-11-09) with full window: {len(new)}, buyers {new.y.sum()}")
        print(new.groupby(band(new.Einstein_Score__c), observed=False).agg(n=('y', 'size'), buy=('y', 'sum'), rate=('y', 'mean')).round(4).to_string())
        print(f"AUC einstein {auc(new.Einstein_Score__c, new.y):.3f}  step {auc(new.step, new.y):.3f}  age(neg) {auc(-new.age, new.y):.3f}")
        # does the score add to step+age? crude: AUC within step bands
        for lo, hi in [(0, 3.4), (3.5, 4.9), (5, 9)]:
            sub = new[(new.step >= lo) & (new.step <= hi)]
            print(f"  step {lo}-{hi}: n {len(sub)} buyers {sub.y.sum()} AUC einstein {auc(sub.Einstein_Score__c, sub.y):.3f} age {auc(-sub.age, sub.y):.3f}")
    latest = r[r.Snapshot_Date__c == s.Snapshot_Date__c.max()]
    print(f"\n== latest snapshot open leads {len(latest)}: corr score~step {latest[['Einstein_Score__c','step']].corr().iloc[0,1]:.2f}, score~age {latest[['Einstein_Score__c','age']].corr().iloc[0,1]:.2f}")
    print(latest.groupby(pd.cut(latest.age, [-1, 3, 7, 14, 21, 30]), observed=False).Einstein_Score__c.agg(['size', 'mean']).round(1).to_string())

if __name__ == '__main__':
    sys.exit(main())
