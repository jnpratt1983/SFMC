"""Salesforce REST/Tooling client.

Auth order: SF_ACCESS_TOKEN + SF_INSTANCE_URL env vars, else `sf org display -o $SF_ORG`
(SF_ORG defaults to blueowl-prod). The Metadata API retrieve uses the sf CLI."""
import json, os, subprocess, tempfile, urllib.parse
from common import http, log

API = "v62.0"


class SF:
    def __init__(self):
        tok, base = os.environ.get("SF_ACCESS_TOKEN"), os.environ.get("SF_INSTANCE_URL")
        self.org = os.environ.get("SF_ORG", "blueowl-prod")
        if not (tok and base):
            out = subprocess.run(["sf", "org", "display", "-o", self.org, "--json"], capture_output=True, text=True).stdout
            res = json.loads(out)["result"]
            tok, base = res["accessToken"], res["instanceUrl"]
        self.token, self.base = tok, base.rstrip("/")

    def get(self, path, **params):
        url = self.base + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        return http(url, headers={"Authorization": "Bearer " + self.token})

    def query(self, soql, tooling=False):
        path = f"/services/data/{API}/" + ("tooling/" if tooling else "") + "query"
        s, d = self.get(path, q=soql)
        if s != 200:
            raise RuntimeError(f"query failed {s}: {str(d)[:300]} :: {soql[:120]}")
        recs = d["records"]
        while not d.get("done") and d.get("nextRecordsUrl"):
            s, d = self.get(d["nextRecordsUrl"])
            recs += d["records"]
        return recs

    def describe(self, obj):
        s, d = self.get(f"/services/data/{API}/sobjects/{obj}/describe")
        if s != 200:
            raise RuntimeError(f"describe {obj} failed {s}")
        return d

    def retrieve_metadata(self, types):
        """types: {MetadataType: [members]} -> path to unpacked folder (temp)."""
        tmp = tempfile.mkdtemp(prefix="mdapi_")
        members = "".join(
            f"<types>{''.join(f'<members>{m}</members>' for m in ms)}<name>{t}</name></types>" for t, ms in types.items())
        pkg = f'<?xml version="1.0" encoding="UTF-8"?><Package xmlns="http://soap.sforce.com/2006/04/metadata">{members}<version>{API[1:]}</version></Package>'
        with open(os.path.join(tmp, "package.xml"), "w") as f:
            f.write(pkg)
        r = subprocess.run(["sf", "project", "retrieve", "start", "-x", os.path.join(tmp, "package.xml"), "-o", self.org,
                            "--target-metadata-dir", tmp, "--unzip"], capture_output=True, text=True)
        if r.returncode != 0:
            log("metadata retrieve stderr:", r.stderr[-500:])
        return os.path.join(tmp, "unpackaged", "unpackaged")

    def list_metadata(self, mtype):
        r = subprocess.run(["sf", "org", "list", "metadata", "-m", mtype, "-o", self.org, "--json"], capture_output=True, text=True)
        try:
            return [x["fullName"] for x in json.loads(r.stdout)["result"]]
        except Exception:
            return []
