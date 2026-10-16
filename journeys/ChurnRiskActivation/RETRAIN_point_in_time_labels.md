# Runbook: retrain the churn model on voluntary churn with point-in-time labels

Companion to `2026-10-16_churn_score_validation.md`. Revised 2026-10-16 after Insurance
(Jennifer Kellett, with Sandy) chose option 2 from the DS-3265 thread: **retrain the churn
model without non-pay**, so the score targets voluntary churn and credit-based signals
(Payment Stability Score, credit score, prior-coverage lapse) stay out of retention targeting.
Insurance is to be consulted on retention-strategy work while the book is reset.

Two things change versus the old model, and both are label-side:

1. Every row is a customer *as of a date*; the label is what they did in the 60 days after.
   Nothing dated after the snapshot may appear in a feature.
2. The positive class is **preventable voluntary cancellation only**. Non-pay, company
   cancels and unpreventable exits are censored, not negatives.

Sources in Data Cloud today: Contact via the Salesforce stream (`CreatedDate`, `Cancel_Date__c`,
`Cancellation_Reason__c`, term and renewal fields), `ssot__EmailEngagement__dlm`,
`MobileApp_c_00D3h0000068eod__dlm`, `Zen_Desk_Ticket_Gold__dlm`, `Forsta_Survey_Response__dlm`.
`Bill__dlm` exists but is **not used** in this design (see step 4). Driving stats
(`Monthly_Driving_Stat__c`) are not a DMO yet; stream them, because telematics savings and
score trend are the strongest non-payment signals available.

## Why the label has to change, in numbers

2026 cancellations through Oct 14, whole book (7,765):

| Reason group | Count | Share | Treatment |
|---|---|---|---|
| Non-payment of premium (+ "Unable to make next months payment") | 3,375 | 43% | censored |
| Company Cancel | 1,572 | 20% | censored |
| Preventable voluntary: Due to high premium, Replacement of insurance carrier, Insured request - other, App issue / UX, poor service | 2,148 | 28% | **positive** |
| Unpreventable voluntary: Sold vehicle, No longer driving, Moved out of state, Total loss, Moved to a new residence | 670 | 9% | censored |

Preventable voluntary runs about 230 a month, so a 60-day label gives roughly a 6% positive
rate on a 7,500-contact book. Both existing models score 0.51 AUC on this class; it is the
hard one, and it is now the only one.

## Step 0. Prototype locally first

Build the training set with `sf data query` and fit a logistic regression or gradient boosting
before touching Data Cloud. The baseline to beat is tenure alone on the voluntary label; compute
it on the first pull and write it down. `scripts/churn_score_validation.py` has the Contact and
history pulls; add the email, app and ticket pulls.

## Step 1. Snapshot calendar

- Snapshots on the 1st of every month from **2024-07-01** through 2026-08-01 (26 snapshots).
  The positive class is small, so go back as far as `Cancel_Date__c` and
  `Cancellation_Reason__c` are populated; check both before 2025.
- Horizon: 60 days primary, 90 days as a second column.
- Holdout by time: train on snapshots through 2026-04, validate on 2026-05 through 2026-08.

## Step 2. Active book at snapshot S

```
CreatedDate <= S
AND (Cancel_Date__c IS NULL OR Cancel_Date__c > S)
AND policy evidence dated <= S   -- first invoice date or term effective date, whichever is streamed
```

Do not use `PolicyStatus__c`, `canceled__c`, `Pending_Cancel_Flag__c`, `Policy_Status_Policy__c`
or `Customer_Persona__c`: current values, they would admit the future. Known gap:
`Cancel_Date__c` keeps only the latest cancellation, so re-purchasers look continuously active.

## Step 3. Labels and censoring

```
cancel_in_window = Cancel_Date__c > S AND Cancel_Date__c <= S + 60 days
label_60 = 1   if cancel_in_window AND Cancellation_Reason__c in PREVENTABLE_VOLUNTARY
label_60 = 0   if NOT cancel_in_window                       -- survived the window
row dropped    if cancel_in_window AND reason in (NONPAY, COMPANY, UNPREVENTABLE, blank)
```

Censoring (dropping) is deliberate: a customer cancelled for non-pay on day 20 never had the
chance to leave voluntarily, and calling them "stayed" teaches the model that non-pay
behaviour predicts loyalty. Keep `reason` as a column for evaluation only.

Drop the old training set's 55,020 all-time cancellation rows entirely.

## Step 4. Features, all dated strictly before S

**Excluded on purpose:** every payment-derived field. No non-pay notices, late-payment rates,
days past due, invoice counts, Payment Stability Score, credit score, prior-coverage lapse.
Two reasons: the label no longer needs them, and a score built on them would reconstruct the
credit-based gate Insurance wants kept out of targeting. If voluntary AUC falls short in
step 7, the only payment feature worth a compliance conversation is the 180-day late rate;
do not add it without sign-off.

| Group | Feature | Source and rule |
|---|---|---|
| Tenure | `tenure_days`, `tenure_bucket` | `S - CreatedDate`; buckets <6mo, 6-12mo, 1-2y, 2y+. Still the strongest single signal. |
| Renewal | `days_to_term_end`, `days_since_renewal_offer`, `renewal_rate_change_pct` | "Due to high premium" and "Replacement of carrier" are 78% of the positive class, and both happen around renewal. Contact holds `Current_Term_Expiration_Date__c`, `Renewal_Offer_Date__c`, `Policy_Renewal_Rate__c`, `Term_Renewal_Rate__c`, `Yesterday_Renewal_Rate_Increase_PCT__c` as **current values**; turn on field history or stream term history so they can be rebuilt as of S. Without this the model will not see voluntary churn. |
| Savings | `telematics_discount`, `savings_per_month`, `lifetime_savings_at_S` | Discount and savings fields; point-in-time needs driving cycles streamed. |
| Driving | `trips_per_month_last_cycle`, `weeks_since_last_trip`, `score_trend_3cycles` | `Monthly_Driving_Stat__c` once streamed, cycles with end date <= S. A falling score erodes the discount, which precedes "high premium" exits. |
| Email | `email_opens_30d`, `email_opens_90d`, `email_clicks_90d`, open/sent ratio | `ssot__EmailEngagement__dlm`, engagement date <= S. |
| App | `app_events_30d`, `app_events_90d`, `days_since_last_app_event` | Mobile app DMO on `Account_Id__c = Contact.Account_Id2__c`. |
| Support | `tickets_90d`, `days_since_last_ticket`, `ticket_type_last` | `Zen_Desk_Ticket_Gold__dlm`, created <= S. Keep billing-type tickets as a count only; do not pull payment status from them. |
| Survey | `nps_latest_before_S`, `days_since_nps` | `Forsta_Survey_Response__dlm`. |
| Household | `policies_in_household_at_S` | Count of active contacts on the same Account at S. |
| Claims | `claim_in_180d` | Only if a claims object is streamed; `Claim_Flag__c` on the old set was a current value. |

Never include: `Cancellation_Reason__c`, `canceled__c`, `Cancel_Date__c`, `Pending_Cancel_Flag__c`,
`PolicyStatus__c`, `Customer_Persona__c`, either existing churn score, anything timestamped after S.

Window rule everywhere: `event_date > S - N days AND event_date <= S`.

## Step 5. Build in Data Cloud

1. **Calendar**: CSV data stream `Churn_Snapshot_Calendar` with one row per snapshot date.
2. **Batch Data Transform** `Churn_PIT_Training_Set`: cross join calendar to Contact, apply step 2,
   left-join one CTE per feature source with the window rule, compute `cancel_in_window`,
   `label_60`, `label_90`, `reason`, and a `censored` flag; filter `censored = 0` in a final
   step (keep the unfiltered output as a second DMO for audit). Primary key
   `contact_id || '_' || snapshot_date`. Schedule monthly on the 2nd.
3. **Scoring transform** `Churn_PIT_Scoring_Set`: same SQL, one snapshot = run date, no labels,
   **no censoring** (everyone active is scored; the journey decides who enters).
4. **Checks before training** (from `sf data query`):
   - rows per snapshot flat near 7,000; positives 5 to 8% every month;
   - audit column `max_feature_date <= snapshot_date` on every row;
   - tenure univariate AUC against `label_60` well below 0.5 (shorter tenure, more churn);
   - no payment-derived column in the output schema. Grep the column list.

Skeleton (adapt names after `SELECT FIELDS(ALL) FROM <dmo> LIMIT 1`):

```sql
WITH cal AS (SELECT snapshot_date FROM Churn_Snapshot_Calendar__dlm),
book AS (
  SELECT c.Id__c AS contact_id, cal.snapshot_date, c.CreatedDate__c, c.Cancel_Date__c, c.Cancellation_Reason__c
  FROM Contact__dlm c CROSS JOIN cal
  WHERE c.CreatedDate__c <= cal.snapshot_date
    AND (c.Cancel_Date__c IS NULL OR c.Cancel_Date__c > cal.snapshot_date)
),
app AS (
  SELECT m.Account_Id__c AS account_uuid, cal.snapshot_date,
         COUNT(CASE WHEN m.Event_Timestamp_UTC__c > cal.snapshot_date - INTERVAL '90' DAY THEN 1 END) AS app_events_90d,
         MAX(m.Event_Timestamp_UTC__c) AS last_app_event
  FROM MobileApp_c_00D3h0000068eod__dlm m CROSS JOIN cal
  WHERE m.Event_Timestamp_UTC__c <= cal.snapshot_date
  GROUP BY m.Account_Id__c, cal.snapshot_date
),
labelled AS (
  SELECT book.*,
    CASE WHEN Cancel_Date__c > snapshot_date AND Cancel_Date__c <= snapshot_date + INTERVAL '60' DAY THEN 1 ELSE 0 END AS cancel_in_window,
    CASE WHEN Cancellation_Reason__c IN ('Due to high premium','Replacement of insurance carrier','Insured request - other',
                                         'App issue / UX','Due to poor customer service','Due to poor claims service') THEN 1 ELSE 0 END AS preventable
  FROM book)
SELECT contact_id, snapshot_date,
       DATEDIFF(day, CreatedDate__c, snapshot_date) AS tenure_days,
       COALESCE(app.app_events_90d, 0) AS app_events_90d,
       CASE WHEN cancel_in_window = 1 AND preventable = 1 THEN 1 ELSE 0 END AS label_60,
       CASE WHEN cancel_in_window = 1 AND preventable = 0 THEN 1 ELSE 0 END AS censored,
       Cancellation_Reason__c AS reason
FROM labelled LEFT JOIN app ON ... ;
```

## Step 6. Train in Einstein Studio (Model Builder)

1. New model from `Churn_PIT_Training_Set__dlm` filtered to `snapshot_date <= 2026-04-01` and
   `censored = 0`. Goal: predict `label_60`, binary classification, maximise class 1.
2. Exclude `contact_id`, `snapshot_date`, `label_90`, `reason`, `censored`, audit columns.
3. Algorithm on auto. At 6% positives consider the class-weight option if the top decile is
   under-populated; otherwise leave it.
4. Ignore the in-tool AUC (random row split leaks customers across snapshots).
5. Prediction job on the holdout snapshots (2026-05 through 2026-08) into
   `Churn_PIT_Holdout_Scores__dlm`.

## Step 7. Validate on the holdout

Join holdout scores to `label_60`, `reason`, tenure. Use the AUC and decile code from
`scripts/churn_score_validation.py`.

| Test | Pass line |
|---|---|
| Overall AUC, 60-day preventable voluntary label | >= 0.68 and at least 0.05 above tenure alone on the same rows (both current models: 0.51) |
| AUC within each tenure bucket | >= 0.60 in all four, including 1-2y |
| AUC by sub-reason | High premium >= 0.70; Replacement of carrier >= 0.65; Insured request >= 0.60 |
| Decile cancel rates | Monotonic; top decile >= 2.5x base |
| Calibration | Mean predicted probability within 1 point of observed per decile (base is ~6%) |
| Stability | Top-decile overlap >= 60% between consecutive snapshots |
| **Compliance proxy check** | Spearman between the new score and Payment Stability Score (once the DS-3265 field sync lands) and credit score < 0.2; share of contacts with a non-pay notice in the prior 90 days inside the top decile within 5 points of their book share. If either fails the score is a credit proxy and goes back to step 4. |

If "high premium" stays below 0.65, the renewal-rate features are not point-in-time yet. Fix
the data, not the model.

## Step 8. Deploy

1. Production prediction job writes to a new field `Voluntary_Churn_Risk_Score__c`
   (probability x 100, two decimals). Leave `Normalized_Churn_Risk_Score__c` and
   `Churn_Risk_Score__c` untouched until cutover. Run on the 1st after the scoring transform.
2. Enable field history on the new field **before** the first write (Contact showed 18 tracked
   fields changing in the last 30 days against a limit of 20; confirm in Setup).
3. Bands from the distribution: High = top decile, Moderate = next two. Publish the cut points
   with the batch.
4. Journey entry filter belongs to the journey, not the score: Insurance has not yet said
   whether chronic non-payers are in or out of retention, so score everyone and keep the
   exclusion (recent non-pay notice) as a journey criterion that can be toggled.
5. Two production batches, re-validate each, then switch `Customer360PersonaBatch`, the Wave
   dataset and the Churn Risk activation journey in one change. Retire the old prediction jobs.

## Step 9. Monthly after go-live

- Day 2: training transform appends last month's snapshot; train only on snapshots with a
  closed 60-day window.
- Each batch: append the raw-by-batch row with `scripts/churn_score_validation.py`, now against
  the voluntary label, and re-run the compliance proxy check.
- Quarterly retrain; promote only if it beats the live model on the same holdout.

## Open questions for Insurance

1. Are chronic non-payers (two or more notices in 12 months) excluded from retention outreach
   altogether, or only from the churn journey? Determines the journey entry filter in step 8.4.
2. Is a 180-day late-payment rate acceptable as a feature if the compliance proxy check in
   step 7 passes, or is any payment-derived input off the table?
3. Does "Insured request - other" count as preventable? It is 4% of cancels and the reason text
   is unstructured; it is in the positive class here pending their view.
