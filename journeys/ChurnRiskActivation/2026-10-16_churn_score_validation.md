# Is `Normalized_Churn_Risk_Score__c` predicting churn? (2026-10-16)

**Short answer: weakly, and worse than two things we already have.** Scored on 2026-08-22 and
judged against the 1,117 cancellations that followed through 2026-10-14, the normalized score
reaches an AUC of 0.59. Customer tenure alone scores 0.68 and the existing
`Customer_Persona__c = 'Lapse Risk'` flag scores 0.61. Only 99 contacts land in the High band
(>= 67), and 69% of the cancellations sit in the Low band. The cause is the training set: 90% of
its rows are all-time historical cancellations, so the model learned that long-tenured customers
are the ones who cancel, which is backwards for the live book.

Do not launch the Churn Risk activation journey (Predicted Did Cancel V7) on the normalized
bands as they stand. Details, numbers and what to change are below. Everything here is
reproducible with `scripts/churn_score_validation.py`; the tables are in `data/`.

## What the two fields are

| Field on Contact | Source | Coverage | History |
|---|---|---|---|
| `Churn_Risk_Score__c` ("raw") | `Churn_Risk_Score__dlm` (Data Cloud, `ChurnRiskScoreOutput`), values match exactly | 11,906 contacts; 4,407 of them are old cancellations, 7,499 overlap the normalized set | Tracked since 2026-06-28; batches land on the 28th and the 1st |
| `Normalized_Churn_Risk_Score__c` | `Churn_Risk_Score_Output_Normalized__dlm` (`ChurnRiskScoreNormalizedOutput`), values match exactly | 7,508 contacts, all written 2026-10-16 between 16:02 and 19:51 UTC | Not tracked. No history rows exist |

The two scores barely agree with each other (Spearman 0.28). Of the 818 contacts the raw score
calls High, the normalized score calls 35 High and 455 Low. They are different models, not a
rescaling.

## How the normalized model was built (from its Data Cloud training set)

`Churn_Risk_Training_Set_Normalized__dlm` has 61,215 rows, one per contact:

| | Rows | Share |
|---|---|---|
| `Did_Cancel__c = true` | 55,020 | 90% |
| `Did_Cancel__c = false` | 6,195 | 10% |

- **Feature snapshot ~2026-08-11.** `Last_Known_Trip_Date__c` tops out at 2026-08-11, and
  trip date plus `Weeks_Since_Last_Trip__c` lands on 2026-08-10/11 for the bulk of rows.
- **Labels frozen ~2026-08-22.** Contacts who cancelled in July are labelled true (516 of 522);
  contacts who cancelled on or after 2026-08-23 are labelled false (271 in Aug, 363 in Sep,
  163 in Oct). That is what makes the test below out-of-time.
- **The positives are the whole cancellation history,** back to 2020. The negatives are the
  active book on that day. So the label separates "ever cancelled" from "active now", not
  "will cancel" from "will stay". Tenure comes out inverted: `Months_Policy_Active__c` has a
  univariate AUC of 0.35 against the label (longer tenure predicts the *cancelled* label),
  while on the live book shorter tenure is the strongest churn signal there is (see below).
- **The 7,508 scored contacts** are 6,023 training negatives, 42 training positives, and
  1,443 contacts not in the training set at all (mostly customers created in August 2026).
  Two scores repeat suspiciously: 26.59 on 253 contacts and 43.59 on 153, almost all August
  creations. Those look like imputed defaults for contacts with no feature history.

The raw model's training set (`Churn_Score_Training_Set__dlm`) is 11,012 rows with 38%
positives, which is a much saner base rate, but see its own problem under "raw score" below.

## Out-of-time test: normalized score vs cancellations after the snapshot

Population: the 7,489 scored contacts not cancelled by 2026-08-22. Outcome: `Cancel_Date__c`
between 2026-08-23 and 2026-10-14 (1,117 cancellations, 14.9%; 641 within 30 days).
`canceled__c` and `Cancel_Date__c` agree on every one of these contacts.

| Predictor (same population, same outcome) | AUC (SE) | 30-day AUC |
|---|---|---|
| Contact tenure, newer = riskier (`CreatedDate`) | **0.683** (0.009) | 0.687 |
| Raw `Churn_Risk_Score__c` as of 2026-07-01 (pre-recalibration) | 0.624 (0.012) | 0.636 |
| `Customer_Persona__c = 'Lapse Risk'` (yes/no) | 0.606 (0.010) | 0.582 |
| **`Normalized_Churn_Risk_Score__c`** | **0.593** (0.010) | 0.589 |
| Raw `Churn_Risk_Score__c` as of 2026-08-22 | 0.560 (0.011) | 0.554 |

AUC 0.5 is a coin flip; 0.7 is where retention models usually start being worth acting on.

**Deciles are not even monotonic.** Base rate 14.9%.

| Normalized decile | Score range | Cancelled | Lift |
|---|---|---|---|
| 1 (top) | 46.3 - 93.0 | 23.0% | 1.54x |
| 2 | 36.8 - 46.3 | 17.9% | 1.20x |
| 3 | 28.8 - 36.8 | 17.8% | 1.19x |
| 4 | 25.2 - 28.8 | 22.2% | 1.49x |
| 5 | 20.9 - 25.2 | 11.3% | 0.76x |
| 6 - 9 | 8.4 - 20.9 | 10.7 - 13.4% | 0.72 - 0.90x |
| 10 (bottom) | 0.2 - 8.4 | 9.7% | 0.65x |

**The shipped bands (67 / 34) do not fit this score's scale.**

| Band | Contacts | Share of book | Cancelled | Share of all cancellations |
|---|---|---|---|---|
| High (>= 67) | 99 | 1.3% | 29.3% | 3% |
| Moderate (34 - 66) | 1,642 | 21.9% | 19.4% | 29% |
| Low (< 34) | 5,748 | 76.8% | 13.4% | 69% |

A journey keyed on High would reach 99 people and miss 97% of the churn. The top decile cut
(>= 46) is the only threshold with a meaningful lift, and it is still only 1.5x.

**Where the signal actually is.** Split by cancellation reason (positives = that reason,
negatives = did not cancel):

| Reason | Cancellations | Normalized AUC | Raw AUC (Jul 1) |
|---|---|---|---|
| Company Cancel | 205 | **0.747** | 0.568 |
| Non-payment of premium | 541 | 0.590 | **0.718** |
| Customer-initiated (all other reasons) | 371 | 0.511 | 0.521 |

The normalized model is decent at spotting company-initiated cancellations (mostly a
telematics / no-trips signal) and blind to customers who leave on their own. The raw model,
before its July recalibration, was the opposite: good on non-pay, blind on the rest. Neither
model sees voluntary churn.

**Within tenure buckets** the normalized score adds something only for customers under six
months old:

| Tenure at snapshot | Contacts | Cancelled | Normalized AUC | Top 20% vs rest |
|---|---|---|---|---|
| < 6 months | 2,151 | 26.4% | 0.612 | 38.1% vs 23.4% |
| 6 - 12 months | 1,019 | 16.6% | 0.532 | 23.2% vs 15.0% |
| 1 - 2 years | 1,559 | 10.1% | 0.495 | 10.0% vs 10.2% |
| 2+ years | 2,760 | 8.1% | 0.557 | 9.6% vs 7.7% |

Tenure by itself already separates 26% from 8%. For anyone past their first year the score
is noise.

## The raw score, for comparison (rebuilt from field history)

Because `Churn_Risk_Score__c` is history-tracked, it can be rebuilt as of each batch and judged
against the cancellations that followed. Population = scored contacts not yet cancelled on
the batch date.

| Score as of | Horizon | Cancelled | AUC score | AUC tenure | AUC within tenure | High band (>= 67) |
|---|---|---|---|---|---|---|
| 2026-06-28 | 60 d | 17.0% | 0.688 | 0.684 | 0.609 | 494 contacts, 38.9% cancelled |
| 2026-07-01 | 60 d | 16.9% | **0.698** | 0.696 | 0.614 | 490 contacts, 39.4% |
| 2026-07-28 (recalibration) | 60 d | 16.0% | 0.601 | 0.686 | 0.547 | 779 contacts, 31.8% |
| 2026-08-01 | 60 d | 15.9% | 0.595 | 0.678 | 0.541 | 761 contacts, 29.0% |
| 2026-08-28 | 30 d | 9.0% | 0.590 | 0.668 | 0.541 | 775 contacts, 15.1% |
| 2026-09-01 | 30 d | 9.0% | 0.604 | 0.665 | 0.555 | 802 contacts, 17.2% |
| 2026-10-01 | 12 d | 4.7% | 0.674 | 0.674 | 0.626 | 946 contacts, 11.3% |

Three things to take from this. The June/July raw score was genuinely useful: its High band
cancelled at 2.3x the base rate within 60 days. The 2026-07-28 recalibration (mean moved from
33 to 43) made it worse for two months. The 2026-10-01 batch looks recovered, but twelve days
of outcomes is too little to call it. Even at its best the raw score only matched tenure overall
and beat a coin flip by 0.11 inside tenure buckets.

## What to do

1. **Do not key the Churn Risk activation journey on `Normalized_Churn_Risk_Score__c` bands.**
   If something has to launch now, the least-bad targeting from this data is customers under
   six months tenure in the normalized top quintile (38% cancel in the next eight weeks), or
   the raw score's High band after confirming the October batch holds up.
2. **Retrain with point-in-time labels.** Snapshot the active book monthly, label each contact
   on whether they cancel in the following 60 or 90 days, keep the survivors as negatives, and
   drop the all-time cancellation rows. That alone fixes the inverted tenure signal. Tenure,
   term age, and recent non-pay notices should be explicit features.
3. **Re-cut bands from the score distribution, not from 67/34.** On the current scale the top
   decile starts at 46 and the top quarter at 33.
4. **Turn on field history for `Normalized_Churn_Risk_Score__c`** (Contact tracks up to 20
   fields; check the current count first). Dating this score's snapshot had to be inferred from
   the training set's trip dates. Next time it should not be.
5. **Report model performance by cancellation reason.** Company cancels, non-pay and
   voluntary churn are three different behaviours; a single AUC hides that both models miss the
   voluntary one entirely.
6. **Re-run `scripts/churn_score_validation.py` after each batch** (first of the month) and
   append the raw-by-batch row. The script caches every pull so re-runs are cheap.

## Caveats

- Outcome is `Cancel_Date__c` on Contact. Its history shows heavy rewriting (212k history rows
  since 2025-04), but on the scored book the flag and the date agree on every contact.
- 6,023 of the scored contacts were training negatives, so for them the test is "in-sample
  negatives who later cancelled". That can only push their scores down uniformly; it does not
  inflate the AUC.
- One outcome window (Aug 23 - Oct 14). Seasonality in cancellations is not controlled.
- How the Data Cloud output was written to Contact on 2026-10-16 (data action, enrichment, or
  a manual push) was not traced. If it is scheduled, the field will be overwritten without
  history and this analysis cannot be repeated for that date.

## Files

| File | What |
|---|---|
| `scripts/churn_score_validation.py` | Pulls Contact, ContactHistory and the four Data Cloud objects via `sf data query`, caches CSVs, prints every table above, writes `data/*.json` |
| `data/normalized_training.json` | Training set labels, implied snapshot dates, feature AUCs, scored-contact overlap |
| `data/normalized_out_of_time.json` | AUCs, deciles, bands, 10-point calibration bins, by-reason and within-tenure tables |
| `data/raw_by_batch.json` | Raw score rebuilt per batch date with outcomes |
