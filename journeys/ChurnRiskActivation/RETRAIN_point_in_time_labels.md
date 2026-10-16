# Runbook: retrain the churn model with point-in-time labels

Companion to `2026-10-16_churn_score_validation.md`. Goal: replace the training set behind
"Predicted Did Cancel" (Einstein Studio / Model Builder, output `Did_Cancel_prediction__c`)
with one where every row is a customer *as of a date* and the label is whether they cancelled
in the 60 days after that date. Nothing after the snapshot date may appear in the features.

Sources in Data Cloud today: `Bill__dlm` (invoice, due, payment, `Nonpay_Cancel_Notice_Created_At_c__c`,
`Nonpay_Cleared_At_c__c`, `Nonpay_Cancelled_At_c__c`, `Contact__c`), Contact via the Salesforce
data stream (`CreatedDate`, `Cancel_Date__c`, `Current_Term_Effective_Date__c`, `Current_Term_Expiration_Date__c`),
`ssot__EmailEngagement__dlm`, `MobileApp_c_00D3h0000068eod__dlm`, `Zen_Desk_Ticket_Gold__dlm`,
`Forsta_Survey_Response__dlm`. Driving stats (`Monthly_Driving_Stat__c`) are **not** a DMO yet;
the current training set's trip features came from Contact snapshot fields, which are current
values, not point-in-time. Stream the driving object if trip recency is to stay a feature.

## Step 0. Prototype locally first (half a day)

Build the training set with `sf data query` and fit a plain logistic regression or gradient
boosting before touching Data Cloud. If the local model does not beat tenure alone (AUC 0.68 on
the 2026-08-22 holdout) the feature set is wrong and no amount of Model Builder will fix it.
`scripts/churn_score_validation.py` already pulls Contact, ContactHistory and the DMOs; extend
it with the Bill, email, app and ticket pulls below.

## Step 1. Pick the snapshot calendar

- Snapshot dates: the 1st of every month, 2025-01-01 through 2026-08-01. That gives 20
  snapshots; the last one with a full 60-day outcome window is 2026-08-01 (window closes
  2026-09-30). Bill data goes back to 2024 and `Cancel_Date__c` values go back further, so
  earlier snapshots are possible; start with 20 and extend if the model is data-starved.
- Horizon: **60 days primary**, because the batch is monthly and the journey acts within a
  month. Carry a `label_90` column too; it is free and smooths the rarer reasons.
- Holdout by time, not by random split: train on snapshots 2025-01 through 2026-04, validate on
  2026-05 through 2026-08. Model Builder's default split is random across rows and will leak
  the same customer across train and test; see step 6.

## Step 2. Define the active book at each snapshot

A contact is in the book at snapshot `S` when:

```
CreatedDate <= S
AND (Cancel_Date__c IS NULL OR Cancel_Date__c > S)
AND at least one Bill__dlm row with Invoice_Date_c__c <= S      -- proof a policy existed
```

Do not use `PolicyStatus__c`, `canceled__c`, `Pending_Cancel_Flag__c` or `Policy_Status_Policy__c`
to define the book: they are current values and would admit the future. Known gap:
`Cancel_Date__c` keeps only the latest cancellation, so a customer who cancelled, came back and is
active again looks active for the whole history. Accept it, or stream the policy history object
if one exists.

Expect roughly 7,000 to 8,000 contacts per snapshot and 150,000 rows total.

## Step 3. Labels

```
label_60 = Cancel_Date__c > S AND Cancel_Date__c <= S + 60 days
label_90 = Cancel_Date__c > S AND Cancel_Date__c <= S + 90 days
reason   = Cancellation_Reason__c when label_60, else NULL     -- for evaluation only, never a feature
```

Everyone else in the book at `S` is a negative. **Drop the current training set's 55,020
all-time cancellation rows entirely.** They are what inverted tenure. Positive rate will be
about 15% at 60 days, which is a normal base rate and needs no rebalancing.

## Step 4. Features, all computed strictly from data dated before `S`

| Group | Feature | Source and rule |
|---|---|---|
| Tenure | `tenure_days` | `S - CreatedDate`. The strongest single signal; it must be in. |
| Tenure | `tenure_bucket` | <6mo, 6-12mo, 1-2y, 2y+. Lets a tree split cleanly on the first-year cliff. |
| Term age | `days_into_term`, `days_to_term_end` | Term effective/expiration as of `S`. `Current_Term_*` on Contact are current values, so for historical snapshots derive the term from the first invoice date plus six-month terms, or stream policy term history. Renewal timing drives voluntary churn, which both models currently miss. |
| Non-pay | `nonpay_notices_90d`, `nonpay_notices_365d` | Count of `Bill__dlm` rows with `Nonpay_Cancel_Notice_Created_At_c__c` in `(S-90d, S]` and `(S-365d, S]`. |
| Non-pay | `days_since_last_nonpay_notice` | `S` minus the latest notice before `S`; large sentinel when none. |
| Non-pay | `open_nonpay_at_snapshot` | Latest notice before `S` has no `Nonpay_Cleared_At_c__c <= S`. This is the single best short-horizon feature. |
| Billing | `late_rate_lifetime`, `late_rate_180d` | Share of invoices with `Payment_Date_c__c > Invoice_Due_Date_c__c + 3 days`, invoices dated before `S` only. |
| Billing | `avg_days_past_due_180d`, `invoices_90d`, `avg_bill_amount_180d` | Same window rule. |
| Email | `email_opens_30d`, `email_opens_90d`, `email_clicks_90d`, `email_sends_90d` | `ssot__EmailEngagement__dlm`, engagement date `<= S`. Keep the ratio open/sent too. |
| App | `app_events_30d`, `app_events_90d`, `days_since_last_app_event` | `MobileApp_c_..__dlm` joined on `Account_Id__c = Contact.Account_Id2__c`, event timestamp `<= S`. |
| Support | `tickets_90d`, `days_since_last_ticket` | `Zen_Desk_Ticket_Gold__dlm`, `Created_at_c__c <= S`, joined on customer number. |
| Driving | `trips_per_month_last_cycle`, `weeks_since_last_trip`, `score_trend_3cycles` | Only once `Monthly_Driving_Stat__c` is streamed; cycles with `cycle_end <= S`. Until then leave driving out rather than use current-value Contact fields. |
| Survey | `nps_latest_before_S` | `Forsta_Survey_Response__dlm`; null for most rows, that is fine. |

Never include: `Cancellation_Reason__c`, `canceled__c`, `Cancel_Date__c`, `Pending_Cancel_Flag__c`,
`PolicyStatus__c`, `Customer_Persona__c` (it is derived from the old churn score),
`Churn_Risk_Score__c`, `Normalized_Churn_Risk_Score__c`, anything with a timestamp after `S`.

Window rule to apply everywhere: `event_date > S - N days AND event_date <= S`.

## Step 5. Build it in Data Cloud

1. **Snapshot calendar table.** A small CSV data stream `Churn_Snapshot_Calendar` with one row
   per snapshot date, or generate it inside the transform with a `VALUES` list. Monthly refresh
   adds the next date.
2. **Batch Data Transform** `Churn_PIT_Training_Set`: cross join the calendar to Contact, apply the
   step 2 filter, left-join each feature aggregate (one CTE per source, grouped by contact and
   snapshot with the window rule), compute labels. Output DLO/DMO `Churn_PIT_Training_Set__dlm`
   with primary key `contact_id || '_' || snapshot_date`. Schedule it monthly on the 2nd, after
   the Salesforce stream has refreshed.
3. **Scoring transform** `Churn_PIT_Scoring_Set`: identical SQL with a single snapshot = run date
   and no label columns. Same column names and types as the training DMO; Model Builder
   requires that.
4. **Sanity checks on the training DMO before training** (run from `sf data query`):
   - rows per snapshot roughly flat at 7,000 to 8,000; positive rate 12 to 18% every month;
   - no row where any feature's underlying max date exceeds its snapshot (add a `max_feature_date`
     audit column in the transform and assert `<= snapshot_date`);
   - univariate AUC of `tenure_days` against `label_60` must come out near **0.32** (shorter tenure,
     higher churn), not 0.65. If it is above 0.5 the label or the book filter is wrong.

Skeleton for one feature CTE (Data Cloud SQL; adapt names after a `SELECT FIELDS(ALL) ... LIMIT 1`):

```sql
WITH cal AS (SELECT snapshot_date FROM Churn_Snapshot_Calendar__dlm),
book AS (
  SELECT c.Id__c AS contact_id, cal.snapshot_date, c.CreatedDate__c, c.Cancel_Date__c
  FROM Contact__dlm c CROSS JOIN cal
  WHERE c.CreatedDate__c <= cal.snapshot_date
    AND (c.Cancel_Date__c IS NULL OR c.Cancel_Date__c > cal.snapshot_date)
),
nonpay AS (
  SELECT b.Contact__c AS contact_id, cal.snapshot_date,
         COUNT(CASE WHEN b.Nonpay_Cancel_Notice_Created_At_c__c > cal.snapshot_date - INTERVAL '90' DAY THEN 1 END) AS nonpay_notices_90d,
         MAX(b.Nonpay_Cancel_Notice_Created_At_c__c) AS last_notice
  FROM Bill__dlm b CROSS JOIN cal
  WHERE b.Nonpay_Cancel_Notice_Created_At_c__c <= cal.snapshot_date
  GROUP BY b.Contact__c, cal.snapshot_date
)
SELECT book.contact_id, book.snapshot_date,
       DATEDIFF(day, book.CreatedDate__c, book.snapshot_date) AS tenure_days,
       COALESCE(nonpay.nonpay_notices_90d, 0) AS nonpay_notices_90d,
       CASE WHEN book.Cancel_Date__c > book.snapshot_date
             AND book.Cancel_Date__c <= book.snapshot_date + INTERVAL '60' DAY THEN 1 ELSE 0 END AS label_60
FROM book LEFT JOIN nonpay USING (contact_id, snapshot_date);
```

## Step 6. Train in Einstein Studio (Model Builder)

1. New model, "Build from scratch", data source `Churn_PIT_Training_Set__dlm` **filtered to
   snapshot_date <= 2026-04-01** (save the filter as a segment or a second transform output,
   `Churn_PIT_Training_Set_Train__dlm`). Goal: predict `label_60`, type binary classification,
   maximise the "1" class.
2. Exclude from the feature list: `contact_id`, `snapshot_date`, `label_90`, `reason`, any audit
   column. Everything else in step 4 stays in.
3. Leave the algorithm on auto (XGBoost). No class weighting needed at 15% positives.
4. Train. Note the reported AUC but do not trust it: Model Builder's internal split is random
   across rows, so the same customer appears in several snapshots on both sides.
5. Run a prediction job against the held-out snapshots (2026-05-01 through 2026-08-01) into
   `Churn_PIT_Holdout_Scores__dlm`.

## Step 7. Validate on the holdout before anyone sees the score

Pull `Churn_PIT_Holdout_Scores__dlm` joined to `label_60` and `reason`, and run the same tests as
the 2026-10-16 report (the AUC and decile code in `scripts/churn_score_validation.py` applies
unchanged):

| Test | Pass line |
|---|---|
| Overall AUC on holdout, 60-day | >= 0.72, and at least 0.04 above tenure alone on the same rows |
| AUC within each tenure bucket | >= 0.62 in every bucket, including 1-2y where both current models are at 0.50 |
| AUC by reason | Non-pay >= 0.75; Company Cancel >= 0.70; voluntary >= 0.60 (the one both models miss today) |
| Decile cancel rates | Monotonic top to bottom; top decile >= 2.5x base |
| Calibration | Mean predicted probability within 2 points of observed rate in each decile |
| Month-to-month stability | Top-decile membership overlap >= 60% between consecutive snapshots |

If voluntary churn still sits near 0.5, the term-age features are the missing piece; go back to
step 4 and get real term dates rather than derived ones.

## Step 8. Deploy and keep the old score until proven

1. Write the production prediction job to a new Contact field, `Churn_Risk_Score_PIT__c`
   (probability times 100, two decimals), not over `Normalized_Churn_Risk_Score__c`. Run it on
   the 1st, after the scoring transform.
2. **Enable field history on the new field** before the first write. Contact had 18 tracked
   fields changing in the last 30 days against a limit of 20; confirm the real count in Setup
   and retire one if needed.
3. Set bands from the scoring run's distribution, not 67/34: High = top decile, Moderate = next
   two deciles. Publish the cut points with the batch so the journey and `Customer_Persona__c`
   use the same numbers.
4. Run two production batches, re-validate each with the script, then switch
   `Customer360PersonaBatch`, the Wave dataset and the Churn Risk activation journey to the new
   field in one change. Stop the old prediction jobs after that.

## Step 9. Monthly after go-live

- Day 2: training transform appends last month's snapshot; label window for the newest
  snapshot is still open, so training uses snapshots at least 60 days old.
- Quarterly: retrain on all closed snapshots, repeat step 7, promote only if it beats the live
  model on the same holdout.
- Each batch: append the raw-by-batch row with `scripts/churn_score_validation.py` and watch
  the within-tenure AUC. A drop below 0.60 is the signal that something upstream changed
  (a stream stopped, a field was repurposed) before it is a modelling problem.
