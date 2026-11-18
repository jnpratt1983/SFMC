# What drives the Einstein Lead Score (empirical, 2026-11-18)

Einstein Lead Scoring does not expose its factors to SOQL: the AI insight objects in the org hold only the Einstein
Discovery "Likely to Convert" prediction (448k rows, all for `lead_likely_to_convert__c`), and `ScoreIntelligence`
carries just the score and segment. So this is a reconstruction: 11,804 scored leads created since 2026-10-01, each of
the model's included fields (the Setup "View Included" list) tested for how much it moves the score, both overall and
inside quote-step x lead-age cells so the step and recency effects are held fixed. Purchase (lifetime `purchased__c`) is
shown next to it so the question "is Einstein leaning on things that actually predict buying" can be answered.

## What moves the score, in order

| Factor | Effect on score | Holds within step x age? | Matches purchase? |
|---|---|---|---|
| Quote step (standard behaviour, not in the custom list) | rank corr 0.59; AUC 0.84 for scoring 96+ | n/a | yes, AUC 0.84 |
| Lead age / recency | rank corr -0.46; mean score 87 at day 0-1, 36 at day 14+ | n/a | weak (most purchases happen on day 0-1 anyway) |
| Projected first-month bill | rank corr -0.45; **-0.53 inside every step x age cell** (34 of 34 cells negative) | yes, the strongest custom field | yes: at step 5-6, age <= 7 days, cheapest quartile scores 94 and buys 41%, dearest scores 84 and buys 15% |
| Acquisition channel (utm_source / campaign / content / medium, landing page) | lead_gen 77, (blank) 54, aggregator 41 overall; still 93 / 90 / 87 inside step >= 4, age <= 7 | yes, smaller | yes: lead_gen buys 32%, aggregator 14% in the same cell |
| First-month discount amount | rank corr -0.37, -0.43 in cells | yes, but it is the bill again (discount dollars scale with bill); discount **percent** is +0.08 | discount percent: top quartile buys 16% vs 10% |
| Declined | true scores 31 vs 51 | n/a (declined leads are excluded from the journeys) | yes, 0.6% buy |
| Saved quote / LeadSource "Quote Page- Saved" | true scores 73 vs 47 overall; no gap inside step >= 4, age <= 7 | no | mixed |
| Underwriting score | +0.17 in cells, positive in 91% of cells | yes, modest | hump-shaped: middle quartiles buy 14-15%, ends 10-11% |
| Currently insured status | blank 27 vs CI 64 / NCI 62 | no: the gap is blank vs filled, i.e. "reached the drivers step". CI vs NCI is 2 points | CI 10.8% vs NCI 9.7%, no real gap |
| # of emails received | 1-2 emails: score 78, 3+: 55-64 | partly (-0.08 in cells) | reverse causation: leads who buy fast stop receiving emails (1-2 emails buy 23%, 3+ buy 2%). Einstein reads "more emails" as "colder", which is tenure, not intent |
| Credit score | +0.04 in cells | barely | purchase 9% in the lowest quartile, 14% in the others |
| Five-year PLE, five-year LTV | 0.02 / -0.10 in cells | no | PLE flat-to-hump, LTV flat |
| State | RI 40 vs AZ 50; 81 vs 90 inside the fresh step >= 4 cell | yes | RI buys 7% vs AZ 21% in that cell |
| Vehicle make / model | eta2 0.09, driven by blank vs filled | mostly a step proxy | n/a |
| Auto/renters bundle opt-in | 113 leads, 60 vs 48 | too few | 11.5% vs 6.6% |

Dead inputs: `of_Sessions__c` (0% populated), `Projected_Bundled_Dollars_Off__c` and `Projected_Bundled_First_Month_Bill__c`
(0%), `of_Calls_to_CC__c` (2%). They are in the model but carry nothing.

## Reading

1. The score is, in order: how far the lead got in the quote, how recently, how cheap the quote is, and which channel
   brought them. Those four explain most of it, and all four also predict purchase in the same direction.
2. The one custom field that adds real information beyond step and recency is **projected first-month bill**. Price is
   the lever Einstein has found. That lines up with the Scenario 1 savings-forward creative test.
3. **Emails received** is the field to be careful with. It falls with intent only because buyers leave the journey early.
   If journey cadence changes (Scenario 2 sends fewer messages to one arm), the score of that arm will drift for a reason
   that has nothing to do with the lead. Consider excluding it (and `of_SMS_Delivered__c`) from the model before the
   channel test; the Setup page allows it.
4. Credit score, underwriting score, PLE and LTV barely move the score. PLE and LTV are value fields, not propensity
   fields, which is why the plan uses them as a segmentation lens rather than expecting the score to carry them.
5. Currently-insured status matters to the score only as "has the lead reached the drivers step". CI vs NCI is not a
   propensity difference in this data.

Script: `scripts/lead_score_factors.py` (export + tables).
