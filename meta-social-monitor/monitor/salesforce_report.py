"""Reshape the monitor's results into the report dict sync/salesforce_social_sync.py accepts.

Pure adapter: uses the stats and flags the rules engine produced, the daily rows and posts the
monitor already pulled, and the Claude summary. Level mapping: critical -> critical,
warning -> warning, info -> none (notes ride along as text, never change a level or count).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

LEVELS = {"critical": "critical", "warning": "warning", "info": "none"}
METRICS = ("followers", "follows", "unfollows", "reach", "impressions", "engagements", "profile_views", "website_clicks")


def build_salesforce_report(report_day: date, stats, flags, rows: list[dict], posts: list[dict],
                            summary: str | None, generated_at: str | None = None, history_days: int = 35) -> dict:
    start = report_day - timedelta(days=history_days - 1)
    daily_by = {}
    for r in rows:
        if start <= r["date"] <= report_day:
            daily_by.setdefault((r["platform"], r["account_id"]), []).append(
                {"date": r["date"].isoformat(), **{m: r.get(m) for m in METRICS}})
    alerts_by = {}
    for f in flags:
        alerts_by.setdefault(f.account, []).append({"level": LEVELS.get(f.severity, "warning"), "message": f.detail})

    accounts = []
    for s in stats:
        accounts.append({
            "platform": s.platform, "account_id": s.account_id, "account_name": s.name,
            "daily": sorted(daily_by.get((s.platform, s.account_id), []), key=lambda x: x["date"]),
            "alerts": alerts_by.get(f"{s.name} ({s.platform})", []),
        })
    out_posts = [{
        "platform": p["platform"], "account_id": p["account_id"], "post_id": p["post_id"],
        "published_at": p["published_at"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if p.get("published_at") else None,
        "type": p.get("type"), "permalink": p.get("permalink"), "text": p.get("text"),
        **{k: p.get(k) for k in ("reach", "impressions", "likes", "comments", "shares", "saves")},
    } for p in posts]
    return {
        "report_date": report_day.isoformat(),
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": summary,
        "accounts": accounts,
        "posts": out_posts,
    }
