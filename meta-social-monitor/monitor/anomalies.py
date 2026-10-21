"""Turn daily account rows and posts into per-account stats and anomaly flags.

Baseline logic (same as the journey monitor): expected reach for the report day is the mean of
the same weekday over the previous 4 weeks; if fewer than 3 of those have data, the trailing 28
day mean. Missing metrics (None) are treated as "unknown", never as zero, so an API hiccup
raises a data_gap warning instead of a fake drop.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Flag:
    severity: str
    account: str
    rule: str
    detail: str


@dataclass
class AccountStats:
    platform: str
    account_id: str
    name: str
    followers: int | None = None
    follower_change: int | None = None
    follows_y: int | None = None
    unfollows_y: int | None = None
    reach_y: int | None = None
    reach_7: int = 0
    reach_prior_7: int = 0
    reach_baseline: float = 0.0
    reach_stdev: float = 0.0
    reach_z: float | None = None
    engagements_y: int | None = None
    engagements_baseline: float = 0.0
    profile_views_y: int | None = None
    posts_7: int = 0
    last_post: str | None = None
    reach_series: list[int | None] = field(default_factory=list)   # oldest -> newest
    followers_series: list[int | None] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.platform}|{self.account_id}"

    @property
    def wow_pct(self) -> float | None:
        return None if not self.reach_prior_7 else (self.reach_7 - self.reach_prior_7) / self.reach_prior_7

    @property
    def vs_baseline_pct(self) -> float | None:
        if self.reach_y is None or not self.reach_baseline:
            return None
        return (self.reach_y - self.reach_baseline) / self.reach_baseline


def _mean(values):
    vals = [v for v in values if v is not None]
    return statistics.mean(vals) if vals else 0.0


def analyze(rows: list[dict], posts: list[dict], report_day: date, cfg: dict):
    t = cfg["thresholds"]
    lookback = cfg["report"]["lookback_days"]
    days = [report_day - timedelta(days=i) for i in range(lookback - 1, -1, -1)]

    by_acct: dict[tuple[str, str], dict[date, dict]] = defaultdict(dict)
    names: dict[tuple[str, str], str] = {}
    for r in rows:
        k = (r["platform"], r["account_id"])
        by_acct[k][r["date"]] = r
        names[k] = r.get("account_name") or r["account_id"]
    posts_by: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in posts:
        posts_by[(p["platform"], p["account_id"])].append(p)

    stats, flags = [], []
    for k in sorted(by_acct, key=lambda x: (x[0], names[x])):
        d = by_acct[k]
        reach = [d.get(x, {}).get("reach") for x in days]
        s = AccountStats(platform=k[0], account_id=k[1], name=names[k], reach_series=reach,
                         followers_series=[d.get(x, {}).get("followers") for x in days])
        y = d.get(report_day, {})
        s.reach_y = y.get("reach")
        s.follows_y, s.unfollows_y = y.get("follows"), y.get("unfollows")
        s.engagements_y, s.profile_views_y = y.get("engagements"), y.get("profile_views")
        s.followers = y.get("followers")
        prev = d.get(report_day - timedelta(days=1), {}).get("followers")
        if s.followers is not None and prev is not None:
            s.follower_change = s.followers - prev
        s.reach_7 = sum(v or 0 for v in reach[-7:])
        s.reach_prior_7 = sum(v or 0 for v in reach[-14:-7])

        same_weekday = [reach[-1 - 7 * j] for j in range(1, 5) if len(reach) > 7 * j]
        trailing = [v for v in reach[-29:-1] if v is not None]
        nonzero = [v for v in same_weekday if v]
        basis = nonzero if len(nonzero) >= 3 else trailing
        s.reach_baseline = _mean(basis)
        s.reach_stdev = statistics.pstdev(trailing) if len(trailing) > 1 else 0.0
        if s.reach_stdev > 0 and s.reach_y is not None:
            s.reach_z = (s.reach_y - s.reach_baseline) / s.reach_stdev
        s.engagements_baseline = _mean(d.get(x, {}).get("engagements") for x in days[-29:-1])

        acct_posts = sorted(posts_by.get(k, []), key=lambda p: p["published_at"] or 0)
        s.posts_7 = sum(1 for p in acct_posts if p["published_at"] and p["published_at"].date() > report_day - timedelta(days=7))
        s.last_post = acct_posts[-1]["published_at"].date().isoformat() if acct_posts and acct_posts[-1]["published_at"] else None
        stats.append(s)
        flags.extend(_rules(s, d, acct_posts, t, report_day, days))

    flags.sort(key=lambda f: (SEVERITY_ORDER[f.severity], f.account))
    return stats, flags


def _rules(s: AccountStats, d: dict, posts: list[dict], t: dict, report_day: date, days: list[date]) -> list[Flag]:
    out: list[Flag] = []
    label = f"{s.name} ({s.platform})"

    if s.reach_y is None:
        out.append(Flag("warning", label, "data_gap", "No reach figure for yesterday; check the token and metric names"))
    else:
        big = s.reach_baseline >= t["min_baseline_reach"]
        z = s.reach_z if s.reach_z is not None else 0.0
        if big and s.reach_y <= s.reach_baseline * (1 - t["reach_drop_pct"]):
            sev = "critical" if z <= -t["zscore_critical"] else "warning"
            out.append(Flag(sev, label, "reach_drop",
                            f"Reach {s.reach_y:,} vs ~{s.reach_baseline:,.0f} expected ({s.vs_baseline_pct:+.0%}, z={z:.1f})"))
        elif big and s.reach_y >= s.reach_baseline * (1 + t["reach_spike_pct"]):
            sev = "critical" if z >= t["zscore_critical"] else "warning"
            out.append(Flag(sev, label, "reach_spike",
                            f"Reach {s.reach_y:,} vs ~{s.reach_baseline:,.0f} expected ({s.vs_baseline_pct:+.0%}, z={z:.1f})"))

    reach_dropped = any(f.rule == "reach_drop" for f in out)
    if (not reach_dropped and s.engagements_y is not None and s.engagements_baseline >= 20
            and s.engagements_y <= s.engagements_baseline * (1 - t["engagement_drop_pct"])):
        out.append(Flag("warning", label, "engagement_drop",
                        f"Engagements {s.engagements_y:,} vs ~{s.engagements_baseline:,.0f} expected"))

    if s.unfollows_y is not None:
        mean_unf = _mean(d.get(x, {}).get("unfollows") for x in days[-29:-1])
        if s.unfollows_y >= t["unfollow_min"] and mean_unf and s.unfollows_y >= mean_unf * t["unfollow_spike_factor"]:
            out.append(Flag("warning", label, "unfollow_spike",
                            f"{s.unfollows_y:,} unfollows yesterday vs ~{mean_unf:,.0f} a day"))

    if s.follower_change is not None and s.followers:
        prev = s.followers - s.follower_change
        if prev and s.follower_change < 0 and -s.follower_change / prev >= t["follower_drop_pct"]:
            out.append(Flag("critical", label, "follower_drop",
                            f"Followers {s.followers:,} ({s.follower_change:+,} in a day, {s.follower_change / prev:+.1%})"))

    if posts:
        last = posts[-1]["published_at"].date() if posts[-1]["published_at"] else None
        if last and (report_day - last).days >= t["posting_gap_days"]:
            out.append(Flag("warning", label, "posting_gap", f"Last post {last:%b %-d}, {(report_day - last).days} days ago"))
        comments = sorted(p["comments"] for p in posts if p.get("comments") is not None)
        if comments:
            median = comments[len(comments) // 2]
            for p in posts:
                c = p.get("comments") or 0
                if c >= t["hot_post_min_comments"] and median and c >= median * t["hot_post_factor"]:
                    out.append(Flag("info", label, "hot_post",
                                    f"{c:,} comments on a post from {p['published_at']:%b %-d} (median {median}); worth a read"))
    else:
        out.append(Flag("warning", label, "posting_gap", "No posts in the window"))
    return out


def to_json(stats, flags) -> dict:
    return {
        "accounts": [{**asdict(s), "wow_pct": s.wow_pct, "vs_baseline_pct": s.vs_baseline_pct, "key": s.key}
                     for s in stats],
        "flags": [asdict(f) for f in flags],
    }
