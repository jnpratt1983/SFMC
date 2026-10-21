"""Optional: have Claude turn the flags into a short read. Rules decide, Claude explains."""
from __future__ import annotations

import json
import os

SYSTEM = (
    "You write the opening summary of a daily social media monitoring report posted in Slack "
    "for a lifecycle marketing team. You are given yesterday's per-account stats for the brand's "
    "Facebook Page and Instagram account and the anomaly flags a rules engine raised. "
    "Write 2 to 4 short sentences in Slack mrkdwn: lead with what most needs a human today and "
    "the likely first thing to check (a post that drew comments, a reach drop after a posting gap, "
    "an unfollow spike after a campaign, an API permission problem when data is missing). "
    "If nothing is flagged, say so in one sentence. Only reference accounts and numbers present in "
    "the data. Do not invent causes as facts; phrase them as things to check. "
    "Never use em dashes. Use American spelling."
)


def summarize(report_day, payload: dict, cfg: dict) -> str | None:
    c = cfg.get("claude", {})
    if not c.get("enabled") or not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        slim = {"report_day": str(report_day), "flags": payload["flags"],
                "accounts": [{k: a[k] for k in ("name", "platform", "followers", "follower_change", "reach_y",
                                                "reach_baseline", "reach_7", "reach_prior_7", "posts_7", "last_post")}
                             for a in payload["accounts"]]}
        client = anthropic.Anthropic()
        msg = client.messages.create(model=c.get("model", "claude-sonnet-5-5"), max_tokens=c.get("max_tokens", 600),
                                     system=SYSTEM, messages=[{"role": "user", "content": json.dumps(slim, default=str)}])
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        return text.replace("—", ", ").replace("–", "-") or None
    except Exception as e:  # never let the summary block the alert
        print(f"[summarize] skipped: {e}")
        return None
