# Meta Social Monitor

Daily monitor for HiRoad's Facebook Page and Instagram business account. Pulls 35 days of
daily insights plus the last 14 days of posts from the Meta Graph API, flags anomalies with a
deterministic rules engine, has Claude write a short triage note, posts a Block Kit report to
Slack, and upserts the same figures into Salesforce (three custom objects) for reporting.
Sibling of `sfmc-journey-monitor`; same structure, same guardrails. README.md is the full
step by step build and setup guide.

## How data flows
1. `monitor/meta.py` (GET only) pulls Page insights (`/{page}/insights`, period=day), Page
   posts with reaction/comment/share counts, Instagram account insights (daily `reach`,
   `follower_count`; `profile_views`, `website_clicks`, `accounts_engaged` as total_value for
   the last 7 days) and Instagram media with per-media insights. Metric names live in
   `config.yaml`; a metric Meta rejects is skipped with a `[meta] skipped` line.
2. `monitor/anomalies.py` builds per-account stats and flags: reach_drop / reach_spike vs a
   same-weekday 4 week baseline, engagement_drop (only when reach did not drop), unfollow_spike,
   follower_drop, posting_gap, hot_post (info), data_gap (metric missing yesterday).
3. `monitor/summarize.py` (optional) asks Claude for 2 to 4 sentences. Rules decide, Claude explains.
4. `monitor/slack.py` posts the report. Full JSON lands in `out/`.
5. `monitor/salesforce_report.py` + `sync/salesforce_social_sync.py` upsert
   `Social_Monitor_Run__c` (one per day), `Social_Metric__c` (one per account per day, with
   35 day series as JSON) and `Social_Post__c` (one per post, refreshed while in the window).
   Object metadata lives in `../journey-monitor-dashboard/force-app` and in `salesforce/` here.

## Commands
- `pip install -r requirements.txt`
- `python -m monitor.main --mock --dry-run` : synthetic data, no credentials
- `python -m monitor.main --probe` : what the token can see (permissions, pages, IG ids)
- `python -m monitor.main --dry-run` : live Meta data, prints Slack and Salesforce payloads
- `python -m monitor.main --no-salesforce` : post to Slack, skip the push
- `python -m unittest discover -t .` : all tests

## Rules (do not break)
- **Read only.** GET only against the Graph API. Never post, reply, like, or change a setting.
- **No identities.** Counts and the brand's own posts only. Never request comment text,
  commenter or follower identities, or audience demographics that could identify a person.
- Thresholds and metric names live in `config.yaml`, not in code.
- The rules engine owns alerting. If Claude's API call fails the report still posts.
- The Salesforce push must never block Slack: it runs after the post, inside a try/except,
  and is skipped without `SF_DOMAIN` or with `--no-salesforce`.
- A missing metric is a data_gap warning, never a zero. Meta deprecates insight metrics
  without notice; fix the name in `config.yaml` rather than in code.
- Writing style for anything user facing: no em dashes, American spelling.
- When changing rules, plant the case in `monitor/mock.py` and confirm it fires in
  `--mock --dry-run` without false positives on the other account.

## Known limits
- Instagram `follower_count` is only served for the last 30 days; the total_value metrics
  are pulled for the last 7 days only (one call per day each).
- Page insights are reported in the Page's time zone; Instagram in UTC. Day boundaries can
  differ by a few hours between the two accounts.
- Ads are out of scope. Adding them means `ads_read` on the token and the Marketing API.

## Backlog
1. Ad account spend, impressions, clicks and CPL via the Marketing API (`act_<id>/insights`).
2. App store reviews and ratings (App Store Connect API, Play Developer API) as a sibling.
3. A Lightning tab like the journey monitor's; until then use reports on the three objects.
