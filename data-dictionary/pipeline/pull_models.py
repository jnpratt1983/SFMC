"""Pull live health for the models described in models/*.json.

For every model file this reads the transforms named in `chain` and `checks` (last runs, schedule), the Einstein Studio
configured models (status), and runs the SOQL / row-count checks. Raw observations go to pipeline/raw/models_health.json;
build.py turns them into pass / fail against each check's threshold. Read-only."""
import datetime, glob, json, os, urllib.parse
from common import save, log, ROOT
from sf_client import SF

API = "v64.0"
MODELS_DIR = os.path.join(ROOT, "models")


def load_models():
    out = []
    for p in sorted(glob.glob(os.path.join(MODELS_DIR, "*.json"))):
        out.append(json.load(open(p)))
    return out


def soql(sf, q):
    s, d = sf.get(f"/services/data/{API}/query", q=q)
    if s != 200:
        return {"error": str(d)[:300]}
    recs = d.get("records") or []
    return {"totalSize": d.get("totalSize"), "record": {k: v for k, v in (recs[0] if recs else {}).items() if k != "attributes"}}


def main():
    sf = SF()
    b = f"/services/data/{API}/ssot"
    models = load_models()
    out = {"checkedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "transforms": {}, "configuredModels": {}, "checks": {}, "otherModels": []}

    names = set()
    for m in models:
        names |= {c["transform"] for c in m.get("chain", []) if c.get("transform")}
        names |= {c["transform"] for c in m.get("checks", []) if c.get("type") == "transform_run"}
    for n in sorted(names):
        t = {}
        s, d = sf.get(f"{b}/data-transforms/{n}")
        if s == 200:
            t.update({"label": d.get("label"), "status": d.get("status"), "lastRunDate": d.get("lastRunDate"), "lastRunStatus": d.get("lastRunStatus")})
        else:
            t["error"] = f"{s}: {str(d)[:200]}"
        s, d = sf.get(f"{b}/data-transforms/{n}/run-history", limit=48)
        if s == 200:
            t["runs"] = [{"start": h.get("startTime"), "end": h.get("endTime"), "status": h.get("status"), "rows": h.get("processedRows")} for h in d.get("histories", [])]
        s, d = sf.get(f"{b}/data-transforms/{n}/schedule")
        if s == 200:
            sch = next(iter((d.get("schedule") or {}).values()), None)
            if sch:
                tm = sch.get("time") or {}
                t["schedule"] = {"frequency": sch.get("frequency"), "interval": sch.get("interval"), "hour": tm.get("hour"), "minute": tm.get("minute"),
                                 "zone": (tm.get("timezone") or {}).get("zoneId"), "next": sch.get("nextScheduledDate")}
        out["transforms"][n] = t

    # Einstein Studio configured models: ours by API name, plus every other custom predictive model for the hygiene list
    mine = {c["apiName"]: m["id"] for m in models for c in m.get("components", []) if c.get("apiName")}
    off = 0
    while True:
        s, d = sf.get(f"{b}/machine-learning/configured-models", limit=25, offset=off)
        items = d.get("configuredModels", []) if s == 200 else []
        for cm in items:
            if cm.get("modelType") != "Predictive" or (cm.get("artifact") or {}).get("namespace") == "llmgateway":
                continue
            row = {"apiName": cm.get("name"), "label": cm.get("label"), "status": cm.get("status"), "capability": cm.get("capability"),
                   "createdDate": cm.get("createdDate"), "inputs": [f.get("name") if isinstance(f, dict) else f for f in (cm.get("inputFields") or [])]}
            if cm.get("name") in mine:
                out["configuredModels"][cm["name"]] = row
            else:
                row["inputs"] = len(row["inputs"])
                out["otherModels"].append(row)
        if len(items) < 25 or not d.get("nextPageUrl"):
            break
        off += 25

    for m in models:
        for c in m.get("checks", []):
            key = m["id"] + ":" + c["id"]
            if c["type"] == "soql_max":
                out["checks"][key] = soql(sf, c["soql"])
            elif c["type"] == "row_match":
                out["checks"][key] = {"a": soql(sf, f"SELECT COUNT() FROM {c['a']}"), "b": soql(sf, f"SELECT COUNT() FROM {c['b']}")}
    save("models_health", out)
    log("models", len(models), "transforms", len(out["transforms"]), "configured", len(out["configuredModels"]), "other", len(out["otherModels"]))


if __name__ == "__main__":
    main()
