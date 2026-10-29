# APPENDIX: the v2 randomized-holdout design (not approved; kept for reference)

Insurance ruled on 2026-10-29 that no holdout runs without formal legal review. This is the v2 plan as it stood
on 2026-10-21, unchanged, so the power table and interim plan are available if a holdout is ever approved.

---

# Test plan: proving the model and the retention layer lower churn (2026-10-19, v2 2026-10-21)

Tracked in Jira as [ANA-6132](https://blueowl.atlassian.net/browse/ANA-6132). This file is the source for the
sample size and run-time analysis; the ticket links here.

Updated 2026-10-21 for the final entry rule (new-term price change plus the v3 model tier) and for spec v2 of
the journey (entry at R-27 behind the existing lifecycle flow, R-21 email, R-14 push, no SMS). The question
the test answers is **whether the layer lowers churn beyond the Heads Up and TDLI emails both arms already
receive**. A null result means the existing flow already captures the available effect, not that outreach
does not work. Short
version: the model is proven (Gate 0 done, see below), the journey mechanics take a month, and a
statistically significant churn reduction needs the approved 50/50 holdout and **about 15 to 18 months
of entries for a 25% effect, 7 to 9 months for a 35% effect**, plus the 57-day outcome lag. Scope is
Arizona and Rhode Island, which is the whole book (85% and 15% of upcoming renewals), so there is no
smaller pilot and no larger audience. An earlier draft of this plan quoted 8 to 11 months; that assumed
a larger, lower-rate population than the rule actually produces, and is superseded here. Nothing shorter is honest at
HiRoad's volumes. The plan below is staged so each gate answers one question and you are never
waiting a year to learn that the entry rule was wrong.

## Volumes the estimate rests on

| Quantity | Value | Source |
|---|---|---|
| Renewals per month (term ends) | ~1,250 (AZ ~1,050, RI ~190) | active contacts by `Current_Term_Expiration_Date__c` and `MailingState`, Nov 2026 to Mar 2027 |
| Entry rule: new-term offer > $20 or > 10% (tier 1) OR v3 top decile (tier 2), evaluated at R-27 | 16% of the term-end window | holdout test of the rule, 911 of 5,601 offer-covered rows |
| After the 90-day non-pay exclusion and opt-outs | ~150 to 250 entrants/month (AZ ~85%, RI ~15%) | +$20 offers ran 108 to 179/month Apr-Aug 2026; tier 2 adds ~55/month |
| 2026 preventable voluntary cancels by state | AZ 1,715, RI 338 | `Cancellation_Reason__c`, Jan to Oct 14 |
| Preventable voluntary cancel rate among entrants, 60 days | 11 to 13% | rule tested on the holdout: 11.4% combined; +$20 offers alone 12.9% |
| Outcome lag per entrant | 57 days | entry R-27, outcome read at R+30 |
| Plausible journey effect | 20 to 35% relative reduction | price-shock interventions act on the stated reason; 35% is the optimistic case |
| TDLI effect on volume | tier 1 entrants fall by about a third as AZ migrates (complete 2027-05) | offers above $20: 19% under azV12 vs 30% under azV11 (211 and 1,408 offers) |

## Months of entries needed for 80% power, two-sided 5%, 50/50 split

Two-proportion test on "preventable voluntary cancel within 60 days of entry". Add the 57-day outcome
lag to every figure to get calendar time. Recomputed 2026-10-21 for the offer-rule population.

| Entrants / month | Base rate | Effect 20% | Effect 25% | Effect 35% |
|---|---|---|---|---|
| 150 | 11% | 39 mo | 24 mo | 12 mo |
| 150 | 13% | 32 mo | 20 mo | 10 mo |
| 200 | 11% | 29 mo | 18 mo | 9 mo |
| 200 | 13% | 24 mo | 15 mo | 7 mo |
| 250 | 11% | 23 mo | 14 mo | 7 mo |
| 250 | 13% | 19 mo | 12 mo | 6 mo |

Reading it: plan on about 200 entrants a month at a 12% base rate for the first six months, then about
140 once Arizona is fully on TDLI (tier 1 shrinks by roughly a third; tier 2 is unaffected). At 140 a month,
a 35% effect takes about 11 months of entries and a 25% effect about 22. The month 4 interim re-checks the
entrant count against this. A 35% reduction, which is what a
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
  the prior 90 days; zero entrants opted out of email with no app activity; zero entrants with a Heads
  Up send in the prior 48 hours.
- Heads Up and TDLI send rates equal across TREAT and HOLDOUT (within 5 points), which proves the
  existing flow is identical in both arms.
- Every R-21 email goes out within 24 hours of the R-21 wait ending; R-14 push only to app-opened contacts in the eligible bands. No sends before R-21 and no SMS.
- Exit DE fires: every cancelled or non-pay contact leaves within one day; renewed contacts
  reach the thank-you journey.
- No contact is in `CurrentlyWaitingInSameInteraction` beyond R+31 (the non-pay journey's
  failure mode).
- Unsubscribe rate below 0.5% per send.

### Gate 2: the model keeps predicting in production (2 monthly batches)

After each scoring batch, score the next 60 days of cancellations on the whole scored book (~7,900
contacts, ~250 preventable cancels per 60 days, AUC standard error ~0.015) with
`../ChurnRiskActivation/scripts/validate_holdout.py`. Pass twice in a row: the model holds its holdout
result, AUC >= 0.60 and top decile >= 2.0x base (v3 scored 0.627 and 2.0x on the holdout; 0.68 was the
original target and was not met, by decision). Two batches are enough; the full book gives far more
outcomes than the journey does. Tier 1 does not depend on the model, so a Gate 2 failure narrows the
journey to tier 1 rather than stopping it.

### Gate 3: the layer lowers churn beyond the existing flow (7 to 18 months of entries; 50/50 holdout approved by compliance 2026-10-20)

**Design.** Randomized 50/50 split assigned in the entry query (`Arm` = TREAT or HOLDOUT, random
order partitioned by state so the AZ:RI mix is identical in both arms) and logged in
`RE_ChurnRetention_History_AF_10202026`. The journey's first activity is a decision split on `Arm`; the
HOLDOUT path has no sends and the same exit criteria. Entry is the fixed rule (offer tier plus top
decile, 150 to 250 a month); it is not widened to gain volume, because a wider rule lowers the base rate
faster than it adds entrants. Both arms keep every existing communication, including the Heads Up rate
email and the TDLI emails. Compliance approved the split on 2026-10-20.

**Primary metric.** Preventable voluntary cancellation within 60 days of entry (which spans R-27 to
R+33 around term end), per entrant. Both arms receive the existing lifecycle flow, so this reads the
incremental effect of the layer. Secondary: any cancellation by R+30; renewal recorded by R+7.

**Analysis.** Two-proportion test, stratified by state, tenure bucket, band (OFFER vs HIGH) and rating version (TDLI vs monthly model).
Interim looks at months 4 and 8 of entries with O'Brien-Fleming boundaries (stop early only for an
effect of 35% or more); a decision read at month 12 of entries, and the plan allows up to month 18 for
a 25% effect. Calendar time adds about 2 months.

**Leading indicators, read monthly from month 2.** Not proof of churn reduction, but they tell
you within 60 days whether the layer is doing anything: open and click on the R-21 email versus the
HiGoals announcement benchmark; coverage review completions in the app within 7 days of the email and
of the push, TREAT vs HOLDOUT (the holdout gives a clean comparison with far more power than churn,
since completions run in the tens of percent); push open rate; app re-activation within 14 days among
the ENGAGE reasons; early renewal acceptance by R-7. Also read by rating version, since the TDLI line
and the monthly-model line are different copy.

**Secondary reads**, reported alongside: the cut-line comparison at the High cut and the
year-over-year renewal-cohort curve. They cross-check the randomized read but do not replace it.

## Calendar

| Month | What |
|---|---|
| 0 | Gate 0 done (v3, 2026-10-20). Holdout approved (2026-10-20). MC Connect fields synced (2026-10-21). DEs created. |
| 1 | Irene reviews the R-21 copy, then Insurance. DE columns added, queries and journey built. Launch in AZ and RI with the 50/50 split. Gate 1 checks weekly. |
| 2 to 3 | Gate 2 after batches 1 and 2. Leading indicators from month 2. |
| 4 to 5 | First interim look at churn (entries from months 1 to 4; outcomes through month 6). Re-check entrants per month against the TDLI migration. |
| 8 to 9 | Second interim look. |
| 14 to 15 | Decision read on 12 months of entries: scale, change, or stop. |
| up to 20 | If the effect is in the 25% range, the test continues to 18 months of entries before the final call. |

Quarterly during the test: retrain the model on closed snapshots and promote only if it beats
the live model on the same holdout; a model change mid-test is logged with its date so the
analysis can be split before and after.

## What would shorten it

- A bigger effect: at 35% relative and 200 entrants a month, about 7 months of entries.
- A mid-term tier. Once savings and discount history exists (`../ChurnRiskActivation/DATA_REQUEST_savings_discount_history.md`),
  a second entry rule on shrinking savings adds entrants outside the term-end window without lowering the
  base rate of the first tier. That is the only volume lever that does not cost power.
- Nothing else. There are no more states to add, and widening the entry rule lowers the base rate faster
  than it adds volume.
