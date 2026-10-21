# Meta Social Monitor: build and setup guide

A daily report on HiRoad's Facebook Page and Instagram account: followers, reach, engagement,
unfollows, the posts of the last two weeks, and anomaly alerts. It posts to Slack and writes
the same numbers into Salesforce so they can be reported on next to the journey monitor.

Everything is read only against Meta, and nothing that identifies a person is ever pulled.

Try it with no setup:

```bash
python3 -m pip install -r requirements.txt
python3 -m monitor.main --mock --dry-run
```

## Step 1. Meta app (10 minutes, needs a Business Manager admin)

1. Go to developers.facebook.com, My Apps, **Create app**.
2. Use case **Other**, app type **Business**. Name it `HiRoad Social Monitor`, pick the HiRoad
   business portfolio, use your work email as the contact. Create.
3. Leave the app in **Development** mode. For insights on assets your own business owns, an
   admin system user token works in development mode and no App Review is needed.
4. App dashboard, **App Review**, **Permissions and Features**: confirm these are available
   with Standard access: `pages_show_list`, `pages_read_engagement`, `pages_read_user_content`,
   `read_insights`, `instagram_basic`, `instagram_manage_insights`, `business_management`.
   If one is missing, click **Request** on it; standard access on your own assets is granted
   without a review.

## Step 2. System user and token

1. business.facebook.com, **Business settings**, Users, **System users**, Add.
   Name `social-monitor`, role **Admin** (Employee also works if you assign assets explicitly).
2. **Assign assets**: the HiRoad Facebook Page (View performance is enough) and the HiRoad
   Instagram account (View performance). The Instagram account must be a business or creator
   account linked to the Page.
3. **Generate new token**: app = HiRoad Social Monitor, expiration **Never**, tick the seven
   permissions from step 1. Generate, copy the token once. It is shown only once.
4. Create `.env` from `.env.example` and set `META_ACCESS_TOKEN`.

## Step 3. Find the account ids

```bash
python3 -m monitor.main --probe
```

Prints the granted permissions, every Page the token can see, and each Page's linked
Instagram business account id. Put the ids in `.env` as `META_PAGE_ID` and `META_IG_USER_ID`.
If `declined` lists a permission you ticked, regenerate the token.

## Step 4. First live run

```bash
python3 -m monitor.main --dry-run --no-salesforce
```

Watch the `[meta] skipped ...` lines. Meta retires insight metrics regularly; when a name is
rejected, change it under `meta:` in `config.yaml`. The report still builds without it and the
rules treat the missing figure as a data gap, not a zero.

## Step 5. Slack

Create (or reuse) a Slack app with an Incoming Webhook into the social or marketing alerts
channel. Put the URL in `.env` as `SLACK_WEBHOOK_URL`. Then:

```bash
python3 -m monitor.main --no-salesforce    # posts for real
```

## Step 6. Salesforce objects

The three objects, two permission sets and two tabs live in `salesforce/` (and in the
`journey-monitor-dashboard` project). Validate, then deploy:

```bash
cd salesforce
sf project deploy validate --source-dir force-app --test-level RunSpecifiedTests --tests JourneyMonitorControllerTest --target-org <alias>
sf project deploy quick --job-id <id from validate> --target-org <alias>
```

Assign **Social Monitor Viewer** to people who should see the data and add the Social Metrics
and Social Posts tabs to the HiRoad app (App Manager, Navigation Items). Build reports and
dashboards on `Social_Metric__c` (one row per account per day) and `Social_Post__c`.

## Step 7. Salesforce push credentials

Reuse the journey monitor's External Client App and integration user: assign the
**Social Monitor Sync** permission set to that user, then put the same `SF_DOMAIN`,
`SF_CLIENT_ID` and `SF_CLIENT_SECRET` in `.env`. Test:

```bash
python3 -m monitor.main --dry-run          # prints the records that would be upserted
python3 -m monitor.main                    # posts to Slack, then pushes
```

A Salesforce failure prints a warning and never blocks the Slack post. Reruns for the same
day update the same rows.

## Step 8. Schedule

Pick one:
- **GitHub Actions**: `.github/workflows/daily-social-monitor.yml` (7:30 AM Central). Add the
  `.env` values as repository secrets.
- **Airflow**: `airflow/meta_social_monitor_dag.py` (7:30 AM Central, DST aware). Values come
  from the worker environment or Airflow Variables of the same names.

## Step 9. Tune

All thresholds are in `config.yaml`. Expect a week of tuning: reach is noisy on small accounts,
so raise `min_baseline_reach` if the drop rule chatters, and raise `hot_post_min_comments`
if every post is "hot". Ads are a later step and need `ads_read` on the token.

## What each number means

| Field | Facebook | Instagram |
|---|---|---|
| Followers | `page_follows` lifetime count | `follower_count` (daily, last 30 days) |
| Reach | `page_impressions_unique` per day | `reach` per day |
| Engagements | `page_post_engagements` per day | `accounts_engaged` (last 7 days) |
| Follows / unfollows | `page_daily_follows`, `page_daily_unfollows` | not served per day |
| Profile views | `page_views_total` | `profile_views` (last 7 days) |
| Website clicks | not served | `website_clicks` (last 7 days) |
| Posts | reactions, comments, shares, `post_impressions_unique` | likes, comments, shares, saves, reach |

Expected = same weekday average over the prior 4 weeks (trailing 28 day mean when fewer than 3
of those have data). Alerts: reach drop or spike vs expected, engagement drop, unfollow spike,
follower drop, posting gap, hot post (info), data gap.

## Guardrails
- Read only. GET only. Never post, reply, or change a setting from this code.
- No identities. No comment text, no commenter or follower names or ids, no demographics.
- The token is a secret: `.env` is git-ignored; use repository secrets or Airflow Variables.
