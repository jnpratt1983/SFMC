# Einstein lead score: first forward read of the new scores (2026-11-10)

One day of forward outcomes on the re-scored model (scores spread 1-99 since the 11-09 snapshot). This is a
direction check, not the 7-day read; rerun `scripts/lead_score_read.py` from 2026-11-17 and
`scripts/lead_score_return_read.py` for the return-to-quote view.

## Setup

- Cohort A: every open lead in the 11-09 snapshot (new score), 6,837 leads, 28 hours forward (to 11-10 17:15 UTC).
- Cohort B: first-snapshot leads in the 11-10 snapshot (created 11-09 12Z to 11-10 12Z), 292 leads, 4 hours forward.
- Excluded at snapshot: already purchased (first `purchased__c` true in LeadHistory, or `Purchased_Date__c`), declined, converted.
- Purchase = first `purchased__c` true after the snapshot.
- Back to quote = a `Quote_Session_Key__c` or `Max_Quote_Step__c` change on the lead after the snapshot (LeadHistory), OR a
  new Lead with the same email created after the snapshot. The second half matters: see data facts below.
- AUC is the chance a random lead with the outcome outscores a random lead without it (0.5 = no signal).

## Results

**Fresh leads (0-3 days old at snapshot, A + B, n = 995).** These are the leads the AC_ journeys actually take.
Back to quote here includes same-email new leads (output of `scripts/lead_score_return_read.py`, 2026-11-10 17:40 UTC).

| Score band | n | Step at snapshot (mean) | Back to quote | Purchased |
|---|---|---|---|---|
| 21-40 | 29 | 2.6 | 0.0% | 0.0% |
| 41-60 | 120 | 2.5 | 3.3% | 0.0% |
| 61-80 | 141 | 2.5 | 4.3% | 0.0% |
| 81-90 | 149 | 2.9 | 4.7% | 0.0% |
| 91-95 | 281 | 3.8 | 10.0% | 0.0% |
| 96-99 | 252 | 4.5 | 12.7% | 3.6% |

- Back to quote: 87 events; score AUC 0.64, quote step AUC 0.58, lead age 0.66. Within steps 1-3 the score still separates (AUC 0.65-0.71,
  e.g. step 1: 7.9% vs 2.6% above/below the median score). Within steps 4-5 it does not (AUC 0.34-0.54): at those steps
  nearly everyone scores 91-99 and the score has no room left.
- Purchase: 9 purchases, all nine in the 96-99 band. Score AUC 0.90, but step AUC is 0.87, so most of this is "they
  were at step 5-6". Within fresh leads at step >= 5 (n = 216): score 96-99 bought 5.6% (7 of 125), score 71-95 bought
  0% (0 of 91). Directional only.
- Cohort B alone (4 hours): 96-99 came back 23.9%, 91-95 10.6%, below 90 2-6%. AUC 0.69 vs step 0.62.

**Older leads (4-30 days at snapshot, n = 6,255, 31 hours, return = new Lead by email or cookie ID).** 63 came back
(1.0%), 4 purchased. Score AUC for coming back 0.69 overall, but lead age is 0.78 and the score tracks age; inside each
age bucket the score's AUC drops to 0.54-0.58 (event-weighted 0.56). By tercile within age: 4-7 days 2.1% / 2.6% / 2.6%,
8-14 days 1.7% / 1.5% / 3.6%, 15-30 days 0.1% / 0.2% / 0.1%. A hint on the 8-14 day leads, nothing elsewhere; too
few events to call either way.

**Score terciles within lead age, back to quote (31 hours forward):**

| Lead age | Low tercile | Mid | High | AUC score | AUC step |
|---|---|---|---|---|---|
| 0-3 days | 3.4% (30-82) | 10.7% (83-95) | 12.7% (96-99) | 0.64 | 0.58 |
| 4-7 days | 2.1% (8-55) | 2.6% (56-87) | 2.6% (88-99) | 0.54 | 0.62 |
| 8-14 days | 1.7% (3-36) | 1.5% (37-70) | 3.6% (71-94) | 0.58 | 0.59 |
| 15-30 days | 0.1% (1-21) | 0.2% (22-51) | 0.1% (52-91) | 0.58 | 0.47 |

**Old model (Previous_Score__c), same cohort:** AUC 0.51-0.62 on every outcome. The retrain helped.

## Reading

1. On fresh leads the new score does predict coming back to the quote, over and above the quote step, at the
   bottom of the funnel (steps 1-3). That is where the Drivers journey (steps 3.0-3.5) lives.
2. At steps 4-6 the score is saturated (91-99); it adds little to the step there. For the Purchase journey (step 6)
   the useful cut is inside 91-99 (e.g. 96+ vs below), not HIGH/LOW on the whole range.
3. Purchase: direction right, nine events. Not a read.
4. Nothing yet on leads older than three days, which is most of the lead population but not the journey population.
5. Caution: Einstein Lead Scoring uses activity recency, so "high score at 13:00" partly means "active this morning",
   which predicts "active this afternoon". The 7-day read will dilute that.

## Data facts found on the way (both affect the test plan)

1. **A Lead is only updated by the quote flow for 24 hours after creation (product rule, confirmed by Jennifer 2026-11-10).**
   A person who comes back after that starts a new quote and a **new Lead**, matched by email or cookie ID
   (`optimizely_dna__Visitor_Id__c`, populated on 96% of leads). The history agrees: quote-field changes between hours 24 and 48
   are sync continuations on leads that were already changing in hours 12-24 (698 of 699), and none exist past 48 hours.
   Dedupe merges only happen in the first hour. For leads created 10-25..11-04: 8.2% had a same-email new lead in hours 1-48,
   4.4% in days 2-7, 2.2% in days 7-30, and 31 of those later leads purchased. Consequence: for journey leads (days 1-3+)
   "came back to the quote" = a new Lead with the same email or cookie ID, and purchase credit must follow the person, not the
   Lead Id. `of_Sessions__c` and `Re_engaged__c` are empty.
2. **`purchased__c` flaps true/false every ~30 minutes on about 1 in 5 purchasers** (162 of 762 purchasers since 10-25,
   median 48 flips, for 1.3-1.9 days, then stops; 8-10 new leads a day, ongoing on 11-10). `Max_Quote_Step__c` toggles
   7.0 <-> 5.0/6.0 in step with it. The pattern looks like the quote-page sync (writes step 5/6, purchased false,
   runs for the 48-hour window) fighting the purchase sync (writes 7.0, true). Last-modified users on those leads: Automated
   Process, Kevin Brown, Airbyte, API SFMC User. Consequences: any LeadHistory- or snapshot-based read must take the FIRST
   purchased=true; journey exit/goal criteria evaluated on `purchased__c` can see false on a purchaser for up to two days.

## Update 2026-11-12: three days forward (11-09 scores, outcomes to 11-12 19:47 UTC)

Both scripts rerun. Cohort = first new-model snapshot per lead, 7,767 open leads, mean window 74 hours.

**Fresh leads (0-3 days at snapshot, n = 1,473):** back to quote 13.3% (196), purchase 2.1% (31).

| Score tercile | Range | Back to quote | Purchased |
|---|---|---|---|
| Low | 30-84 | 6.3% | 0.2% (1) |
| Mid | 85-95 | 15.0% | 1.6% (9) |
| High | 96-99 | 16.5% | 5.3% (21) |

- Back to quote: score AUC 0.61 vs step 0.57. Within a step the score's own contribution is now small (step-stratified
  AUC 0.53; steps 1-3 still 0.60-0.62 but steps 4.5-5 reversed at 0.40). The first-day lift inside steps was partly recency.
- Purchase: score AUC 0.80 vs step 0.77 (31 events). At steps 4-6 pooled: score <=90 bought 0% (n 93), 91-95 3.3%, 96-99
  5.4%. At step >= 5: 96+ bought 7.4% vs 3.3% below (n 202 / 153). The score adds to the step at the top of the funnel.
- Point-in-time 3-day purchase on every new-model snapshot row (`lead_score_read.py --window 3`, 7,399 rows, 20 buyers):
  91-99 bought 2.1%, every other band 0-0.2%; AUC score 0.89, step 0.72, age 0.87. Within step bands the score and age are
  near-identical (0.82-0.90), so the score has not yet shown lift over age plus step.

**Older leads (4-30 days, n = 6,294):** back 1.7% (107), purchase 7. Within age buckets score AUC 0.56-0.58; terciles
4-7 days 3.4 / 4.4 / 5.1%, 8-14 days 3.2 / 2.8 / 5.5%, 15-30 days flat. Same picture as day one: mostly age.

**Call so far:** the score ranks fresh leads for purchase and for coming back, mainly by sorting the top of the funnel
(96+ vs the rest). It is not yet shown to beat "quote step plus lead age"; that is the bar for the 11-17 read.

## Update 2026-11-16: first full 7-day window

Cohort = first new-model snapshot per lead, 8,775 open leads; 6,709 have a full 7-day window (the 11-09 snapshot), the rest partial.

**Fresh leads (0-3 days at snapshot).** Full window n = 668, 26 purchases, 87 back; all windows n = 2,209, 102 purchases.

| Score band | n (full window) | 7-day purchase (full) | 7-day purchase (all windows, n 2,209) | Back to quote |
|---|---|---|---|---|
| 90 and under | 306 | 0.7% | 0.5% | 9.8% |
| 91-95 | 177 | 4.5% | 3.7% | 15.8% |
| 96-99 | 185 | 8.6% | 10.9% | 15.7% |

- **Purchase: the score clears the bar.** Cross-validated AUC on fresh leads: quote step + lead age 0.70, score alone
  0.77 (0.80 on all windows), step + age + score 0.71. The score carries information the step and age do not, and the
  96-99 band buys 12-20x the rate of 90-and-under. By step group: steps 1-3.4 at 96-99 bought 7.7% vs 0.4% under 90
  (n 26 vs 272); steps 5-6 at 96-99 bought 11.8% vs 7.5% at 91-95.
- **Back to quote: mostly the step.** Step + age 0.54, with score 0.57, score alone 0.57. The 90-and-under band comes
  back about two-thirds as often as the rest, and that gap is the step. Do not expect the score to move this outcome.
- Point-in-time 7-day purchase on all 7,399 new-model snapshot rows: 91-99 bought 3.4%, 84-90 0.6%, everything else 0-0.3%.
  AUC score 0.85, step 0.72, age 0.82.

**Older leads (4-30 days, n 6,566; 21 purchases).** Purchase now rises with score inside each age bucket: 4-7 days
0.0 / 0.3 / 1.4% by tercile (n ~350 each), 8-14 days 0.2 / 0.7 / 0.9%, 15-30 days 0.0 / 0.2 / 0.3%. Back to quote
within age is still weak (AUC 0.58-0.59). Few events; the direction is right.

**Where this leaves the model.** Use it as the propensity lens in both journeys. For Purchase the cut is 96+. For
Drivers, whose entrants span 50-95, HIGH >= 80 and LOW < 60 stand. It is a purchase predictor, not a re-engagement
predictor: on fresh leads the step already tells you who comes back.

## Update 2026-11-17: 7-day read on two full snapshot days (corrects the 11-16 baseline)

Fresh leads (0-3 days at snapshot) with a full 7-day window: n = 945, 37 purchases, 146 back. All fresh leads incl.
partial windows: n = 2,415, 111 purchases.

| Score band | n (full window) | 7-day purchase | Back to quote |
|---|---|---|---|
| 90 and under | 427 | 0.7% | 9.6% |
| 91-95 | 266 | 4.9% | 21.8% |
| 96-99 | 252 | 8.3% (10.9% on all 680 fresh leads at 96+) | 18.7% |

Cross-validated AUC for 7-day purchase: quote step alone 0.78, step + age 0.77, score alone 0.77, step + age + score 0.78.
Yesterday's "score 0.77 vs step + age 0.70" came from 668 leads and 26 buyers; with 945 leads and 37 buyers the step + age
baseline is 0.77, so the score **matches** step + age rather than beating it, and adds about 0.02 on top. Back to quote:
step + age 0.61, with score 0.62. Point in time on all 9,696 new-model snapshot rows: score 0.86, step 0.74, age 0.83;
91-99 bought 4.1%, every other band 0-0.5%.

**Revised call.** The score's practical value is the 96+ cut on fresh leads, which buys 8-11% against under 1% below 90
and is sharper than any single quote step. As a ranking it is no better than the quote step, and it does not predict
coming back. Treat it as a purchase-propensity flag for the top band, not as a general lead ranking. Recorded in the data
dictionary Models page (lead-score.json validation list, 2026-11-17, "marginal pass"). Next read 2026-11-23 (14-day).

**Framing note (2026-11-17, user decision).** The test is of the score, not of the score against the quote step. The
pass line is: 7-day purchase rises monotonically across score bands on leads scored before the outcome, and the top band
buys at several times the rate of the bottom. On the 11-17 read that holds (0.7% / 4.9% / 8.3-10.9%). Quote step and lead
age AUCs stay in these notes as context only and are not a gate on the journey tests.

## Update 2026-11-20: five snapshot days with full 7-day windows

Fresh leads (0-3 days at scoring) with a full 7-day window: n = 1,710, 88 purchases, 280 back. All fresh leads incl.
partial windows: n = 3,292, 171 purchases (5.2%).

| Score band | n | 7-day purchase | Back to quote |
|---|---|---|---|
| 1-60 | 176 | 0.6% | 8.0% |
| 61-80 | 248 | 0.4% | 10.5% |
| 81-90 | 301 | 0.7% | 13.0% |
| 91-95 | 508 | 4.3% | 20.3% |
| 96-99 | 477 | 13.0% | 20.5% |

- Purchase is monotonic across the bands and the gap has widened as the sample grew: 96-99 buys 13.0% against 0.4-0.7%
  below 90, about 20x. 91-95 sits at 4.3%. On all fresh leads with any window 96-99 is 11.9%.
- By snapshot day the 96-99 rate runs 7.5 / 8.6 / 13.3 / 20.0 / 22.1% and 90-and-under runs 0.0 / 0.6 / 0.8 / 1.1 / 0.0%.
  The ordering holds on every day; the 96-99 level varies because each day is 65-185 leads.
- Back to quote also rises with score (8% to 20%) but flattens from 91 up; this remains the weaker outcome.
- Point in time on all 15,324 new-model snapshot rows: 91-99 bought 5.0% in 7 days, 84-90 0.7%, everything else 0-0.6%;
  AUC 0.87 (context: quote step 0.76, lead age 0.81).
- Older leads (4-30 days, n = 6,551, 22 purchases): purchase rises with score inside the 4-7 and 8-14 day buckets
  (0.0 / 0.5 / 1.7% and 0.4 / 0.4 / 1.1% by tercile); 15-30 days is flat. Back to quote follows (4-7 days: 4.0 / 5.7 / 7.4%).

**Call.** Yes, the score predicts propensity to buy on fresh leads, and the bands are stable enough to use: 96+ is the
buyer band, 91-95 is warm, 90 and under is cold. That is the cut the Purchase journey test uses. Next read 2026-11-23
(14-day window).
