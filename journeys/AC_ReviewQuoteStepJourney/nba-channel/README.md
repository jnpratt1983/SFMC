# Next Best Action channel model: diagnosis and rebuild

Reviewed 2026-11-02 in blueowl-prod (Data Cloud + Marketing Cloud + CRM). This folder holds the
replacement training sets and the plan. Nothing here has been created in the org yet.

## What the current models are

Three Einstein Studio binary classifiers (Custom, Legacy), all retrained 2026-08-03:
`Predicted Is Email V2`, `Predicted Is Phone`, `Predicted Is SMS`. They write
`Is_Email_prediction__c`, `Is_Phone_prediction__c`, `Is_SMS_prediction__c` (0-100) into
`Lead_Multi_Channel_Scoring__dlm` hourly, which lands on the Lead as `Email_Score__c`,
`Call_Score__c`, `SMS_Score__c`, and a rule turns those into `Predicted_Channel__c`.

| Piece | What it actually is |
|---|---|
| Training set `Channel_Prediction_Training_Set__dlm` | 22,138 leads, 2021-2026. Labels are mutually exclusive: Is_Email 19,775 (89%), Is_Phone 1,455 (7%), Is_SMS 908 (4%). |
| Where the label comes from | `Prediction_NextBestAction__dlm.Closest_Channel_to_Purchased_Date__c`: the channel of the engagement record nearest the purchase date. Phone = a Zendesk ticket existed, SMS = an SMS delivery existed, Email = everything else. |
| What "Is_Email" means | The residual bucket. Of 19,775 Is_Email leads, only 6,518 have any email engagement row and only 4,628 (23%) ever opened an email. It is not "responds to email"; it is "no ticket and no SMS". |
| What "Is_Phone" means | A Zendesk ticket near the purchase. Lead-linked tickets are 60% inbound phone calls, so this is "called us", not "answers our calls". |
| Who is in the training set | 54-61% purchased, against a 9% population rate. The models learned purchase intent plus channel presence, which is why Call_Score ranks purchase (AUC 0.57) and Email_Score ranks it inverted (AUC 0.43). |
| Features | Area code, first car make, state group, UTM medium, age range, email-domain bucket, credit score, mobile and email opt-out, lead create date. Demographics only; nothing about quote behaviour. |
| Output behaviour | Email_Score predicts opening the first journey email at AUC 0.526. Call_Score has no relation to call pickup (answer rate by quartile 14%, 4%, 7%, 14%). Only 37% of journey entrants still carry the channel they were routed on. Share predicted Call + Email went from 22% (Dec 2025) to 77% (Oct 2026). |
| Holdout result | Jan 28 - Sep 17 2026 randomized control: NBA arms 10.2% vs control 11.9% 30-day purchase (n 2,785 vs 1,104), no lift. Call branch 8.7% vs 12.7% for Call + Email leads. |

Verdict: retire all three models, the `Predicted_Channel__c` rule, and `Recommended_Channel__c`.
Do not retrain them on the same labels; the label is the problem, not the algorithm.

## The goal, and why the label is the whole problem

The goal is unchanged: predict how a lead wants to be communicated with (some people pick up the
phone, some answer a text, some never open an email) by looking at leads with similar attributes
and seeing how they responded and converted. That is a sound goal. The legacy models failed it
because they never saw a response. Their label was "which channel had a record nearest the
purchase date", so a lead who bought after ignoring five emails is an Email lead, and a lead who
phoned us is a Phone lead. A preference model needs, for each channel, "we used this channel on
this lead and the lead did / did not respond", observed at the lead level. That is what the files
below build, channel by channel, from the records that exist today:

| Channel | Response we can see per lead | Source |
|---|---|---|
| Email | opened / clicked the first journey email | `ssot__EmailEngagement__dlm` |
| Call | picked up and talked, per the rep's note on the Next Best Action ticket | `Zen_Desk_Ticket_Bronze__dlm`, subject `New Lead- Next Best Action +<LeadId>` |
| SMS | delivered only; clicks sit in Bitly per link, not per lead | `SMS__c`, Bitly |

Put together, the preference is: score each lead with the three response models, weight each by
the purchase rate of leads who responded on that channel, and route to the highest. The
factorial test matters for one reason: today a lead only has a call label if the old router chose to
call them, so the call model would learn the old router's choices. Randomizing who gets called
removes that.

## What a channel model has to predict

"Which channel changes whether this lead buys" is the uplift form of the same question and needs
randomized treatment data; the 2x2 factorial test (call yes/no x SMS yes/no, email to all) produces
it. Until then the per-channel response models carry the goal:

| Channel | Response label available today | Status |
|---|---|---|
| Email | Opened / clicked within 3 days of the first quote-journey email. 3.8M engagement rows, 642k leads, 133k opens in 2026 alone. | Build now (`Email_Response_*` below). |
| Call | Reached / not reached, from the rep's internal comment on the "New Lead- Next Best Action +<LeadId>" ticket that the router creates alongside the Task (reps work from Zendesk, not Salesforce; the Tasks are never touched). 969 tickets since 2026-04 (Jan-Mar tasks made none), 97% with `Lead__c` set, the rest carry the lead id in the subject. Tags exist on 63% (answer 44, no_answer 414); the comment text labels the other 37% ("lvm", "no answer", "answered, still shopping"). Reach rate 14% of calls; 9% of tickets were never dialed (ex-customers, bad numbers). | Label available now (`Call_Response_Training_Set__cio.sql`). About 135 positives, +30 a month: enough to read the test's call arm, not yet enough to train a score. No tags needed; the comment is the record. |
| SMS | Delivery per lead only (`SMS__c` in CRM, 206k rows, and `ssot__MessageEngagement__dlm`). Clicks are tracked in Bitly: every review SMS carries one static branded link per message (`hiroad.cc/3StjPBu`, `/3Sq4KjS`, `/43RxeZF`, `/3tWMxkF`), the same for all recipients, redirecting to `quote.hiroad.com/discovery?utm_source=sfmc&utm_medium=sms&utm_campaign=review...`. Bitly reports clicks per link per hour, not per recipient, and nothing from Bitly lands in Data Cloud or Salesforce today. | Partly blocked. A Bitly API pull (clicks by link by hour, joined to the SMS send batches) gives the SMS arm a campaign-level click rate for the test readout; that is worth doing. A per-lead label needs one of: SFMC tracked links (MobileConnect link tracking writes click events per subscriber), per-recipient Bitly links created at send time, or the quote app attributing the `utm_medium=sms` session to the lead (`Quote_Session_ID__c` style). |
| Purchase uplift by channel | Needs the factorial test arm on the Lead (`NBA_Test_Arm__c`, `NBA_Entry_At__c`). | Build after the test has ~1,700 leads per factor (`Channel_Uplift_*` below). |

## Outcome capture for calls and SMS (prerequisite for the test readout)

- Call: the Next Best Action ticket is the record, and the fields on it are enough. Two things
  keep it clean: reps write the outcome comment on every ticket (97% already do, median 26 hours
  after the call), and tickets the rep decided not to dial say so (today 9% say "ex customer" or
  "bad number"; those are not non-responses). The `next_best_action_answer` / `_no_answer` tags are
  optional; the comment rule in the SQL covers untagged tickets, and the Zendesk AI classifier can
  replace the rule when it runs on these tickets. Nothing about Salesforce Tasks is needed.
- SMS: pull Bitly click counts by link and hour over the API for the four review links and store them
  against the SMS send batches (`SMS__c.CreateDate_c__c`, message name). That gives clicks per 100
  delivered by arm and by message. For per-lead clicks switch the SMS copy to MobileConnect tracked
  links, which write click events per subscriber that the Marketing Cloud connector can ingest.

## Files

1. `Email_Response_Training_Set__cio.sql` - one row per lead created 2025-01-01 onward that received
   a quote-step journey email (`AC_%`) within 30 days of creation, observed at the time of that first
   send. Label `Opened_3d__c` (and `Clicked_7d__c` as a second target). Features are what Salesforce
   knew about the lead at creation plus prior-lead history. The current Email_Open_Score and the three
   channel scores are deliberately excluded (current-state values, they leak).
2. `Email_Response_Scoring_Set__cio.sql` - same columns for leads created in the last 14 days with no
   journey email yet. Refresh hourly after the lead sync.
3. `Call_Response_Training_Set__cio.sql` - one row per Next Best Action call ticket, lead attributes at
   creation plus email behaviour before the call, labels `Called__c` and `Call_Reached__c` from the tag or
   the comment text. Create it now so the label accrues; train when positives pass ~1,000.
4. `Channel_Uplift_Training_Set__cio.sql` - rows from the factorial test. One row per test lead with
   arm flags, entry-time features and `Purchased_30d__c`. Train two Model Builder models on it
   (T-learner): `Purchase given call` on rows where Call_Arm__c = true, `Purchase given no call` on
   rows where it is false, score every lead with both, and the difference is the call uplift. Same for
   SMS. Model Builder has no native uplift model, so this is the supported way to get one.

## Setup steps

1. Data Cloud > Calculated Insights > New > SQL, paste `Email_Response_Training_Set__cio.sql`,
   API name `Email_Response_Training_Set`, run once. Then `Email_Response_Scoring_Set`, hourly.
2. Einstein Studio > Model Builder > Binary classification, training data
   `Email_Response_Training_Set`, target `Opened_3d__c`. Exclude `Lead_Id__c`,
   `Unified_Individual_Id__c`, `Clicked_7d__c`, `First_Send_At__c`. Expect AUC around 0.60-0.65;
   below 0.58 means the lead attributes do not carry channel signal and the model should not ship.
3. Batch prediction on `Email_Response_Scoring_Set` into `Email_Response_Prediction`. Data Action to
   `Lead.Email_Open_Likelihood__c` (existing field) if the CRM needs it.
4. Do NOT route on this score during the factorial test. Log it on the Lead at entry
   (`NBA_Entry_Email_Score__c`) so the interaction analysis can test whether high-score leads gain
   less from calls.
5. Create `Call_Response_Training_Set` now (daily). Report reach rate by month from it; it is the
   call arm's response metric in the test readout. Train `Call_Reached__c` only once positives pass
   ~1,000 and the test has randomized who is called.
6. After the test: create `Channel_Uplift_Training_Set`, train the four T-learner models, publish
   `Call_Uplift__c` and `SMS_Uplift__c` to the Lead. The new routing rule is: call if
   Call_Uplift >= cost-of-call threshold, SMS if SMS_Uplift >= threshold, email otherwise.
7. Retire: the three legacy models, `Lead_Multi_Channel_Scoring`, `Lead_SMS_Channel_Scoring`
   (stale, newest lead 2025-12-15), the `Predicted_Channel__c` rule, `Recommended_Channel__c`,
   and `Prediction_NextBestAction__dlm` (leads only through 2025-12-10).

## Validated 2026-11-02 (Trino translation of the training-set logic, via queryv2)

| First AC_ email year | Leads with a first send within 30 days of creation | Opened within 3 days | Clicked within 7 days |
|---|---|---|---|
| 2025 | 137,234 | 49,496 (36.1%) | 5,350 (3.9%) |
| 2026 | 76,545 | 31,013 (40.5%) | 3,413 (4.5%) |

So the email model trains on ~214k rows with an 36-40% positive rate for opens; clicks are rare enough
that `Clicked_7d__c` should be a second model, not a second target.

## Baseline to beat

- Email open on the first review-journey email: 44% overall, flat across predicted channel today.
- Purchase within 30 days of journey entry: 11.9% in the untreated control arm.
- Any new router must beat the email-only control cell on 30-day purchase with a confidence interval
  that excludes zero. The old router did not.
