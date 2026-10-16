#!/usr/bin/env python3
"""Out-of-time validation of the two churn scores on Contact in blueowl-prod.

  Churn_Risk_Score__c             raw Data Cloud model output (Churn_Risk_Score__dlm), batch on ~28th and 1st,
                                  history-tracked since 2026-06-28 so it can be rebuilt as of any date.
  Normalized_Churn_Risk_Score__c  "Predicted Did Cancel V7" normalized model (Churn_Risk_Score_Output_Normalized__dlm),
                                  first written to Contact 2026-10-16; not history-tracked. Its training set
                                  (Churn_Risk_Training_Set_Normalized__dlm) has features as of ~2026-08-11 and labels
                                  frozen ~2026-08-22, so cancellations from 2026-08-23 on are an out-of-time test.

Outcome = Contact.Cancel_Date__c (canceled__c and Cancel_Date__c agree 1:1 on the scored book).
Metric = AUC (rank-based, ties averaged) with Hanley-McNeil SE, plus decile and band cancel rates.
Baselines = Customer_Persona__c = 'Lapse Risk' and contact tenure (CreatedDate; newer = riskier).

Usage:
  python3 churn_score_validation.py --cache ./cache [--org blueowl-prod] [--json ../data]
Pulls are cached as CSV in --cache; delete the folder to re-pull. Requires sf CLI auth.
"""
import argparse, collections, csv, io, json, math, os, subprocess, sys
from datetime import datetime, timedelta

ap = argparse.ArgumentParser()
ap.add_argument("--org", default="blueowl-prod")
ap.add_argument("--cache", default="cache")
ap.add_argument("--json", help="folder to write result json files into")
ap.add_argument("--snapshot", default="2026-08-22", help="normalized-model label freeze date (end of day)")
ap.add_argument("--through", default="2026-10-14", help="last complete cancel date to count")
a = ap.parse_args()
os.makedirs(a.cache, exist_ok=True)

def soql(name, q):
    p = os.path.join(a.cache, name + ".csv")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        env = dict(os.environ, SF_ORG_MAX_QUERY_LIMIT="200000")
        r = subprocess.run(["sf", "data", "query", "-o", a.org, "-q", q, "--result-format", "csv"],
                           capture_output=True, text=True, env=env)
        if r.returncode != 0 or not r.stdout.strip():
            sys.exit(f"query {name} failed: {r.stderr[-500:]}")
        open(p, "w").write(r.stdout)
    return list(csv.DictReader(open(p)))

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

contacts = soql("contacts", "SELECT Id, Churn_Risk_Score__c, Normalized_Churn_Risk_Score__c, canceled__c, Cancel_Date__c, "
    "Cancellation_Reason__c, Customer_Persona__c, CreatedDate FROM Contact WHERE Churn_Risk_Score__c != null "
    "OR Normalized_Churn_Risk_Score__c != null OR Cancel_Date__c != null OR canceled__c = true")
hist = soql("score_hist", "SELECT ContactId, CreatedDate, OldValue, NewValue FROM ContactHistory "
    "WHERE Field = 'Churn_Risk_Score__c' ORDER BY CreatedDate")
train_norm = soql("dc_train_norm", "SELECT Id1__c, Did_Cancel__c, Months_Policy_Active__c, Weeks_Since_Last_Trip__c, "
    "Last_Known_Trip_Date__c, Lifetime_Late_Payment_Rate__c, Trips_Per_Month__c FROM Churn_Risk_Training_Set_Normalized__dlm")
out_norm = soql("dc_out_norm", "SELECT Id__c, Did_Cancel_prediction__c FROM Churn_Risk_Score_Output_Normalized__dlm")
train_raw = soql("dc_train_raw", "SELECT Id__c, Did_Cancel__c FROM Churn_Score_Training_Set__dlm")

rows = {r["Id"]: r for r in contacts}
def cd(r): return datetime.strptime(r["Cancel_Date__c"][:10], "%Y-%m-%d") if r["Cancel_Date__c"] else None
byc = collections.defaultdict(list)
for h in hist:
    h["t"] = datetime.strptime(h["CreatedDate"][:19], "%Y-%m-%dT%H:%M:%S"); h["new"] = num(h["NewValue"]); h["old"] = num(h["OldValue"])
    byc[h["ContactId"]].append(h)
for v in byc.values(): v.sort(key=lambda h: h["t"])
raw_ids = set(byc) | {i for i, r in rows.items() if num(r["Churn_Risk_Score__c"]) is not None}

def raw_at(cid, t):
    hs = byc.get(cid, []); b = [h for h in hs if h["t"] <= t]
    if b: return b[-1]["new"]
    if hs: return hs[0]["old"]
    r = rows.get(cid); return num(r["Churn_Risk_Score__c"]) if r else None

def auc(pairs):
    pos = [s for s, l in pairs if l]; neg = [s for s, l in pairs if not l]
    if not pos or not neg: return None
    allv = sorted(pairs, key=lambda p: p[0]); n = len(allv); ranks = [0] * n; i = 0
    while i < n:
        j = i
        while j + 1 < n and allv[j + 1][0] == allv[i][0]: j += 1
        for k in range(i, j + 1): ranks[k] = (i + j) / 2 + 1
        i = j + 1
    sp = sum(r for (s, l), r in zip(allv, ranks) if l)
    return (sp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))

def auc_se(pairs):
    a_ = auc(pairs)
    if a_ is None: return None, None
    n1 = sum(l for s, l in pairs); n0 = len(pairs) - n1
    q1 = a_ / (2 - a_); q2 = 2 * a_ * a_ / (1 + a_)
    return a_, math.sqrt((a_ * (1 - a_) + (n1 - 1) * (q1 - a_ * a_) + (n0 - 1) * (q2 - a_ * a_)) / (n1 * n0))

def band(s): return "High" if s >= 67 else ("Moderate" if s >= 34 else "Low")
def tenure_bucket(r, t):
    d = (t - datetime.strptime(r["CreatedDate"][:10], "%Y-%m-%d")).days
    return "<6mo" if d < 180 else ("6-12mo" if d < 365 else ("1-2y" if d < 730 else "2y+"))
def rate(p): return 100 * sum(l for s, l in p) / len(p) if p else None
def fmt(a_, se): return "n/a" if a_ is None else "%.3f ± %.3f" % (a_, se)

out = {"generated_at": datetime.utcnow().isoformat() + "Z", "snapshot": a.snapshot, "through": a.through}
snap = datetime.strptime(a.snapshot, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
through = datetime.strptime(a.through, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)

# ---------------------------------------------------------------- 1. what the normalized model was trained on
tl = collections.Counter(r["Did_Cancel__c"] for r in train_norm)
imp = collections.Counter()
for r in train_norm:
    if r["Last_Known_Trip_Date__c"] and num(r["Weeks_Since_Last_Trip__c"]) is not None:
        imp[(datetime.strptime(r["Last_Known_Trip_Date__c"], "%Y-%m-%d") + timedelta(days=7 * num(r["Weeks_Since_Last_Trip__c"]))).date().isoformat()] += 1
lab_by_cancel_month = collections.defaultdict(collections.Counter)
for r in train_norm:
    c = rows.get(r["Id1__c"]); m = c["Cancel_Date__c"][:7] if c and c["Cancel_Date__c"] else "none"
    lab_by_cancel_month[m][r["Did_Cancel__c"]] += 1
feat_auc = {}
for f in ("Months_Policy_Active__c", "Weeks_Since_Last_Trip__c", "Lifetime_Late_Payment_Rate__c", "Trips_Per_Month__c"):
    p = [(num(r[f]), r["Did_Cancel__c"] == "true") for r in train_norm if num(r[f]) is not None]
    feat_auc[f] = {"n": len(p), "auc": round(auc(p), 3)}
scored = {r["Id__c"]: num(r["Did_Cancel_prediction__c"]) for r in out_norm}
in_train = {r["Id1__c"]: r["Did_Cancel__c"] for r in train_norm}
overlap = collections.Counter(in_train.get(c, "not in training set") for c in scored)
repeated = collections.Counter(round(v, 4) for v in scored.values()).most_common(3)
out["normalized_training"] = {"rows": len(train_norm), "labels": dict(tl), "implied_feature_snapshot": imp.most_common(3),
    "label_by_cancel_month": {m: dict(v) for m, v in sorted(lab_by_cancel_month.items()) if m >= "2026-06"},
    "feature_univariate_auc": feat_auc, "scored_contacts": len(scored), "scored_contacts_training_label": dict(overlap),
    "most_repeated_scores": repeated, "raw_training_rows": len(train_raw),
    "raw_training_labels": dict(collections.Counter(r["Did_Cancel__c"] for r in train_raw))}
print("1. Normalized training set: %d rows, labels %s" % (len(train_norm), dict(tl)))
print("   implied feature snapshot (trip date + weeks since):", imp.most_common(3))
print("   label by cancel month:", {m: dict(v) for m, v in sorted(lab_by_cancel_month.items()) if m >= "2026-07"})
print("   feature univariate AUC vs label:", feat_auc)
print("   scored contacts %d; their training label: %s; most repeated scores %s" % (len(scored), dict(overlap), repeated))
print("   raw training set: %d rows, labels %s" % (len(train_raw), dict(collections.Counter(r["Did_Cancel__c"] for r in train_raw))))

# ---------------------------------------------------------------- 2. normalized score, out-of-time
pop = [r for r in rows.values() if num(r["Normalized_Churn_Risk_Score__c"]) is not None and not (cd(r) and cd(r) <= snap)]
def lab(r, H=None):
    c = cd(r)
    return bool(c and c > snap and c <= (snap + timedelta(days=H) if H else through))
cands = {
    "normalized": lambda r: num(r["Normalized_Churn_Risk_Score__c"]),
    "raw_as_of_snapshot": lambda r: raw_at(r["Id"], snap),
    "raw_as_of_2026-07-01": lambda r: raw_at(r["Id"], datetime(2026, 7, 1, 23, 59, 59)),
    "persona_lapse_risk": lambda r: 1.0 if r["Customer_Persona__c"] == "Lapse Risk" else 0.0,
    "tenure_newer_is_riskier": lambda r: -(snap - datetime.strptime(r["CreatedDate"][:10], "%Y-%m-%d")).days,
}
sec = {"population": len(pop), "cancels": sum(lab(r) for r in pop), "cancels_30d": sum(lab(r, 30) for r in pop), "auc": {}}
print("\n2. Normalized population: %d contacts scored and not canceled by %s; %d canceled %s..%s (%.1f%%), %d within 30d"
      % (len(pop), a.snapshot, sec["cancels"], a.snapshot, a.through, 100 * sec["cancels"] / len(pop), sec["cancels_30d"]))
for name, f in cands.items():
    p = [(f(r), lab(r)) for r in pop if f(r) is not None]; p30 = [(f(r), lab(r, 30)) for r in pop if f(r) is not None]
    a_, se = auc_se(p); a30, se30 = auc_se(p30)
    sec["auc"][name] = {"n": len(p), "auc": round(a_, 3), "se": round(se, 3), "auc_30d": round(a30, 3), "se_30d": round(se30, 3)}
    print("   %-26s n=%5d  AUC %s   30-day %s" % (name, len(p), fmt(a_, se), fmt(a30, se30)))
sec["by_reason"] = {}
print("   by cancellation reason (positives = that reason; negatives = not canceled):")
for name in ("normalized", "raw_as_of_snapshot", "raw_as_of_2026-07-01"):
    f = cands[name]; sec["by_reason"][name] = {}
    for reason, test in (("Non-payment of premium", lambda r: r["Cancellation_Reason__c"] == "Non-payment of premium"),
                         ("Company Cancel", lambda r: r["Cancellation_Reason__c"] == "Company Cancel"),
                         ("Customer-initiated (other)", lambda r: r["Cancellation_Reason__c"] not in ("Non-payment of premium", "Company Cancel", ""))):
        p = [(f(r), True) for r in pop if lab(r) and test(r) and f(r) is not None] + [(f(r), False) for r in pop if not lab(r) and f(r) is not None]
        sec["by_reason"][name][reason] = {"positives": sum(l for s, l in p), "auc": round(auc(p), 3)}
        print("     %-22s %-28s pos=%4d AUC %.3f" % (name, reason, sum(l for s, l in p), auc(p)))
sec["deciles"] = {}; sec["bands"] = {}
for name in ("normalized", "raw_as_of_snapshot"):
    f = cands[name]; p = sorted([(f(r), lab(r)) for r in pop if f(r) is not None], key=lambda x: -x[0]); n = len(p); base = rate(p)
    sec["deciles"][name] = []
    print("   %s deciles (top first): range | cancel%% | lift   (base %.1f%%)" % (name, base))
    for d in range(10):
        ch = p[d * n // 10:(d + 1) * n // 10]
        sec["deciles"][name].append({"decile": d + 1, "min": round(ch[-1][0], 1), "max": round(ch[0][0], 1), "n": len(ch), "cancel_pct": round(rate(ch), 1), "lift": round(rate(ch) / base, 2)})
        print("     %2d  %5.1f-%5.1f  %5.1f%%  %.2fx" % (d + 1, ch[-1][0], ch[0][0], rate(ch), rate(ch) / base))
    sec["bands"][name] = {b: {"n": len(q), "cancel_pct": round(rate(q), 1)} for b in ("High", "Moderate", "Low") for q in [[x for x in p if band(x[0]) == b]]}
    print("   %s bands:" % name, sec["bands"][name])
# calibration in 10-point bins
f = cands["normalized"]; bins = collections.defaultdict(list)
for r in pop: bins[min(9, int(f(r) // 10))].append((f(r), lab(r)))
sec["calibration_10pt"] = [{"bin": "%d-%d" % (b * 10, b * 10 + 9), "n": len(bins[b]), "cancel_pct": round(rate(bins[b]), 1)} for b in sorted(bins)]
print("   normalized 10-point bins:", [(x["bin"], x["n"], x["cancel_pct"]) for x in sec["calibration_10pt"]])
# within tenure
sec["within_tenure"] = {}
print("   within tenure bucket (n, cancel%, AUC normalized, AUC raw-at-snapshot, normalized top-20% vs rest):")
for b in ("<6mo", "6-12mo", "1-2y", "2y+"):
    sub = [r for r in pop if tenure_bucket(r, snap) == b]
    pn = [(cands["normalized"](r), lab(r)) for r in sub]; pr = [(cands["raw_as_of_snapshot"](r), lab(r)) for r in sub if cands["raw_as_of_snapshot"](r) is not None]
    ps = sorted(pn, key=lambda x: -x[0]); k = len(ps) // 5
    sec["within_tenure"][b] = {"n": len(sub), "cancel_pct": round(rate(pn), 1), "auc_normalized": round(auc(pn), 3), "auc_raw": round(auc(pr), 3),
                               "top20_cancel_pct": round(rate(ps[:k]), 1), "rest_cancel_pct": round(rate(ps[k:]), 1)}
    print("     %-7s" % b, sec["within_tenure"][b])
out["normalized_out_of_time"] = sec

# ---------------------------------------------------------------- 3. raw score by batch date
print("\n3. Raw Churn_Risk_Score__c rebuilt as of each batch date; outcome = cancel within H days; population = scored, not yet canceled")
print("   %-12s %3s %6s %6s %6s  %-14s %-14s %-9s %-9s" % ("as of", "H", "n", "canc", "rate%", "AUC score", "AUC tenure", "within-ten", "High>=67"))
batch_days = sorted({h["t"].date() for h in hist}); out["raw_by_batch"] = []
today = datetime.utcnow()
for day in batch_days:
    t = datetime.combine(day, datetime.max.time())
    for H in (30, 60):
        if t + timedelta(days=H) > today and not (H == 30 and day == batch_days[-1]): continue
        H_eff = min(H, (through - t).days)
        ps, pt, strata = [], [], collections.defaultdict(list)
        for cid in raw_ids:
            r = rows.get(cid)
            if not r: continue
            c = cd(r)
            if c and c <= t: continue
            s = raw_at(cid, t)
            if s is None: continue
            y = bool(c and c <= t + timedelta(days=H_eff))
            ps.append((s, y)); pt.append((-(t - datetime.strptime(r["CreatedDate"][:10], "%Y-%m-%d")).days, y)); strata[tenure_bucket(r, t)].append((s, y))
        npos = sum(y for s, y in ps)
        wt = sum(auc(p) * sum(l for s, l in p) for p in strata.values() if auc(p) is not None) / npos
        hb = [l for s, l in ps if s >= 67]
        a_, se = auc_se(ps); at, set_ = auc_se(pt)
        rec = {"as_of": day.isoformat(), "horizon_days": H_eff, "n": len(ps), "cancels": npos, "auc_score": round(a_, 3), "se": round(se, 3),
               "auc_tenure": round(at, 3), "auc_within_tenure": round(wt, 3), "high_band_n": len(hb), "high_band_cancel_pct": round(100 * sum(hb) / len(hb), 1)}
        out["raw_by_batch"].append(rec)
        print("   %-12s %3d %6d %6d %5.1f  %-14s %-14s %.3f     %.1f%% (n=%d)" % (day, H_eff, len(ps), npos, 100 * npos / len(ps), fmt(a_, se), fmt(at, set_), wt, rec["high_band_cancel_pct"], len(hb)))

if a.json:
    os.makedirs(a.json, exist_ok=True)
    for k in ("normalized_training", "normalized_out_of_time", "raw_by_batch"):
        json.dump({"generated_at": out["generated_at"], "snapshot": a.snapshot, "through": a.through, k: out[k]}, open(os.path.join(a.json, k + ".json"), "w"), indent=1)
    print("\nwrote json to", a.json)
