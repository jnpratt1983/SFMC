# Hourly scoring chain: what is scheduled, what is not, and how to finish it (2026-11-04)

## Finding
Einstein Studio **Predict Jobs have no schedule and do not follow their input.** Test on 2026-11-04 00:22 UTC: ChannelScoringSet was
re-run (finished 00:25:55); the three Predict Jobs (SMS Click Predict, Phone Prediction, Email Prediction) kept their 19:18 / 19:28 /
19:30 last-run times for the following 20 minutes. Their row menu offers Edit, Run, Deactivate, View Job History, Delete only.
The "Schedule Training" dialog on the model is retraining, not scoring; leave it on Manual.

The legacy chain solved this the same way Salesforce documents it: a **batch data transform with the model inside it** (node action
`cdpPredict`, three of them chained in `LeadMultiChannelScoring`, output straight to a DMO). A transform has an hourly schedule.

## State of the chain right now

| Step | Object | Schedule | Last run |
|---|---|---|---|
| 1 | ChannelScoringSet (transform) | hourly at :00 (America/Chicago) | 00:25 UTC, SUCCESS |
| 2 | SMS / Email / Phone Predict Jobs | **none** | 19:18 / 19:28 / 19:30 UTC, once |
| 3 | ChannelScores (transform) | hourly at :35 (set by API 2026-11-04) | 19:55 UTC |
| 4 | Channel_Scores_Lead_default (enrichment) | runs after its source refreshes | 20:46 UTC |
| legacy | LeadMultiChannelScoring, ChannelPredictionTrainingData | schedule removed 2026-11-04 | – |

Until step 2 runs hourly, step 3 re-publishes stale predictions and every lead created after 18:21 UTC on 11-03 stays unscored,
which the v9 entry gate turns into zero journey entrants.

## Finish it: three model transforms (UI; the API refused the transform write from this session)

For each model (Predicted SMS, Predicted Phone, Predicted Email), on the model page, Integrations tab, Batch Data Transforms,
**New Transform**:

1. Input node: DMO `Channel Scoring Set` (`Channel_Scoring_Set__dlm`), all columns.
2. AI model node: the active version. Map the model's input variables to the scoring-set columns of the same name
   (`Email_Domain__c`, `State__c`, `Vehicle_Make__c`, `Credit_Score__c`, `Lead_Source__c`, `Publisher__c`, `UTM_Source__c`,
   `UTM_Medium__c`, `Previous_Insurance__c`, `Lead_Hour__c`, `Lead_Day_Of_Week__c`, `Days_Since_Create__c`, `Max_Quote_Step__c`,
   `Declined__c`, `Has_Mobile__c`, `Mobile_Opt_Out__c`; the scoring set was built with the training-set names, so each input has a
   same-name column). Outputs: the prediction **and the class probabilities** (both classes), as the Predict Job did.
3. Output node: the **same prediction DMO the Predict Job writes today**, write mode Overwrite, with the same column names:
   - SMS → `SMS_Click_Prediction__dlm`: `PrimaryObjectPk__c` = `Lead_Id__c`, `KQ_PrimaryObjectPk__c` = `KQ_Lead_Id__c`,
     `PredictedClicked_14d1__c`, `PredictedClicked_14d1Value__c`, `PredictedClicked_14d2__c`, `PredictedClicked_14d2Value__c`
   - Email → `Email_Prediction__dlm`: same keys, `PredictedOpened_First_Email1__c` / `1Value__c` / `2__c` / `2Value__c`
   - Phone → `Phone_Prediction__dlm`: same keys, `PredictedCalled_Us_30d1__c` / `1Value__c` / `2__c` / `2Value__c`
   Keeping these names means the ChannelScores rollup, the Channel_Scores DMO, the enrichment and the Lead fields need no change.
   If the output node will not let you target the existing prediction DMO, create a new DMO per model with exactly those column
   names and repoint the three load nodes in ChannelScores (`LOAD_SMS`, `LOAD_EMAIL`, `LOAD_PHONE`).
4. Save, run once, check the DMO row count equals the scoring set (4,073 today) and that `...1Value__c` is populated.
5. Schedule: hourly, SMS at :10, Email at :15, Phone at :20 (America/Chicago, any start hour). ChannelScoringSet is :00, ChannelScores :35.
6. Deactivate the three Predict Jobs (row menu, Deactivate) so nothing writes the prediction DMOs twice.

Schedule bodies the API accepts, for the record (`PUT /services/data/v64.0/ssot/data-transforms/{id}/schedule`):
`{"frequency":"Hourly","interval":1,"daysOfWeek":[...7 days...],"time":{"hour":20,"minute":35,"timeZone":"America/Chicago"}}`

## Verify after the first full hour
- Lead: `SELECT MAX(Last_Channel_Scoring_Date__c) FROM Lead WHERE CreatedDate = TODAY` moves every hour.
- Entry DE `AC_ReviewNBATest_AF_01272026` shows rows within ~15 min of a new scored lead (then empties again as they enter).
- `DataActionJobSummary` shows a `Channel_Scores_Lead_default` run after each ChannelScores run.

## Update 2026-11-04 01:00 UTC: build the single model transform in the UI

Model API names (model Overview tab): `Predicted_SMS_CM_12l_eod907571dc` (target Clicked_14d), `Predicted_Call_CM_12l_eod7bc9743a`
(Called_Us_30d), `Predicted_Opened_First_Email_CM_12l_eod20adcc71` (Opened_First_Email).

The Connect API rejects every definition that contains a `cdpPredict` node with "Unable to find source DLOs or DMOs", including the
legacy transform's own definition re-submitted unchanged and single-node probes with the new names, the legacy name, empty input
mappings and alternative output names. Definitions without a model node validate. So the model transform has to be built in the UI;
`transforms/ChannelScores_models.api.json` documents the intended graph. The old canvas (LeadMultiChannelScoring) is the template.

Steps (Data Cloud, Data Transforms):
1. Deactivate the API-built **ChannelScores** rollup (it owns the Channel Scores output; the UI will refuse a second writer). Its
   hourly :35 schedule can be deleted.
2. New batch data transform **ChannelScores_Models**. Input: DMO **Channel Scoring Set**.
3. Three AI nodes in a row, like the old canvas: Predicted SMS (v2), Predicted Opened_First_Email (v1), Predicted Call (v1). Inputs
   map by the same name (Email_Domain, State, Vehicle_Make, Credit_Score, Lead_Source, Publisher, UTM_Source, UTM_Medium,
   Previous_Insurance, Lead_Hour, Lead_Day_Of_Week, Days_Since_Create, Max_Quote_Step, Declined, Has_Mobile, Mobile_Opt_Out).
   Outputs: the prediction and the probability of class **1** for each.
4. Transform node, four formulas:
   `SMS_Score__c   = round(100 * <P(Clicked_14d = 1)>, 2)`
   `Email_Score__c = round(100 * <P(Opened_First_Email = 1)>, 2)`
   `Call_Score__c  = round(100 * <P(Called_Us_30d = 1)>, 2)`
   `Scored_At__c   = now()`  (DateTime, format yyyy-MM-dd'T'HH:mm:ss.SSS'Z')
   If the node only gives the probability of the predicted class: `case when <class> like '1%' then <p> else 1 - <p> end`.
5. Output: existing DMO **Channel Scores**, Overwrite. Map Lead_Id__c ← Lead_Id__c, KQ_Lead_Id__c ← KQ_Lead_Id__c, the three scores,
   Scored_At__c. Nothing downstream changes: the enrichment keeps copying these six fields to Lead.
6. Save, run once. Check: 4,073 rows (today's scoring set), Call_Score p80 ≈ 42, SMS median ≈ 40, as on 11-03.
7. Schedule hourly at :35 (ChannelScoringSet is :00). Deactivate the three Predict Jobs. The prediction DMOs can be deleted later.

## Update 2026-11-11: two corrections, and a shorter UI build

**1. "Hourly" only ran five times a day.** Run history showed ChannelScoringSet running at 19:00–23:00 Central and nothing else
(01:04–05:04 UTC every day since 11-04); the ChannelScores rollup ran 20:35–23:35. An hourly Data Cloud schedule starts at its
start time and stops at the end of that day, so the start hour has to be **0**. ChannelScoringSet was re-set by API on 11-11 to
`{"frequency":"Hourly","interval":1,"time":{"hour":0,"minute":0,"timeZone":"America/Chicago"}}`; next run came back as the next
top of the hour. Use `hour: 0, minute: 35` for the model transform. Run history: `GET /ssot/data-transforms/{id}/run-history`.

**2. No score formulas are needed.** `POST /services/data/v64.0/ssot/machine-learning/predict` with
`{"type":"RawData","model":{"name":"Predicted_SMS_CM_12l_eod907571dc"},"fieldNames":[...],"rows":[[...]]}` returns
`predictedValue` 31.75 / 49.81 / 27.88 for three leads whose stored SMS_Score__c is 31.75 / 49.81 / 27.88. The binary model's
prediction is already P(class 1) x 100, so the AI node's prediction column maps straight to the score field (the legacy transform
did the same). Only `Scored_At__c = now()` needs a formula.

Model inputs (scoring-set column labels):
- Predicted SMS: Credit Score, Declined, Max Quote Step, State, Vehicle Make, UTM Source, UTM Medium, Lead Source, Lead Day Of Week
- Predicted Opened_First_Email: Lead Day Of Week, Mobile Opt Out, Lead Created Month, Credit Score, Lead Hour, Max Quote Step,
  State, UTM Medium, Lead Source, Email Domain, Vehicle Make
- Predicted Call: Lead Day Of Week, Mobile Opt Out, Lead Hour, Credit Score, Declined, Max Quote Step, Lead Source, State,
  Vehicle Make, UTM Medium, UTM Source

Output mapping to Channel Scores (`Channel_Scores__dlm`, Upsert, primary key Lead Id): Lead Id and Key Qualifier Lead Id map by
name; Predicted Clicked_14d -> SMS Score; Predicted Opened_First_Email -> Email Score; Predicted Called_Us_30d -> Call Score;
Scored At -> Scored At.

State on 11-11 16:50 UTC: no model transform saved yet; Predict Jobs last ran 11-03; Channel Scores holds 4,073 rows from 11-03
predictions (scoring set is now 4,250 leads), so leads created after 11-03 are still unscored.

## Update 2026-11-11 (afternoon): chain live, first entrants

**What was built (supersedes the single-transform plan above).** Two transforms instead of one:

| Step | Transform (id) | Reads -> writes | Schedule (America/Chicago) |
|---|---|---|---|
| 1 | Channel Scoring Set (1dtVt0000000X2PIAU) | Lead__dll -> Channel_Scoring_Set__dll | hourly, hour 0 minute 0 |
| 2 | Channel_Scores_Models (1dtVt0000000XbtIAE), UI-built, three AI nodes | Channel_Scoring_Set__dlm -> **Channel_Scores_Field_v2__dlm** (Overwrite) | hourly, hour 0 minute 35 |
| 3 | Channel Scores (1dtVt0000000X41IAE), rewired by API | Channel_Scores_Field_v2__dlm -> Channel_Scores__dlm (Overwrite) | hourly, hour 0 minute 10 (was :50 until 15:58 Central on 11-11) |
| 4 | Channel_Scores_Lead_default (copy field) | Channel_Scores__dlm -> Lead | follows step 3 within ~3 min |

Step 3's definition is generated by `transforms/build_scores_from_models.py` (`ChannelScores_from_models.api.json`); schedule
bodies are `transforms/schedule_models_0035.json` and `schedule_rollup_0010.json` (`schedule_rollup_0050.json` is the superseded
first setting). The session could not PUT the definition or the first two schedules, so the user ran them; the :10 schedule PUT
went through from the session.
Do not save a schedule from the UI dialog: it only offers on-the-hour times and would overwrite the minute and start hour.

**First run of step 2 failed** ("Hmm, that didn't work", Error ID 2000-b90547f, zero rows, ~35 min of internal retries). It was the
only transform in the org that mapped system columns (`InternalOrganization__c`, `cdp_sys_SourceVersion__c`) into its output and
the only one on Upsert. Unchecking the four system columns on the input node and switching to Overwrite fixed it (which of the two
mattered is not known). The first output object, `Channel_Scores_Field__dlm`, is empty and unused and can be deleted.

**Verified.** 4,338 rows; SMS scores equal the predict-endpoint values for three leads; ~99% of 1,813 leads that also had 11-03
scores agree on all three scores. Actual start times run ~10 min late (step 2 at :44-:47, ~6.5 min; step 3 at :54), so step 3
started within a minute or so of step 2 finishing. To remove that race, step 3 was moved to minute 10 on 11-11: it now publishes
the rows from the step 2 run that started at :35 of the previous hour, so a new lead's scores reach Lead about 15 minutes later
than before (lead created -> on Lead in roughly 1.5 to 3.5 hours).

**Entry query fix.** The copy to Lead stamps LastModifiedBy = Automated Process (0053h000003B5ZYAA0) on every scored lead each
hour; `AC_ReviewNBA_v9` only accepted API SFMC User and Airbyte Read Only User, so entry depended on Airbyte touching the lead
afterwards. The third id was added to the live query at 13:23 Central (repo copy updated).

**First entrants.** 38 leads entered v17 at 13:34 Central (19:34 UTC): SMS 20, CALL 10, CALL_SMS 8; MODEL 21 / RANDOM 17; all got
ES1; model routing matches the 42.3 / 39.8 thresholds. 16 call tasks at 15:35 Central; the other two call-arm leads purchased
inside the 2-hour wait and exited. Real 14-day suppression removed 25 of 63 scored candidates. Expected steady state: 12-18
entrants and 6-9 call tasks a day (v16 averaged 6.3 tasks a day).

**Open.** (1) The user deactivated the three Predict Jobs on 11-11 (the API does not expose activation state, so not confirmed
from the session; they last ran 11-03 and nothing reads them); the prediction DMOs can go later. (2) Every run re-stamps Scored At, so ~4,400
Leads are updated every hour (~100k updates a day through Lead automation and the Marketing Cloud sync); making the stamp daily
would cut that. The copy to Lead does not add storage; the cost is Lead flows firing on every update, a meaningless Last Modified Date, ~4,400 rows an hour through the Lead sync, and possibly Data Cloud credits per row written (rate not known). Not changed yet; whether the copy step skips unchanged rows is unverified.
(3) Journey Builder's population counter showed 0 after entry; Lead stamps and sends are the source of truth. (4) Predict Job "Voluntary Churn 60d v3 - Production Scoring" failed 11-11 15:29 Central (unrelated to this chain).
