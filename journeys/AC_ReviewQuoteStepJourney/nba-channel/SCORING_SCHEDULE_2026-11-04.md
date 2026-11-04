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
