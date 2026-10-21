"""Synthetic Facebook Page and Instagram data with planted anomalies, for --mock runs and tests."""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

PLANTED = {
    "facebook": "reach_drop",      # yesterday's reach at 30% of normal
    "instagram": "unfollow_spike",  # 60 unfollows yesterday vs ~8 a day
}


def mock_data(report_day: date, lookback: int = 35, post_window: int = 14, seed: int = 7):
    rnd = random.Random(seed)
    rows, posts = [], []
    specs = [
        ("facebook", "1000001", "HiRoad", 5200, 42000),
        ("instagram", "1780000001", "hiroad", 3100, 18500),
    ]
    for platform, acct, name, reach0, followers0 in specs:
        followers = followers0 - 6 * lookback
        for k in range(lookback):
            d = report_day - timedelta(days=lookback - 1 - k)
            weekend = d.weekday() >= 5
            reach = max(0, int(rnd.gauss(reach0 * (0.7 if weekend else 1.0), reach0 * 0.08)))
            follows = max(0, int(rnd.gauss(14, 3)))
            unfollows = max(0, int(rnd.gauss(8, 2)))
            if d == report_day:
                if PLANTED[platform] == "reach_drop":
                    reach = int(reach * 0.3)
                if PLANTED[platform] == "unfollow_spike":
                    unfollows = 60
            followers += follows - unfollows
            rows.append({
                "platform": platform, "account_id": acct, "account_name": name, "date": d,
                "followers": followers, "follows": follows, "unfollows": unfollows,
                "reach": reach, "impressions": int(reach * 1.4), "engagements": int(reach * 0.045),
                "profile_views": int(reach * 0.02), "website_clicks": int(reach * 0.004) if platform == "instagram" else None,
            })
        for i in range(6):
            d = report_day - timedelta(days=2 * i + 1)
            if d < report_day - timedelta(days=post_window - 1):
                break
            comments = 180 if (platform == "instagram" and i == 1) else int(rnd.gauss(12, 4))
            posts.append({
                "platform": platform, "account_id": acct, "post_id": f"{acct}_{i}",
                "published_at": datetime(d.year, d.month, d.day, 15, 0, tzinfo=timezone.utc),
                "type": "reel" if platform == "instagram" and i % 2 else "post",
                "permalink": f"https://example.invalid/{platform}/{acct}_{i}",
                "text": f"Mock {platform} post {i}: safe driving tip of the week",
                "reach": int(rnd.gauss(2400, 300)), "impressions": int(rnd.gauss(3100, 300)),
                "likes": int(rnd.gauss(90, 15)), "comments": max(0, comments),
                "shares": int(rnd.gauss(6, 2)), "saves": int(rnd.gauss(10, 3)) if platform == "instagram" else None,
            })
    return rows, posts
