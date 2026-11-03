# NBA channel test: analysis plan and read schedule

Written 2026-11-02 for the AC_ReviewQuoteStepJourney version 17 launch. Companion to
`Review_Journey_Test_Spec.md` (what the journey does) and the SQL in this folder (how it is measured).

## 1. Questions, in priority order

| # | Question | Comparison | Decision it drives |
|---|---|---|---|
| Q1 | Does adding a call to a lead who is being texted lift purchase? | CALL_SMS vs SMS, random slice | whether calls stay in the mix and for whom |
| Q2 | Does adding texts to a lead who is being called lift purchase? | CALL_SMS vs CALL, random slice | whether texts stay in the mix |
| Q3 | Is the v17 routing rule right? (low open likelihood -> call) | within low-likelihood leads in the random slice: CALL_SMS vs SMS | keep, flip or retire the rule before v18 |
| Q4 | Did v17 as a whole move purchase against v16? | before/after, all entrants, seasonally adjusted | program-level reporting only |
| D | Diagnostics: reach, click, open, opt-out, call volume | by arm, all leads | operations, not routing |

Primary metric for Q1 to Q4: purchased within 30 days of `NBA_Entry_At__c`. `Purchased_Date__c` is
date-only; `Max_Quote_Step__c = 7.0` is the fallback marker. Intention to treat: a lead counts in the
arm it was assigned, whether or not the text delivered or the call was made.

## 2. Population and analysis sets

- Test population: leads with `NBA_Test_Arm__c` in (SMS, CALL, CALL_SMS) and `NBA_Entry_At__c` on or
  after the v17 publish time. Exclude `INELIGIBLE`.
- Causal set (Q1 to Q3): `NBA_Assignment__c = 'RANDOM'` only. Model-routed leads were chosen by
  score and are never pooled with the slice.
- Reporting set (Q4, D): everyone.
- One row per lead (single entry across versions guarantees this). A lead re-created by a text click
  is a different Lead record; it is a click label on the texted lead, not a new test unit.
- Censoring: a lead enters the 30-day read only once 30 days have passed since entry. Monthly reads
  use entrants up to the 30th day before the read date.

## 3. Pre-registered hypotheses and rules

- H1 (Q1): purchase(CALL_SMS) > purchase(SMS). H2 (Q2): purchase(CALL_SMS) > purchase(CALL).
  H3 (Q3): among low-open-likelihood leads, purchase(CALL_SMS) > purchase(SMS).
- Test: two-sided difference in proportions, 95% interval, plus the Bayesian posterior
  P(arm A > arm B) with a flat prior, reported every month. No peeking penalty is needed for the
  posterior; the frequentist interval is reported at the pre-set read points only.
- Harm stop: if at any monthly read P(an arm is worse than the best arm by more than 3 points) > 0.90
  with at least 300 leads per arm, that arm stops receiving new random assignments.
- Opt-out guardrail: mobile opt-outs within 30 days of entry per texted arm; stop texting an arm if
  its opt-out rate exceeds the SMS arm's by more than 2 points with P > 0.90.
- Call capacity guardrail: calls generated per month (random call arms + model low-likelihood) must
  stay within the call team's agreed volume; at a 50% slice that is about 225 a month, about today's.

## 4. Power and the read schedule

Base rate 11%. Minimum detectable difference (80% power, two-sided 5%) in percentage points, by
months since launch. Arm vs arm is CALL_SMS vs SMS or CALL_SMS vs CALL (1:1). Call factor pools
CALL_SMS + CALL against SMS (2:1) and only answers "does a call help at all".

| Scenario | per arm / month | month 3 | month 6 | month 9 | month 12 | month 18 |
|---|---|---|---|---|---|---|
| today's entry, slice 50% | 75 | 9.5 / 8.5 | 6.5 / 5.7 | 5.2 / 4.6 | 4.5 / 3.9 | 3.6 / 3.1 |
| today's entry, slice 20% | 30 | 16.0 / 14.4 | 10.8 / 9.6 | 8.6 / 7.6 | 7.3 / 6.5 | 5.9 / 5.2 |
| wider entry (x2), slice 50% | 150 | 6.5 / 5.7 | 4.5 / 3.9 | 3.6 / 3.1 | 3.1 / 2.7 | 2.5 / 2.2 |
| wider entry (x2), slice 20% | 60 | 10.8 / 9.6 | 7.3 / 6.5 | 5.9 / 5.2 | 5.0 / 4.4 | 4.1 / 3.5 |

Each cell: arm vs arm / call factor. For reference: +3 points needs ~1,900 per arm, +4 needs ~1,100,
+5 needs ~730. The old router's gap against the control was about 2 points, so an effect worth
routing on is probably in the 3 to 5 point range.

Recommended configuration: widen the entry query (7-day email suppression, 7-day window, keep step
6.0 out only if there is a reason) and run the slice at 50% for the first six months. Every lead still
gets a channel; only how it is chosen changes.

When you can read what (recommended configuration):

| When | What you get | What you can decide |
|---|---|---|
| Launch + 1 week | Pipeline QA: arms are 1/3 each in the slice, Lead fields populated, SMS__c rows per text, NBA tickets created, emails sent; open rate equal across arms | fix wiring; nothing about channels |
| Month 1 | Diagnostics with tight intervals: reach rate per call arm (~14%), text click floor (~1%), opt-outs, call volume, score distribution of the model-routed path | operations, capacity, threshold sanity |
| Month 3 | First purchase read: direction only, 30-day rates with +/-4 point intervals per arm; harm stop check | stop an arm only on clear harm |
| Month 6 | Arm vs arm detectable at ~4.5 points, call factor at ~4; Q3 first look (low-likelihood leads only, wide) | shrink the slice to 20% if Q1/Q2 are trending clearly; keep 50% otherwise |
| Month 9 | Arm vs arm ~3.6, call factor ~3 | provisional routing rule for v18 |
| Month 12 | Arm vs arm ~3, call factor ~2.7; Q3 at ~6 points (low-likelihood is a third of the slice) | v18 decision: which channel for which leads; train the uplift models on the slice |
| Month 18+ | Per-lead uplift model has enough purchases per arm to train (about 1,000 per arm by then only with the wider entry) | replace the rule with the predicted channel |

With today's entry volume and no widening, move every row down by about six months.

## 5. Data sources and the queries

| Measure | Source | Key |
|---|---|---|
| Arm, assignment, entry time, entry scores | Lead: `NBA_Test_Arm__c`, `NBA_Assignment__c`, `NBA_Entry_At__c`, `NBA_Entry_*_Score__c` | Lead Id |
| Purchase | Lead: `Purchased_Date__c`, `Max_Quote_Step__c` | Lead Id |
| Email sends and opens (balance check) | `ssot__EmailEngagement__dlm`, `ssot__EmailName__c LIKE 'AC_Review%'` | `ssot__LeadlId__c` |
| Texts delivered | `SMS__c` (`SMS_Key__c` rows, one per text, since 2026-11-03) | `SubscriberKey__c` / `Lead__c` |
| Text clicks | same-person Lead created with `utm_medium = 'sms'` within 14 days | `IndividualIdentityLink__dlm` |
| Calls made and reached | `Zen_Desk_Ticket_Bronze__dlm`, subject `New Lead- Next Best Action +<LeadId>`, comment text | `Lead__c` / subject |
| Opt-outs | Lead `Mobile_Opt_Out_Date__c` after entry; MC `_SMSSubscriptionLog` | Lead Id |

Canonical read: `Channel_Uplift_Training_Set__cio.sql` (random slice, one row per lead, arm flags,
`Purchased_30d__c`, `Opened_First_Email__c`). The weekly operations query is a count by week of entry,
arm and assignment with sends, deliveries, calls, tickets and opt-outs joined on.

## 6. Analysis per read

1. Balance: entry-score means and lead attribute shares by arm within the slice (they should match;
   a chi-square across state, publisher, step, score tercile).
2. Delivery: texts delivered per texted lead, call tickets per called lead, open rate per arm. Equal
   open rates across arms are the check that the emails really are identical.
3. Primary: 30-day purchase rate per arm with Wilson intervals; pairwise differences with intervals;
   posterior P(A > B). Report the slice only.
4. Q3: the same within the bottom score tercile at entry.
5. Model-routed path: purchase rate by score tercile and arm, reported separately, labelled
   observational.
6. Guardrails: opt-out, call volume, complaints.
7. Q4: v17 monthly purchase rate for all entrants against the same months in v16 and the prior year,
   seasonally adjusted the way the non-pay analysis was.

## 7. Readiness checklist before publishing v17

- Six Lead fields deployed and added to the CRM connector; visible in Data Cloud.
- Email response model scoring into `Email_Open_Likelihood__c`, and the value present in the entry DE.
  If not ready, publish with the model path routing everyone to SMS.
- `SMS__c` feed on the new path (done 2026-11-03; stop the old journey after a few clean days).
- Zendesk NBA tickets still created by the call task (unchanged activity).
- Entry query widened; eligibility rules in place; `AC_ReviewNBA_TestLog` DE created.
- Exit criterion confirmed and set on purchase; goal added.
- First QA read scheduled for launch + 7 days.

## 8. Reporting cadence

- Weekly: operations table by arm (entrants, deliveries, calls, tickets, opt-outs), no purchase.
- Monthly: the read in section 6, two pages, posted to the repo under
  `journeys/AC_ReviewQuoteStepJourney/nba-channel/reads/YYYY-MM.md`.
- Decision points: month 3 (harm), month 6 (slice size), month 9 (provisional rule), month 12 (v18).
