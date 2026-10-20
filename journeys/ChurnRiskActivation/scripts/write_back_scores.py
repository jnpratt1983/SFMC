#!/usr/bin/env python3
"""Monthly write-back of the voluntary-churn score to Contact.

Reads the Model Builder prediction output (score + top 3 contributors) and the scoring set (reason and
personalization numbers) through Data Cloud SQL, computes the band from this batch's deciles, and
bulk-updates Contact. Idempotent: re-running overwrites the same fields.

Usage: python3 write_back_scores.py [--org blueowl-prod] [--dry-run] [--high 59.99 --moderate 49.05]
With no cuts given, High = top decile of this batch, Moderate = next two deciles; the cuts used are printed
and should be copied into RE_ChurnRetention_Config.

Fields written: Voluntary_Churn_Risk_Score__c, Voluntary_Churn_Band__c, Voluntary_Churn_Scored_At__c,
Voluntary_Churn_Top_Factors__c, Voluntary_Churn_Reason__c, Voluntary_Churn_Offer_Change__c,
Voluntary_Churn_Discount_Change__c, Voluntary_Churn_Driving_Score__c.
"""
import argparse, csv, json, os, subprocess, sys, tempfile
from datetime import date

ap = argparse.ArgumentParser()
ap.add_argument("--org", default="blueowl-prod")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--high", type=float); ap.add_argument("--moderate", type=float)
ap.add_argument("--scores", default="Voluntary_Churn_Score__dlm")
ap.add_argument("--scoring", default="Churn_PIT_Scoring_Set__dll")
a = ap.parse_args()

def sql(q):
    body = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False); json.dump({"sql": q}, body); body.close()
    r = subprocess.run(["sf", "api", "request", "rest", "/services/data/v64.0/ssot/queryv2", "-o", a.org, "-X", "POST", "--body", "@" + body.name], capture_output=True, text=True)
    os.unlink(body.name); d = json.loads(r.stdout.strip())
    if isinstance(d, list): sys.exit("query failed: " + str(d[0])[:300])
    return d["data"]

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

LABELS = {"Drv_Score_Latest__c": "Driving score", "Drv_Discount_Latest__c": "Earned discount", "Drv_Discount_Change__c": "Discount change", "Drv_Score_Trend__c": "Driving score trend",
          "Drv_Trips_Latest__c": "Trips", "Drv_Miles_Latest__c": "Miles", "Days_Since_Last_Cycle__c": "Days since last driving cycle", "Drv_Cycles__c": "Driving cycles",
          "Bill_Net_Latest__c": "Premium", "Bill_Net_Change_3m__c": "Premium change", "Bill_Net_Change_3m_Pct__c": "Premium change %", "Bill_Gross_Latest__c": "Gross premium", "Bill_Count__c": "Invoices",
          "Renewal_Offer_Change_Dollars__c": "Renewal offer change", "Renewal_Offer_Change_Pct__c": "Renewal offer change %", "Renewal_Offer_Rate__c": "Renewal offer rate", "Renewal_Rating_Version__c": "Rating version", "Days_Since_Renewal_Offer_PIT__c": "Days since renewal offer",
          "App_Events_30d__c": "App use 30d", "App_Events_90d__c": "App use 90d", "Days_Since_Last_App_Event__c": "Days since app use",
          "Email_Open_Rate_90d__c": "Email open rate", "Days_Since_Last_Email_Event__c": "Days since email activity", "Tickets_90d__c": "Support tickets", "Days_Since_Last_Ticket__c": "Days since last ticket",
          "Tenure_Days__c": "Tenure", "Tenure_Bucket__c": "Tenure", "Policy_Days__c": "Policy age", "Days_Into_Term_Est__c": "Days into term", "Days_To_Term_End_Est__c": "Days to term end", "Mailing_State__c": "State"}
def factor(s):
    if not s: return None
    name = s.split(":")[0]; val = s.split(":", 1)[1] if ":" in s else ""
    lab = LABELS.get(name, name.replace("__c", "").replace("_", " "))
    if val in ("nan", "", "9999", "None"): return lab + " (none)" if val in ("nan", "9999") else lab
    return lab

scores = sql(f"SELECT PrimaryObjectPk__c, Label_60__c, TopContributor1__c, TopContributor2__c, TopContributor3__c FROM {a.scores}")
feats = {r[0]: r[1:] for r in sql(f"SELECT Row_Key__c, Contact_Id__c, Churn_Reason__c, Renewal_Offer_Change_Dollars__c, Drv_Discount_Change__c, Drv_Score_Latest__c FROM {a.scoring}")}
vals = sorted(num(r[1]) for r in scores if num(r[1]) is not None); n = len(vals)
high = a.high if a.high is not None else vals[int(0.9 * n)]
mod = a.moderate if a.moderate is not None else vals[int(0.7 * n)]
print(f"scored {len(scores)} | with features {sum(1 for r in scores if r[0] in feats)} | cuts: High >= {high:.2f}, Moderate >= {mod:.2f}")

today = date.today().isoformat(); rows = []; missing = 0
for rk, score, c1, c2, c3 in scores:
    f = feats.get(rk)
    if not f: missing += 1; continue
    cid, reason, offer, disc, drv = f
    s = num(score)
    if s is None or not cid: missing += 1; continue
    band = "High" if s >= high else ("Moderate" if s >= mod else "Low")
    factors = "; ".join(x for x in (factor(c1), factor(c2), factor(c3)) if x)[:255]
    rows.append({"Id": cid, "Voluntary_Churn_Risk_Score__c": f"{s:.2f}", "Voluntary_Churn_Band__c": band, "Voluntary_Churn_Scored_At__c": today,
                 "Voluntary_Churn_Top_Factors__c": factors, "Voluntary_Churn_Reason__c": reason or "GENERAL",
                 "Voluntary_Churn_Offer_Change__c": "" if num(offer) is None else f"{num(offer):.2f}",
                 "Voluntary_Churn_Discount_Change__c": "" if num(disc) is None else f"{num(disc):.2f}",
                 "Voluntary_Churn_Driving_Score__c": "" if num(drv) is None else f"{num(drv):.2f}"})
print(f"rows to update {len(rows)} | skipped {missing} | bands: High {sum(r['Voluntary_Churn_Band__c']=='High' for r in rows)}, Moderate {sum(r['Voluntary_Churn_Band__c']=='Moderate' for r in rows)}, Low {sum(r['Voluntary_Churn_Band__c']=='Low' for r in rows)}")
print("sample:", rows[0])
out = os.path.join(tempfile.gettempdir(), "churn_writeback.csv")
with open(out, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n"); w.writeheader(); w.writerows(rows)
if a.dry_run: print("dry run; file at", out); sys.exit()
r = subprocess.run(["sf", "data", "update", "bulk", "-o", a.org, "-s", "Contact", "-f", out, "-w", "30", "--json"], capture_output=True, text=True)
d = json.loads(r.stdout.strip()[r.stdout.find("{"):]); j = (d.get("result") or {}).get("jobInfo", {})
print("bulk update:", j.get("state"), "| processed", j.get("numberRecordsProcessed"), "| failed", j.get("numberRecordsFailed"), "| message", (d.get("message") or "")[:300])
