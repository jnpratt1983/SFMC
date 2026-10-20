#!/usr/bin/env python3
"""Validate a Model Builder prediction job's output against the point-in-time holdout.

Pulls the scores DMO and the holdout DMO through Data Cloud SQL (ssot/queryv2), joins on the row
key, and reports the pass lines from journeys/RE_ChurnRetention/TEST_PLAN.md / BUILD_GUIDE phase 5:
overall AUC vs the tenure baseline, AUC within tenure buckets, AUC by cancellation reason, deciles,
calibration, top-contributor mix, and the compliance proxy check (non-pay history share in the top decile).

Usage: python3 validate_holdout.py [--scores Voluntary_Churn_Holdout_Scores__dlm] [--holdout Churn_PIT_Holdout__dlm] [--org blueowl-prod] [--json out.json]
"""
import argparse, collections, json, math, os, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("--org", default="blueowl-prod")
ap.add_argument("--scores", default="Voluntary_Churn_Holdout_Scores__dlm")
ap.add_argument("--holdout", default="Churn_PIT_Holdout__dlm")
ap.add_argument("--json")
a = ap.parse_args()

def sql(q):
    body = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump({"sql": q}, body); body.close()
    r = subprocess.run(["sf", "api", "request", "rest", "/services/data/v64.0/ssot/queryv2", "-o", a.org, "-X", "POST", "--body", "@" + body.name], capture_output=True, text=True)
    os.unlink(body.name)
    d = json.loads(r.stdout.strip())
    if isinstance(d, list): sys.exit("query failed: " + str(d[0])[:300])
    return d["data"]

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def auc(pairs):
    pos = [s for s, l in pairs if l]; neg = [s for s, l in pairs if not l]
    if not pos or not neg: return None
    allv = sorted(pairs, key=lambda p: p[0]); n = len(allv); ranks = [0] * n; i = 0
    while i < n:
        j = i
        while j + 1 < n and allv[j + 1][0] == allv[i][0]: j += 1
        for k in range(i, j + 1): ranks[k] = (i + j) / 2 + 1
        i = j + 1
    return (sum(r for (s, l), r in zip(allv, ranks) if l) - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))

def auc_se(pairs):
    a_ = auc(pairs)
    if a_ is None: return None, None
    n1 = sum(l for s, l in pairs); n0 = len(pairs) - n1; q1 = a_ / (2 - a_); q2 = 2 * a_ * a_ / (1 + a_)
    return a_, math.sqrt((a_ * (1 - a_) + (n1 - 1) * (q1 - a_ * a_) + (n0 - 1) * (q2 - a_ * a_)) / (n1 * n0))

scores = {r[0]: (num(r[1]), r[2], r[3], r[4]) for r in sql(f"SELECT PrimaryObjectPk__c, Label_60__c, TopContributor1__c, TopContributor2__c, TopContributor3__c FROM {a.scores}")}
hold = sql(f"SELECT Row_Key__c, Label_60__c, Tenure_Days__c, Tenure_Bucket__c, Snapshot_Key__c, Reason__c, Renewal_Offer_Change_Dollars__c, Contact_Id__c FROM {a.holdout}")
rows = []
for rk, lab, ten, tb, sk, reason, offer, cid in hold:
    if rk in scores and scores[rk][0] is not None:
        rows.append({"rk": rk, "y": num(lab) == 1, "s": scores[rk][0], "ten": num(ten), "tb": tb, "sk": sk, "reason": reason, "offer": num(offer), "cid": cid, "top": scores[rk][1:]})
print(f"holdout rows {len(hold)} | scored {len(scores)} | joined {len(rows)} | positives {sum(r['y'] for r in rows)} ({100*sum(r['y'] for r in rows)/len(rows):.2f}%)")
out = {"joined": len(rows), "positives": sum(r["y"] for r in rows)}

p_model = [(r["s"], r["y"]) for r in rows]; p_ten = [(-r["ten"], r["y"]) for r in rows if r["ten"] is not None]
am, sem = auc_se(p_model); at, set_ = auc_se(p_ten)
print(f"\nOverall AUC: model {am:.3f} ± {sem:.3f} | tenure alone {at:.3f} ± {set_:.3f} | lift over tenure {am-at:+.3f}   (pass: >= 0.68 and >= tenure + 0.05)")
out["auc_model"], out["auc_tenure"] = round(am, 3), round(at, 3)

print("\nWithin tenure bucket (pass: >= 0.60 each):")
out["within_tenure"] = {}
for b in ("lt6mo", "6to12mo", "1to2y", "2yplus"):
    p = [(r["s"], r["y"]) for r in rows if r["tb"] == b]; a_ = auc(p)
    out["within_tenure"][b] = {"n": len(p), "rate": round(100 * sum(l for s, l in p) / len(p), 2), "auc": round(a_, 3) if a_ else None}
    print(f"  {b:8s} n={len(p):6d} rate {100*sum(l for s,l in p)/len(p):5.2f}%  AUC {a_ if a_ is None else round(a_,3)}")

print("\nBy cancellation reason (positives = that reason, negatives = not cancelled; pass: high premium >= 0.70, carrier >= 0.65, insured request >= 0.60):")
out["by_reason"] = {}
neg = [(r["s"], False) for r in rows if not r["y"]]
for reason in ("Due to high premium", "Replacement of insurance carrier", "Insured request - other"):
    pos = [(r["s"], True) for r in rows if r["y"] and r["reason"] == reason]
    a_ = auc(pos + neg); out["by_reason"][reason] = {"positives": len(pos), "auc": round(a_, 3) if a_ else None}
    print(f"  {reason:34s} pos={len(pos):5d} AUC {a_ if a_ is None else round(a_,3)}")

srt = sorted(rows, key=lambda r: -r["s"]); n = len(srt); base = sum(r["y"] for r in rows) / n
print(f"\nDeciles (top first; pass: monotonic, top decile >= 2.5x base {100*base:.2f}%):")
out["deciles"] = []
for d in range(10):
    ch = srt[d * n // 10:(d + 1) * n // 10]; rate = sum(r["y"] for r in ch) / len(ch); mean_s = sum(r["s"] for r in ch) / len(ch)
    out["deciles"].append({"decile": d + 1, "score_min": round(ch[-1]["s"], 4), "score_max": round(ch[0]["s"], 4), "cancel_pct": round(100 * rate, 2), "lift": round(rate / base, 2), "mean_score": round(mean_s, 4)})
    print(f"  {d+1:2d}  score {ch[-1]['s']:.4f}-{ch[0]['s']:.4f}  mean {mean_s:.4f}  cancel {100*rate:5.2f}%  lift {rate/base:.2f}x")

print("\nTop contributors (share of rows where each variable is contributor 1):")
c1 = collections.Counter(r["top"][0] for r in rows); out["top_contributor1"] = c1.most_common(10)
for k, v in c1.most_common(10): print(f"  {str(k):40s} {100*v/len(rows):5.1f}%")

print("\nCompliance proxy check (share of top decile with a renewal offer vs book share is informational; non-pay share needs the Bill join, see note):")
top = srt[:n // 10]
off_top = sum(1 for r in top if r["offer"] is not None) / len(top); off_all = sum(1 for r in rows if r["offer"] is not None) / n
print(f"  with recent offer: top decile {100*off_top:.1f}% vs all {100*off_all:.1f}%")
print("  NOTE: non-pay-history share in the top decile needs Bill__c; run scripts/churn_score_validation.py style pull on Contact Ids of the top decile:")
print("  top-decile contact ids written to the json when --json is given")
out["top_decile_contacts"] = sorted({r["cid"] for r in top})
if a.json:
    json.dump(out, open(a.json, "w"), indent=1); print("\nwrote", a.json)
