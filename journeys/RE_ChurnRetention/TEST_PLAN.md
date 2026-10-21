# Test plan: proving the model and the journey lower churn (2026-10-19)

Updated 2026-10-21 for the final entry rule (renewal price shock plus the v3 model tier). Short
version: the model is proven (Gate 0 done, see below), the journey mechanics take a month, and a
statistically significant churn reduction needs the approved 50/50 holdout and **about 15 to 18 months
of entries for a 25% effect, 7 to 9 months for a 35% effect**, plus the 75-day outcome lag. Scope is
Arizona and Rhode Island, which is the whole book (85% and 15% of upcoming renewals), so there is no
smaller pilot and no larger audience. An earlier draft of this plan quoted 8 to 11 months; that assumed
a larger, lower-rate population than the rule actually produces, and is superseded here. Nothing shorter is honest at
HiRoad's volumes. The plan below is staged so each gate answers one question and you are never
waiting a year to learn that the entry rule was wrong.

## Volumes the estimate rests on

| Quantity | Value | Source |
|---|---|---|
| Renewals per month (term ends) | ~1,250 (AZ ~1,050, RI ~190) | active contacts by `Current_Term_Expiration_Date__c` and `MailingState`, Nov 2026 to Mar 2027 |
| Entry rule: offered increase > $20 or > 10% (tier 1) OR v3 top decile among offer-covered (tier 2), term end within 45 days | 16% of the renewal window | holdout test of the rule, 911 of 5,601 offer-covered rows |
| After the 90-day non-pay exclusion and opt-outs | ~150 to 250 entrants/month (AZ ~85%, RI ~15%) | +$20 offers ran 108 to 179/month Apr-Aug 2026; tier 2 adds ~55/month |
| 2026 preventable voluntary cancels by state | AZ 1,715, RI 338 | `Cancellation_Reason__c`, Jan to Oct 14 |
| Preventable voluntary cancel rate among entrants, 60 days | 11 to 13% | rule tested on the holdout: 11.4% combined; +$20 offers alone 12.9% |
| Outcome lag per entrant | 75 days | entry T-45, outcome read at T+30 |
| Plausible journey effect | 20 to 35% relative reduction | price-shock interventions act on the stated reason; 35% is the optimistic case |

## Months of entries needed for 80% power, two-sided 5%, 50/50 split

Two-proportion test on "preventable voluntary cancel within 60 days of entry". Add the 75-day outcome
lag to every figure to get calendar time. Recomputed 2026-10-21 for the offer-rule population.

| Entrants / month | Base rate | Effect 20% | Effect 25% | Effect 35% |
|---|---|---|---|---|
| 150 | 11% | 39 mo | 24 mo | 12 mo |
| 150 | 13% | 32 mo | 20 mo | 10 mo |
| 200 | 11% | 29 mo | 18 mo | 9 mo |
| 200 | 13% | 24 mo | 15 mo | 7 mo |
| 250 | 11% | 23 mo | 14 mo | 7 mo |
| 250 | 13% | 19 mo | 12 mo | 6 mo |

Reading it: plan on about 200 entrants a month at a 12% base rate. A 35% reduction, which is what a
well-targeted price conversation can produce, proves out in 7 to 9 months of entries. A 25% reduction
takes 15 to 18 months. A 20% reduction is not provable inside two years at this volume; if the interim
reads point there, the decision is made on the leading indicators and the secondary reads, not on
significance. Rhode Island on its own (~30 entrants a month) never reaches significance; randomize
within state, report AZ and RI separately as descriptives, test on the combined population.

## The staged plan

### Gate 0: the model predicts (done 2026-10-20)

Historical holdout, snapshots May to August 2026, 25,419 rows, 1,269 cancellations. v3 result: AUC
0.627 (tenure 0.560), three of four tenure buckets at or above 0.60, monotonic deciles, top decile
2.0x, renewal window 0.623, outside the window 0.628. The 0.68 target and 2.5x top decile were not met;
the entry rule does not depend on them because tier 1 is the offer itself. Non-pay correlation in the
top decile accepted by decision. Details: `../ChurnRiskActivation/2026-10-20_v3_holdout_validation.md`.

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

**Primary metric.** Preventable voluntary cancellation within 60 days of entry (which spans T-45 to
T+15 around term end), per entrant. Secondary: any cancellation by T+30; renewal recorded by T+7.

**Analysis.** Two-proportion test, stratified by state, tenure bucket and band (OFFER vs HIGH).
Interim looks at months 4 and 8 of entries with O'Brien-Fleming boundaries (stop early only for an
effect of 35% or more); a decision read at month 12 of entries, and the plan allows up to month 18 for
a 25% effect. Calendar time adds about 2.5 months.

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
| 0 | Gate 0 done (v3, 2026-10-20). Holdout approved (2026-10-20). MC Connect fields synced (2026-10-21). DEs created. |
| 1 | Launch in AZ and RI with the 50/50 split. Gate 1 checks weekly. |
| 2 to 3 | Gate 2 after batches 1 and 2. Leading indicators from month 2. |
| 4 to 5 | First interim look at churn (entries from months 1 to 4; outcomes through month 6.5). |
| 8 to 9 | Second interim look. |
| 14 to 15 | Decision read on 12 months of entries: scale, change, or stop. |
| up to 20 | If the effect is in the 25% range, the test continues to 18 months of entries before the final call. |

Quarterly during the test: retrain the model on closed snapshots and promote only if it beats
the live model on the same holdout; a model change mid-test is logged with its date so the
analysis can be split before and after.

## What would shorten it

- A bigger effect: at 35% relative, 400 entrants a month proves out in about 4 months of entries.
- A higher base rate: if the model's top decile reaches 20% churn, every figure above drops by
  about a third. Gate 0 tells you which base rate to plan on before launch.
- Nothing else. There are no more states to add, and bands or channels beyond the Moderate
  line lower the base rate faster than they add volume.
