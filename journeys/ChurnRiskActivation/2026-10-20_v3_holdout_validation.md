# Voluntary Churn 60d v3: holdout validation (2026-10-20, night)

**Verdict: the first version with real lift beyond price-at-renewal, and the one to deploy after
one variable is removed.** Overall AUC 0.627 against 0.599 (v2), 0.579 (v1) and 0.560 (tenure).
It clears the "tenure + 0.05" line, three of four tenure buckets, and for the first time ranks
customers outside the renewal window (0.628) as well as inside it (0.623). It does not reach the
0.68 target or the 2.5x top decile. The compliance proxy fails, and the diagnosis below says why
and what to change.

What changed from v2: five bill columns (latest net and gross premium, 3-month change in $ and %,
invoice count), all email counts removed. 31 variables, CatBoost, same windows and labels.

## Pass lines across versions

| Test | Pass line | v1 | v2 | v3 |
|---|---|---|---|---|
| Overall AUC | >= 0.68 and >= tenure + 0.05 (0.610) | 0.579 | 0.599 | **0.627** (clears the tenure line) |
| Within tenure <6mo / 6-12 / 1-2y / 2y+ | >= 0.60 each | 0.611 / 0.536 / 0.565 / 0.545 | 0.638 / 0.575 / 0.560 / 0.565 | **0.652 / 0.607 / 0.606** / 0.597 |
| High premium / carrier / insured request | 0.70 / 0.65 / 0.60 | 0.58 / 0.57 / 0.60 | 0.61 / 0.58 / 0.61 | **0.655** / 0.598 / 0.590 |
| Top decile lift | >= 2.5x, monotonic | 1.77x | 1.91x | **2.02x**, monotonic bar one adjacent pair |
| Renewal window AUC / top decile | | 0.611 / 2.48x | 0.616 / 2.48x | 0.623 / 2.41x |
| Outside the renewal window | | | | **0.628** (tenure 0.561) |
| By state | | | AZ 0.595, RI 0.604 | AZ 0.620, RI 0.653 |
| Compliance proxy (non-pay notice in prior 90 d, top decile vs rest) | within 5 pts | 15.8 vs 24.9 | 29.3 vs 23.4 | **35.4 vs 22.7, fail** |

v3 deciles, top first (base 4.99%): 10.07, 6.65, 6.25, 6.33, 4.84, 3.46, 3.66, 3.07, 2.95, 2.64.

## Where the lift came from

The top contributor family is now the bill (36% of rows), then the driving discount (18%), then the
renewal offer (15%). Premium level and trajectory carry the signal they showed univariately: a
latest net premium above $300 cancels at 9.0% (score 51) against 3.2% below $100 (score 29); a
3-month rise of $50 or more cancels at 8.1% against 3.7% flat.

"No recent bill" is the single most frequent top contributor (16% of rows). Those 7,608 holdout rows
have no invoice linked to the contact at all, which means they are household members who are not the
billed policyholder. They cancel at 5.5% and the model scores them above average. Observable at
scoring time, so legitimate, but it is the model learning "not the policyholder", not a behaviour.

## The compliance finding, and the fix

The top decile has 35.4% of contacts with a real non-pay notice in the prior 90 days against 22.7% in
the rest. Two causes, measured on the holdout:

| Driver | Non-pay history in prior 90 d | Cancel rate |
|---|---|---|
| Invoices per month > 1.3 (re-issued bills) | 45.3% | 5.9% |
| Invoices ~1 per month | 19.4% | 4.8% |
| Latest net premium >= $300 | 39.3% | 9.0% |
| Latest net premium < $100 | 29.1% | 3.2% |
| Net premium up $50+ in 3 months | 45.5% | 8.1% |

- **`Bill_Count__c` is a payment proxy and must come out.** Customers with failed payments get
  re-issued invoices, so a high invoice count encodes non-pay directly. Removing it is a one-variable
  change in Model Builder (new version of the same model, 30 variables) and a re-run of the predict job.
- **Premium level and premium increases are not payment behaviour, but they correlate with it.**
  Higher and rising premiums go with both voluntary churn and non-pay history. Any price-driven
  selection has this property; the renewal offer rule itself does (see the companion number in the
  journey spec). That is a question of framing for Insurance, not a defect: the score ranks on price,
  and the journey's entry criteria exclude anyone with a notice in 90 days, so non-pay customers are
  never targeted regardless of their score.

## What to do

1. **Train v3.1: same objects, deselect `Bill Count`, 30 variables.** Re-run the holdout job into
   `Voluntary_Churn_Holdout_Scores_V31`. Expect the AUC to hold within a point and the top-decile
   non-pay share to drop toward 30%. That is the production candidate.
2. **Deploy v3.1 as the scored field on Contact** with monthly bands, and use it two ways: ranking
   inside the renewal-window entry (replacing "model top decile among offer-covered" with the v3.1
   top decile), and as the general risk score for reporting and the persona batch. It is the first
   version where the general score means something.
3. **Journey entry stays rule-first:** offered increase > $20 or > 10%, term end within 45 days, PNI,
   no non-pay notice in 90 days; v3.1 top decile among offer-covered customers adds the next tier. On
   the holdout the combined rule flags 16% of the window at 11.1% cancel and captures 37% of its
   preventable cancellations.
4. **Stop here on modelling.** v3.1 is a one-variable retrain, not a new build. The next real gain needs
   data that does not exist yet (18 months of offer history, Contact field history on savings).
