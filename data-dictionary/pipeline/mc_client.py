"""Marketing Cloud Engagement client (REST + SOAP Retrieve). Credentials from env vars
MC_CLIENT_ID / MC_CLIENT_SECRET / MC_AUTH_BASE (optionally MC_MID), or from ~/.config/sfmc/env."""
import os, re, subprocess, time, urllib.parse, urllib.request
from common import http, log

ENV_FILE = os.path.expanduser("~/.config/sfmc/env")


def creds():
    need = ["MC_CLIENT_ID", "MC_CLIENT_SECRET", "MC_AUTH_BASE"]
    if all(os.environ.get(k) for k in need):
        return {k: os.environ.get(k, "") for k in need + ["MC_MID"]}
    if os.path.exists(ENV_FILE):
        out = subprocess.run(["bash", "-c", f"set -a; source {ENV_FILE}; env"], capture_output=True, text=True).stdout
        env = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
        return {k: env.get(k, "").strip() for k in need + ["MC_MID"]}
    raise SystemExit("Marketing Cloud credentials missing (env vars or ~/.config/sfmc/env)")


class MC:
    def __init__(self):
        self.c = creds()
        self.exp = 0
        self.auth()

    def auth(self):
        if time.time() < self.exp - 120:
            return
        body = {"grant_type": "client_credentials", "client_id": self.c["MC_CLIENT_ID"], "client_secret": self.c["MC_CLIENT_SECRET"]}
        if self.c.get("MC_MID"):
            body["account_id"] = self.c["MC_MID"]
        s, t = http(self.c["MC_AUTH_BASE"].rstrip("/") + "/v2/token", body=body)
        if s != 200 or "access_token" not in t:
            raise SystemExit(f"MC token failed {s}: {str(t)[:200]}")
        self.token = t["access_token"]
        self.exp = time.time() + t.get("expires_in", 1080)
        self.rest = t["rest_instance_url"].rstrip("/")
        self.soap = t["soap_instance_url"].rstrip("/") + "/Service.asmx"

    def get(self, path, **params):
        self.auth()
        url = self.rest + path + (("?" + urllib.parse.urlencode(params)) if params else "")
        return http(url, headers={"Authorization": "Bearer " + self.token}, timeout=120)

    def post(self, path, body):
        self.auth()
        return http(self.rest + path, headers={"Authorization": "Bearer " + self.token}, body=body, timeout=120)

    def retrieve(self, obj, props, filter_xml="", query_all=True):
        """SOAP Retrieve with ContinueRequest paging. Strips nested blocks so Name is the DE's own name."""
        rows, rid, status = [], None, None
        while True:
            self.auth()
            inner = (f"<ContinueRequest>{rid}</ContinueRequest>" if rid else
                     f"<ObjectType>{obj}</ObjectType>{''.join(f'<Properties>{p}</Properties>' for p in props)}{filter_xml}"
                     + ("<QueryAllAccounts>true</QueryAllAccounts>" if query_all else ""))
            env = (f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
                   f'<s:Header><fueloauth xmlns="http://exacttarget.com">{self.token}</fueloauth><a:Action s:mustUnderstand="1">Retrieve</a:Action>'
                   f'<a:To s:mustUnderstand="1">{self.soap}</a:To></s:Header><s:Body><RetrieveRequestMsg xmlns="http://exacttarget.com/wsdl/partnerAPI" '
                   f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><RetrieveRequest>{inner}</RetrieveRequest></RetrieveRequestMsg></s:Body></s:Envelope>')
            req = urllib.request.Request(self.soap, data=env.encode(), headers={"Content-Type": "application/soap+xml; charset=utf-8", "SOAPAction": "Retrieve"})
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(req, timeout=180) as r:
                        x = r.read().decode()
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(3 * (attempt + 1))
            status = (re.search(r"<OverallStatus>([^<]*)", x) or [None, "?"])[1]
            rid = (re.search(r"<RequestID>([^<]*)", x) or [None, None])[1]
            if status not in ("OK", "MoreDataAvailable"):
                raise RuntimeError(f"SOAP {obj}: {status}: {x[:300]}")
            for blk in re.findall(r"<Results[^>]*>(.*?)</Results>", x, re.S):
                blk = re.sub(r"<(DataExtension|SendableSubscriberField|SendableDataExtensionField|Client|Template)>.*?</\1>", "", blk, flags=re.S)
                rows.append(dict(re.findall(r"<(\w+)>([^<]*)</\1>", blk)))
            if status != "MoreDataAvailable":
                return rows


def simple(prop, op, values):
    return f"<Filter xsi:type='SimpleFilterPart'><Property>{prop}</Property><SimpleOperator>{op}</SimpleOperator>{''.join(f'<Value>{v}</Value>' for v in values)}</Filter>"
