"""
Push one Meta social monitor report into Salesforce.

Writes three objects (metadata in journey-monitor-dashboard/force-app):
  Social_Monitor_Run__c   one row per report date, upserted on Run_Key__c (YYYY-MM-DD)
  Social_Metric__c        one row per account per report, upserted on Metric_Key__c
                          (YYYY-MM-DD|platform|account_id), child of the run
  Social_Post__c          one row per post, upserted on Post_Key__c (platform|post_id);
                          engagement figures refresh on every run while the post is in the window

Report contract
---------------
{
  "report_date": "2026-10-20",
  "generated_at": "2026-10-21T12:16:00Z",       # optional
  "summary": "Start with ...",                  # optional
  "accounts": [
    {"platform": "facebook", "account_id": "1000001", "account_name": "HiRoad",
     "daily": [{"date": "2026-10-20", "followers": 42000, "follows": 14, "unfollows": 8, "reach": 5200,
                "impressions": 7300, "engagements": 230, "profile_views": 100, "website_clicks": null}],
     "alerts": [{"level": "warning", "message": "Reach 1,500 vs ~5,200 expected"}]}
  ],
  "posts": [
    {"platform": "instagram", "account_id": "178...", "post_id": "1790...", "published_at": "2026-10-19T15:00:00Z",
     "type": "reel", "permalink": "https://...", "text": "first 200 chars of the caption",
     "reach": 2400, "impressions": null, "likes": 90, "comments": 12, "shares": 6, "saves": 10}
  ]
}

Aggregates and the brand's own posts only. No commenter or follower identities, ever.

Environment: SF_DOMAIN, SF_CLIENT_ID, SF_CLIENT_SECRET, optional SF_API_VERSION (62.0).
CLI: python -m sync.salesforce_social_sync report.json [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from typing import Any

import requests

RUN_OBJECT = "Social_Monitor_Run__c"
METRIC_OBJECT = "Social_Metric__c"
POST_OBJECT = "Social_Post__c"
BATCH_SIZE = 200
HISTORY_DAYS = 35
LEVEL_RANK = {"none": 0, "warning": 1, "critical": 2}
LEVEL_LABEL = {0: "None", 1: "Warning", 2: "Critical"}
RUN_STATUS = {0: "OK", 1: "Warning", 2: "Critical"}
PLATFORM_LABEL = {"facebook": "Facebook", "instagram": "Instagram"}


class SyncError(RuntimeError):
    pass


def _date(s) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def _clip(s, n):
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def _sum(rows, key):
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    return sum(vals) if vals else None


def build_records(report: dict[str, Any]) -> dict[str, Any]:
    """Pure: report dict -> {"run": fields, "metrics": [records], "posts": [records]}."""
    if not report.get("report_date"):
        raise ValueError("report_date is required")
    end = _date(report["report_date"])
    run_key = end.isoformat()
    window = [end - dt.timedelta(days=i) for i in range(HISTORY_DAYS - 1, -1, -1)]
    last7 = window[-7:]
    prior7 = window[-14:-7]

    metrics, counts, worst = [], {"critical": 0, "warning": 0}, 0
    tot_followers, tot_reach = 0, 0
    for a in report.get("accounts", []):
        platform, acct = str(a.get("platform") or "").lower(), str(a.get("account_id") or "").strip()
        if platform not in PLATFORM_LABEL or not acct:
            raise ValueError(f"account needs platform (facebook|instagram) and account_id: {a.get('account_name')!r}")
        by_day = {}
        for row in a.get("daily", []):
            d = _date(row["date"])
            if window[0] <= d <= end:
                by_day[d] = row
        y = by_day.get(end, {})
        rank, lines = 0, []
        for al in a.get("alerts") or []:
            r = LEVEL_RANK.get(str(al.get("level", "warning")).lower(), 1)
            rank = max(rank, r)
            if r == 2:
                counts["critical"] += 1
            elif r == 1:
                counts["warning"] += 1
            if al.get("message"):
                lines.append(str(al["message"]))
        worst = max(worst, rank)
        reach7 = _sum([by_day.get(d, {}) for d in last7], "reach")
        reachp7 = _sum([by_day.get(d, {}) for d in prior7], "reach")
        prev_followers = by_day.get(end - dt.timedelta(days=1), {}).get("followers")
        tot_followers += y.get("followers") or 0
        tot_reach += y.get("reach") or 0
        name = a.get("account_name") or acct
        metrics.append({
            "attributes": {"type": METRIC_OBJECT},
            "Metric_Key__c": f"{run_key}|{platform}|{acct}"[:120],
            "Run__r": {"Run_Key__c": run_key},
            "Name": _clip(f"{name} {PLATFORM_LABEL[platform]} {run_key}", 80),
            "Platform__c": PLATFORM_LABEL[platform],
            "Account_Id__c": acct[:50],
            "Account_Name__c": _clip(name, 255),
            "Metric_Date__c": run_key,
            "Followers__c": y.get("followers"),
            "Follower_Change__c": (y.get("followers") - prev_followers) if y.get("followers") is not None and prev_followers is not None else None,
            "Follows__c": y.get("follows"),
            "Unfollows__c": y.get("unfollows"),
            "Reach__c": y.get("reach"),
            "Impressions__c": y.get("impressions"),
            "Engagements__c": y.get("engagements"),
            "Profile_Views__c": y.get("profile_views"),
            "Website_Clicks__c": y.get("website_clicks"),
            "Reach_Last_7_Days__c": reach7,
            "Reach_Prior_7_Days__c": reachp7,
            "Week_Over_Week_Change__c": round((reach7 - reachp7) / reachp7 * 100, 1) if reach7 is not None and reachp7 else None,
            "Alert_Level__c": LEVEL_LABEL[rank],
            "Alerts__c": _clip("\n".join(lines), 4000) if lines else None,
            "Daily_Reach__c": json.dumps([{"d": d.isoformat(), "r": by_day.get(d, {}).get("reach")} for d in window],
                                         separators=(",", ":")),
            "Daily_Followers__c": json.dumps([{"d": d.isoformat(), "f": by_day.get(d, {}).get("followers")} for d in window],
                                             separators=(",", ":")),
        })

    posts = []
    for p in report.get("posts", []):
        platform, acct, pid = str(p.get("platform") or "").lower(), str(p.get("account_id") or ""), str(p.get("post_id") or "")
        if platform not in PLATFORM_LABEL or not pid:
            raise ValueError(f"post needs platform and post_id: {p!r}"[:200])
        posts.append({
            "attributes": {"type": POST_OBJECT},
            "Post_Key__c": f"{platform}|{pid}"[:120],
            "Name": _clip(f"{PLATFORM_LABEL[platform]} {str(p.get('published_at') or '')[:10]} {p.get('text') or pid}", 80),
            "Platform__c": PLATFORM_LABEL[platform],
            "Account_Id__c": acct[:50],
            "Post_Id__c": pid[:80],
            "Published_At__c": p.get("published_at"),
            "Post_Type__c": _clip(p.get("type"), 40),
            "Permalink__c": _clip(p.get("permalink"), 255),
            "Text__c": _clip(p.get("text"), 255),
            "Reach__c": p.get("reach"),
            "Impressions__c": p.get("impressions"),
            "Likes__c": p.get("likes"),
            "Comments__c": p.get("comments"),
            "Shares__c": p.get("shares"),
            "Saves__c": p.get("saves"),
            "Engagements__c": sum(v for v in (p.get("likes"), p.get("comments"), p.get("shares"), p.get("saves")) if v) or None,
            "Last_Synced__c": report.get("generated_at") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    run = {
        "Name": f"Meta Social Monitor {run_key}",
        "Run_Date__c": run_key,
        "Overall_Status__c": RUN_STATUS[worst],
        "Accounts__c": len(metrics),
        "Followers__c": tot_followers,
        "Reach_Yesterday__c": tot_reach,
        "Posts_In_Window__c": len(posts),
        "Critical_Alerts__c": counts["critical"],
        "Warning_Alerts__c": counts["warning"],
        "Triage_Summary__c": _clip(report.get("summary"), 32000),
        "Monitor_Ran_At__c": report.get("generated_at") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return {"run": run, "metrics": metrics, "posts": posts}


class Salesforce:
    def __init__(self, domain, client_id, client_secret, api_version="62.0", session=None, scheme="https"):
        self.base = f"{scheme}://{domain.replace('https://', '').rstrip('/')}"
        self.client_id, self.client_secret = client_id, client_secret
        self.api = f"/services/data/v{api_version}"
        self.http = session or requests.Session()
        self.token = None

    @classmethod
    def from_env(cls):
        missing = [k for k in ("SF_DOMAIN", "SF_CLIENT_ID", "SF_CLIENT_SECRET") if not os.environ.get(k)]
        if missing:
            raise SyncError("Missing environment variables: " + ", ".join(missing))
        return cls(os.environ["SF_DOMAIN"], os.environ["SF_CLIENT_ID"], os.environ["SF_CLIENT_SECRET"],
                   os.environ.get("SF_API_VERSION", "62.0"))

    def login(self):
        r = self.http.post(f"{self.base}/services/oauth2/token", data={
            "grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret}, timeout=30)
        if r.status_code != 200:
            raise SyncError(f"Salesforce login failed ({r.status_code}): {r.text[:300]}")
        body = r.json()
        self.token = body["access_token"]
        if body.get("instance_url"):
            self.base = body["instance_url"].rstrip("/")

    def _req(self, method, path, payload):
        if not self.token:
            self.login()
        for attempt in range(3):
            r = self.http.request(method, self.base + self.api + path, json=payload, timeout=60,
                                  headers={"Authorization": f"Bearer {self.token}"})
            if r.status_code == 401 and attempt == 0:
                self.login()
                continue
            if r.status_code >= 500 and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return r
        return r

    def upsert_one(self, obj, ext_field, key, fields):
        r = self._req("PATCH", f"/sobjects/{obj}/{ext_field}/{key}", fields)
        if r.status_code not in (200, 201, 204):
            raise SyncError(f"{obj} upsert failed ({r.status_code}): {r.text[:500]}")

    def upsert_many(self, obj, ext_field, records) -> list[str]:
        errors = []
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i:i + BATCH_SIZE]
            r = self._req("PATCH", f"/composite/sobjects/{obj}/{ext_field}", {"allOrNone": False, "records": batch})
            if r.status_code != 200:
                raise SyncError(f"{obj} upsert failed ({r.status_code}): {r.text[:500]}")
            for rec, res in zip(batch, r.json()):
                if not res.get("success"):
                    errors.append(f"{rec[ext_field]}: " + "; ".join(e.get("message", "") for e in res.get("errors", [])))
        return errors


def push_report(report, sf=None):
    recs = build_records(report)
    sf = sf or Salesforce.from_env()
    run_key = recs["run"]["Run_Date__c"]
    sf.upsert_one(RUN_OBJECT, "Run_Key__c", run_key, recs["run"])
    errors = sf.upsert_many(METRIC_OBJECT, "Metric_Key__c", recs["metrics"])
    errors += sf.upsert_many(POST_OBJECT, "Post_Key__c", recs["posts"])
    return {"run_key": run_key, "accounts": len(recs["metrics"]), "posts": len(recs["posts"]),
            "failed": errors, "status": recs["run"]["Overall_Status__c"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Push a Meta social monitor report to Salesforce.")
    ap.add_argument("report")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    with open(a.report) as f:
        report = json.load(f)
    if a.dry_run:
        print(json.dumps(build_records(report), indent=2))
        return 0
    try:
        out = push_report(report)
    except (SyncError, ValueError) as e:
        print(f"Salesforce sync failed: {e}", file=sys.stderr)
        return 1
    print(f"Salesforce sync: {out['accounts']} accounts, {out['posts']} posts for {out['run_key']} ({out['status']})")
    for err in out["failed"]:
        print(f"  failed: {err}", file=sys.stderr)
    return 2 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
