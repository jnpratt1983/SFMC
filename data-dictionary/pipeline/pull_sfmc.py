"""Pull Marketing Cloud journeys, event definitions, automations, queries, data extensions and message assets."""
import os, json, re
from common import save, log, RAW
from mc_client import MC, simple

JOURNEY_STATUSES = {"Published", "Sent"}   # journeys whose field usage is reported


BLOCK_REF = re.compile(r'(?i)ContentBlockBy(Id|Key|Name)\s*\(\s*\\?["\']?([^"\'\\)]+)')


def pull_blocks(m, max_depth=4, roots=None):
    """Fetch content blocks that emails / pushes / texts pull in with ContentBlockById, ByKey or ByName (AMPscript) or as
    `<div data-type="slot">` references, following blocks that reference other blocks. Saved next to the message assets as
    mc_assets/<id>.json; key and name references are recorded in mc_block_refs.json as "key:<k>" / "name:<n>" -> asset id."""
    adir = os.path.join(RAW, "mc_assets")
    refs_path = os.path.join(RAW, "mc_block_refs.json")
    refs = json.load(open(refs_path)) if os.path.exists(refs_path) else {}
    done, fetched, fresh = set(), 0, set()

    def fetch(aid):
        nonlocal fetched
        fn = os.path.join(adir, f"{aid}.json")
        if str(aid) not in fresh:
            fresh.add(str(aid))
            s, r = m.get(f"/asset/v1/content/assets/{aid}")
            if s != 200:
                return None
            json.dump(r, open(fn, "w"))
            fetched += 1
        return fn

    def lookup(kind, val):
        k = f"{kind}:{val}"
        if k not in refs:
            prop = "customerKey" if kind == "key" else "name"
            s, r = m.post("/asset/v1/content/assets/query", {"query": {"property": prop, "simpleOperator": "equal", "value": val.split("\\")[-1]}, "fields": ["id", "name"]})
            its = r.get("items", []) if isinstance(r, dict) else []
            refs[k] = its[0]["id"] if its else None
        return refs[k]

    frontier = [os.path.join(adir, f"{a}.json") for a in roots] if roots else [os.path.join(adir, f) for f in os.listdir(adir) if f.endswith(".json")]
    frontier = [f for f in frontier if os.path.exists(f)]
    for _ in range(max_depth):
        nxt = []
        for fn in frontier:
            if fn in done:
                continue
            done.add(fn)
            for kind, val in set(BLOCK_REF.findall(open(fn).read())):
                kind, val = kind.lower(), val.strip()
                aid = val if kind == "id" and val.isdigit() else lookup(kind, val) if kind in ("key", "name") else None
                got = fetch(aid) if aid else None
                if got and got not in done:
                    nxt.append(got)
        frontier = nxt
        if not frontier:
            break
    json.dump(refs, open(refs_path, "w"), indent=0)
    log("content blocks fetched", fetched, "key/name refs", len(refs))


def main():
    m = MC()
    items, page = [], 1
    while True:
        s, j = m.get("/interaction/v1/interactions", **{"$page": page, "$pageSize": 100})
        its = j.get("items", []) if s == 200 else []
        items += its
        if len(its) < 100:
            break
        page += 1
    save("mc_journeys_list", items)

    details = {}
    for i in items:
        if i.get("status") not in JOURNEY_STATUSES:
            continue
        s, d = m.get(f"/interaction/v1/interactions/{i['id']}", extras="all")
        if s == 200:
            details[i["id"]] = d
    save("mc_journeys", details)

    eventdefs = {}
    for d in details.values():
        for t in d.get("triggers", []):
            k = t.get("metaData", {}).get("eventDefinitionKey")
            if k and k not in eventdefs:
                s, e = m.get(f"/interaction/v1/eventDefinitions/key:{k}")
                if s == 200:
                    eventdefs[k] = e
    save("mc_eventdefs", eventdefs)

    s, j = m.get("/automation/v1/automations", **{"$page": 1, "$pageSize": 500})
    adet, queries = {}, {}
    for a in j.get("items", []):
        s, d = m.get(f"/automation/v1/automations/{a['id']}")
        if s != 200:
            continue
        adet[a["id"]] = d
        for step in d.get("steps", []):
            for act in step.get("activities", []):
                if act.get("objectTypeId") == 300 and act.get("activityObjectId") and act["activityObjectId"] not in queries:
                    s, qd = m.get(f"/automation/v1/queries/{act['activityObjectId']}")
                    if s == 200:
                        queries[act["activityObjectId"]] = qd
    # queries not in any automation (still may target entry DEs)
    page = 1
    while True:
        s, j = m.get("/automation/v1/queries", **{"$page": page, "$pageSize": 100})
        its = j.get("items", []) if s == 200 else []
        for q in its:
            if q.get("queryDefinitionId") not in queries:
                queries[q["queryDefinitionId"]] = q
        if len(its) < 100:
            break
        page += 1
    save("mc_automations", adet)
    save("mc_queries", queries)

    des = m.retrieve("DataExtension", ["Name", "CustomerKey", "ObjectID", "ModifiedDate", "CreatedDate", "IsSendable", "CategoryID"], simple("Name", "like", ["%"]))
    save("mc_de_list", des)
    need_ids = {e.get("dataExtensionId") for e in eventdefs.values() if e.get("dataExtensionId")}
    # DEs needed: synced *_Salesforce, journey entry DEs, and every query target/source DE name we can see
    qnames = set()
    for q in queries.values():
        if q.get("targetKey"):
            qnames.add(q["targetKey"].upper())
    targets = [d for d in des if d.get("Name", "").endswith("_Salesforce") or d.get("ObjectID") in need_ids or d.get("CustomerKey", "").upper() in qnames]
    fields = {}
    for d in targets:
        fl = m.retrieve("DataExtensionField", ["Name", "FieldType", "IsPrimaryKey", "MaxLength", "ObjectID", "Ordinal"],
                        simple("DataExtension.CustomerKey", "equals", [d["CustomerKey"]]))
        fields[d["CustomerKey"]] = {"name": d.get("Name"), "objectId": d.get("ObjectID"), "key": d["CustomerKey"], "modified": d.get("ModifiedDate"),
                                    "fields": [{k: f.get(k) for k in ("Name", "FieldType", "IsPrimaryKey", "MaxLength", "ObjectID")} for f in fl]}
    save("mc_de_fields", fields)
    log("DEs", len(des), "with fields", len(fields))

    # message assets used by the reported journeys
    os.makedirs(os.path.join(RAW, "mc_assets"), exist_ok=True)
    legacy = {}
    pulled = set()
    def asset(aid):
        fn = os.path.join(RAW, "mc_assets", f"{aid}.json")
        if aid in pulled:   # once per run; always re-fetched across runs so edited emails are picked up
            return
        pulled.add(aid)
        s, r = m.get(f"/asset/v1/content/assets/{aid}")
        if s == 200:
            json.dump(r, open(fn, "w"))
    def legacy_to_asset(lid):
        lid = str(lid)
        if lid in legacy:
            return legacy[lid]
        s, r = m.post("/asset/v1/content/assets/query", {"query": {"property": "data.email.legacy.legacyId", "simpleOperator": "equal", "value": lid}, "fields": ["id", "name"]})
        its = r.get("items", []) if isinstance(r, dict) else []
        legacy[lid] = its[0]["id"] if its else None
        return legacy[lid]
    for d in details.values():
        for a in d.get("activities", []):
            ca = a.get("configurationArguments") or {}
            if a["type"] == "EMAILV2":
                lid = (ca.get("triggeredSend") or {}).get("emailId")
                aid = legacy_to_asset(lid) if lid else None
                if aid:
                    asset(aid)
            elif a["type"] in ("PUSHNOTIFICATIONACTIVITY", "SMSSYNC") and ca.get("assetId"):
                asset(ca["assetId"])
    save("mc_legacy_map", legacy)
    pull_blocks(m, roots=pulled)


if __name__ == "__main__":
    main()
