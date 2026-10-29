# Test plan v3: measuring the retention layer without a holdout (2026-10-29)

Tracked in Jira as [ANA-6132](https://blueowl.atlassian.net/browse/ANA-6132). Supersedes v2 (2026-10-21),
which was built on a 50/50 randomized holdout. Insurance (Kellett, Betz) ruled on 2026-10-29 that no
holdout of any length is supported without formal legal review, and that a 30 to 45 day cap is the most
they would consider. A holdout that short cannot read cancellations (the outcome window closes about 57
days after entry), so the holdout is dropped rather than shortened. The v2 design, power table and interim
plan are kept in `v3-draft/TEST_PLAN_v2_holdout_appendix.md` in case a holdout is ever approved.

**What this plan can and cannot say.** Without a randomized control there is no causal estimate of the
layer's effect on cancellation. Every retention read below is directional: it can show that entrants
cancelled less than comparable customers did, and it can show the layer is doing nothing, but it cannot
rule out that something else changed at the same time. The behavioral reads are cleaner, because they
compare against customers who were not contacted, but they measure engagement, not retention. The plan
is honest about that distinction in every readout.

## What the journey is, in one line

Everyone eligible at R-27 gets the coverage check-in email at R-21 and, if in the high band or an
app-engaged reason, a push at R-14. No arms, no variants, no discount-drop messaging. Declining drivers
(score down 5+ with steady trips) are excluded at entry (`INSURANCE_FILTER_RULE.md`).

## Volumes the reads rest on

| Quantity | Value | Source |
|---|---|---|
| Term ends per month | ~1,250 (AZ ~1,050, RI ~190) | active contacts by `Current_Term_Expiration_Date__c` |
| Entry rule: new-term offer > $20 or > 10% (tier 1) OR v3 top decile (tier 2), at R-27 | 16% of the term-end window | holdout test of the rule, 911 of 5,601 offer-covered rows |
| After exclusions (non-pay 90 days, DNR, declining drivers ~5 to 10, unreachable) | ~150 to 250 entrants a month | +$20 offers ran 108 to 179 a month Apr to Aug 2026; tier 2 adds ~55 |
| Preventable voluntary cancel rate among entrants, 60 days | 11 to 13% | rule tested on the holdout: 11.4% combined; +$20 offers alone 12.9% |
| TDLI effect on volume | tier 1 falls by about a third as AZ migrates (complete 2027-05) | offers above $20: 19% under azV12 vs 30% under azV11 |
| Outcome lag per entrant | 57 days | entry R-27, outcome read at R+30 |

## The reads

### Read 1: year-over-year term-end cohort (retention, directional, primary)

The method used for the non-pay journey. For each term-end week after launch, take the customers who
entered the journey and compute their preventable voluntary cancel rate within 60 days of R-27. Compare
with customers whose term ended in the same calendar week one year earlier and who would have qualified
under the same entry rule (offer > $20 or > 10%, or score in the top decile re-scored historically from the
point-in-time set), same state, same tenure bucket.

- Source: `RE_ChurnRetention_History_AF_10202026` joined to Contact for the current cohort; the
  point-in-time training set (`Churn_PIT_Training_Set`) for the prior-year cohort, which already carries
  the offer and label at each monthly snapshot.
- Confounders to report alongside, not adjust away: rating version mix (TDLI did not exist a year ago),
  rate change size distribution, the Heads Up email's send rate, and the non-pay journey's reach.
- Reported monthly once a cohort has 60 days of outcomes. First read 2027-03 on November to January
  entries (about 600 entrants, about 70 expected cancellations). With no control arm there is no power
  calculation; the read is a difference in rates with a 95% interval, and the interval will be wide:
  at 600 entrants and a 12% base, roughly ±2.6 points.

### Read 2: cut-line comparison (retention, directional, primary)

Customers just above the entry line against customers just below it, same term-end weeks, same tenure
bucket, same state. Two cut lines:

- Tier 1: offered change of $20 to $30 (entered) vs $10 to $20 (did not enter). The 60-day cancel rates on
  the holdout were 11.0% and about 4.3%, so this comparison starts with a known gap that the journey has to
  close, not a level playing field. Report the gap before and after launch.
- Tier 2: score in the first decile (entered) vs the second decile (did not enter), both without a $20
  offer. Base rates 10.1% and about 7%.

The before-launch gap comes from the May to August 2026 holdout months. If the after-launch gap narrows
by more than the prior-year read moved, that is the strongest non-randomized evidence available.

### Read 3: 90-day behavioral read (engagement, cleaner, secondary)

Irene's proposal, adopted as the early read. Binary per customer, measured against the just-below group
from Read 2 (not contacted), same weeks:

| Endpoint | Window | Source |
|---|---|---|
| Coverage review completed | 7 days after the R-21 send | app event (to be confirmed with product; no event, no metric) |
| App session | 14 days after the R-21 send | `app_opened__c` / Amplitude |
| Trips resumed (any trip after 14+ days without one) | 30 days after the R-21 send | `Monthly_Driving_Stat__c` / `Last_Known_Trip_Date__c` |
| Push opened | 3 days after the R-14 send | MobilePush engagement |

Read monthly from month 2. These decide copy iteration and whether a track is kept, not whether the
journey retained anyone. Opens and clicks on the email itself are reported but never compared to a
non-contacted group, since the non-contacted group has none.

### Read 4: exclusion report (compliance)

Monthly: how many customers met the driving-decline rule at entry, how many of them would otherwise have
entered, and confirmation that none received a send. Goes to Insurance with the behavioral read.

## Gates before and after launch

### Gate 0: the model predicts (done 2026-10-20)

v3 on the May to August 2026 holdout: AUC 0.627 (tenure 0.560), monotonic deciles, top decile 2.0x.
v3.1 (retrained with the driving-decline rows removed) must match or beat this on the same holdout
before it replaces v3 in scoring.

### Gate 1: the journey runs correctly (first 4 weeks)

- Entrants per day within 50% of the expected 5 to 8; zero entrants with a non-pay notice in 90 days;
  zero entrants meeting the driving-decline rule; zero entrants with a Heads Up send in the prior 48 hours.
- Every R-21 email sent within 24 hours of the wait ending; R-14 push only to app-opened contacts in the
  eligible groups; nothing sent before R-21; no SMS.
- Exit DE fires within a day for cancelled, pending cancel and non-pay; renewed contacts reach the
  thank-you journey.
- No contact in `CurrentlyWaitingInSameInteraction` beyond R+31.
- Unsubscribe rate below 0.5% per send.

### Gate 2: the model keeps predicting in production (2 monthly batches)

After each scoring batch, score the next 60 days of cancellations on the whole book with
`../ChurnRiskActivation/scripts/validate_holdout.py`. Pass twice in a row: AUC >= 0.60 and top decile
>= 2.0x base. A failure narrows the journey to tier 1; it does not stop it.

### Gate 3: the layer is worth keeping (first retention read, 2027-03)

There is no significance test to pass. The decision rule, agreed before launch so it is not fitted to the
result:

- **Keep and extend** if Read 1 and Read 2 both move in the right direction and at least one behavioral
  endpoint shows a difference against the not-contacted group.
- **Keep and change copy** if the behavioral read is positive and the retention reads are flat.
- **Stop** if the behavioral read is flat after three monthly reads, whatever the retention reads say,
  because a journey nobody acts on is not the cause of any retention it coincides with.

## Calendar

| Month | What |
|---|---|
| 2026-11 | Insurance call 11/02, filter rule signed. Copy packet 11/02, review back by 11/09. DE columns, queries, journey built week of 11/09. Launch week of 11/16. Gate 1 checks weekly. |
| 2026-12 to 2027-01 | Gate 2 after batches 1 and 2. v3.1 retrain validated and promoted if it passes. |
| 2027-02 | First behavioral read (Read 3) on November and December entries. Exclusion report starts. |
| 2027-03 | First retention read (Reads 1 and 2) on November to January entries. Gate 3 decision. |
| monthly after | Reads 1 to 4 refreshed; the TDLI migration tracked in the entrant count. |

## What would make this a real test

A randomized holdout, of any size, run long enough to read cancellations: about 8 months of entries for a
35% effect at 200 entrants a month. The design is in the appendix and needs only the Arm split restored
in the entry query and the journey. Until Insurance and legal approve one, every retention number from
this journey is reported as directional.
