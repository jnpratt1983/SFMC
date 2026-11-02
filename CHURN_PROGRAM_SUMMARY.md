# Voluntary churn program: what was built, why, and what comes next

Written 2026-10-21 for HiRoad lifecycle marketing, Insurance and Data Science; updated 2026-11-02 with the v4
model and the savings history it runs on. Companion to `CHURN_PROGRAM_CHECKLIST.md` (status by item) and the
detailed reports under `journeys/ChurnRiskActivation/`.

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
change, trips, miles. The discount figures are dollars of earned discount per month. Where the discount fell
$5 or more over three cycles, churn runs 7.2% against 4.9 to 6.2%.

**Price history from bills.** Net premium per invoice, every month, for every billed customer: the latest
amount and the change over three months. Up $50 or more in three months: 10.8% cancel; flat or down: 4 to
5%. It covers 70% of rows in every year, where offers cover 22%.

**Email history recovered by address.** HiRoad emails leads far more than customers, and sends made
before conversion stay on the lead record. Matching Individual Email Results on the email address instead
of the contact lookup found 87,529 customer-period sends in 2024 and 106,197 in 2025, where the lookup
found 5,181 and 3,652.

**Savings and discount history, backfilled and captured (2026-10-31).** Lifetime savings and the telematics
discount lived on Account as one running total and one current percent, so the model had never seen savings
shrink before a cancellation. Data Analytics delivered a customer-month extract (ANA-6320, Liz Pund): 363,264
rows, May 2023 to September 2026, cancelled customers included. We built `Savings_History__c`, one row per
customer per billing cycle with standard and net premium, rated discount percent, discount dollars, lifetime
savings to date and the driving-earned discount fraction, loaded the backfill, and an Account flow
(`Savings_History_Capture`) now writes each cycle as it closes. The earned fraction is a warehouse figure that
no Salesforce field holds, so version 2 of the flow reconstructs it from the driving cycle's earned dollars
over the discountable base; on backfill cycles since mid-2025 it lands within 0.01 of the extract on 83%.
Streamed into Data Cloud and joined to each snapshot on customer number, point-in-time on the cycle close, it
covers 52 to 58% of training rows by year, in line with the driving branch. The first read of it, before any
model:

| Savings history signal (uncensored rows) | Preventable cancel within 60 days |
|---|---|
| fell 5 points or more over about three months | 8.2% |
| flat | 6.6% |
| rose 5 points or more | 5.3% |
| latest rated discount under 10% | 8.7% |
| latest rated discount 40% and over | 4.9% |

**What was deliberately left out.** Every payment-behaviour field (notices, late rates, days past due,
Payment Stability Score, credit score). `Driver_Role__c`, which is populated only on customers still
active and would have leaked the label. Lead attributes and post-purchase re-quotes, which turned out
to mark customers who lapse and re-buy, not customers deciding to leave. From v4 onward, the current-value
lifetime savings and telematics discount columns, replaced by their point-in-time versions; and every row
that meets the Insurance driving-decline rule of 2026-10-29 (display score fell 5 or more points over about
three cycles while trips did not halve), removed from both training and holdout. That rule marks 4 to 9% of
rows by year and the slice it removes cancels slightly more often (7.2% against 6.7%).

## The models, honestly

| Version | Inputs | Holdout AUC (snapshots May to Aug 2026; 25,419 rows and 1,269 cancels through v3, 24,450 rows and 1,209 cancels for v4 after the driving-decline exclusion) | Verdict |
|---|---|---|---|
| Normalized score (existing) | trained on all cancellations, non-pay included | 0.51 on the preventable label | not usable under the Insurance decision |
| v1 | tenure, term, app, email, tickets, offers | 0.579 | fails; top contributor was the non-pay journey's reminder count |
| v2 | + driving, email by address, state; no send counts | 0.599 | better, monotonic deciles, still short |
| v3 | + premium history from bills; no email counts | 0.627 | clears tenure + 0.05; three of four tenure buckets pass; first lift outside the renewal window (0.628); **the production model today** |
| **v4** | **+ 13 savings-history columns and trips change; current-value savings fields out; driving-decline rows out** | **0.639 (v3 scores the same 24,450 rows at 0.628)** | **beats v3 on identical rows, gain +0.003 to +0.020 at 95%, ahead in 200 of 200 resamples; all four tenure buckets pass 0.60; top decile 11.3% (2.28x) against 10.0%; trained 2026-10-31, promotion pending** |

v4 still does not reach the 0.68 target or a 2.5x top decile. Its gain comes from the savings history: the
driving-earned discount fraction is the single largest contributor (9.0% of importance), ahead of the bill
columns, and the latest net and standard premium and the count of savings cycles also sit in the top fifteen.
Deciles, top first (base 4.9%): 11.3, 6.5, 5.2, 5.6, 4.8, 4.6, 3.6, 3.2, 2.7, 2.0; against v3 on the same
rows it lifts the top decile by 1.3 points and lowers the bottom one by 0.6, so it separates the tails better
and flattens the middle. By cancel reason it scores 0.665 on high premium (line 0.70), 0.611 on carrier
switch (0.65) and 0.612 on insured request (0.60). Model Builder's own cross-validation figure for v4 (0.673)
is inflated by contacts appearing on both sides of a random split and is not quoted, as with v3. The 45
variables and the comparison method are in `BUILD_GUIDE.md` (Version 4) and
`2026-10-31_v4_holdout_validation.md`; a v4 model must not be scored on the v3 holdout object, which lacks
14 of its inputs, so versions are compared by joining their score objects on the row key.

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

- **Score on every active customer, from v3.** 7,878 contacts scored on 2026-10-20 with v3: 795 High (score 59.99
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
- **v4 trained and validated, not yet scoring production.** The training transform carries the savings
  branch (237,547 rows, 78 columns) and the V4 train and holdout views exist with the driving-decline rows
  removed. Promotion was made conditional on the capture flow populating the earned discount fraction, the
  model's top input, once the backfill ages out. Read on 2026-11-02: the flow has written 237 cycle rows since
  the 2026-11-01 nightly batch, 175 of them with a discount, and 115 of those (66%) carry the earned fraction
  (mean 0.30, range 0.03 to 0.50). The gap is cycles with no matching driving record, and the driving feed has
  carried primary drivers only since September 2026, so coverage in production will sit below the backfill's
  roughly 90%. The model treats a missing value as "no driving data", which it saw in training, so this is a
  known degradation rather than a break; a recurring feed of the engine's own value from Data Analytics would
  close it.

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
6. Done 2026-10-31: the savings and discount backfill (ANA-6320) landed, `Savings_History__c` and its
   capture flow are live, and v4 was trained and validated on it (see "The models, honestly").
7. Promote v4 to production scoring, now that the flow is writing rows. Accept or resolve the earned-fraction
   coverage noted above (66% of discount cycles against about 90% in the backfill), then: update the scoring
   transform `ChurnPITScoringSet` from the regenerated definition, run it and re-map its object so the savings
   columns are visible; create the production predict job on v4 and retire the v3 job after the first v4 batch;
   point `write_back_scores.py` at the new output and re-derive the High and Moderate cut points into the
   journey's config DE. Claude does the transform and write-back by API; the predict job is a UI step.
8. Keep re-reading the holdout as snapshots close: the next genuinely new read comes when the 2026-09 snapshot's
   60-day window closes, and the first live read of production scores against real cancellations is
   2026-12-19. Promote a later version only if it beats the live model on the same rows, as v4 did.
9. Raise two acceptance gaps from the backfill with Data Analytics: lifetime savings ties out to the Account
   field within $1 on only 46% of current cycles, and 3,633 customers in the extract (2023 to 2024 leavers)
   have no Contact. Ask for the engine's earned discount fraction as a recurring feed.
