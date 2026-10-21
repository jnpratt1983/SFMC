# Voluntary churn program: what was built, why, and what comes next

Written 2026-10-21 for HiRoad lifecycle marketing, Insurance and Data Science. Companion to
`CHURN_PROGRAM_CHECKLIST.md` (status by item) and the detailed reports under `journeys/ChurnRiskActivation/`.

## Why the program was rebuilt

Insurance asked that retention effort go to keeping standard customers and not to keeping non-standard
ones. The existing churn scores could not honour that: they were trained on every cancellation, and
non-payment is 43% of cancellations, so the customers they ranked highest were largely the ones
Insurance does not want us to pursue. The program had to be rebuilt from the label up so that the
score, the reasons and the journey all point at preventable voluntary churn only.

## What Insurance decided, and what it changed

Insurance (Jennifer Kellett with Sandy) chose to retrain without non-pay, so that credit-based signals
stay out of retention targeting. That turned the problem from "who cancels" into "who leaves for a reason
we can act on." Of 7,765 cancellations in 2026 to mid-October:

| Reason group | Share | Treatment in the model |
|---|---|---|
| Non-payment of premium | 43% | censored (not a negative, not a positive) |
| Company cancel | 20% | censored |
| Preventable voluntary (high premium, switching carrier, insured request, app or service) | 28% | **the label** |
| Unpreventable (sold vehicle, no longer driving, moved, total loss) | 9% | censored |

Preventable voluntary churn runs about 230 customers a month, a 4 to 8% rate over 60 days. Both
existing models scored 0.51 on it, no better than chance, because they were built for a different label. Compliance separately approved a 50/50 randomized holdout for the
journey, which is what makes the eventual result causal rather than an estimate.

## The data we built, and why each piece

**A point-in-time training set.** Every customer as of the first of each month from July 2024 to August
2026, 26 snapshots, 237,980 rows, labelled on whether they cancelled for a preventable reason in the
next 60 days, with every feature dated strictly before the snapshot and an audit column proving it (zero
violations). This replaced a training set that measured leavers up to their cancel date and stayers up to
today. It is built by a Data Cloud batch transform created through the API (`ChurnPITTrainingSet`, 145
nodes) and rebuilds itself; the snapshot calendar is loaded through 2028 and new months activate once
their 60-day window closes.

**Renewal offers, captured for the first time.** The strongest churn driver in the book lived in four
Account fields that reset to zero after each offer window. We built `Renewal_Offer__c` with a flow that
captures every offer as it is issued, backfilled 7,606 offers from field history (October 2025 onward),
and streamed it into Data Cloud. Example: a customer offered +$91 a month at renewal now carries that
number on their Contact record and scored 90.7 out of 100.

**Driving telemetry.** `Monthly_Driving_Stat__c`, 219,710 monthly cycles for 24,672 customers since May
2023, streamed and joined by customer number: latest score, three-cycle trend, earned discount and its
change, trips, miles. Where the discount fell five or more points, churn runs 7.2% against 4.9 to 6.2%.

**Price history from bills.** Net premium per invoice, every month, for every billed customer: the latest
amount and the change over three months. Up $50 or more in three months: 10.8% cancel; flat or down: 4 to
5%. It covers 70% of rows in every year, where offers cover 22%.

**Email history recovered by address.** HiRoad emails leads far more than customers, and sends made
before conversion stay on the lead record. Matching Individual Email Results on the email address instead
of the contact lookup found 87,529 customer-period sends in 2024 and 106,197 in 2025, where the lookup
found 5,181 and 3,652.

**What was deliberately left out.** Every payment-behaviour field (notices, late rates, days past due,
Payment Stability Score, credit score). `Driver_Role__c`, which is populated only on customers still
active and would have leaked the label. Lead attributes and post-purchase re-quotes, which turned out
to mark customers who lapse and re-buy, not customers deciding to leave.

## The models, honestly

| Version | Inputs | Holdout AUC (May to Aug 2026, 25,419 rows, 1,269 cancels) | Verdict |
|---|---|---|---|
| Normalized score (existing) | trained on all cancellations, non-pay included | 0.51 on the preventable label | not usable under the Insurance decision |
| v1 | tenure, term, app, email, tickets, offers | 0.579 | fails; top contributor was the non-pay journey's reminder count |
| v2 | + driving, email by address, state; no send counts | 0.599 | better, monotonic deciles, still short |
| **v3** | **+ premium history from bills; no email counts** | **0.627** | **clears tenure + 0.05; three of four tenure buckets pass; first lift outside the renewal window (0.628); production model** |

On the renewal window, customers with an offer in the prior 60 days, every version lands at 0.61 to 0.62
and a one-line rule, "offered increase over $20", lands at 0.614. The renewal offer is the prediction. v3's
top decile cancels at 10.1% against a 5.0% base; its top decile on the renewal window is 62% customers
offered a large increase, so it found the price signal and had little else to add to it.

The measured step function that drives everything downstream (11,725 offers since December 2025,
uncensored):

| Offered monthly change | Cancel within 60 days |
|---|---|
| decrease, or increase up to $20 | 4.1 to 4.3% |
| +$20 to $30 | 11.0% |
| +$30 to $50 | 11.6% |
| +$50 and up | 20.9% |

One finding accepted by decision: v3's top decile carries more non-pay history than the rest (35% vs
23% in 90 days), because premium level and invoice count correlate with it. The journey's 90-day non-pay
exclusion at entry governs who is contacted, whatever the score's correlation. Customers offered a $20-plus
increase carry a 41% non-pay history themselves.

## What is live today

- **Score on every active customer.** 7,878 contacts scored on 2026-10-20 with v3: 795 High (score 59.99
  and up), 1,568 Moderate (49.05 and up), 5,515 Low. Written to eight Contact fields with the band, the
  three top factors in plain words, and a primary churn reason assigned by fixed priority from the same
  signals: 986 price shock, 459 discount erosion, 2,447 new customer, 1,404 disengaged, 37 low savings,
  2,545 general. Example: Jaquan Brigham, score 90.3, High, PRICE_SHOCK, offer +$57.34, driving score 69.
- **Self-running pipeline.** Offers captured by the flow as issued; the scoring transform rebuilds the
  active book daily; the production predict job re-scores on Streaming; the write-back to Contact runs on
  the 2nd of each month from a scheduled job and prints that month's band cut points.
- **Marketing Cloud ready for the journey.** The synced Contact carries the new fields and term dates; the
  offer object and driving cycles are synced; four data extensions exist in the Airflow Data folder
  (`RE_ChurnRetention_Config/Entry/History/Exit_AF_10202026`) with the cut points loaded.

## The recommendation, in one paragraph

Target the new-term price change, inside the rules Insurance already set. Enter customers 27 days before
their term ends, after the policy system has issued the new-term offer (R-32) and after the existing Heads Up
rate email has landed (R-28/29), when the offer was more than $20 a month or more than 10% up (tier 1) or the
v3 model puts them in its top decile (tier 2). Exclude anyone with a non-pay notice in 90 days, and split
50/50 so the result is causal. Send one email at R-21, a coverage check-in with the customer's lifetime
savings as the value line and no premium or price figures, with content switched by churn reason and state;
one app push at R-14 for the high band and the app-engaged reasons; a thank-you at R+7. Email and push only.
Tested on the holdout, this entry rule flags 16% of the term-end window at an 11% cancel rate and captures
37% of its preventable cancellations: about 150 to 250 customers a month. Both arms keep the existing
lifecycle flow, so the test reads what the layer adds (aligned with lifecycle comms, 2026-10-21).

## Next step: build the journey (`journeys/RE_ChurnRetention/`, spec v2)

1. Add `AppOpened`, `LifetimeSavings`, `RatingVersion` to the Entry DE and `RatingVersion` to the History
   DE (Claude can do this by API on request).
2. Query activities from `01..03_*.sql` and the daily 10:00 automation, after `Master Customer Journey
   Daily Sends`; run the entry query once and confirm 5 to 10 rows a day with the expected mix of OFFER
   and HIGH bands (Claude can verify by API).
3. Nine content blocks and the R-21 email template from `CONTENT_SPEC.md`; two push variants; subject
   lines per reason as the first A/B. Irene reviews the copy first, then Insurance.
4. Journey `RE_ChurnRetention_<Month>2026`: entry DE, Arm split, wait to R-21, email, push-eligibility
   split, wait to R-14, push, exit on the exit DE, goal "not cancelled 30 days after term end"; a one-step
   thank-you journey on the RENEWED exits.
5. Launch in AZ and RI with the holdout; measurement gates and timing in `TEST_PLAN.md`.
6. In parallel, ask Data Analytics for a customer-month backfill of savings and discount history and
   build `Savings_History__c` to hold it, the same pattern as `Renewal_Offer__c`. The exact request,
   column list, and acceptance checks are in
   `journeys/ChurnRiskActivation/DATA_REQUEST_savings_discount_history.md`. Today Contact holds only
   the current value of lifetime savings and discount, and Account field history on them starts
   2025-11-14, so the model has never seen savings shrink before a cancellation. With that history and
   12 months of renewal offers, v4 can be trained on the same holdout.
