#!/usr/bin/env python3
"""Creates the train and holdout view transforms over Churn_PIT_Training_Set__dll via the API.

  ChurnPITTrain    : Censored = 0 AND Snapshot_Key <= TRAIN_LAST   -> Churn_PIT_Train__dll
  ChurnPITHoldout  : Censored = 0 AND Snapshot_Key >= HOLDOUT_FIRST -> Churn_PIT_Holdout__dll

Model Builder trains on data model objects, so after these run, add both outputs to the default
data space and map each to a DMO (UI). Usage: python3 build_view_transforms.py [--post] [--run]
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ORG = "blueowl-prod"
TRAIN_LAST, HOLDOUT_FIRST = "202604", "202605"
SRC = "Churn_PIT_Training_Set__dll"
VERSION = "V3" if "--v3" in sys.argv else ("V2" if "--v2" in sys.argv else "")   # --v2: drops leakage columns; --v3: email counts dropped too
OFFER_ONLY = "--offers-only" in sys.argv   # restrict to rows with a renewal offer in the prior 60 days
# Driver_Role__c is populated only on contacts still active today (label 0 wherever it is set): leakage, never carried.
DROP = {"Driver_Role__c"} | ({"Email_Opens_90d__c", "Email_Sends_90d__c", "Email_Opens_30d__c", "Email_Clicks_90d__c"} if VERSION == "V3" else set())

def api(path, method="GET", body=None):
    cmd = ["sf", "api", "request", "rest", path, "-o", ORG, "-X", method]
    if body is not None:
        p = os.path.join(HERE, ".tmp_body.json"); json.dump(body, open(p, "w")); cmd += ["--body", "@" + p]
    r = subprocess.run(cmd, capture_output=True, text=True); out = r.stdout.strip()
    try: return json.loads(out)
    except Exception: return {"raw": out[:400], "err": r.stderr[-300:]}

dlo = api(f"/services/data/v64.0/ssot/data-lake-objects/{SRC}")["dataLakeObjects"][0]
fields = [f for f in dlo["dataLakeFieldInfoRepresentation"] if not f["name"].startswith(("KQ_", "DataSource", "InternalOrganization", "cdp_sys")) and f["name"] not in DROP]
names = [f["name"] for f in fields]

def definition(name, label, exprs, out_dlo):
    # range comparisons on a TEXT key are rejected by the filter validator ("Unable to find source DLOs or DMOs"),
    # so the window is a formula flag and the filter is two equality tests.
    nodes = {
        "LOAD0": {"action": "load", "sources": [], "parameters": {"dataset": {"name": SRC, "type": "dataLakeObject"}, "fields": names, "sampleDetails": {"type": "TopN"}}},
        "FORMULA0": {"action": "formula", "sources": ["LOAD0"], "parameters": {"expressionType": "SQL", "fields": [{"businessType": "Number", "defaultValue": "", "formulaExpression": exprs, "label": "In view", "name": "In_View", "precision": 18, "scale": 0, "type": "NUMBER"}]}},
        "FILTER0": {"action": "filter", "sources": ["FORMULA0"], "parameters": {"filterBooleanLogic": "1 AND 2", "filterExpressions": [
            {"field": "Censored__c", "operands": ["0"], "operator": "EQUAL", "type": "NUMBER"},
            {"field": "In_View", "operands": ["1"], "operator": "EQUAL", "type": "NUMBER"}]}},
        "OUTPUT0": {"action": "outputD360", "sources": ["FILTER0"], "parameters": {"dedupOrder": [], "fieldsMappings": [{"sourceField": n, "targetField": n} for n in names], "name": out_dlo, "type": "dataLakeObject", "writeMode": "OVERWRITE"}},
    }
    ui = {"nodes": {"LOAD0": {"label": SRC, "type": "LOAD_DATASET", "top": 112, "left": 112, "parameters": {"sampleSize": 500, "sampleDetails": {"type": "TopN"}, "dataspace": "default"}},
                    "T0": {"label": "Window flag", "description": "", "type": "TRANSFORM", "top": 112, "left": 392, "graph": {"FORMULA0": {"parameters": {"type": "BASE_FORMULA_UI"}, "label": "In view"}}, "connectors": []},
                    "FILTER0": {"label": label, "type": "FILTER", "top": 112, "left": 672},
                    "OUTPUT0": {"label": out_dlo, "type": "OUTPUT", "top": 112, "left": 952}},
          "connectors": [{"source": "LOAD0", "target": "T0"}, {"source": "T0", "target": "FILTER0"}, {"source": "FILTER0", "target": "OUTPUT0"}], "hiddenColumns": []}
    out_fields = [{"isPrimaryKey": f["name"] == "Row_Key__c", "label": f["label"], "name": f["name"], "type": f["dataType"]} for f in fields]
    return {"label": label, "name": name, "dataSpaceName": "default", "type": "BATCH", "description": label,
            "definitions": [{"label": label, "name": name, "version": "56.0", "type": "STL", "nodes": nodes,
                             "outputDataObjects": [{"category": "Other", "label": label, "name": out_dlo, "type": "dataLakeObject", "fields": out_fields}], "ui": ui}]}

views = [
    (f"ChurnPITTrain{VERSION}", f"Churn PIT Train {VERSION}".strip(), f"case when Snapshot_Key__c <= '{TRAIN_LAST}'" + (" and Renewal_Offer_Change_Dollars__c is not null" if OFFER_ONLY else "") + " then 1 else 0 end", f"Churn_PIT_Train{('_' + VERSION) if VERSION else ''}__dll"),
    (f"ChurnPITHoldout{VERSION}", f"Churn PIT Holdout {VERSION}".strip(), f"case when Snapshot_Key__c >= '{HOLDOUT_FIRST}'" + (" and Renewal_Offer_Change_Dollars__c is not null" if OFFER_ONLY else "") + " then 1 else 0 end", f"Churn_PIT_Holdout{('_' + VERSION) if VERSION else ''}__dll"),
]
for name, label, exprs, out_dlo in views:
    d = definition(name, label, exprs, out_dlo)
    json.dump(d, open(os.path.join(HERE, f"{name}.api.json"), "w"), indent=1)
    if "--put" in sys.argv:
        r = api(f"/services/data/v64.0/ssot/data-transforms/{name}", "PUT", d)
        print(name, "PUT ->", (f"updated {r['name']}" if isinstance(r, dict) and r.get("name") else r))
    if "--post" in sys.argv:
        r = api("/services/data/v64.0/ssot/data-transforms", "POST", d)
        print(name, "POST ->", (f"created {r['name']} {r.get('status')}" if isinstance(r, dict) and r.get("name") else r))
    if "--run" in sys.argv:
        r = api(f"/services/data/v64.0/ssot/data-transforms/{name}/actions/run", "POST", {})
        print(name, "run ->", r)
print("fields carried:", len(names))
