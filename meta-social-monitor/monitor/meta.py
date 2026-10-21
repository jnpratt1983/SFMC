"""Read-only Meta Graph API client: Facebook Page and Instagram business account insights.

Every call is a GET. Nothing here posts, replies, or changes a setting. Comment text and the
identities of people who react or comment are never requested: the monitor only pulls counts
and the brand's own posts.

Meta deprecates insight metrics regularly. Every metric is fetched defensively: a metric the
API rejects is logged and skipped, the rest of the report still builds.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone

import requests

TIMEOUT = 60
TEXT_CHARS = 200


class MetaError(RuntimeError):
    pass


class Meta:
    def __init__(self, token: str | None = None, version: str | None = None, log=print):
        self.token = token or os.environ.get("META_ACCESS_TOKEN")
        if not self.token:
            raise MetaError("META_ACCESS_TOKEN is not set")
        self.base = f"https://graph.facebook.com/{version or os.environ.get('META_API_VERSION', 'v23.0')}"
        self.log = log
        self.calls = 0
        self.skipped: list[str] = []

    # ---------- transport ----------
    def get(self, path: str, params: dict | None = None) -> dict:
        p = dict(params or {})
        p["access_token"] = self.token
        self.calls += 1
        for attempt in range(4):
            r = requests.get(f"{self.base}/{path.lstrip('/')}", params=p, timeout=TIMEOUT)
            if r.status_code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            body = r.json() if r.content else {}
            if r.status_code != 200 or "error" in body:
                err = body.get("error", {})
                code = err.get("code")
                if code in (4, 17, 32, 613) and attempt < 3:  # rate limits
                    time.sleep(30)
                    continue
                raise MetaError(f"{path}: {err.get('message') or r.text[:200]} (code {code})")
            return body
        raise MetaError(f"{path}: gave up after retries")

    def get_all(self, path: str, params: dict | None = None, limit: int = 2000) -> list[dict]:
        """Follow cursor pagination."""
        out, p = [], dict(params or {})
        while True:
            body = self.get(path, p)
            out += body.get("data", [])
            nxt = (body.get("paging") or {}).get("cursors", {}).get("after")
            if not nxt or not body.get("data") or len(out) >= limit or not (body.get("paging") or {}).get("next"):
                return out
            p["after"] = nxt

    def _try(self, label: str, fn):
        try:
            return fn()
        except MetaError as e:
            self.skipped.append(f"{label}: {e}")
            self.log(f"[meta] skipped {label}: {e}")
            return None

    # ---------- discovery ----------
    def probe(self) -> dict:
        """What the token can see: permissions, pages, linked Instagram accounts."""
        perms = self.get("me/permissions").get("data", [])
        pages = self.get_all("me/accounts", {"fields": "id,name,instagram_business_account{id,username}"})
        return {
            "granted": sorted(p["permission"] for p in perms if p.get("status") == "granted"),
            "declined": sorted(p["permission"] for p in perms if p.get("status") != "granted"),
            "pages": [{"page_id": p["id"], "page_name": p["name"],
                       "ig_user_id": (p.get("instagram_business_account") or {}).get("id"),
                       "ig_username": (p.get("instagram_business_account") or {}).get("username")}
                      for p in pages],
        }

    # ---------- Facebook Page ----------
    def page_daily(self, page_id: str, metrics: dict[str, str], since: date, until: date) -> list[dict]:
        """One row per day with the configured metrics (missing metric -> None)."""
        info = self.get(page_id, {"fields": "id,name,followers_count,fan_count"})
        days = {since + timedelta(days=i): {"platform": "facebook", "account_id": page_id,
                                             "account_name": info.get("name"), "date": since + timedelta(days=i)}
                for i in range((until - since).days + 1)}
        for key, metric in metrics.items():
            data = self._try(f"page {metric}", lambda: self.get_all(
                f"{page_id}/insights",
                {"metric": metric, "period": "day",
                 "since": since.isoformat(), "until": (until + timedelta(days=1)).isoformat()}))
            for m in data or []:
                for v in m.get("values", []):
                    d = _day(v.get("end_time"), shift=-1)  # end_time is the day after the value's day
                    if d in days:
                        days[d][key] = _num(v.get("value"))
        # today's lifetime follower count as a fallback for the newest day
        last = days.get(until)
        if last is not None and last.get("followers") is None:
            last["followers"] = info.get("followers_count") or info.get("fan_count")
        return list(days.values())

    def page_posts(self, page_id: str, since: date, metrics: list[str]) -> list[dict]:
        posts = self.get_all(f"{page_id}/posts", {
            "fields": "id,created_time,message,permalink_url,shares,"
                      "comments.summary(true).limit(0),reactions.summary(true).limit(0)",
            "since": since.isoformat(), "limit": 100})
        out = []
        for p in posts:
            row = {
                "platform": "facebook", "account_id": page_id, "post_id": p["id"],
                "published_at": _ts(p.get("created_time")), "type": "post",
                "permalink": p.get("permalink_url"), "text": (p.get("message") or "")[:TEXT_CHARS],
                "likes": _num((p.get("reactions") or {}).get("summary", {}).get("total_count")),
                "comments": _num((p.get("comments") or {}).get("summary", {}).get("total_count")),
                "shares": _num((p.get("shares") or {}).get("count")),
                "saves": None, "reach": None, "impressions": None,
            }
            if metrics:
                ins = self._try(f"post insights {p['id']}", lambda: self.get(
                    f"{p['id']}/insights", {"metric": ",".join(metrics)}))
                for m in (ins or {}).get("data", []):
                    val = _num((m.get("values") or [{}])[0].get("value"))
                    if m["name"] == "post_impressions_unique":
                        row["reach"] = val
                    elif m["name"] == "post_impressions":
                        row["impressions"] = val
            out.append(row)
        return out

    # ---------- Instagram ----------
    def ig_daily(self, ig_user_id: str, daily: dict[str, str], totals: dict[str, str],
                 since: date, until: date) -> list[dict]:
        info = self.get(ig_user_id, {"fields": "id,username,name,followers_count,media_count"})
        days = {since + timedelta(days=i): {"platform": "instagram", "account_id": ig_user_id,
                                             "account_name": info.get("username") or info.get("name"),
                                             "date": since + timedelta(days=i)}
                for i in range((until - since).days + 1)}
        for key, metric in daily.items():
            # follower_count is only served for the last 30 days; ask for what the API allows
            start = max(since, until - timedelta(days=29)) if metric == "follower_count" else since
            data = self._try(f"instagram {metric}", lambda: self.get_all(
                f"{ig_user_id}/insights",
                {"metric": metric, "period": "day",
                 "since": start.isoformat(), "until": (until + timedelta(days=1)).isoformat()}))
            for m in data or []:
                for v in m.get("values", []):
                    d = _day(v.get("end_time"), shift=-1)
                    if d in days:
                        days[d][key] = _num(v.get("value"))
        if totals:
            # total_value metrics come back as one number per request, so ask one day at a time
            # for the last 7 days only (enough for the rules; older days stay None).
            for d in [until - timedelta(days=i) for i in range(6, -1, -1)]:
                if d not in days:
                    continue
                body = self._try(f"instagram totals {d}", lambda: self.get(
                    f"{ig_user_id}/insights",
                    {"metric": ",".join(totals.values()), "period": "day", "metric_type": "total_value",
                     "since": d.isoformat(), "until": (d + timedelta(days=1)).isoformat()}))
                for m in (body or {}).get("data", []):
                    key = next((k for k, v in totals.items() if v == m["name"]), None)
                    if key:
                        days[d][key] = _num((m.get("total_value") or {}).get("value"))
        last = days.get(until)
        if last is not None and last.get("followers") is None:
            last["followers"] = info.get("followers_count")
        return list(days.values())

    def ig_media(self, ig_user_id: str, since: date, metrics: list[str]) -> list[dict]:
        media = self.get_all(f"{ig_user_id}/media", {
            "fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count",
            "since": int(datetime.combine(since, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
            "limit": 50})
        out = []
        for m in media:
            ts = _ts(m.get("timestamp"))
            if ts and ts.date() < since:
                continue
            row = {
                "platform": "instagram", "account_id": ig_user_id, "post_id": m["id"],
                "published_at": ts, "type": (m.get("media_product_type") or m.get("media_type") or "").lower(),
                "permalink": m.get("permalink"), "text": (m.get("caption") or "")[:TEXT_CHARS],
                "likes": _num(m.get("like_count")), "comments": _num(m.get("comments_count")),
                "shares": None, "saves": None, "reach": None, "impressions": None,
            }
            if metrics:
                ins = self._try(f"media insights {m['id']}", lambda: self.get(
                    f"{m['id']}/insights", {"metric": ",".join(metrics)}))
                for i in (ins or {}).get("data", []):
                    val = _num((i.get("values") or [{}])[0].get("value"))
                    name = i["name"]
                    if name == "reach":
                        row["reach"] = val
                    elif name == "saved":
                        row["saves"] = val
                    elif name == "shares":
                        row["shares"] = val
                    elif name == "views":
                        row["impressions"] = val
            out.append(row)
        return out


# ---------- helpers ----------

def _num(v):
    if v is None or isinstance(v, (dict, list)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None


def _day(s: str | None, shift: int = 0) -> date | None:
    t = _ts(s)
    return (t.date() + timedelta(days=shift)) if t else None
