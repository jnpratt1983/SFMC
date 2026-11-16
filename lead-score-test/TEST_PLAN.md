# Einstein Lead Score in the acquisition journeys: test plan

Written 2026-11-09, revised 2026-11-16 (7-day read; test assignment moved from custom Lead fields to Campaigns, user decision) and 2026-11-10 after the first forward read (`EARLY_READ_2026-11-10.md`: 24-hour Lead update rule, person key, purchase-flag flapping, band guidance). Earlier revisions the same day after two decisions: the user owns the Marketing Cloud sync change, and the
two scenarios run in two different journeys (Scenario 1 in Purchase, Scenario 2 in Drivers; Coverages is excluded because another test is running there). Covers the two roadmap items: **Combination of scoring (4Q26)** and
**Communication medium by propensity (1Q27)**. Companion to `scripts/lead_score_read.py`
(the purchase read) and `scripts/lead_score_return_read.py` (back-to-quote read, person-level join) and `data-cloud/nba-channel/` (the channel test already built into the Review journey).

## 0. What we know going in (2026-11-09)

| Fact | Evidence | Consequence for the test |
|---|---|---|
| Einstein re-scored every lead between the 11-08 and 11-09 snapshots; scores went from 80% at "83" to a spread over 1-99 | `Lead_Score_Snapshot__c`, 7,420 leads changed | The old model had no usable signal (AUC 0.55 for 7-day purchase). Every read below is on the **new** scores, which have no forward outcomes yet |
| The new score tracks lead age (0-3 days old: mean 81; 21-30 days: mean 36) and quote step (corr 0.47) | Nov 9 snapshot, open leads | Journeys take leads created in the last 3 days, so entrants will cluster at the high end. Bands must be set on the **entrant** distribution, not the lead population |
| `Lead_Score__c` on Lead = Einstein score, copied nightly by `LeadScoreSyncBatch` (Kevin Brown, 2026-11-04); identical to `ScoreIntelligence.Score` on all 8,017 populated leads | Lead export | A plain Lead field exists, so Marketing Cloud Connect can sync it and query activities / decision splits can read it. Lag up to ~24h |
| Einstein removes the score once a lead converts; `Lead_Score__c` keeps the last value | field description; 22% scored at step 7 | Never read "current score vs purchased" from Lead. Reads use the **entry-time** score stamped by the journey or the snapshot table |
| `Five_Year_PLE__c` (Kevin Brown, 2026-04) and `Five_Year_LTV__c` (2026-02) are populated only once a quote is rated: 100% at steps 4-7, under 10% at steps 1-3 | Lead export, 30 days | Any test that uses PLE or discount tier has to run at step 4 or later. `Five_Year_LTV__c`, `First_Month_Discount_Amount__c`, `Projected_First_Month_Bill__c` are already in the MC Lead sync (used by `AC_Purchase_v4`); `Lead_Score__c` and `Five_Year_PLE__c` are not |
| Discount tier ≈ `First_Month_Discount_Amount__c / (discount + Projected_First_Month_Bill__c)`; quartile cuts 19% / 27% / 29%; purchase rises 30% -> 40% across quartiles at step >= 5 | Lead export | Discount tier is a strong **segmentation** variable now. Changing the discount itself is out of scope until the LTV test completes (June 2027) |
| PLE is not monotonic with purchase (quartiles 27 / 40 / 31 / 34%); LTV is flat | Lead export, step >= 5 | PLE is a value lens, not a propensity lens. Use it to define who is worth extra effort, not to predict who buys |
| `AC_ReviewQuoteStepJourney` v17 (the NBA channel test, published 11-03) has had **zero entrants**: the entry gate needs `Last_Channel_Scoring_Date__c`, and only 217 of 2,247 leads created since 11-03 are scored. No lead carries `NBA_Test_Arm__c` | Lead counts, entry DE row count 0, journey history 0 rows | Review is spoken for and currently dark. Do not put a second test in it; fix the scoring chain first (`SCORING_SCHEDULE_2026-11-04.md`) |
| The Coverages step journey IS live: `AC_CoveragesQuote_September2026` v5 (the list shows the newer draft's name, `AC_CoveragesQuote_October2026` v6, 63 activities). 110 contacts messaged yesterday. A copy `TEST-AB-AC_CoveragesQuote_October2026 (Copy)` has been published since 2026-10-23. 5% of entrants loop back every 15 min for 3 days after ES1 fails (see memory `coverages-journey-entry-loop`) | journey history 11-08, journey list | **Excluded** (user, 2026-11-09): another test is running in Coverages |

| The quote flow updates a Lead for only 24 hours after creation (product rule, Jennifer 2026-11-10; history shows sync tails to 48h, nothing after). A later return is a new quote and a new Lead, matched by email or cookie ID `optimizely_dna__Visitor_Id__c` (4.4% of leads in days 2-7, 2.2% in days 7-30); merges only happen in the first hour | LeadHistory since 10-25, `EARLY_READ_2026-11-10.md` | "Back to quote" for journey leads = new Lead with the same email or cookie ID after entry. Reads join on both keys; purchase credit follows the person |
| `purchased__c` flaps true/false every ~30 min on ~1 in 5 purchasers for up to 2 days (quote sync vs purchase sync) | LeadHistory, 162 of 762 purchasers since 10-25 | Reads take the FIRST purchased=true; journey exit on `purchased__c` can lag up to 2 days. Needs an owner |
| First forward day on the new scores (2026-11-10, 31h): on 0-3-day leads the score predicts coming back to the quote (terciles 3.4% / 10.7% / 12.7%; AUC 0.64 vs step 0.58; separates within steps 1-3, saturated at 91-99 for steps 4-6); 9 purchases, all in 96-99; on leads older than 3 days the score only restates age (AUC 0.54-0.58 within age buckets) | `EARLY_READ_2026-11-10.md` | Bands for Drivers: whole range. Bands for Purchase: cut inside 91-99 (96+ vs below). 7-day read 11-17 stands |

| 7-day read (2026-11-16, first full window, 668 fresh leads / 26 purchases; 2,209 fresh leads with partial windows / 102 purchases): 7-day purchase by score 96-99 = 8.6-10.9%, 91-95 = 3.7-4.5%, 90 and under = 0.5-0.7%. Score alone AUC 0.77-0.80 vs quote step 0.72 and vs step+age combined 0.70 (cross-validated). Back to quote: 96-99 and 91-95 at 15-17%, under 90 at 8-10%, but almost all of that is the step (step+age 0.54, +score 0.57). Older leads (4-30 days): purchase rises monotonically with score inside each age bucket (4-7 days: 0.0 / 0.3 / 1.4% by tercile) on 21 events | `EARLY_READ_2026-11-10.md`, update 2026-11-16 | The score clears the step+age bar for **purchase on fresh leads**. Use it as the propensity lens in both journeys; do not expect it to move back-to-quote on its own. Purchase cut 96+; Drivers HIGH >= 80 |

Primary outcome everywhere: `purchased__c` true (first true in LeadHistory, or `Purchased_Date__c`) within 30 days of entry (user decision 2026-11-09).
Secondary outcome everywhere: **back to quote** = a new Lead with the same email or cookie ID (or a quote-step/session change on the lead itself inside its first 24 hours) within 7 days of entry; base rate 4-8% on fresh leads, so it reads in weeks rather than months.

## 1. Journeys: Purchase for Scenario 1, Drivers for Scenario 2

Decision 2026-11-09: one journey per scenario, no shared entrants. Candidates, AZ/RI leads created in the last 30 days, excluding compare and renters landing pages:

| Journey (feeder step) | Leads / 30 days | 30-day purchase | PLE populated | Score populated | Structure | Verdict |
|---|---|---|---|---|---|---|
| **AC_PurchaseQuoteStepJourney_July2026 (6.0)** | 477 | 13.0% | 100% | 92% | 3 emails + SMS variant, one availability split, v12; ~24 contacts/day | **Scenario 1** |
| **AC_DriversQuote_July2026 (3.0-3.5)** | ~2,220 (SMS-eligible ~50%) | ~1.2% | 60% (steps 3.2-3.5) | 99% | 3 emails + SMS variants, one availability split, STO 24h, v19; ~136 contacts/day; no test copy running | **Scenario 2** |
| AC_VehiclesQuoteStepJourney_July2026 (2.0/2.5) | ~1,175 (SMS-eligible 47%) | ~1.6% | <10% | 98% | Same shape as Drivers; ~120 contacts/day; ES1 failure loop suspected | Fallback for Scenario 2 |
| AC_CoveragesQuote_September2026 v5 (4.0/4.5) | 1,480 | 2.6% | 100% | 98% | `TEST-AB-AC_CoveragesQuote_October2026 (Copy)` running since 10-23 | Excluded: another test running |
| AC_SavedQuote_July2026 (saved quote, mostly step 5) | 392 (SMS-eligible 39%) | 11.7% | 99% | 92% | 5 emails + 3 SMS, engagement decisions, v49 | Reserve |
| AC_ReviewQuoteStepJourney_November2026 (5.0/5.5) | 616 | 7.1% | 100% | 96% | NBA channel test lives here; 0 entrants since 11-03 | Do not touch |
| AC_QuoteDiscovery / AC_Compare (1-2) | ~1,100 | 1.3-2% | <10% | 98% | 67 / 63 contacts a day | Too small |

Why Purchase for Scenario 1: all three scoring inputs are populated, the purchase rate is the highest (each lead
buys the most statistical power), the structure is the simplest to split and restore, and it is clear of the NBA
test. Its weakness is volume (~480 leads a month).

Why Drivers for Scenario 2: Coverages is excluded (another test is running there). Drivers is the next-largest
SMS-eligible population among the clean journeys (~1,100 SMS-eligible entrants a month, ~550 per arm), its feeder
covers steps 3.0-3.5 so 60% of entrants already carry PLE and discount, every entrant is scored, no test copy is
running on it and no re-entry loop has been seen (Vehicles is suspected of one). Its weakness is the purchase base
rate (~1.2%), so the Q1 readout is SMS cost, opt-outs, click-leads and purchase direction; a 1-point purchase read
needs ~3,300 per arm, about six months. Back to quote (new Lead with the same email or cookie ID within 7 days, base ~4-8% on fresh leads) is the intermediate outcome; it reads
in weeks, and the first-day read shows the score separates it at steps 1-3. Vehicles is the fallback.

Published test copies still exist for Purchase (`TEST-AC_PurchaseQuoteStepJourney_February2026 (Copy)`, 2026-03) and
SavedQuote (`TEST-SMS-AC_SavedQuote_March2024 (Copy)`, 2025-08); neither sent anything on 11-08, so they look dormant.
Confirm before publishing in Purchase.

## 2. Harness (build once, reuse in every journey). No custom Lead fields.

Decision 2026-11-16: test assignment is recorded with standard **Campaigns**, not custom fields on Lead. Nothing is deployed
to Salesforce for a test; a new test is a new set of campaigns.

1. **Marketing Cloud Connect sync** (owner: Jennifer): add `Lead_Score__c`, `Lead_Score_Last_Update__c`, `Five_Year_PLE__c`
   to the synchronized Lead (enterprise BU 110006745). Verify with a query on `ent.Lead_Salesforce`; the Contact Builder link
   in the child BU does not pick up new columns, but query activities do. This is the only Salesforce-side prerequisite.
2. **Campaigns** (standard objects, created in Setup or by `sf data create record`): one parent per test
   (`LS Test - Purchase - Savings Creative`, `LS Test - Drivers - Channel`) and one child per arm (`... - CONTROL`,
   `... - VARIANT`; `... - SMS_EMAIL`, `... - EMAIL_ONLY`, `... - INELIGIBLE`). Type "Test", Status "In Progress", Active.
   Confirm the Marketing Cloud Connect integration user can create Campaign Members (Campaign read + CampaignMember create).
3. **Journey**: new version. Immediately after entry: RANDOMSPLIT 50/50 -> one Sales Cloud **Campaign Member** activity per
   arm (adds the lead to the arm's campaign) -> Join back into the existing paths or into the variant path. Decision splits
   read Journey Data (the entry DE columns). Exit criterion stays purchase/declined. Entry mode stays single entry.
   Arm = campaign membership; entry time = CampaignMember.CreatedDate.
4. **Entry values** are not stamped anywhere. Entry score = latest `Lead_Score_Snapshot__c` row on or before the entry time
   (the journey itself only ever sees the nightly copy, so this is the same value). Entry PLE and discount tier = the Lead
   export values; both are fixed once the quote is rated. Segment (HIGH_PROP x HIGH_PLE x TIER) is computed at read time.
5. **Feeder queries**: add `Lead_Score__c`, `Lead_Score_Last_Update__c`, `Five_Year_PLE__c` (and for Purchase
   `Projected_First_Month_Bill__c`, `First_Month_Discount_Amount__c`, already selected) to `AC_Purchase_v4` -> `AC_Purchase_v5`
   and `AC_Drivers_v5` -> `AC_Drivers_v6`; add the same columns to the entry DEs `AC_Purchase_AF_02182026` and
   `AC_DriversQuote_AF_04252024`. In `AC_Drivers_v6` also exclude leads already in the journey (guards against the
   ES1 re-entry loop seen in Coverages and suspected in Vehicles). Unscored entrants (today ~8%) are randomized like everyone
   else and read as their own band.
6. **Mirror DE** `AC_JourneyTest_Log` (Update Contact activity on each arm: subscriber key, journey, arm, entry score) as the
   Marketing Cloud-side copy for QA and for the SMS cost read.
7. **Read**: CampaignMember (arm, entry time) x `Lead_Score_Snapshot__c` (entry score) x Lead export (purchase, PLE,
   discount, email, cookie ID). Every read works at the person level: a return or a purchase after entry can land on a NEW
   Lead (the quote flow updates a Lead for only 24 hours), so join entrants to later Leads on email and
   `optimizely_dna__Visitor_Id__c`, and take the FIRST `purchased__c` = true in LeadHistory (the flag flaps on ~1 in 5
   purchasers). `scripts/lead_score_return_read.py` already does the person join; a `--campaign` option for the arm is to be added once the campaigns exist.
   CampaignMember is a standard object, so the same table is available in Salesforce reports and Data Cloud without new metadata.

## 3. Scenario 1: Combination of scoring (4Q26)

Goal for the quarter: define the combined segment and show it separates purchase, then launch the journey test
that asks whether the segment deserves different treatment. The quarter has seven weeks left, so the journey
test launches in December and its purchase read lands in Q1.

**3a. Observational read (no journey change, start now).** Weekly from `scripts/lead_score_read.py` extended with
PLE and discount tier: 30-day purchase by entry-score tercile x PLE half x discount quartile, point in time
(snapshot taken before purchase). First read with the new scores: ~2026-11-23 (14 days of forward window).
Deliverable by 2026-12-12: a one-page segment table with purchase rate, lead counts and the proposed cuts.

Provisional cuts (to be reset on the first two weeks of **entrant** data, because entrants are 0-3 days old and
score high), and per journey because the entrant score ranges differ: **Purchase** (step 6, entrants score 94-97 median) HIGH = 96+,
LOW = below 96, since the first-day read shows no separation inside 91-95 at steps 4-6; **Drivers** (steps 3.0-3.5, medians 62-95)
HIGH >= 80, LOW < 60, MID between. PLE HIGH >= 250 (population median 256);
discount tier 1 = top quartile (>= 29%), tier 2 = 27-29%, tier 3 below.

**3b. Journey test in Purchase (publish target 2026-12-08).** Question: does leading with the lead's own
savings numbers lift purchase, and does the lift concentrate in HIGH propensity x HIGH PLE x tier 1-2?

- Arms: CONTROL = today's three emails. VARIANT = same cadence and STO, savings-forward creative that puts
  `First_Month_Discount_Amount__c` and `Projected_First_Month_Bill__c` in the subject and hero (both fields are
  already in the entry DE; no new data). One lever only; no cadence change in this version.
- Randomize 50/50 across all entrants, stratified by nothing (campaign membership fixes the arm and entry time, the
  snapshot table fixes the entry score, so the subgroup read is pre-registered, not post hoc).
- Primary read: VARIANT vs CONTROL, 30-day purchase, all entrants. Secondary (pre-registered): the same within
  the HIGH x HIGH x tier 1-2 segment and within everyone else; the interaction is the roadmap question.
- Power at a 13% base, 80% power, two-sided 5%: +5 points needs 830 per arm; +3 needs 2,270 per arm. Purchase
  gives ~240 per arm per month, so +5 reads in ~3.5 months (mid-March) and +3 in ~10. The segment-level read
  will not be conclusive before Q2; treat it as directional in the Q1 readouts. SavedQuote is the reserve if
  more volume is needed and the two-journey rule is relaxed later.
- Secondary: 7-day back to quote (new Lead, same email or cookie ID) by arm; at ~240 per arm per month it reads a 5-point difference by March.
- Guardrails: unsubscribe and complaint rate by arm; no change to SMS or calls in this test.

**3c. Discount-tier treatment test** (changing the offer, not the message) stays parked until the LTV test completes
(June 2027), per the roadmap. Discount tier is a segmentation variable only until then.

## 4. Scenario 2: Communication medium by propensity (1Q27), in Drivers

Question: does adding SMS to email lift purchase more for HIGH propensity leads than for LOW, and can LOW propensity
leads go email only (or to Next Best Action) without losing purchases?

Design: within SMS-eligible entrants of `AC_DriversQuote` (mobile present, no mobile opt-out, the existing
"Email & SMS" path), RANDOMSPLIT 50/50 -> SMS_EMAIL (today's ES1/SE1 path) vs EMAIL_ONLY (today's E1/E2/E3 path)
regardless of score; the Campaign Member activity records arm and entry time, the snapshot table supplies the entry
score. Nothing is routed on the score yet; the score is recorded and read by band. Routing on it is the next version once the
interaction is measured. Email-ineligible and SMS-ineligible leads follow today's paths and join the INELIGIBLE campaign.

Prerequisites specific to Drivers: dedupe entrants in `AC_Drivers_v6` so a lead whose first email fails is not
re-randomized; confirm one Start row per contact in journey history during QA; keep SE1/SE2 unchanged so the cost
read is against today's spend.

Readouts, in the order they become readable:

1. **Cost** (month 1): SMS segments per entrant by arm from `SMSMTEvent` / the lifecycle watch runner. EMAIL_ONLY
   for half the SMS-eligible entrants removes ~550 texts a month (two per lead) at today's volume.
2. **Diagnostics and back to quote** (month 1-2): mobile opt-outs by arm, same-person click leads (`utm_medium = sms`) by arm and band,
   email open rate by arm (should be equal), unsubscribes; 7-day back-to-quote (new Lead, same email or cookie ID) by arm and band, ~550 per arm per month
   at a 4-8% base reads a 3-point difference in about two months.
3. **Purchase, non-inferiority for LOW** (month 4+): 30-day purchase EMAIL_ONLY vs SMS_EMAIL within LOW propensity.
   At a ~1.2% base and ~550 per arm per month, a 1-point difference needs ~3,300 per arm (about six months); the Q1
   read is direction and a Bayesian P(EMAIL_ONLY within 1 point of SMS_EMAIL).
4. **Interaction HIGH vs LOW** (Q3): the roadmap question; pre-registered, read when each band has ~2,000 per arm.

The NBA random slice in Review (once it has entrants) supplies the call-arm answer for LOW propensity leads; do not
add a call arm here. The roadmap says Scenario 2 follows "more insights from NBA full audience testing"; that test
has not started (zero entrants), so fixing the channel-scoring schedule is the first task on this list.

## 5. Timeline and read schedule

| Date | Milestone |
|---|---|
| 2026-11-10 | First forward read done (`EARLY_READ_2026-11-10.md`). Find an owner for the `purchased__c` flapping. Fix channel scoring chain so Review v17 takes entrants (NBA test clock starts). Jennifer adds `Lead_Score__c`, `Lead_Score_Last_Update__c`, `Five_Year_PLE__c` to the MC Lead sync. Confirm the dormant TEST copies on Purchase and SavedQuote are inactive |
| 2026-11-16 | 7-day read done: score clears step+age for purchase on fresh leads (see section 0). Decision: Campaigns instead of custom Lead fields |
| 2026-11-20 | Test campaigns created (parents + arms); MC Connect user confirmed able to add Campaign Members. Sync columns visible in `ent.Lead_Salesforce` |
| 2026-11-23 | 14-day forward read; provisional segment cuts from entrant data (Purchase and Drivers entrants separately) |
| 2026-12-01 | `AC_Purchase_v5` and `AC_Drivers_v6` queries + entry DE columns live; Drivers dedupe verified (one Start row per contact); Purchase variant creative approved |
| 2026-12-08 | Publish Purchase test version (Scenario 1) |
| 2026-12-12 | Segment table (3a) delivered: combination of scoring defined with purchase rates |
| 2026-12-15 | Purchase launch + 7 QA: campaign members = journey entrants, arms 50/50, sends equal |
| 2027-01-12 | Scenario 1 month-1 diagnostics. Drivers test version built |
| 2027-01-19 | Publish Drivers test version (Scenario 2) |
| 2027-01-26 | Drivers launch + 7 QA: arms 50/50 within SMS-eligible, INELIGIBLE campaign filled, no SMS in EMAIL_ONLY |
| 2027-02-16 | Scenario 1 first purchase read (direction; +5 detectable mid-March). Scenario 2 cost read |
| 2027-03-30 | Scenario 1 +5-point read. Scenario 2 diagnostics and purchase direction by band |
| 2027-06 | LTV test completes; discount-tier treatment test scoped. Scenario 2 LOW non-inferiority posterior |
| 2027-Q3 | Scenario 2 HIGH vs LOW interaction read; routing version of Coverages |

## 6. Open items for the user

1. Confirm the variant creative for 3b (savings-forward) or substitute one lever.
2. Units and meaning of `Five_Year_PLE__c` (median 256; "Five Year Policy Lifetime Expectancy", Kevin Brown) so the HIGH cut is defensible.
3. When the Coverages test ends (it is the better Scenario 2 home: 2x the purchase rate, PLE on every entrant, the most expensive SMS); Scenario 2 could move or extend there afterwards.
4. Whether the SMS cost saving alone justifies routing LOW propensity to email only before the purchase read matures.
5. Who owns the `purchased__c` flapping (quote sync vs purchase sync, ~1 in 5 purchasers, up to 2 days). It affects journey exits and every read.
6. Confirm the Marketing Cloud Connect user's Campaign Member rights (or name who can grant them).
7. Person key for the back-to-quote join: email + `optimizely_dna__Visitor_Id__c` on Lead today (both ~96-100% populated); Data Cloud unified individual later.
