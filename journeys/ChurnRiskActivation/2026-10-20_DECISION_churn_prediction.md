# Decision: how HiRoad predicts voluntary churn (2026-10-20)

**The prediction is the renewal offer.** A customer offered a monthly increase of more than $20 at
renewal cancels for a preventable reason at 11% in the next 60 days, rising to 21% above $50, against
4% for everyone else. That single fact, measured on 11,725 renewal offers since December 2025, is
stronger than any model built this week, and it is stronger because it is the cause, not a correlate.

| Offered monthly change | Offers | Cancel within 60 d | within 90 d |
|---|---|---|---|
| decrease | 7,207 | 4.1% | 5.5% |
| +$0 to $10 | 1,532 | 4.2% | 6.1% |
| +$10 to $20 | 1,099 | 4.3% | 6.2% |
| **+$20 to $30** | 734 | **11.0%** | 14.0% |
| **+$30 to $50** | 631 | **11.6%** | 14.4% |
| **+$50 and up** | 522 | **20.9%** | 24.7% |

Uncensored customers with an offer issued in the 60 days before the snapshot; non-pay, company and
unpreventable cancellations excluded. By percent the step is at +10%: 9.1% cancel from +10% to +20%,
14.4% above +20%.

**The models, honestly.** Three were tested against actual cancellations: the existing normalized
score (0.59 AUC), v1 (0.58) and v2 with driving data (0.60). No single input in the book scores above
0.56 alone. Inside the renewal window the best model reaches 0.616 and the "$20 rule" reaches 0.614.
The models are not wrong; the data cannot say who leaves except where price says it. More versions will
move the third decimal.

## The recommendation

1. **Target renewal price shock, nothing else, for the first twelve months.** Journey entry: offer
   issued, increase more than $20 a month or more than 10%, term ends within 45 days, primary named
   insured, no non-pay notice in 90 days. That is 100 to 180 customers a month in AZ and RI (the +$20
   share of offers has risen from 108 in April to 179 in August), cancelling at 11 to 21% without
   intervention. It is small and it is where the money is.
2. **Run the approved 50/50 holdout on exactly that population.** With a 13% base rate and 150
   entrants a month, a 25% relative reduction reaches significance in about 11 months of entries;
   a 35% reduction in 6. Both are shorter than the earlier estimate because the base rate is three times
   higher than a model-selected population's.
3. **The "why" is already known: price.** Tracks by top factor are unnecessary for this journey. One
   message family: what the discount is worth over the new term and how to keep it, with the Engage
   content for customers whose driving score has fallen (the second-strongest signal, 7.2% vs 5.9%).
4. **Keep the v2 score as a monthly reporting field on Contact**, labelled as a general risk score,
   not as targeting. Retire the normalized score and its journey placeholder.
5. **Stop building models until one of two things changes:** the renewal offer history reaches 18
   months (v3 on the renewal window then has enough positives to beat the rule), or Contact field
   history on savings and discount exists so the non-renewal half of churn has a measurable driver.
   Set a calendar reminder for April 2027. Nothing before then will pass.

## What exists and runs without further work

- `Renewal_Offer__c` captures every offer from the Account flow; 7,606 backfilled; streaming into Data
  Cloud. This is the trigger object.
- `ChurnPITTrainingSet` and the views rebuild monthly; `validate_holdout.py` re-scores any model in
  minutes.
- Journey spec, entry/suppression/exit queries, DE schemas and the test plan in `journeys/RE_ChurnRetention/`;
  the entry query needs its score condition replaced by the offer condition above, which is a
  three-line change.
