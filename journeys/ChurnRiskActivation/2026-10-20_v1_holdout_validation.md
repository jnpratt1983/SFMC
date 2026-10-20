# Voluntary Churn 60d v1: holdout validation (2026-10-20)

**Verdict: v1 does not pass.** Overall AUC 0.579 on the May to August 2026 holdout against a
pass line of 0.68 and a tenure-only baseline of 0.560. It is not a usable general churn score.
Two things in it are usable now: on the renewal window, the rows the journey targets, it
reaches 0.611 with a top decile that cancels at 2.5x the base rate, and it learned the price
signal, since 61% of that top decile are customers offered a $25-plus monthly increase. A
one-line rule on the offer amount matches it there.

Model: Einstein Studio Model Builder, CatBoost, 21 point-in-time predictors, trained on
`Churn_PIT_Train__dlm` (179,196 rows, 12,408 positives, snapshots 2024-07 to 2026-04). Scored
`Churn_PIT_Holdout__dlm` (25,419 rows, 1,269 positives, 4.99%) into
`Voluntary_Churn_Holdout_Scores__dlm`. Script: `scripts/validate_holdout.py`.

## Pass lines

| Test | Pass line | Result | |
|---|---|---|---|
| Overall AUC | >= 0.68 and >= tenure + 0.05 | 0.579 ± 0.009 (tenure 0.560) | fail |
| AUC within tenure bucket | >= 0.60 in all four | <6mo 0.611, 6-12mo 0.536, 1-2y 0.565, 2y+ 0.545 | fail |
| AUC by reason | high premium >= 0.70, carrier >= 0.65, insured request >= 0.60 | 0.581, 0.568, 0.604 | fail |
| Deciles | monotonic, top >= 2.5x base | top 1.77x, not monotonic (decile 3 above decile 2) | fail |
| Compliance proxy | non-pay share in top decile near book share | top decile 15.8% vs rest 24.9% (90 d); 23.1% vs 37.6% (365 d) | pass, see note |

Deciles, top first: 8.85%, 5.27%, 5.98%, 5.15%, 4.48%, 5.00%, 4.09%, 4.25%, 3.86%, 2.99%
(base 4.99%). Scores run 0 to 90 and are not calibrated probabilities (top decile mean score 61).

## The renewal window is where it works

Holdout rows with a renewal offer issued in the 60 days before the snapshot (n = 5,601, 4.82%
positive), which is the population `RE_ChurnRetention` enters at T-45:

| Ranking | AUC | Top decile cancel rate |
|---|---|---|
| Model score | 0.611 | 12.0% (2.48x) |
| Offer change in dollars alone | 0.614 | |
| Tenure alone | 0.554 | |

Cancel rate by offered change: decrease 3.8%, +$0-10 3.0%, +$10-25 4.5%, **+$25 or more 13.6%**
(n = 602). The model's top decile on this subset is 61% "+$25 or more" rows against 10.7%
overall, so it found the signal; it has nothing else strong enough to add to it.

## What the model leaned on, and a feature to remove

Top contributor on 15% of rows is `Email_Sends_90d`. Sends are not customer behaviour: they
count the non-pay journey's reminder emails, so they encode billing cadence and non-pay
episodes. On the holdout, contacts with zero sends had a 2% chance of a real non-pay notice in
the prior 90 days and 0.2 bills; six or more sends, 82% and 4.3 bills. More sends means lower
voluntary churn in this label, because non-pay leavers are censored, so the model uses send
count as a "safe" marker. It points away from non-payers, which is why the compliance proxy
check passes, but it is still a payment-derived input by another name and comes out in v2,
along with the open and click counts that scale with it. Keep `Email_Open_Rate_90d` only.

Note on the compliance check: the top decile has fewer non-pay histories than the rest, not
more. That is the censoring design working, not targeting bias, but it also means the score
systematically down-ranks customers with non-pay history for voluntary churn. Insurance should
know that before it is used for anything beyond this journey.

Trap for anyone repeating the check: `Bill.Non_Pay_Cancel_Date` is populated on every bill (it
is the date a cancellation would take effect), so it is not a notice. Use the `Non_pay` flag on
the bill, or the notice timestamp cast from text.

## Why it is weak, honestly

The strongest single features available are weak: tenure 0.56, email opens 0.53, app events
0.50, tickets 0.51. The offer signal is strong but exists for 22% of rows, and only for the last
nine snapshots of training (offers begin 2025-11). Email coverage is sparse for 2024-25
snapshots and tickets start in 2025, so two of the four behavioural groups are near-empty for
most of the training history. A model cannot be better than its inputs; this one is roughly as
good as those inputs allow.

## What to do

1. **Journey entry, now.** Do not key entry on this score. Use the renewal-window rule the data
   supports: term ends in 45 days and the offered change is +$25 a month or more, plus the
   model's top decile among offer-covered rows for the Moderate band. Expected entrants: the
   +$25 group is about 10% of offers, roughly 65 a month, cancelling at 13.6% in the following
   60 days; the model top decile adds about 55 a month at 12%. Small, but it is the highest-yield
   population in the book and it is exactly where the price conversation belongs.
2. **v2, renewal-anchored.** Train only on offer-covered rows (snapshots 2025-12 onward) with
   offer change in dollars and percent, rating version, days since offer, tenure, term position,
   app recency, open rate, tickets. Drop send, open and click counts. Fewer rows (about 8,000
   training, 400 positives) but the right population. Pass line for this version: AUC >= 0.66 on
   the holdout's offer subset and top decile >= 3x.
3. **Data to add before v3.** Telematics discount and savings trajectory (needs driving stats
   streamed or Contact field history), real term dates once they have history, and the full
   email engagement history if the 2024-25 IER gap can be backfilled from Marketing Cloud.
4. **Do not retire the planning numbers.** The test plan's volumes assumed the Moderate and
   High bands of a working score; the rule-based entry is roughly 120 a month, so the
   randomized read on churn takes longer than the 8 to 10 months estimated. Re-run the power
   table once v2's lift is known.
