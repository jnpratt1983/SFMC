"""Pull Data Cloud metadata: streams (+field mappings), DLOs, DMOs, calculated insights, segments, activations,
data graphs, data actions, transforms, identity resolution."""
from common import save, log
from sf_client import SF, API


def paged(sf, path, key, size=50, page_param="batchSize", off_param="offset"):
    out, off = [], 0
    while True:
        s, d = sf.get(path, **{page_param: size, off_param: off})
        items = (d.get(key) if isinstance(d, dict) else None) or []
        if s != 200:
            log("page fail", path, s, str(d)[:200])
            break
        out += items
        if len(items) < size:
            break
        off += size
    return out


def main():
    sf = SF()
    b = f"/services/data/{API}/ssot"
    for et in ["CalculatedInsight", "DataLakeObject", "DataModelObject"]:
        s, d = sf.get(f"{b}/metadata", entityType=et)
        save("dc_meta_" + et, d.get("metadata", []))

    cis, off = [], 0
    while True:
        s, d = sf.get(f"{b}/calculated-insights", batchSize=25, offset=off)
        items = d.get("calculatedInsights") or d.get("collection", {}).get("items") or []
        cis += items
        if len(items) < 25:
            break
        off += 25
    save("dc_calculated_insights", cis)

    segs = paged(sf, f"{b}/segments", "segments")
    details = {}
    for sg in segs:
        name = sg.get("apiName") or sg.get("id")
        s, d = sf.get(f"{b}/segments/{name}")
        if s == 200:
            details[name] = (d.get("segments") or [d])[0]
    save("dc_segments", list(details.values()) or segs)

    acts = paged(sf, f"{b}/activations", "activations")
    adet = []
    for a in acts:
        s, d = sf.get(f"{b}/activations/{a['id']}")
        adet.append({**a, **(d if s == 200 and isinstance(d, dict) else {})})
    save("dc_activations", adet)

    streams = paged(sf, f"{b}/data-streams", "dataStreams", page_param="limit")
    for st in streams:
        s, d = sf.get(f"{b}/data-streams/{st['name']}", includeMappings="true")
        st["mappings"] = d.get("mappings", []) if s == 200 else []
    save("dc_data_streams", streams)

    s, d = sf.get(f"{b}/data-graphs/metadata")
    save("dc_data_graphs", d.get("dataGraphMetadata", []) if s == 200 else [])
    das, off = [], 0
    while True:
        s, d = sf.get(f"{b}/data-actions", limit=50, offset=off)
        items = d.get("dataActions", []) if s == 200 else []
        das += items
        if len(items) < 50 or not d.get("nextPageUrl"):
            break
        off += 50
    save("dc_data_actions", das)
    save("dc_data_transforms", paged(sf, f"{b}/data-transforms", "dataTransforms", page_param="limit"))
    s, d = sf.get(f"{b}/identity-resolutions")
    save("dc_identity_resolutions", d.get("identityResolutions", []) if s == 200 else [])
    log("CIs", len(cis), "segments", len(details), "streams", len(streams), "activations", len(adet))


if __name__ == "__main__":
    main()
