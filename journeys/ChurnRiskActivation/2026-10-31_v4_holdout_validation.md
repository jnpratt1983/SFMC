# Voluntary Churn 60d v4: holdout validation (2026-10-31, night)

**Verdict: v4 beats v3 on identical rows and should replace it, once the flow-computed earned
fraction is confirmed populating in production.** AUC 0.639 against 0.628 for v3 on the same 24,450
holdout rows (paired bootstrap 95% interval for the gain +0.003 to +0.020; v4 ahead in 200 of 200
resamples). Top decile 11.29% (2.28x) against 10.02% (2.03x). v4 is ahead in all four tenure buckets.
It still does not reach the 0.68 target or the 2.5x top decile.

What changed from v3: 13 savings-history columns from `Savings_History__c` (ANA-6320 backfill plus the
`Savings_History_Capture` flow) and `Drv_Trips_Change_Pct__c`; current-value `Lifetime_Savings__c` and
`Telematics_Discount__c` dropped; rows meeting the Insurance driving-decline rule removed from train and
holdout by the V4 views. 45 variables, CatBoost, same windows and labels. Model Builder's own
cross-validation said 0.673 (four folds 0.672 to 0.674); as with v3 that figure is inflated by contacts
appearing on both sides of a random split and is not quoted.

## Pass lines across versions

| Test | Pass line | v3 | v4 |
|---|---|---|---|
| Overall AUC (V4 holdout, 24,450 rows, 1,209 positives) | >= 0.68 and >= tenure + 0.05 (0.614) | 0.628 | **0.639** (clears the tenure line) |
| Within tenure <6mo / 6-12 / 1-2y / 2y+ | >= 0.60 each | 0.652 / 0.601 / 0.606 / 0.598 | **0.662 / 0.618 / 0.630 / 0.601** (all four pass) |
| High premium / carrier / insured request | 0.70 / 0.65 / 0.60 | 0.655 / 0.598 / 0.590 | 0.665 / 0.611 / 0.612 |
| Top decile lift | >= 2.5x, monotonic | 2.03x | **2.28x**, monotonic bar deciles 3-4 and 5-6 |
| With recent offer, top decile vs book | informational | | 15.4% vs 21.8% |

v4 deciles, top first (base 4.94%): 11.29, 6.54, 5.19, 5.56, 4.79, 4.62, 3.64, 3.15, 2.70, 1.96.
v3 on the same rows: 10.02, 6.46, 6.26, 6.42, 4.79, 3.35, 3.80, 2.94, 2.86, 2.54.

v4 separates the tails better (top decile up 1.3 points, bottom decile down 0.6) and flattens the
middle. The v3 figures here differ slightly from the 2026-10-20 report (0.627 on 25,419 rows) because
969 driving-decline rows are excluded from the V4 holdout; the labels on the common rows are identical.

## Where the gain came from

Model Builder importance: `Sav_Earned_Latest__c` 9.0% (first), then the bill columns (`Bill_Net_Latest__c`
6.4%, `Bill_Gross_Latest__c` 5.1%, `Bill_Net_Change_3m_Pct__c` 3.9%, `Bill_Count__c` 3.6%), term position,
app recency. Among the savings columns `Sav_Net_Latest__c` 3.1%, `Sav_Standard_Latest__c` 3.0% and
`Sav_Cycles__c` 2.9% also made the top fifteen. On the holdout, `Sav_Earned_Latest__c` is contributor 1
on roughly one row in ten, spread across values from 0 to 0.44, which is the rated-discount gradient
seen univariately (latest rated discount under 10%: 8.7% preventable cancel in 60 days; 40% and over: 4.9%).

## The production dependency

`Sav_Earned_Latest__c` is the earned discount fraction, which the warehouse extract carried but no
Salesforce field holds. `Savings_History_Capture` version 2 (active 2026-11-01) reconstructs it as
Monthly_Driving_Stat earned dollars over the discountable base (discount / rated %). On backfill rows
since 2025-06 the reconstruction is within 0.01 of the extract on 83% and within 0.02 on 88% (median
error 0). Until the first flow rows are checked after the 2026-11-01 batch, treat promotion as conditional.
A recurring feed of the engine's own value from Data Analytics would remove the dependency.

## Promotion steps (when confirmed)

1. `PUT ChurnPITScoringSet` from `transforms/Churn_PIT_Training_Set.scoring.api.json` (already generated with
   the savings branch), run it, re-map the `Churn_Pit_Scoring_Set` DMO so the new columns are visible.
2. Einstein Studio: new predict job `Voluntary Churn 60d v4 - Production Scoring` on the scoring DMO,
   same output shape as v3; deactivate the v3 job once the first v4 batch lands.
3. `scripts/write_back_scores.py` reads the new output; re-derive the High/Moderate cut points from the
   first v4 production batch and copy them into the retention journey's config DE.
4. Re-run this validation monthly on closed snapshots as the checklist says.

Compliance proxy (non-pay history share in the top decile) was not re-run; it needs the Bill join and the
journey's 90-day non-pay exclusion governs targeting either way.
