"""Build the Slack Block Kit report and post it to an incoming webhook."""
from __future__ import annotations

import requests

ICON = {"critical": ":red_circle:", "warning": ":large_orange_circle:", "info": ":large_blue_circle:"}
SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values) -> str:
    vals = [v or 0 for v in values]
    if not vals or max(vals) == 0:
        return SPARK[0] * len(vals)
    hi = max(vals)
    return "".join(SPARK[min(len(SPARK) - 1, int(v / hi * (len(SPARK) - 1)))] for v in vals)


def _pct(p):
    return "  n/a" if p is None else f"{p:+5.0%}"


def _n(v):
    return "n/a" if v is None else f"{v:,}"


def build_blocks(report_day, stats, flags, posts, summary, cfg) -> list[dict]:
    counts = {sev: sum(1 for f in flags if f.severity == sev) for sev in ICON}
    status = (":rotating_light: Needs attention" if counts["critical"]
              else ":warning: Review" if counts["warning"] else ":white_check_mark: All clear")
    tot_followers = sum(s.followers or 0 for s in stats)
    tot_reach = sum(s.reach_y or 0 for s in stats)
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Meta Social Monitor · {report_day:%a %b %-d}"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Status*\n{status}"},
            {"type": "mrkdwn", "text": f"*Accounts*\n{len(stats)}"},
            {"type": "mrkdwn", "text": f"*Followers*\n{tot_followers:,}"},
            {"type": "mrkdwn", "text": f"*Reach yesterday*\n{tot_reach:,}"},
        ]},
    ]
    if summary:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": summary[:2900]}})
    blocks.append({"type": "divider"})
    if flags:
        chunk = f"*Anomalies ({len(flags)})*\n"
        for f in flags:
            line = f"{ICON[f.severity]} *{f.account}*: {f.detail}\n"
            if len(chunk) + len(line) > 2900:
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
                chunk = ""
            chunk += line
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
    else:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": ":white_check_mark: No anomalies detected."}})

    if stats:
        w = min(28, max(len(f"{s.name} ({s.platform[:2]})") for s in stats))
        head = f"{'Account':<{w}}  {'Followers':>9}  {'Δday':>5}  {'Reach':>7}  {'vsExp':>5}  {'7d':>8}  {'WoW':>5}  14d reach"
        body = "\n".join(
            f"{(s.name + ' (' + s.platform[:2] + ')')[:w]:<{w}}  {_n(s.followers):>9}  "
            f"{(f'{s.follower_change:+d}' if s.follower_change is not None else 'n/a'):>5}  {_n(s.reach_y):>7}  "
            f"{_pct(s.vs_baseline_pct)}  {s.reach_7:>8,}  {_pct(s.wow_pct)}  {sparkline(s.reach_series[-14:])}"
            for s in stats)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"```{head}\n{body}```"[:2990]}})

    top = sorted([p for p in posts if p.get("published_at")],
                 key=lambda p: (p.get("likes") or 0) + (p.get("comments") or 0) + (p.get("shares") or 0), reverse=True)[:5]
    if top:
        lines = [f"• <{p['permalink']}|{p['published_at']:%b %-d} {p['platform']}>: "
                 f"{_n(p.get('reach'))} reach, {_n(p.get('likes'))} likes, {_n(p.get('comments'))} comments"
                 for p in top]
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                                                   "text": f"*Top posts, last {cfg['report']['post_window_days']} days*\n" + "\n".join(lines)}})
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": "Meta Graph API insights · expected = same weekday avg, prior 4 wks"}]})
    return blocks[:50]


def fallback_text(report_day, flags) -> str:
    c = sum(1 for f in flags if f.severity == "critical")
    w = sum(1 for f in flags if f.severity == "warning")
    return f"Meta Social Monitor {report_day:%b %-d}: {c} critical, {w} warnings"


def post(webhook_url: str, blocks: list[dict], text: str) -> None:
    r = requests.post(webhook_url, json={"text": text, "blocks": blocks}, timeout=30)
    r.raise_for_status()
