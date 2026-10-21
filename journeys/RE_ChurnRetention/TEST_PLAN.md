# Test plan: proving the model and the journey lower churn (2026-10-19)

Short version: the model can be proven in weeks, the journey mechanics in a month, but a
statistically significant churn reduction needs a randomized holdout and **9 to 12 months at the
widest sensible audience**, or about 20 months at the entry rule as written. Scope is Arizona
and Rhode Island, which is the whole book (85% and 15% of upcoming renewals; one contact in
California), so there is no smaller pilot to run first and no larger audience to widen to later. Nothing shorter is honest at
HiRoad's volumes. The plan below is staged so each gate answers one question and you are never
waiting a year to learn that the entry rule was wrong.

## Volumes the estimate rests on

| Quantity | Value | Source |
|---|---|---|
| Renewals per month (term ends) | ~1,250 (AZ ~1,050, RI ~190) | active contacts by `Current_Term_Expiration_Date__c` and `MailingState`, Nov 2026 to Mar 2027 |
| Entry rule share (High band 10% + Moderate 20% x tenure under 12 months 42%) | ~18% | score deciles and tenure mix on the Aug 22 book |
| After non-pay-in-90-days and opt-out exclusions (~30%) | ~150 entrants/month (AZ ~130, RI ~20) | non-pay notice volume (~1,500/month) |
| 2026 preventable voluntary cancels by state | AZ 1,715, RI 338 | `Cancellation_Reason__c`, Jan to Oct 14 |
| Preventable voluntary cancel rate among entrants, T-45 to T+30 | 12 to 15% | top-decile lift ~2.5x on a ~6% 60-day base |
| Outcome lag per entrant | 75 days | entry T-45, outcome read at T+30 |
| Plausible journey effect | 15 to 25% relative reduction | typical for renewal-window retention programs; 35% would be exceptional |

## Months of entries needed for 80% power, two-sided 5%

Two-proportion test on "preventable voluntary cancel by T+30". Add the 75-day outcome lag to
every figure to get calendar time.

| Entrants / month | Base rate | Effect | 50/50 holdout | 80/20 holdout |
|---|---|---|---|---|
| 150 (AZ + RI, entry rule as written) | 15% | 25% | 17 mo | 27 mo |
| 150 | 15% | 15% | 49 mo | 78 mo |
| 250 (AZ + RI, all Moderate band) | 15% | 25% | 10 mo | 16 mo |
| 400 (AZ + RI, Moderate + High, no tenure gate) | 12% | 25% | ~8 mo | ~13 mo |
| 400 | 12% | 35% | ~4 mo | ~6 mo |

Reading it: a 15% effect is not provable at any audience we can assemble. A 25% effect is
provable in about a year if the audience is widened to the full Moderate and High bands in both
states with a 50/50 split. Widening further dilutes the base rate and does not help. **Rhode
Island on its own (~20 to 60 entrants a month) will never reach significance**; randomize within
state so both are represented, report AZ and RI separately as descriptives, and test on the
combined population.

## The staged plan

### Gate 0: the model predicts (1 week, before launch)

Historical holdout, snapshots May to August 2026, from `../ChurnRiskActivation/BUILD_GUIDE.md`
phase 5. Pass: AUC >= 0.68, >= 0.05 above tenure alone, >= 0.60 in each tenure bucket, top
decile >= 2.5x base, monotonic deciles, compliance proxy check passed. This is a one-off read on
about 1,100 outcomes and needs no waiting.

### Gate 1: the journey runs correctly (first 4 weeks after launch)

Binary checks, no statistics:

- Entrants per day within 50% of the expected ~5 to 8; zero entrants with a non-pay notice in
  the prior 90 days; zero entrants who are opted out on every channel.
- Every T-45 send goes out within 24 hours of entry; T-30 SMS only to consented contacts.
- Exit DE fires: every cancelled or non-pay contact leaves within one day; renewed contacts
  reach the thank-you journey.
- No contact is in `CurrentlyWaitingInSameInteraction` beyond T+14 (the non-pay journey's
  failure mode).
- Unsubscribe rate below 0.5% per send.

### Gate 2: the model keeps predicting in production (2 monthly batches)

After each scoring batch, re-run `../ChurnRiskActivation/scripts/churn_score_validation.py`
against the next 60 days of cancellations on the whole scored book (~7,500 contacts, ~250
preventable cancels per 60 days, AUC standard error ~0.015). Pass twice in a row: AUC >= 0.68
and top decile >= 2.5x. Two batches are enough; the full book gives far more outcomes than the
journey does.

### Gate 3: the journey lowers churn (9 to 12 months; 50/50 holdout approved by compliance 2026-10-20)

**Design.** Randomized 50/50 split assigned in the entry query (`Arm` = TREAT or HOLDOUT, random
order partitioned by state) and logged in `RE_ChurnRetention_History_AF_10202026`. The journey's first
activity is a decision split on `Arm`; the HOLDOUT path has no sends and the same exit criteria. Widen entry to the full Moderate and High bands
in both states to reach ~400 entrants a month; keep the non-pay exclusion. Stratify the random
split by state (two Random Split activities behind a state decision split, or one split with the
state recorded) so the AZ:RI mix is identical in both arms. Holdout contacts still
get every servicing communication. Compliance approved the split on 2026-10-20.

**Primary metric.** Preventable voluntary cancellation by T+30 after term end, per entrant.
Secondary: any cancellation by T+30; renewal recorded by T+7.

**Analysis.** Two-proportion test, stratified by state, tenure bucket and band. Interim looks at month
4 and month 8 of entries with O'Brien-Fleming boundaries (stop early only for an effect of 35%
or more); final read at month 12 of entries, so about month 14 to 15 in calendar time.

**Leading indicators, read monthly from month 2.** Not proof of churn reduction, but they tell
you within 60 days whether the journey is doing anything: open and click on the T-45 email versus
the HiGoals announcement benchmark; savings-page visits from the email; app re-activation within
14 days among the Engage track (holdout gives a clean comparison here with far more power, since
the base rate is 30 to 50%); early renewal acceptance by T-7.

**Secondary reads**, reported alongside: the cut-line comparison at the High cut and the
year-over-year renewal-cohort curve. They cross-check the randomized read but do not replace it.

## Calendar

| Month | What |
|---|---|
| 0 | Gate 0. Holdout approved (done 2026-10-20). MC Connect fields synced. |
| 1 | Launch in AZ and RI with the 50/50 split. Gate 1 checks weekly. |
| 2 to 3 | Gate 2 after batches 1 and 2. Leading indicators from month 2. |
| 4 to 5 | First interim look at churn (entries from months 1 to 4; outcomes through month 6.5). |
| 8 to 9 | Second interim look. |
| 14 to 15 | Final read on 12 months of entries. Decision: scale, change, or stop. |

Quarterly during the test: retrain the model on closed snapshots and promote only if it beats
the live model on the same holdout; a model change mid-test is logged with its date so the
analysis can be split before and after.

## What would shorten it

- A bigger effect: at 35% relative, 400 entrants a month proves out in about 4 months of entries.
- A higher base rate: if the model's top decile reaches 20% churn, every figure above drops by
  about a third. Gate 0 tells you which base rate to plan on before launch.
- Nothing else. There are no more states to add, and bands or channels beyond the Moderate
  line lower the base rate faster than they add volume.
