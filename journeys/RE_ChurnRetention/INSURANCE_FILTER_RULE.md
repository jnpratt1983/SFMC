# Retention journey: audience filter rule (for Insurance sign-off)

Prepared 2026-10-29 by Jennifer Pratt for Jennifer Kellett and Sandy Betz. Call Monday 2026-11-02.
Applies to the term-end retention journey (RE_ChurnRetention) and, at the next retrain, to the churn
model's training data.

## What Insurance asked for (2026-10-29)

Retention effort should not go to customers whose risk is getting worse. Customers whose driving scores
dropped, and whose discount fell as a result, are left out of outreach. Where a discount fell for another
reason, step in only if the cause is a credibility problem (trips not recorded).

## The rule

**Excluded from the journey:** any primary driver whose average driving score fell by 5 points or more
between their latest completed month and the month three months earlier, while their trips did not fall
(latest month has more than half the trips of the earlier month). They keep every communication HiRoad
sends today; they get nothing extra from this journey.

**No discount-drop messaging to anyone.** The journey sends nothing about a discount going down. Every
entrant gets the same coverage check-in email: no premium, price or rate figures, nothing about driving
getting worse. This honours "only intervene on credibility problems" without having to classify the cause
of each drop.

## The numbers (monthly driving cycles since April 2026, pulled 2026-10-27)

| Group | Customers |
|---|---|
| Active primary drivers on the book | 5,431 |
| With four or more months of driving data since April | 3,109 |
| Whose monthly Safe Driving Discount fell by $5 or more over three months | 959 |
| of which: trips or miles fell by half or more (recording problem) | 127 |
| of which: **driving score fell 5+ points with steady trips (the excluded group)** | **163** |
| of which: steady trips and scores, discount still fell (cause not visible) | 669 |

Discount figures are dollars of earned discount per month. Driving score is the average of the four
app subscores (safe speeds, smooth driving, distracted driving, driving patterns).

| Next 30 days of term ends | Customers |
|---|---|
| Drivers meeting the exclusion rule, whole book | 138 |
| Reaching term end in the next 30 days | 37 |
| Of those, who would otherwise have entered on the high-risk tier | 5 |
| Others among the 37 enter only if their new-term price also rose $20 or 10% | a few |

The rule removes roughly 5 to 10 customers a month from a journey of about 200.

## How it is applied

- Checked on the day of entry (R-27) from `Monthly_Driving_Stat__c_Salesforce`, already synced to
  Marketing Cloud. Not from a monthly snapshot.
- Applied to the training set at the next scheduled retrain (v3.1), so the model stops learning from
  these customers.
- Exclusion count reported alongside the journey each month.

## Not covered yet

- **Other drivers on the policy.** The driving feed carries only the primary driver's cycles (PNI rows
  only since 2026-09). Data request to the driving data team; the rule extends to all drivers once the
  feed includes them.
- **The 669 unexplained drops.** Data Analytics asked how the monthly discount is calculated. Until then
  they are treated like everyone else: standard coverage email, no discount messaging.
