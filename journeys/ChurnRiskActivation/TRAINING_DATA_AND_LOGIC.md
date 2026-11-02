# Voluntary churn model: training data and logic

Prepared for Legal review. HiRoad lifecycle marketing, 2026-11-02. Companion to the RE_ChurnRetention
journey mockup. Technical detail for the Data Science audience is in `CHURN_MODEL_FOR_DATA_SCIENCE.md`;
every build step is in `journeys/ChurnRiskActivation/BUILD_GUIDE.md`.

## 1. What the model is and what it is used for

The model estimates, for each active policyholder, the likelihood of a **preventable voluntary
cancellation in the next 60 days**: the customer chooses to leave because of price, a competing carrier,
or dissatisfaction. It is not a measure of risk, creditworthiness or payment behaviour, and it is not used
for pricing, underwriting, claims or any coverage decision.

Its only use is to help decide who receives one retention email and one app push in the four weeks
before their term ends (the RE_ChurnRetention journey). The score is one of two ways into that journey;
the other is a plain rule on the size of the renewal offer. The customer never sees the score, the band,
or any wording derived from them.

| Item | Value |
|---|---|
| Model type | Gradient-boosted classifier, Salesforce Model Builder (Einstein Studio), Data Cloud |
| Current production version | v3 (live since 2026-10-20); v4 trained 2026-10-31, promotion pending |
| Scored population | Active policyholders in Arizona and Rhode Island (about 7,900 contacts) |
| Scoring cadence | Daily feature refresh; score written to the Contact record monthly on the 2nd |
| Outputs on the Contact record | Score (0 to 100), band (High = top decile, Moderate = next two deciles, Low), scored date, top three contributing factors, a rule-based primary reason code |
| Where the outputs are visible | Salesforce CRM (internal users), Marketing Cloud (as journey entry data) |

## 2. The outcome the model learns from (the label)

Every historical customer-month is labelled from the cancellation reason recorded in Salesforce
(`Contact.Cancellation_Reason__c`). Share of 2026 cancellations through mid-October (7,765 in total):

| Group | Reasons | Share | How it is treated |
|---|---|---|---|
| Preventable voluntary | Due to high premium; Replacement of insurance carrier; Insured request - other; App issue / UX; poor customer service; poor claims service | 28% | **Positive label** |
| Non-payment | Non-payment of premium | 43% | Censored (removed from training) |
| Company cancel | Underwriting or company-initiated | 20% | Censored |
| Unpreventable | Sold vehicle; no longer driving; moved out of state; total loss | 9% | Censored |

"Censored" means that if a customer cancelled for one of those reasons inside the 60-day window, their
row is removed from training and evaluation entirely. They are neither a positive nor a negative example.
This is how the model is kept from learning to find non-payment or underwriting outcomes, which Insurance
ruled out as retention targets on 2026-10-16.

## 3. How the training table is built

The training table is built inside Salesforce Data Cloud from the organisation's own Salesforce data.
No external data, purchased data or third-party enrichment is used.

- **One row per customer per month.** Snapshots are taken on the first of each month from July 2024
  onward. A customer is in a snapshot if their policy was in force on that date. About 237,000 rows over
  27 snapshots, roughly 7,000 to 9,500 customers per month.
- **Point in time.** Every feature is calculated only from events dated on or before the snapshot. An
  audit column records the latest event date used by any feature and is checked on every run; it has
  never exceeded the snapshot date.
- **Train and test are split by time, not at random.** Training uses snapshots through April 2026;
  evaluation uses May through August 2026, so performance is measured on months the model never saw.
- **Rows the journey cannot act on are removed.** Since v4, customer-months where the driving score
  fell 5 or more points over three months while trips held steady are removed from training, matching
  the journey's entry exclusion (Insurance, 2026-10-29).

## 4. Data sources and fields used

All sources are Salesforce objects in HiRoad's production org, synced to Data Cloud. Joins are on the
customer number or contact id and are restricted to dates on or before each snapshot.

| Family | Salesforce source | What is used | What it tells the model | Coverage |
|---|---|---|---|---|
| Tenure and term | Contact | Days since the customer joined, tenure bucket, days since policy effective date, estimated position in the 6-month term, mailing state (AZ or RI) | New customers cancel more; term end is when decisions are made | All rows |
| Renewal offers | Renewal_Offer__c (captured by an Account flow since 2026-10-20, backfilled from field history to 2025-10) | Offered rate for the new term, dollar and percent change from the prior term, rating version, days since the offer | The strongest single driver: an offered increase above $20 a month cancels at 11 to 21% against about 4% | About 22% of rows from 2026-02 |
| Billing (price history) | Bill__c | Net and gross premium on the latest invoice, change in net premium over 3 months, number of invoices | Price level and price change | About 70% |
| Driving telemetry | Monthly_Driving_Stat__c (monthly cycles since 2023-05) | Latest driving score and its trend, trips, miles, monthly earned discount in dollars and its change, cycles seen, recency, trips change | Engagement with the app and the discount the customer is earning | About 45% |
| Savings history (v4) | Savings_History__c (warehouse backfill 2023-05 to 2026-09, extended nightly by an Account flow) | Rated discount percent and its 3-month change, discount dollars and change, lifetime savings to date, savings per month of tenure, standard and net premium on the cycle, earned-discount fraction, cycles seen, recency | How much the customer is saving and whether that is rising or falling | 52 to 58% |
| App usage | MobileApp__c events | App events in the last 30 and 90 days, days since the last event | Engagement | About 62% |
| Email engagement | Individual Email Results (Marketing Cloud sync) | Open rate over 90 days, days since the last email event | Engagement | Varies by year |
| Customer support | Zen_Desk_Ticket__c | Tickets in the last 90 days, days since the last ticket | Service friction | From 2025 |

The current production model (v3) uses 31 of these columns; v4 uses 45 (adds the savings family and the
trips change). The exact lists are in the build guide.

## 5. Data that is deliberately not used

| Excluded | Why |
|---|---|
| Payment Stability Score, credit score, any credit-derived field | Insurance decision 2026-10-16: credit-based signals stay out of retention targeting |
| Non-payment notices, late or past-due flags, payment history | Same decision; also the reason non-payment cancellations are censored rather than learned |
| Email send, open and click **counts** | Removed after v1: the number of sends was dominated by the non-payment reminder journey, so it acted as a payment proxy |
| Driver role on the Contact record | Populated only for customers still active today, so it leaks the outcome |
| Current-value fields (today's lifetime savings, today's discount, real term dates) | Describe the present, not the snapshot month; the point-in-time versions are used instead |
| Lead and quote attributes, post-purchase re-quotes | Tested; no signal for voluntary churn |
| Demographic attributes: age, date of birth, gender, marital status, occupation, household composition | Not in the training table. Location enters only as the state (AZ or RI) |
| Claims history, vehicle details, garaging address | Not in the training table |
| Any data from outside HiRoad's Salesforce org | None is used |

## 6. How the score is used, and the controls around it

1. **Two ways into the journey, both reviewed.** Tier 1 is a rule with no model: the captured new-term
   offer is more than $20 a month or more than 10% up. Tier 2 is the model: score at or above the
   top-decile cut from the latest batch (the cut is stored in a config table and refreshed monthly).
2. **Exclusions applied at entry regardless of score.** Customers with a non-payment notice in the last
   90 days, customers in the non-payment journey, customers whose driving score declined while trips held
   steady, do-not-reach flags, cancelled or pending-cancel policies, and anyone not reachable on email or
   app push are removed in the entry query before the journey runs.
3. **What the customer receives does not depend on the score.** Everyone who enters gets the same
   coverage check-in email for their state. The score and band decide only whether the app push follows.
   No copy mentions the score, the band, payment status, credit, a premium amount, a price change or a rate.
4. **No randomized holdout.** Insurance ruled on 2026-10-29 that no customer is withheld from the
   journey for measurement. The effect is read year over year and by comparing customers just above and
   just below the entry cut.
5. **Human review.** Every content block is reviewed by lifecycle communications, then Insurance, then
   Legal before launch. The exclusion count is reported monthly.

## 7. How well it works, and its known limits

Measured on months the model did not train on (May to August 2026, about 24,000 to 25,000 customer-months):

| Version | Area under the curve | Tenure alone | Top decile cancel rate vs base |
|---|---|---|---|
| Existing "Predicted Did Cancel" score (all-cause label) | 0.51 on the preventable-voluntary outcome | 0.56 | not usable for this purpose |
| v3 (production) | 0.627 | 0.560 | 10.1% vs 5.0% (2.0x) |
| v4 (trained, pending promotion) | 0.639 on the same rows (v3: 0.628) | 0.564 | 11.3% vs 4.9% (2.3x) |

Known limits, all documented in the validation reports:

- The model is modest. It beats tenure alone but does not reach the pre-set target of 0.68, and on
  customers who just received a renewal offer it adds little over the plain offer rule. That is why the
  offer rule is tier 1 and the model is tier 2.
- Premium level and premium increase correlate with non-payment as well as voluntary churn, so the top
  decile carries more non-payment history than the book. The journey-level non-payment exclusion is the
  control for this; the program owner accepted the model as is on 2026-10-20.
- Term position is estimated from the effective date because historical term dates are not stored.
- About half of customer-months have no driving or savings record; missing data is itself a signal the
  model uses.
- v4's top feature (earned-discount fraction) is reconstructed by a flow in production and is present on
  about two thirds of new cycles, lower than in the backfill. This is a known distribution shift and the
  reason v4 has not yet replaced v3.

## 8. Retention, access and change control

- Training tables (`Churn_PIT_Training_Set`, versioned train and holdout views) and score tables live in
  HiRoad's Salesforce Data Cloud instance under the same access controls as the CRM. Scores are written
  to eight fields on the Contact record; three of them are history-tracked.
- Monthly: the training table re-runs and the newest closed month joins the evaluation set; scores are
  rewritten; band cut points are refreshed.
- Any retrain is evaluated with the same script and the same pass lines, compared with the previous
  version on identical rows, and documented in a dated validation report before promotion.
- Decisions log: 2026-10-16 Insurance (exclude non-payment, no credit signals); 2026-10-20 compliance
  approved a 50/50 holdout, later withdrawn; 2026-10-20 program owner shipped v3 as is; 2026-10-21
  Insurance via lifecycle comms (no premium, price or rate figures; email and push only); 2026-10-29
  Insurance (driving-decline exclusion, no discount-drop messaging, no holdout).

## 9. Where to look

- `CHURN_PROGRAM_SUMMARY.md`: program narrative and status.
- `CHURN_MODEL_FOR_DATA_SCIENCE.md`: technical companion.
- `journeys/ChurnRiskActivation/BUILD_GUIDE.md`: every build step and the variable list per version.
- `journeys/ChurnRiskActivation/transforms/README.md`: feature definitions and the transform design.
- `journeys/ChurnRiskActivation/2026-10-20_v1..v3_holdout_validation.md`, `2026-10-31_v4_holdout_validation.md`.
- `journeys/RE_ChurnRetention/`: journey README, content spec, Insurance filter rule, entry and exit SQL.
