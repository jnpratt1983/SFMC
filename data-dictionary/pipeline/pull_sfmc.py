"""Pull Marketing Cloud journeys, event definitions, automations, queries, data extensions and message assets."""
import os, json
from common import save, log, RAW
from mc_client import MC, simple

JOURNEY_STATUSES = {"Published", "Sent"}   # journeys whose field usage is reported


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
    def asset(aid):
        fn = os.path.join(RAW, "mc_assets", f"{aid}.json")
        if os.path.exists(fn):
            return
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


if __name__ == "__main__":
    main()
