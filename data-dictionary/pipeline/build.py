"""Build data/dictionary.json, data/search-index.json and the monthly changelog from pipeline/raw/*.json.

Resolution rules (summarised; see README.md for the long form):
- Salesforce field -> Marketing Cloud: the Marketing Cloud Connect synced DE "<Object>_Salesforce" carries the field as a
  column with the same API name. A SQL query uses the field when it references that DE and the column name. A journey uses
  the field when (a) a query in the chain that fills its entry DE uses it, (b) a decision split, entry filter, email, push,
  SMS or Sales Cloud activity references the column (resolved through the entry-DE column map), or (c) the journey is
  triggered by a Salesforce data event on that object/field.
- Salesforce field -> Data Cloud: the CRM data stream maps the field to a DLO column; the DLO column maps to DMO fields through
  the package-kit field maps (standard fields) or by name (custom fields, DMO field named either like the Salesforce field or
  like the DLO column). Calculated insights, segments, identity rules, data graphs, data actions and activations are then
  scanned for DMO.field references.
"""
import json, os, re, html, glob, datetime
from collections import defaultdict, OrderedDict
from common import load, log, RAW, DATA, ROOT

OBJECTS = ["Lead", "Contact", "Account", "Bill__c", "Monthly_Driving_Stat__c"]
OBJECT_LABELS = {"Monthly_Driving_Stat__c": "Monthly Driving Stats", "Bill__c": "Bill"}
# Extra DMOs to treat as mapped from an object (beyond kit maps + auto-detected). Edit as the org evolves.
DMO_OVERRIDES = {"Bill__c": ["Bill__dlm"]}
AUTO_DMO_MIN_MATCHES = 10
TODAY = datetime.date.today().isoformat()

# ---------------------------------------------------------------- helpers
def norm(s):
    return (s or "").strip().lower()

def de_short_type(t):
    return t

def key(obj, field):
    return f"{obj}.{field}"

def html_unescape_json(s):
    try:
        return json.loads(html.unescape(s)) if isinstance(s, str) and s.strip() else (s or {})
    except Exception:
        return {}

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

def normalize_name(n):
    """Compare field names ignoring case, underscores and the __c / _c__c suffixes."""
    n = re.sub(r"(_c)?__c$", "", n or "", flags=re.I)
    return re.sub(r"[^a-z0-9]", "", n.lower())

# ---------------------------------------------------------------- 1. Salesforce fields
def build_fields():
    desc = load("sf_describe")
    cfs = {}
    for r in load("sf_customfields"):
        ns = r.get("NamespacePrefix")
        api = (ns + "__" if ns else "") + r["DeveloperName"] + "__c"
        cfs[(r["TableEnumOrId"], api)] = r
    ents = {e["QualifiedApiName"]: e for e in load("sf_entities")}
    fds = {(r["EntityDefinition"]["QualifiedApiName"], r["QualifiedApiName"]): r for r in load("sf_fielddefs")}
    try:
        inst = json.loads(os.popen("sf org display -o %s --json 2>/dev/null" % os.environ.get("SF_ORG", "blueowl-prod")).read())["result"]["instanceUrl"]
    except Exception:
        inst = os.environ.get("SF_INSTANCE_URL", "")
    fields, objects = [], []
    for o in OBJECTS:
        d = desc[o]
        durable = ents.get(o, {}).get("DurableId", o)
        objects.append({"apiName": o, "label": OBJECT_LABELS.get(o, d["label"]), "pluralLabel": d.get("labelPlural"), "custom": d.get("custom"),
                        "fieldCount": len(d["fields"]), "customCount": sum(1 for f in d["fields"] if f["custom"])})
        for f in d["fields"]:
            cf = cfs.get((durable, f["name"])) or cfs.get((o, f["name"]))
            fd = fds.get((o, f["name"]), {})
            t = f["type"]
            tdetail = t
            if t == "reference":
                tdetail = "Lookup(" + ", ".join(f.get("referenceTo") or []) + ")"
            elif t == "picklist":
                tdetail = "Picklist" + (" (restricted)" if f.get("restrictedPicklist") else "")
            elif t == "multipicklist":
                tdetail = "Multi-select picklist"
            elif t in ("string", "textarea", "email", "phone", "url"):
                tdetail = {"string": "Text", "textarea": "Long text" if f.get("length", 0) > 255 else "Text area", "email": "Email", "phone": "Phone", "url": "URL"}[t] + f"({f.get('length')})"
            elif t in ("double", "currency", "percent", "int"):
                tdetail = {"double": "Number", "currency": "Currency", "percent": "Percent", "int": "Number"}[t] + f"({f.get('precision', 0) - f.get('scale', 0)}, {f.get('scale', 0)})" if t != "int" else f"Number({f.get('digits')}, 0)"
            elif t == "boolean":
                tdetail = "Checkbox"
            elif t == "datetime":
                tdetail = "Date/Time"
            elif t == "date":
                tdetail = "Date"
            elif t == "id":
                tdetail = "Id"
            if f.get("calculated") and f.get("calculatedFormula"):
                tdetail = "Formula (" + tdetail + ")"
            elif f.get("autoNumber"):
                tdetail = "Auto number"
            setup = (f"{inst}/lightning/setup/ObjectManager/{o}/FieldsAndRelationships/{cf['Id'][:15] if cf else f['name']}/view") if inst else ""
            fields.append(OrderedDict(
                key=key(o, f["name"]), object=o, apiName=f["name"], label=f["label"], type=t, typeDetail=tdetail, custom=f["custom"],
                length=f.get("length"), precision=f.get("precision"), scale=f.get("scale"),
                required=(not f.get("nillable") and f.get("createable") and not f.get("defaultedOnCreate")), unique=f.get("unique"), externalId=f.get("externalId"),
                picklistValues=[{"value": p["value"], "label": p["label"], "active": p["active"]} for p in (f.get("picklistValues") or [])],
                formula=f.get("calculatedFormula"), defaultValue=f.get("defaultValue") if not isinstance(f.get("defaultValue"), dict) else None,
                description=(cf or {}).get("Description") or fd.get("Description") or "", helpText=f.get("inlineHelpText") or (cf or {}).get("InlineHelpText") or "",
                referenceTo=f.get("referenceTo") or [], relationshipName=f.get("relationshipName"),
                createdDate=(cf or {}).get("CreatedDate"), createdBy=((cf or {}).get("CreatedBy") or {}).get("Name"),
                lastModifiedDate=(cf or {}).get("LastModifiedDate") or fd.get("LastModifiedDate"), lastModifiedBy=((cf or {}).get("LastModifiedBy") or fd.get("LastModifiedBy") or {}).get("Name") if (cf or fd) else None,
                historyTracked=fd.get("IsFieldHistoryTracked"), businessStatus=fd.get("BusinessStatus"), businessOwner=(fd.get("BusinessOwner") or {}).get("Name") if fd.get("BusinessOwner") else None,
                securityClassification=fd.get("SecurityClassification"), complianceGroup=fd.get("ComplianceGroup"),
                namespace=(cf or {}).get("NamespacePrefix"), setupUrl=setup, updateable=f.get("updateable"), createable=f.get("createable"),
                sfmc={"syncedDE": None, "queries": [], "journeys": []}, dc={"stream": None, "dloField": None, "dmoFields": [], "calculatedInsights": [], "segments": [], "identityResolution": [], "dataGraphs": [], "dataActions": [], "activations": []},
            ))
    return fields, objects, inst

# ---------------------------------------------------------------- 2. Marketing Cloud
AMP_FUNCS = {"v", "iif", "if", "then", "else", "elseif", "endif", "set", "var", "and", "or", "not", "empty", "propercase", "uppercase", "lowercase",
             "concat", "length", "substring", "replace", "trim", "now", "formatdate", "format", "formatnumber", "redirectto", "cloudpagesurl",
             "contentblockbyid", "contentblockbyname", "contentblockbykey", "beginimpressionregion", "endimpressionregion", "lookup", "lookuprows",
             "lookuprowscs", "lookuporderedrows", "row", "rowcount", "field", "attributevalue", "treatascontent", "raiseerror", "add", "subtract",
             "multiply", "divide", "mod", "datediff", "dateadd", "datepart", "systemdatetodate", "guid", "random", "urlencode", "base64encode",
             "base64decode", "md5", "sha256", "httpget", "output", "outputline", "indexof", "isnull", "isnullorempty", "true", "false", "null",
             "for", "next", "do", "to", "downto", "stringtodate", "stringtohex", "char", "requestparameter", "queryparameter", "insertde", "updatede",
             "upsertde", "deletede", "datasourcename", "getsendtime", "localdatetoystemdate", "localdatetosystemdate", "getportfolioitem", "viewemailurl",
             "beginimpressionregion", "buildrowsetfromstring", "domain", "wat", "watp", "sha1", "sha512", "nl2br", "tostring", "regexmatch", "microsite",
             "microsurl", "redirect", "sendlog", "comment"}

def mc_build(fields):
    jd = load("mc_journeys")
    eventdefs = load("mc_eventdefs")
    autos = load("mc_automations")
    queries = load("mc_queries")
    de_list = load("mc_de_list")
    de_fields = load("mc_de_fields")
    legacy = load("mc_legacy_map")
    by_key = {f["key"]: f for f in fields}
    by_obj = defaultdict(dict)
    for f in fields:
        by_obj[f["object"]][f["apiName"].lower()] = f

    # synced DE per object
    synced = {}  # object -> {name, key, cols:set}
    for v in de_fields.values():
        n = v.get("name") or ""
        for o in OBJECTS:
            if norm(n) == norm(o + "_Salesforce"):
                cols = {c["Name"] for c in v["fields"]}
                synced[o] = {"name": n, "key": v["key"], "cols": cols, "colsLower": {c.lower(): c for c in cols}, "fieldCount": len(cols), "modified": v.get("modified")}
    for o, s in synced.items():
        for f in by_obj[o].values():
            if f["apiName"] in s["cols"]:
                f["sfmc"]["syncedDE"] = s["name"]
    de_name_by_key = {v["key"].upper(): v["name"] for v in de_fields.values()}
    de_by_objid = {d.get("ObjectID"): d for d in de_list}
    de_key_by_name = {norm(d.get("Name")): d.get("CustomerKey") for d in de_list}
    de_name_by_key_all = {d.get("CustomerKey", "").upper(): d.get("Name") for d in de_list}
    synced_by_norm = {norm(s["name"]): o for o, s in synced.items()}

    # automations per query
    q_autos = defaultdict(list)
    for a in autos.values():
        for st in a.get("steps", []):
            for act in st.get("activities", []):
                if act.get("objectTypeId") == 300 and act.get("activityObjectId"):
                    q_autos[act["activityObjectId"]].append({"id": a["id"], "name": a.get("name"), "status": a.get("status"), "schedule": (a.get("schedule") or {}).get("scheduleStatus")})

    # parse queries: tables/aliases, field uses
    TABLE_RE = re.compile(r"(?i)\b(?:from|join)\s+(?:ent\.)?\[?([A-Za-z0-9_\- ]+?)\]?(?:\s+(?:as\s+)?(?!on\b|where\b|left\b|right\b|inner\b|join\b|group\b|order\b|union\b|cross\b|outer\b|full\b)([A-Za-z_][A-Za-z0-9_]*))?(?=\s|,|\)|$)")
    query_info = {}
    for qid, q in queries.items():
        sql = q.get("queryText") or ""
        tables = {}
        for m in TABLE_RE.finditer(sql):
            t, alias = m.group(1).strip(), m.group(2)
            tables[norm(t)] = norm(alias) if alias else None
        synced_used = {o: s for o, s in synced.items() if norm(s["name"]) in tables}
        uses = []  # (fieldKey, how)
        sql_l = sql.lower()
        for o, s in synced_used.items():
            alias = tables[norm(s["name"])]
            for col_l, col in s["colsLower"].items():
                f = by_obj[o].get(col_l)
                if not f:
                    continue
                pat = re.compile(r"(?<![\w\.\[])" + re.escape(col_l) + r"(?![\w\]])")
                qpat = re.compile(r"(?:" + "|".join(re.escape(x) for x in [norm(s["name"]), alias or "~~"]) + r")\.\[?" + re.escape(col_l) + r"\]?(?![\w])")
                qualified = bool(qpat.search(sql_l))
                unqualified = bool(pat.search(sql_l))
                other_alias_qualified = False
                if not qualified and unqualified:
                    # is every occurrence qualified with another table's alias? then skip
                    occ = [mm.start() for mm in re.finditer(r"(?<![\w])\[?" + re.escape(col_l) + r"\]?(?![\w])", sql_l)]
                    mine = 0
                    for pos in occ:
                        before = sql_l[max(0, pos - 40):pos]
                        mm = re.search(r"([A-Za-z0-9_\.\]\[]+)\.\[?$", before)
                        if mm:
                            q_alias = mm.group(1).strip("[]").lower().replace("ent.", "")
                            if q_alias in (alias, norm(s["name"])):
                                mine += 1
                        else:
                            mine += 1
                    other_alias_qualified = mine == 0
                if qualified or (unqualified and not other_alias_qualified):
                    uses.append(f["key"])
        sources = [t for t in tables]
        query_info[qid] = {"id": qid, "name": q.get("name"), "key": q.get("key"), "targetDE": q.get("targetName"), "targetKey": (q.get("targetKey") or "").upper(),
                           "targetUpdateType": q.get("targetUpdateTypeName"), "sources": sources, "syncedSources": [synced[o]["name"] for o in synced_used],
                           "automations": q_autos.get(qid, []), "fields": sorted(set(uses)), "sql": sql, "modified": q.get("modifiedDate")}
    queries_by_target = defaultdict(list)
    for qi in query_info.values():
        queries_by_target[qi["targetKey"]].append(qi["id"])
        if qi["targetDE"]:
            queries_by_target["NAME:" + norm(qi["targetDE"])].append(qi["id"])

    def feeders(de_key, de_name, depth=0, seen=None):
        """Queries that fill a DE, following staging DEs upstream (max depth 3)."""
        seen = seen or set()
        out = []
        ids = list(queries_by_target.get((de_key or "").upper(), [])) + list(queries_by_target.get("NAME:" + norm(de_name), []))
        for qid in ids:
            if qid in seen:
                continue
            seen.add(qid)
            qi = query_info[qid]
            out.append({"id": qid, "depth": depth})
            if depth < 3:
                for src in qi["sources"]:
                    if src in synced_by_norm or src.startswith("_") or src in ("ent._subscribers",):
                        continue
                    k = de_key_by_name.get(src)
                    out += feeders(k, src, depth + 1, seen)
        return out

    # Data extension column -> field keys (only through synced DEs, by exact name)
    def resolve_col(col, chain_objs):
        col_l = norm(col)
        hits = []
        for o in chain_objs:
            f = by_obj[o].get(col_l)
            if f and f["apiName"] in synced.get(o, {}).get("cols", set()):
                hits.append((f["key"], "entry data"))
        if hits:
            return hits
        # fallback: unique custom field name across objects that is synced
        cands = [by_obj[o][col_l]["key"] for o in OBJECTS if col_l in by_obj[o] and col_l.endswith("__c") and by_obj[o][col_l]["apiName"] in synced.get(o, {}).get("cols", set())]
        return [(c, "name match") for c in cands] if len(cands) == 1 else []

    def tokens_from_text(text):
        """Return (explicit (DE, col) lookups, bare identifiers) referenced in AMPscript / personalization strings."""
        explicit, bare = set(), set()
        if not text:
            return explicit, bare
        for m in re.finditer(r'(?i)Lookup\w*\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"', text):
            explicit.add((m.group(1), m.group(2)))
        for m in re.finditer(r'(?i)(?:AttributeValue|Field)\s*\(\s*(?:@\w+\s*,\s*)?"([^"]+)"', text):
            bare.add(m.group(1))
        for m in re.finditer(r"%%\s*(?!=|\[)([A-Za-z_][A-Za-z0-9_]*)\s*%%", text):
            bare.add(m.group(1))
        for blk in re.findall(r"%%=(.*?)=%%", text, re.S) + re.findall(r"%%\[(.*?)\]%%", text, re.S):
            for m in re.finditer(r"\[([A-Za-z_][A-Za-z0-9_ ]*)\]", blk):
                bare.add(m.group(1))
            for m in IDENT.finditer(re.sub(r'"[^"]*"', '""', blk)):
                w = m.group(0)
                if w.lower() in AMP_FUNCS or blk[max(0, m.start() - 1):m.start()] == "@":
                    continue
                bare.add(w)
        return explicit, bare

    def asset_texts(asset):
        out = []
        def walk(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, str) and (k in ("content", "display:title", "display:message", "display:subtitle", "openBehavior:url", "message") or "%%" in v):
                        out.append(v)
                    else:
                        walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(asset.get("views", {}))
        return out

    def parse_criteria_xml(x):
        cols = []
        for m in re.finditer(r'Key="([^"]+)"', x or ""):
            k = m.group(1)
            parts = k.split(".")
            cols.append((parts[0], ".".join(parts[1:-1]), parts[-1]))  # (root, middle, column)
        return cols

    journeys_out = []
    for jid, d in jd.items():
        trig = (d.get("triggers") or [{}])[0]
        ekey = trig.get("metaData", {}).get("eventDefinitionKey")
        ev = eventdefs.get(ekey, {})
        entry_de = de_by_objid.get(ev.get("dataExtensionId")) or {}
        entry_de_name = ev.get("dataExtensionName") or entry_de.get("Name")
        entry_de_key = entry_de.get("CustomerKey")
        chain = feeders(entry_de_key, entry_de_name) if entry_de_key or entry_de_name else []
        chain_qs = [query_info[c["id"]] for c in chain]
        chain_objs = sorted({o for qi in chain_qs for o in synced if synced[o]["name"] in qi["syncedSources"]})
        items = []   # {kind, name, activityKey, fields:[{key, how}], columns:[unresolved]}
        def add_item(kind, name, akey, hits, cols_unresolved=None, detail=None):
            items.append({"kind": kind, "name": name, "activityKey": akey, "fields": [{"key": k, "how": h} for k, h in sorted(set(hits))],
                          "unresolvedColumns": sorted(set(cols_unresolved or [])), "detail": detail})
        # entry
        entry_fields = []
        for qi in chain_qs:
            add_item("query", qi["name"], None, [(k, "query") for k in qi["fields"]], detail={"automations": [a["name"] for a in qi["automations"]], "targetDE": qi["targetDE"], "depth": [c["depth"] for c in chain if c["id"] == qi["id"]][0]})
        if trig.get("type") == "SalesforceObjectTriggerV2" or ev.get("type") == "SalesforceObjectTriggerV2":
            ca = ev.get("configurationArguments", {})
            obj = ca.get("objectAPIName")
            hits, cols = [], []
            try:
                for ob in json.loads(ca.get("eventDataConfig") or "{}").get("objects", []):
                    if ob.get("dePrefix", "").rstrip(":") == obj:
                        for fn in ob.get("fields", []):
                            f = by_obj.get(obj, {}).get(norm(fn))
                            (hits.append((f["key"], "event data")) if f else cols.append(fn))
            except Exception:
                pass
            try:
                for c in json.loads(ca.get("primaryObjectFilterCriteria") or "{}").get("conditions", []):
                    f = by_obj.get(obj, {}).get(norm(c.get("fieldName")))
                    (hits.append((f["key"], "entry filter")) if f else cols.append(c.get("fieldName")))
            except Exception:
                pass
            add_item("entry", f"Salesforce data event: {obj} {ca.get('salesforceTriggerCriteria', '')}".strip(), trig.get("key"), hits, cols, detail={"filter": ca.get("primaryObjectFilterSummary")})
        # entry criteria XML (trigger criteria / event filter)
        for xml, label in [(trig.get("configurationArguments", {}).get("criteria"), "Entry filter"), (ev.get("filterDefinitionTemplate"), "Event filter")]:
            if xml:
                hits, cols = [], []
                for root, mid, col in parse_criteria_xml(xml):
                    r = resolve_col(col, chain_objs) if root == "Event" else ([(by_obj[synced_by_norm[norm(root)]][norm(col)]["key"], "synced DE")] if norm(root) in synced_by_norm and norm(col) in by_obj[synced_by_norm[norm(root)]] else [])
                    (hits.extend(r) if r else cols.append(col))
                if hits or cols:
                    add_item("entry", label, trig.get("key"), hits, cols)
        # activities
        for a in d.get("activities", []):
            t = a.get("type")
            ca = a.get("configurationArguments") or {}
            if t == "MULTICRITERIADECISION":
                hits, cols, labels = [], [], []
                for oc in a.get("outcomes", []):
                    md = oc.get("metaData", {})
                    xml = (ca.get("criteria") or {}).get(oc.get("key"))
                    if md.get("criteriaDescription"):
                        labels.append(f"{md.get('label')}: {md.get('criteriaDescription')}")
                    for root, mid, col in parse_criteria_xml(xml or ""):
                        if root == "Event":
                            r = resolve_col(col, chain_objs)
                        elif norm(root) in synced_by_norm:
                            o = synced_by_norm[norm(root)]
                            f = by_obj[o].get(norm(col))
                            r = [(f["key"], "synced DE lookup")] if f else []
                        else:
                            r = []
                        (hits.extend(r) if r else cols.append(f"{root}.{col}" if root != "Event" else col))
                dname = a.get("name") or ("Decision split: " + "; ".join(l.split(": ", 1)[0] for l in labels[:3]) + (" ..." if len(labels) > 3 else "") if labels else "Decision split")
                add_item("decision", dname, a.get("key"), hits, cols, detail={"paths": labels[:24]})
            elif t == "EMAILV2":
                ts = ca.get("triggeredSend") or {}
                aid = legacy.get(str(ts.get("emailId")))
                texts = [ts.get("emailSubject") or "", ts.get("preHeader") or ""]
                asset = None
                if aid and os.path.exists(os.path.join(RAW, "mc_assets", f"{aid}.json")):
                    asset = json.load(open(os.path.join(RAW, "mc_assets", f"{aid}.json")))
                    texts += asset_texts(asset)
                hits, cols = [], []
                for txt in texts:
                    ex, bare = tokens_from_text(txt)
                    for de, col in ex:
                        if norm(de) in synced_by_norm:
                            f = by_obj[synced_by_norm[norm(de)]].get(norm(col))
                            (hits.append((f["key"], f"Lookup {de}")) if f else cols.append(f"{de}.{col}"))
                    for w in bare:
                        r = resolve_col(w, chain_objs)
                        (hits.extend(r) if r else None)
                add_item("email", a.get("name") or ts.get("name") or (asset or {}).get("name") or "Email", a.get("key"), hits, cols,
                         detail={"subject": ts.get("emailSubject"), "assetName": (asset or {}).get("name"), "assetId": aid, "emailId": ts.get("emailId")})
            elif t in ("PUSHNOTIFICATIONACTIVITY", "SMSSYNC"):
                aid = ca.get("assetId")
                texts = []
                asset = None
                if aid and os.path.exists(os.path.join(RAW, "mc_assets", f"{aid}.json")):
                    asset = json.load(open(os.path.join(RAW, "mc_assets", f"{aid}.json")))
                    texts = asset_texts(asset)
                hits, cols = [], []
                for txt in texts:
                    ex, bare = tokens_from_text(txt)
                    for de, col in ex:
                        if norm(de) in synced_by_norm:
                            f = by_obj[synced_by_norm[norm(de)]].get(norm(col))
                            (hits.append((f["key"], f"Lookup {de}")) if f else cols.append(f"{de}.{col}"))
                    for w in bare:
                        r = resolve_col(w, chain_objs)
                        (hits.extend(r) if r else None)
                msg = ""
                if asset:
                    v = asset.get("views", {})
                    cb = ((v.get("push") or v.get("sms") or {}).get("meta") or {}).get("options", {}).get("customBlockData", {})
                    msg = cb.get("display:message") or ""
                add_item("push" if t == "PUSHNOTIFICATIONACTIVITY" else "sms", a.get("name") or (asset or {}).get("name") or t, a.get("key"), hits, cols,
                         detail={"assetName": (asset or {}).get("name"), "assetId": aid, "message": re.sub(r"%%\[.*?\]%%", "", msg, flags=re.S).strip()[:300]})
            elif t == "SALESCLOUDACTIVITY":
                hits, cols = [], []
                for ob in (a.get("arguments", {}).get("objectMap", {}) or {}).get("objects", []):
                    obj = ob.get("type")
                    for fl in ob.get("fields", []):
                        f = by_obj.get(obj, {}).get(norm(fl.get("FieldName")))
                        (hits.append((f["key"], f"writes ({ob.get('action')})")) if f else cols.append(f"{obj}.{fl.get('FieldName')}"))
                        for m in re.finditer(r'\{\{Event\."[^"]+"\."([^"]+)"\}\}', fl.get("FieldValue") or ""):
                            hits.extend(resolve_col(m.group(1), chain_objs))
                    for stp in (ob.get("lookup") or {}).get("steps", []):
                        for c in stp.get("criteria", []):
                            f = by_obj.get(obj, {}).get(norm(c.get("FieldName")))
                            (hits.append((f["key"], "lookup key")) if f else None)
                add_item("salescloud", a.get("name") or "Sales Cloud update", a.get("key"), hits, cols)
            elif t == "UPDATECONTACTDATA":
                hits, cols = [], []
                for u in ((a.get("arguments", {}).get("activityData") or {}).get("updateContactFields") or []):
                    de = de_by_objid.get(u.get("dataExtensionId")) or {}
                    dename = de.get("Name") or u.get("dataExtensionId")
                    fname = None
                    for v in de_fields.values():
                        if v.get("objectId") == u.get("dataExtensionId"):
                            for c in v["fields"]:
                                if c.get("ObjectID") == u.get("field"):
                                    fname = c["Name"]
                    if norm(dename) in synced_by_norm and fname:
                        f = by_obj[synced_by_norm[norm(dename)]].get(norm(fname))
                        (hits.append((f["key"], "updates DE column")) if f else None)
                    else:
                        cols.append(f"{dename}.{fname or u.get('field')}")
                add_item("contactupdate", a.get("name") or "Update contact data", a.get("key"), hits, cols)
        jo = {"id": jid, "name": d.get("name"), "status": d.get("status"), "version": d.get("version"), "modifiedDate": d.get("modifiedDate"),
              "createdDate": d.get("createdDate"), "description": d.get("description"),
              "entry": {"type": ev.get("type") or trig.get("type"), "dataExtension": entry_de_name, "eventDefinition": ev.get("name"),
                        "automations": sorted({a["name"] for qi in chain_qs for a in qi["automations"]})},
              "activityCount": len(d.get("activities", [])), "items": items,
              "fieldKeys": sorted({f["key"] for it in items for f in it["fields"]})}
        journeys_out.append(jo)
    journeys_out.sort(key=lambda j: j["name"].lower())

    # attach to fields
    for jo in journeys_out:
        per_field = defaultdict(list)
        for it in jo["items"]:
            for f in it["fields"]:
                rec = {"kind": it["kind"], "name": it["name"], "how": f["how"]}
                if rec not in per_field[f["key"]]:
                    per_field[f["key"]].append(rec)
        for k, its in per_field.items():
            by_key[k]["sfmc"]["journeys"].append({"id": jo["id"], "name": jo["name"], "status": jo["status"], "items": its})
    for qi in query_info.values():
        for k in qi["fields"]:
            by_key[k]["sfmc"]["queries"].append({"id": qi["id"], "name": qi["name"], "targetDE": qi["targetDE"], "automations": [a["name"] for a in qi["automations"]]})
    queries_out = [{k: v for k, v in qi.items() if k != "sql"} | {"sqlPreview": (qi["sql"] or "")[:4000]} for qi in query_info.values() if qi["fields"]]
    queries_out.sort(key=lambda q: (q["name"] or "").lower())
    return journeys_out, queries_out, synced, load("mc_journeys_list")

# ---------------------------------------------------------------- 3. Data Cloud
def dc_build(fields):
    streams = load("dc_data_streams")
    dlos = {m["name"]: m for m in load("dc_meta_DataLakeObject")}
    dmos = {m["name"]: m for m in load("dc_meta_DataModelObject")}
    kit = load("dc_kit_fieldmaps")
    cis = load("dc_calculated_insights")
    ci_meta = {m["name"]: m for m in load("dc_meta_CalculatedInsight")}
    segs = load("dc_segments")
    acts = load("dc_activations")
    graphs = load("dc_data_graphs")
    dactions = load("dc_data_actions")
    transforms = load("dc_data_transforms")
    idres = load("dc_identity_resolutions")
    sfrefs = load("sf_dc_refs")
    by_key = {f["key"]: f for f in fields}
    by_obj = defaultdict(dict)
    for f in fields:
        by_obj[f["object"]][f["apiName"].lower()] = f

    # stream per object
    obj_stream = {}
    for st in streams:
        cd = (st.get("connectorInfo") or {}).get("connectorDetails") or {}
        if (st.get("connectorInfo") or {}).get("connectorType") == "SalesforceDotCom" and cd.get("sourceObject") in OBJECTS and cd["sourceObject"] not in obj_stream:
            obj_stream[cd["sourceObject"]] = st
    # kit maps: object -> {sfField: [DMO.field]}
    kit_map = defaultdict(lambda: defaultdict(list))
    kit_dmos = defaultdict(set)
    for m in kit:
        src, tgt = m["source"], m["target"]
        so, sf_ = src.split(".", 1)
        so = re.sub(r"^\w+?__", "", so)
        so = re.sub(r"_00D\w+$", "", so)
        so = re.sub(r"\d+$", "", so)
        sf_ = re.sub(r"^\w+?__", "", sf_)
        sf_ = re.sub(r"__c$", "", sf_)
        if so in OBJECTS:
            kit_map[so][sf_.lower()].append(tgt)
            kit_dmos[so].add(tgt.split(".")[0])
    # candidate DMOs per object: kit + overrides + auto by custom-name overlap
    dmo_fields = {n: {f["name"] for f in m["fields"]} for n, m in dmos.items()}
    obj_dmos = {}
    for o in OBJECTS:
        st = obj_stream.get(o)
        cands = set(kit_dmos[o]) | set(DMO_OVERRIDES.get(o, []))
        if st:
            sfn = {m["sourceFieldName"] for m in st["mappings"] if m.get("sourceFieldName", "").endswith("__c")}
            dln = {m["targetFieldName"] + "__c" for m in st["mappings"] if m.get("sourceFieldName", "").endswith("__c")}
            for n, names in dmo_fields.items():
                if len(names & sfn) + len(names & dln) >= AUTO_DMO_MIN_MATCHES:
                    cands.add(n)
        obj_dmos[o] = sorted(c for c in cands if c in dmos)
    # DMO.field -> [(fieldKey, method)]
    dmo_to_sf = defaultdict(list)
    for o in OBJECTS:
        st = obj_stream.get(o)
        if not st:
            continue
        dlo_name = st["dataLakeObjectInfo"]["name"]
        for m in st["mappings"]:
            sfn = m.get("sourceFieldName")
            if not sfn:
                continue
            f = by_obj[o].get(sfn.lower())
            if not f:
                continue
            dlo_field = m["targetFieldName"] + "__c"
            f["dc"]["stream"] = st["name"]
            f["dc"]["dloField"] = f"{dlo_name}.{dlo_field}"
            targets = []
            for t in kit_map[o].get(sfn.lower(), []):
                targets.append((t, "kit mapping"))
            for dn in obj_dmos[o]:
                names = dmo_fields[dn]
                for cand in (sfn, dlo_field):
                    if cand in names and f"{dn}.{cand}" not in [t for t, _ in targets]:
                        targets.append((f"{dn}.{cand}", "name match"))
                if sfn.endswith("__c") and not any(t.startswith(dn + ".") for t, _ in targets):
                    nz = normalize_name(sfn)
                    for cand in names:
                        if not cand.startswith("ssot__") and normalize_name(cand) == nz:
                            targets.append((f"{dn}.{cand}", "name match (normalized)"))
            seen_t = set()
            for t, how in targets:
                if t in seen_t:
                    continue
                seen_t.add(t)
                f["dc"]["dmoFields"].append({"dmoField": t, "method": how})
                dmo_to_sf[t].append((f["key"], how))
    # Data Cloud objects referenced
    REF = re.compile(r"\b([A-Za-z0-9_]+__(?:dlm|cio))\.([A-Za-z0-9_]+__c)\b")

    def refs_in_json(o, acc):
        if isinstance(o, dict):
            oa, fa = o.get("objectApiName"), o.get("fieldApiName")
            if oa and fa:
                acc.add(f"{oa}.{fa}")
            for v in o.values():
                refs_in_json(v, acc)
        elif isinstance(o, list):
            for v in o:
                refs_in_json(v, acc)

    def attach(refs, section, item):
        hit_keys = set()
        for r in refs:
            for k, how in dmo_to_sf.get(r, []):
                hit_keys.add(k)
        for k in hit_keys:
            by_key[k]["dc"][section].append(item)
        return sorted(hit_keys)

    # CIs
    ci_out = []
    for c in cis:
        expr = html.unescape(c.get("expression") or "")
        refs = sorted({f"{a}.{b}" for a, b in REF.findall(expr)})
        objs = sorted({r.split(".")[0] for r in refs})
        ci_refs = sorted({x for x in objs if x.endswith("__cio") and x != c["apiName"]})
        item = {"apiName": c["apiName"], "displayName": c.get("displayName")}
        sfk = attach(refs, "calculatedInsights", item)
        meta = ci_meta.get(c["apiName"], {})
        ci_out.append({"apiName": c["apiName"], "displayName": c.get("displayName"), "description": c.get("description") or "", "status": c.get("calculatedInsightStatus"),
                       "definitionStatus": c.get("definitionStatus"), "definitionType": c.get("definitionType"), "creationType": c.get("creationType"),
                       "isEnabled": c.get("isEnabled"), "lastRun": c.get("lastRunDateTime"), "lastRunStatus": c.get("lastRunStatus"), "schedule": c.get("publishScheduleInterval"),
                       "expression": expr, "dimensions": [{"name": d.get("apiName"), "label": d.get("displayName"), "type": d.get("dataType"), "formula": d.get("formula")} for d in c.get("dimensions", [])],
                       "measures": [{"name": d.get("apiName"), "label": d.get("displayName"), "type": d.get("dataType"), "formula": d.get("formula")} for d in c.get("measures", [])],
                       "sourceRefs": refs, "sourceObjects": objs, "referencesCIs": ci_refs, "salesforceFields": sfk,
                       "relationships": meta.get("relationships", []), "partitionBy": meta.get("partitionBy"),
                       "usedIn": {"segments": [], "calculatedInsights": [], "dataGraphs": [], "dataActions": [], "activations": [], "salesforce": []}})
    ci_by = {c["apiName"]: c for c in ci_out}
    for c in ci_out:
        for r in c["referencesCIs"]:
            if r in ci_by:
                ci_by[r]["usedIn"]["calculatedInsights"].append({"apiName": c["apiName"], "displayName": c["displayName"]})
    # segments
    seg_out = []
    for s in segs:
        inc, exc = html_unescape_json(s.get("includeCriteria")), html_unescape_json(s.get("excludeCriteria"))
        refs = set()
        refs_in_json(inc, refs); refs_in_json(exc, refs)
        refs = sorted(refs)
        objs = sorted({r.split(".")[0] for r in refs} | ({s.get("segmentOnApiName")} if s.get("segmentOnApiName") else set()))
        item = {"apiName": s.get("apiName"), "displayName": s.get("displayName")}
        sfk = attach(refs, "segments", item)
        used_cis = sorted({o for o in objs if o.endswith("__cio")})
        for cn in used_cis:
            if cn in ci_by:
                ci_by[cn]["usedIn"]["segments"].append(item)
        seg_out.append({"apiName": s.get("apiName"), "displayName": s.get("displayName"), "status": s.get("segmentStatus"), "segmentOn": s.get("segmentOnApiName"),
                        "publishInterval": s.get("publishInterval"), "publishStatus": s.get("publishStatus"), "lastPublish": s.get("lastPublishDateTime") or s.get("nextPublishDateTime"),
                        "refs": refs, "calculatedInsights": used_cis, "salesforceFields": sfk, "activations": []})
    seg_by = {s["apiName"]: s for s in seg_out}
    # activations
    act_out = []
    for a in acts:
        seg = seg_by.get(a.get("segmentApiName")) or next((s for s in seg_out if s["displayName"] == a.get("segmentApiName") or s["apiName"] == a.get("segmentId")), None)
        schema = html_unescape_json(a.get("activationRecordSchema") or "")
        attrs = sorted(k for k in (schema.keys() if isinstance(schema, dict) else []) if k != "type")
        refs = set()
        if seg and seg.get("segmentOn"):
            names = dmo_fields.get(seg["segmentOn"], set())
            for at in attrs:
                for cand in (at + "__c", "ssot__" + at + "__c"):
                    if cand in names:
                        refs.add(f"{seg['segmentOn']}.{cand}")
        item = {"name": a.get("name"), "target": a.get("activationTargetName"), "segment": a.get("segmentApiName")}
        sfk = attach(sorted(refs), "activations", item)
        if seg:
            seg["activations"].append(item)
            for cn in seg["calculatedInsights"]:
                if cn in ci_by:
                    ci_by[cn]["usedIn"]["activations"].append(item)
        act_out.append({"id": a.get("id"), "name": a.get("name"), "target": a.get("activationTargetName"), "segment": a.get("segmentApiName"), "status": a.get("status"),
                        "refreshType": a.get("refreshType"), "lastPublish": a.get("lastPublishDate"), "lastPublishStatus": a.get("lastPublishStatus"), "attributes": attrs, "salesforceFields": sfk})
    # identity resolution
    for ir in idres:
        for mr in ir.get("matchRules", []):
            refs = sorted({f"{c.get('entityName')}.{c.get('fieldName')}" for c in mr.get("criteria", []) if c.get("entityName") and c.get("fieldName")})
            attach(refs, "identityResolution", {"ruleset": ir.get("label"), "rule": mr.get("label"), "type": "match rule"})
        for rr in ir.get("reconciliationRules", []):
            refs = sorted({f"{rr.get('entityName')}.{f.get('fieldName')}" for f in rr.get("fields", []) if f.get("fieldName")})
            attach(refs, "identityResolution", {"ruleset": ir.get("label"), "rule": rr.get("ruleType"), "type": "reconciliation", "object": rr.get("entityName")})
    # data graphs
    graph_out = []
    for g in graphs:
        objs = set()
        def walk(node):
            dn = node.get("developerName")
            if dn:
                objs.add(dn)
                for f in node.get("fields", []):
                    if f.get("developerName"):
                        objs.add(f"{dn}.{f['developerName']}")
            for r in node.get("relatedObjects", []) or []:
                walk(r)
        walk(g.get("dgObject", {}))
        refs = sorted(x for x in objs if "." in x)
        item = {"name": g.get("developerName"), "status": g.get("status")}
        sfk = attach(refs, "dataGraphs", item)
        for cn in sorted(x for x in objs if x.endswith("__cio")):
            if cn in ci_by:
                ci_by[cn]["usedIn"]["dataGraphs"].append(item)
        graph_out.append({"name": g.get("developerName"), "status": g.get("status"), "primaryObject": g.get("primaryObjectName"), "objects": sorted(x for x in objs if "." not in x), "salesforceFields": sfk})
    # data actions
    da_out = []
    for da in dactions:
        refs = sorted({f"{p.get('objectApiName')}.{p.get('fieldApiName')}" for p in da.get("dataActionProjectedFields", []) if p.get("objectApiName")})
        acc = set(); refs_in_json(da.get("actionConditions"), acc)
        refs = sorted(set(refs) | acc)
        item = {"name": da.get("dataActionName")}
        sfk = attach(refs, "dataActions", item)
        for cn in sorted({r.split(".")[0] for r in refs if r.split(".")[0].endswith("__cio")}):
            if cn in ci_by:
                ci_by[cn]["usedIn"]["dataActions"].append(item)
        da_out.append({"name": da.get("dataActionName"), "objects": sorted({r.split(".")[0] for r in refs}), "salesforceFields": sfk})
    for r in sfrefs:
        for cn in r["objects"]:
            if cn in ci_by:
                ci_by[cn]["usedIn"]["salesforce"].append({"type": r["type"], "name": r["name"]})
    streams_out = [{"object": o, "name": st["name"], "dlo": st["dataLakeObjectInfo"]["name"], "status": st.get("status"), "lastRefresh": st.get("lastRefreshDate"),
                    "lastRunStatus": st.get("lastRunStatus"), "totalRecords": st.get("totalRecords"), "mappedFields": sum(1 for m in st["mappings"] if m.get("sourceFieldName")),
                    "refresh": ((st.get("refreshConfig") or {}).get("frequency") or {}).get("frequencyType"), "dmos": obj_dmos[o]} for o, st in obj_stream.items()]
    tr_out = [{"name": t.get("name"), "label": t.get("label"), "type": t.get("type"), "status": t.get("status"), "lastRun": t.get("lastRunDate"), "lastRunStatus": t.get("lastRunStatus")} for t in transforms]
    return ci_out, seg_out, act_out, graph_out, da_out, streams_out, tr_out

# ---------------------------------------------------------------- 4. snapshots and changelog
def changelog(fields, cis, journeys, segs):
    snapdir = os.path.join(DATA, "snapshots")
    os.makedirs(snapdir, exist_ok=True)
    cur = {"date": TODAY, "fields": sorted(f["key"] for f in fields), "fieldLabels": {f["key"]: f["label"] for f in fields},
           "cis": sorted(c["apiName"] for c in cis), "journeys": sorted(j["name"] for j in journeys), "segments": sorted(s["apiName"] for s in segs)}
    prev_files = sorted(p for p in glob.glob(os.path.join(snapdir, "*.json")) if not p.endswith(TODAY + ".json"))
    logp = os.path.join(DATA, "changelog.json")
    log_entries = json.load(open(logp)) if os.path.exists(logp) else []
    entry = {"date": TODAY, "previous": None, "fieldsAdded": [], "fieldsRemoved": [], "cisAdded": [], "cisRemoved": [], "journeysAdded": [], "journeysRemoved": [], "segmentsAdded": [], "segmentsRemoved": []}
    if prev_files:
        prev = json.load(open(prev_files[-1]))
        entry["previous"] = prev["date"]
        for k, a, b in [("fields", "fieldsAdded", "fieldsRemoved"), ("cis", "cisAdded", "cisRemoved"), ("journeys", "journeysAdded", "journeysRemoved"), ("segments", "segmentsAdded", "segmentsRemoved")]:
            entry[a] = sorted(set(cur[k]) - set(prev.get(k, [])))
            entry[b] = sorted(set(prev.get(k, [])) - set(cur[k]))
        entry["fieldLabels"] = {k: cur["fieldLabels"].get(k) or prev.get("fieldLabels", {}).get(k) for k in entry["fieldsAdded"] + entry["fieldsRemoved"]}
    log_entries = [e for e in log_entries if e["date"] != TODAY] + [entry]
    log_entries.sort(key=lambda e: e["date"], reverse=True)
    json.dump(log_entries, open(logp, "w"), indent=1)
    json.dump(cur, open(os.path.join(snapdir, TODAY + ".json"), "w"))
    return log_entries

# ---------------------------------------------------------------- models
MODELS_DIR = os.path.join(ROOT, "models")

def _ts(v):
    """Parse a Salesforce datetime or date into an aware datetime (dates count as the end of that day, UTC)."""
    if not v: return None
    v = str(v)
    try:
        if len(v) == 10: return datetime.datetime.fromisoformat(v + "T23:59:59+00:00")
        v = re.sub(r"\.\d+", "", v).replace("Z", "+00:00")
        v = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", v)
        d = datetime.datetime.fromisoformat(v)
        return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None

def _age(hours):
    if hours is None: return "never"
    if hours < 1: return f"{max(int(hours * 60), 0)} min ago"
    if hours < 48: return f"{hours:.0f} h ago"
    return f"{hours / 24:.0f} days ago"

def models_build(fields, journeys):
    """Merge models/*.json (hand-maintained) with pipeline/raw/models_health.json (pulled) into the `models` section.
    Each check gets state ok / fail / unknown plus what was observed; a model's `running` is the worst of its checks."""
    try:
        health = load("models_health")
    except FileNotFoundError:
        health = {}
        log("models: no models_health.json (run pull_models.py); checks will show as not checked")
    now = _ts(health.get("checkedAt"))
    trs, cms, obs = health.get("transforms", {}), health.get("configuredModels", {}), health.get("checks", {})
    fkeys = {f["key"] for f in fields}
    jby = {j["name"]: j["id"] for j in journeys}
    out = []
    for p in sorted(glob.glob(os.path.join(MODELS_DIR, "*.json"))):
        m = json.load(open(p))
        for c in m.get("components", []):
            cm = cms.get(c.get("apiName") or "")
            c["status"] = cm["status"] if cm else None
            c["inputs"] = cm["inputs"] if cm else []
        for st in m.get("chain", []):
            t = trs.get(st.get("transform") or "")
            if t:
                runs = t.get("runs") or []
                day = [r for r in runs if now and _ts(r.get("start")) and (now - _ts(r["start"])).total_seconds() <= 86400]
                st["live"] = {"lastRun": t.get("lastRunDate"), "lastRunStatus": t.get("lastRunStatus"), "rows": runs[0].get("rows") if runs else None,
                              "runs24h": len(day), "failed24h": sum(1 for r in day if (r.get("status") or "").upper() not in ("SUCCESS", "SKIPPED_NO_CHANGES", "RUNNING", "IN_PROGRESS")),
                              "schedule": t.get("schedule")}
        for o in m.get("outputs", []):
            o["known"] = o["field"] in fkeys
        for c in m.get("consumers", []):
            c["journeyId"] = jby.get(c.get("name"))
        for c in m.get("checks", []):
            state, seen = "unknown", "not checked"
            if not now:
                pass
            elif c["type"] == "model_enabled":
                cm = cms.get(c["model"])
                state, seen = ("ok" if cm and cm["status"] == "Enabled" else "fail"), (cm["status"] if cm else "model not found")
            elif c["type"] == "transform_run":
                t = trs.get(c["transform"]) or {}
                last = _ts(t.get("lastRunDate"))
                hrs = (now - last).total_seconds() / 3600 if last else None
                good = (t.get("lastRunStatus") or "").upper() in ("SUCCESS", "SKIPPED_NO_CHANGES")
                state = "ok" if hrs is not None and hrs <= c["maxAgeHours"] and good else "fail"
                seen = f"last run {_age(hrs)}, {t.get('lastRunStatus') or t.get('error') or 'no status'}"
            elif c["type"] == "soql_max":
                r = obs.get(m["id"] + ":" + c["id"]) or {}
                v = (r.get("record") or {}).get("m")
                last = _ts(v)
                hrs = max((now - last).total_seconds() / 3600, 0) if last else None
                if r.get("error"): seen = "query failed: " + r["error"][:120]
                else:
                    state = "ok" if hrs is not None and hrs <= c["maxAgeHours"] else "fail"
                    seen = f"latest {v}" if v else "no rows"
            elif c["type"] == "row_match":
                r = obs.get(m["id"] + ":" + c["id"]) or {}
                a, b2 = (r.get("a") or {}).get("totalSize"), (r.get("b") or {}).get("totalSize")
                if a is None or b2 is None: seen = "count failed"
                else:
                    gap = abs(a - b2) / a * 100 if a else 100
                    state = "ok" if gap <= c["tolerancePct"] else "fail"
                    seen = f"{a:,} rows in, {b2:,} scored ({gap:.1f}% apart)"
            c["state"], c["observed"] = state, seen
        states = [c["state"] for c in m.get("checks", [])]
        m["running"] = "fail" if "fail" in states else "unknown" if (not states or "unknown" in states) else "ok"
        m["checkedAt"] = health.get("checkedAt")
        for o in m.get("outputs", []):
            f = next((f for f in fields if f["key"] == o["field"]), None)
            if f is not None:
                f.setdefault("models", []).append({"id": m["id"], "name": m["name"], "note": o.get("note") or ""})
        out.append(m)
    out.sort(key=lambda m: m.get("order", 99))
    mine = {c.get("apiName") for m in out for c in m.get("components", [])}
    others = [o for o in health.get("otherModels", []) if o["apiName"] not in mine]
    others.sort(key=lambda o: (o["status"] != "Enabled", o["label"] or ""))
    return out, others

# ---------------------------------------------------------------- main
DEFS = os.path.join(ROOT, "definitions")

def apply_definitions(fields):
    """Overlay hand-written definitions from definitions/<Object>.json.
    Falls back to the Salesforce field description when the overlay has no entry."""
    missing = []
    for f in fields:
        path = os.path.join(DEFS, f["object"] + ".json")
        entry = None
        if os.path.exists(path):
            entry = (json.load(open(path)) if path not in apply_definitions.cache else apply_definitions.cache[path]) .get(f["apiName"])
            apply_definitions.cache[path] = apply_definitions.cache.get(path) or json.load(open(path))
        if entry and entry.get("definition"):
            f["definition"], f["definitionSource"], f["definitionConfidence"] = entry["definition"].strip(), "dictionary", entry.get("confidence")
        elif f.get("description"):
            f["definition"], f["definitionSource"], f["definitionConfidence"] = f["description"], "salesforce", None
        else:
            f["definition"], f["definitionSource"], f["definitionConfidence"] = "", None, None
            missing.append(f["key"])
    if missing:
        log("fields with no definition (add them to definitions/<Object>.json):", len(missing))
        for k in missing: log("  ", k)
    return missing
apply_definitions.cache = {}

def main():
    fields, objects, inst = build_fields()
    undefined = apply_definitions(fields)
    journeys, queries, synced, jlist = mc_build(fields)
    cis, segs, acts, graphs, dactions, streams, transforms = dc_build(fields)
    models, other_models = models_build(fields, journeys)
    for f in fields:
        f.setdefault("models", [])
        f["usage"] = {"sfmcJourneys": len(f["sfmc"]["journeys"]), "sfmcQueries": len(f["sfmc"]["queries"]),
                      "dc": len(f["dc"]["calculatedInsights"]) + len(f["dc"]["segments"]) + len(f["dc"]["identityResolution"]) + len(f["dc"]["dataGraphs"]) + len(f["dc"]["dataActions"]) + len(f["dc"]["activations"]),
                      "inSfmc": bool(f["sfmc"]["syncedDE"]), "inDataCloud": bool(f["dc"]["stream"])}
    for o in objects:
        fs = [f for f in fields if f["object"] == o["apiName"]]
        o["syncedDE"] = synced.get(o["apiName"], {}).get("name")
        o["stream"] = next((s["name"] for s in streams if s["object"] == o["apiName"]), None)
        o["dmos"] = next((s["dmos"] for s in streams if s["object"] == o["apiName"]), [])
        o["stats"] = {"inSfmc": sum(1 for f in fs if f["usage"]["inSfmc"]), "inDataCloud": sum(1 for f in fs if f["usage"]["inDataCloud"]),
                      "usedInJourneys": sum(1 for f in fs if f["usage"]["sfmcJourneys"]), "usedInQueries": sum(1 for f in fs if f["usage"]["sfmcQueries"]),
                      "usedInDataCloud": sum(1 for f in fs if f["usage"]["dc"]), "defined": sum(1 for f in fs if f["definition"]), "unused": sum(1 for f in fs if not (f["usage"]["sfmcJourneys"] or f["usage"]["sfmcQueries"] or f["usage"]["dc"]))}
    changes = changelog(fields, cis, journeys, segs)
    from collections import Counter
    jstat = Counter(j.get("status") for j in jlist)
    out = {"generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "org": {"instanceUrl": inst, "alias": os.environ.get("SF_ORG", "blueowl-prod")},
           "objects": objects, "fields": fields, "journeys": journeys, "queries": queries, "calculatedInsights": cis, "segments": segs, "activations": acts,
           "dataGraphs": graphs, "dataActions": dactions, "streams": streams, "transforms": transforms, "models": models, "otherModels": other_models, "changelog": changes,
           "summary": {"fields": len(fields), "undefinedFields": undefined, "journeysReported": len(journeys), "journeyStatuses": dict(jstat), "queriesWithFields": len(queries), "cis": len(cis), "segments": len(segs)}}
    os.makedirs(DATA, exist_ok=True)
    json.dump(out, open(os.path.join(DATA, "dictionary.json"), "w"), indent=0)
    idx = [{"t": "field", "k": f["key"], "o": f["object"], "n": f["apiName"], "l": f["label"], "ty": f["typeDetail"], "j": f["usage"]["sfmcJourneys"], "q": f["usage"]["sfmcQueries"], "d": f["usage"]["dc"]} for f in fields]
    idx += [{"t": "ci", "k": c["apiName"], "n": c["apiName"], "l": c["displayName"]} for c in cis]
    idx += [{"t": "journey", "k": j["id"], "n": j["name"], "l": j["status"]} for j in journeys]
    idx += [{"t": "model", "k": m["id"], "n": m["name"], "l": m["stage"] + " model"} for m in models]
    idx += [{"t": "segment", "k": s["apiName"], "n": s["apiName"], "l": s["displayName"]} for s in segs]
    json.dump(idx, open(os.path.join(DATA, "search-index.json"), "w"))
    log("fields", len(fields), "journeys", len(journeys), "queries", len(queries), "cis", len(cis), "segments", len(segs))
    log("size MB", round(os.path.getsize(os.path.join(DATA, "dictionary.json")) / 1e6, 2))


if __name__ == "__main__":
    main()
