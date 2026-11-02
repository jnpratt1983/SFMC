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

## What a channel model has to predict

"How does this lead want to be contacted" is only answerable as "which channel changes whether
this lead buys". That is an uplift question and needs randomized treatment data. The 2x2 factorial
test (call yes/no x SMS yes/no, email to all) produces it. Until that data exists, the only honest
models are per-channel response models with point-in-time labels:

| Channel | Response label available today | Status |
|---|---|---|
| Email | Opened / clicked within 3 days of the first quote-journey email. 3.8M engagement rows, 642k leads, 133k opens in 2026 alone. | Build now (`Email_Response_*` below). |
| Call | None for the calls the router triggers. All 1,009 "Call Lead- Next Best Action" tasks since Jan 28 are still Open with no disposition, duration or notes (17 touched by hand). Of those 1,009 leads, 2 have a Zendesk ticket in the 7 days after the task, both inbound. Inbound quote calls are well recorded (2,218 prospect call tickets in 2026, 96% with a Genesys interaction URL, 70% linked to a Lead, agent time and notes on every one) but they are leads calling us, not us reaching them. | Blocked until the outbound call leaves a record. No tagging needed: the ticket fields already carry outcome (`Genesys_URL__c`, `Total_time_spent_sec_int__c`, `Comments__c`, `Replies__c`). What is missing is the ticket itself. Either Genesys creates a Zendesk ticket for outbound quote calls the way it does for inbound, or the rep closes the Task with a disposition. Label = reached (ticket or closed task with talk time) vs not. |
| SMS | Delivery per lead only (`SMS__c` in CRM, 206k rows, and `ssot__MessageEngagement__dlm`). Clicks are tracked in Bitly: every review SMS carries one static branded link per message (`hiroad.cc/3StjPBu`, `/3Sq4KjS`, `/43RxeZF`, `/3tWMxkF`), the same for all recipients, redirecting to `quote.hiroad.com/discovery?utm_source=sfmc&utm_medium=sms&utm_campaign=review...`. Bitly reports clicks per link per hour, not per recipient, and nothing from Bitly lands in Data Cloud or Salesforce today. | Partly blocked. A Bitly API pull (clicks by link by hour, joined to the SMS send batches) gives the SMS arm a campaign-level click rate for the test readout; that is worth doing. A per-lead label needs one of: SFMC tracked links (MobileConnect link tracking writes click events per subscriber), per-recipient Bitly links created at send time, or the quote app attributing the `utm_medium=sms` session to the lead (`Quote_Session_ID__c` style). |
| Purchase uplift by channel | Needs the factorial test arm on the Lead (`NBA_Test_Arm__c`, `NBA_Entry_At__c`). | Build after the test has ~1,700 leads per factor (`Channel_Uplift_*` below). |

## Outcome capture for calls and SMS (prerequisite for the test readout)

The factorial test can be read on purchase alone, but to learn anything about channel response it
needs the two outbound touches to leave a record:

- Call: today the router creates a Task and nothing closes it. Options, cheapest first: (a) reps set
  Task Status and `CallDisposition` (Reached / Voicemail / No answer / Bad number) when they work the
  task; (b) Genesys outbound interactions on the quote queue create a Zendesk ticket like inbound ones
  do, so the existing ticket fields (Genesys URL, time spent, comments) carry the outcome and the
  nightly Zendesk sync brings it to `Zen_Desk_Ticket__c` with `Lead__c` set from the dialed number.
  (b) is the durable one; it needs no tags and no rep behaviour change.
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
3. `Channel_Uplift_Training_Set__cio.sql` - rows from the factorial test. One row per test lead with
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
5. After the test: create `Channel_Uplift_Training_Set`, train the four T-learner models, publish
   `Call_Uplift__c` and `SMS_Uplift__c` to the Lead. The new routing rule is: call if
   Call_Uplift >= cost-of-call threshold, SMS if SMS_Uplift >= threshold, email otherwise.
6. Retire: the three legacy models, `Lead_Multi_Channel_Scoring`, `Lead_SMS_Channel_Scoring`
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
