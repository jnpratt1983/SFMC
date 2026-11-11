"""Shared helpers for the data dictionary pipeline (stdlib only)."""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "pipeline", "raw")
DATA = os.path.join(ROOT, "data")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def save(name, obj):
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, name + ".json"), "w") as f:
        json.dump(obj, f, indent=0, default=str)
    log("saved", name)


def load(name):
    with open(os.path.join(RAW, name + ".json")) as f:
        return json.load(f)


def http(url, headers=None, body=None, method=None, timeout=300, retries=4):
    """JSON request with retry on 429/5xx. Returns (status, parsed-or-text)."""
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                try:
                    return r.status, json.loads(raw or b"{}")
                except ValueError:
                    return r.status, raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            try:
                return e.code, json.loads(raw or b"{}")
            except ValueError:
                return e.code, raw.decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ConnectionResetError):
            if attempt == retries - 1:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")
