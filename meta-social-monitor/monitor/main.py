"""Daily Meta social monitor.

  python -m monitor.main                   # live run, posts to Slack, pushes to Salesforce
  python -m monitor.main --dry-run         # live data, prints the Slack payload and Salesforce records
  python -m monitor.main --mock --dry-run  # synthetic data, no credentials needed
  python -m monitor.main --probe           # what the token can see: permissions, pages, IG accounts
  python -m monitor.main --date 2026-10-20 # report on a specific day
  python -m monitor.main --no-salesforce   # post to Slack, skip the Salesforce push

The Salesforce push runs after Slack, inside a try/except, and is skipped when SF_DOMAIN is not
set. It can never block the Slack report.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .anomalies import analyze, to_json
from .salesforce_report import build_salesforce_report
from .slack import build_blocks, fallback_text, post
from .summarize import summarize

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--date", help="report day YYYY-MM-DD (default: yesterday in report timezone)")
    ap.add_argument("--mock", action="store_true", help="use synthetic data")
    ap.add_argument("--dry-run", action="store_true", help="print the Slack payload and Salesforce records, send nothing")
    ap.add_argument("--no-salesforce", action="store_true", help="skip the Salesforce push")
    ap.add_argument("--probe", action="store_true", help="print token permissions, pages and Instagram accounts, then exit")
    ap.add_argument("--out", default=str(ROOT / "out"))
    args = ap.parse_args(argv)

    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    cfg = yaml.safe_load(Path(args.config).read_text())
    tz = ZoneInfo(cfg["report"]["timezone"])
    report_day = date.fromisoformat(args.date) if args.date else datetime.now(tz).date() - timedelta(days=1)
    lookback = cfg["report"]["lookback_days"]
    post_since = report_day - timedelta(days=cfg["report"]["post_window_days"] - 1)

    if args.probe:
        from .meta import Meta
        print(json.dumps(Meta().probe(), indent=2))
        return

    if args.mock:
        from .mock import mock_data
        rows, posts = mock_data(report_day, lookback, cfg["report"]["post_window_days"])
    else:
        from .meta import Meta
        m = Meta()
        mc = cfg["meta"]
        since = report_day - timedelta(days=lookback - 1)
        rows, posts = [], []
        page_id, ig_id = os.environ.get("META_PAGE_ID"), os.environ.get("META_IG_USER_ID")
        if not page_id and not ig_id:
            raise SystemExit("Set META_PAGE_ID and/or META_IG_USER_ID (run --probe to find them)")
        if page_id:
            rows += m.page_daily(page_id, mc["page_metrics"], since, report_day)
            posts += m.page_posts(page_id, post_since, mc.get("post_metrics") or [])
        if ig_id:
            rows += m.ig_daily(ig_id, mc["ig_daily_metrics"], mc.get("ig_total_metrics") or {}, since, report_day)
            posts += m.ig_media(ig_id, post_since, mc.get("ig_media_metrics") or [])
        print(f"[meta] {len(rows)} account-day rows, {len(posts)} posts, {m.calls} API calls, {len(m.skipped)} metrics skipped")

    stats, flags = analyze(rows, posts, report_day, cfg)
    payload = to_json(stats, flags)
    summary = summarize(report_day, payload, cfg)
    blocks = build_blocks(report_day, stats, flags, posts, summary, cfg)
    text = fallback_text(report_day, flags)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"report_{report_day}.json").write_text(
        json.dumps({"report_day": str(report_day), "summary": summary, **payload,
                    "posts": posts}, indent=2, default=str))

    if args.dry_run:
        print(json.dumps({"text": text, "blocks": blocks}, indent=2, ensure_ascii=False))
    else:
        post(os.environ["SLACK_WEBHOOK_URL"], blocks, text)
        print(f"Posted: {text}")

    if args.no_salesforce:
        print("[salesforce] skipped: --no-salesforce")
    else:
        sync_salesforce(report_day, stats, flags, rows, posts, summary, out, args.dry_run)


def sync_salesforce(report_day, stats, flags, rows, posts, summary, out: Path, dry_run: bool) -> None:
    """Push to Salesforce after Slack. Every failure is a printed warning, never an exception."""
    try:
        from sync.salesforce_social_sync import build_records, push_report
        report = build_salesforce_report(report_day, stats, flags, rows, posts, summary)
        (out / f"salesforce_report_{report_day}.json").write_text(json.dumps(report, indent=2))
        if dry_run:
            print("[salesforce] dry run, records that would be upserted:")
            print(json.dumps(build_records(report), indent=2, ensure_ascii=False))
            return
        if not os.environ.get("SF_DOMAIN"):
            print("[salesforce] skipped: SF_DOMAIN not set")
            return
        result = push_report(report)
        print(f"[salesforce] synced {result['accounts']} accounts, {result['posts']} posts for {result['run_key']} ({result['status']})")
        for err in result["failed"]:
            print(f"[salesforce] row failed: {err}")
    except Exception as e:  # never let the Salesforce push block the Slack report
        print(f"[salesforce] warning: push failed, Slack report unaffected: {e}")


if __name__ == "__main__":
    main()
