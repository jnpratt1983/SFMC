# Voluntary Churn 60d v2: holdout validation (2026-10-20, evening)

**Verdict: better than v1 on every line, still short of the pass lines.** Overall AUC 0.599 against
0.579 for v1 and a tenure baseline of 0.560; deciles are now monotonic; the under-six-months bucket
passes; the renewal window is unchanged at 0.616, where a one-line rule on the offer amount still
matches the model. The general score is not ready to drive targeting. The renewal-window rule plus
the model's top decile among offer-covered customers is ready, and is the recommended journey entry.

What changed between v1 and v2: email features keyed on the customer's address (recovering the
sends that sat on the lead record), nine driving features from `Monthly_Driving_Stat__c`, state as a
feature, `Driver_Role` removed (label leakage), send/open/click counts removed except `Email_Opens_90d`,
which was left selected by mistake. Same train and holdout windows, same labels, CatBoost, 26 variables.
Training-page cross-validation AUC 0.634 (random row split, optimistic); holdout 0.599.

## Pass lines, v1 vs v2

| Test | Pass line | v1 | v2 | |
|---|---|---|---|---|
| Overall AUC | >= 0.68 and >= tenure + 0.05 (0.610) | 0.579 | **0.599** ± 0.009 | fail, by 0.011 on the tenure line |
| Within tenure | >= 0.60 each | 0.611 / 0.536 / 0.565 / 0.545 | **0.638** / 0.575 / 0.560 / 0.565 | only <6mo passes |
| By reason: high premium / carrier / insured request | 0.70 / 0.65 / 0.60 | 0.581 / 0.568 / 0.604 | 0.607 / 0.579 / 0.609 | fail |
| Deciles | monotonic, top >= 2.5x | top 1.77x, not monotonic | top **1.91x, monotonic** | fail on lift |
| Compliance proxy | top decile non-pay share near book share | 15.8% vs 24.9% (below) | 29.3% vs 23.4% (above, +5.9 pts at 90 d; 39.3% vs 35.8% at 365 d) | borderline, see note |
| By state | | | AZ 0.595, RI 0.604 | consistent |

v2 deciles, top first (base 4.99%): 9.52, 6.45, 5.35, 5.31, 5.00, 4.01, 3.93, 3.70, 3.89, 2.75.

## Renewal window (offer issued in the 60 days before the snapshot; n = 5,601, 4.82% positive)

| Ranking | AUC | Top decile |
|---|---|---|
| v2 model | 0.616 | 12.0%, 2.48x, 62% of it "+$25 or more" offers |
| v1 model | 0.611 | 12.0%, 2.48x |
| Offer change in dollars alone | 0.614 | |
| Tenure alone | 0.554 | |

**Entry rule tested on the holdout:** "+$25 or more" OR model top decile among offer-covered
customers flags 14.6% of the renewal window (816 of 5,601), who cancel at 11.4% in the next 60 days
and account for 34% of the window's preventable cancellations. That is the journey's entry
population: about 120 to 140 contacts a month in AZ and RI.

## What the model is doing

- Driving data is the top contributor family on 35% of rows (latest score, latest discount, days
  since last cycle) and app recency on 12%. Where there is no driving data (52% of rows) or no app
  event (27%), the model scores higher and those rows do cancel more (5.4% vs 4.6%, 5.6% vs 4.8%).
  Absence is observable at scoring time, so this is legitimate, but it means half the book is scored
  mostly on tenure, term position and the absence itself.
- The renewal-offer features are near the bottom of the importance list because offers exist on
  22% of rows and only in the last nine training snapshots. The model still finds them where they
  exist (top decile of the window is 62% large increases), it just cannot use them elsewhere.
- **Compliance note.** v2's top decile carries slightly more non-pay history than the rest (29.3%
  vs 23.4% with a real notice in the prior 90 days), the opposite of v1. Not a payment feature at
  work, but the retained `Email_Opens_90d` scales with the non-pay reminder cadence and should be
  dropped in v3, after which this check must be re-run. The plan's threshold is 5 points; v2 is at
  5.9.

## What to do

1. **Journey entry: use the renewal-window rule now.** Term ends in 45 days and (offered increase
   >= $25 a month, or v2 score in the top decile among offer-covered customers). Compliance-approved
   50/50 split applies inside it. This does not wait on a passing general score.
2. **v3: train on the renewal window only.** Views `ChurnPITTrainV3` / `ChurnPITHoldoutV3` restrict
   to uncensored rows with an offer in the prior 60 days (about 8,000 training rows, 400 positives;
   5,601 holdout rows, 270 positives). Drop `Email_Opens_90d`. Pass line for v3: AUC >= 0.66 on the
   holdout window and top decile >= 3x; it only has to beat the $25 rule (0.614) by a clear margin
   to be worth deploying over it.
3. **Keep v2 as the production general score for reporting, not targeting**, scored monthly into
   the Contact field with its band, so the persona batch and dashboards have a point-in-time score
   that is honest about what it is. Replace with v3 or later when a version passes.
4. **Data still missing for a stronger general score:** Contact field history on savings and
   discount (so those become features for every snapshot), and the 2024-25 email gap, which the
   address rekey only partly fills.
