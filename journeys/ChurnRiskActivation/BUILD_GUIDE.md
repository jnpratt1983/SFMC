# Build guide: point-in-time training set and voluntary-churn model

Step-by-step for Data Cloud and Einstein Studio in blueowl-prod. Read `RETRAIN_point_in_time_labels.md`
for the reasoning; this file is the click path. The appendix at the bottom lists every canvas node
and formula, generated from `transforms/Churn_PIT_Training_Set.json`, so the builder and the JSON
cannot drift.

Time budget: one day for phase 1 and 2, half a day for phase 3, one day for phases 4 to 6, plus
whatever the Contact stream change needs from the Salesforce admin.

## Phase 0. Prerequisites

1. **Permissions.** Data Cloud Admin (data streams, transforms, Einstein Studio) and Salesforce
   admin rights on Contact (new field, field history). The `HiRoad API` user is not needed.
2. **Confirm field names still match** (they were verified 2026-10-16):
   ```
   sf data query -o blueowl-prod -q "SELECT Account_Id__c, Event_Timestamp_UTC__c FROM MobileApp_c_00D3h0000068eod__dlm LIMIT 1"
   sf data query -o blueowl-prod -q "SELECT Customer_Number_c__c, Created_at_c__c FROM Zen_Desk_Ticket_Gold__dlm LIMIT 1"
   sf sobject describe -s IndividualEmailResults__dll -o blueowl-prod --json | grep -o '"name": "et4ae5_[A-Za-z_]*"' | sort -u
   sf sobject describe -s Contact__dll -o blueowl-prod --json | grep -o '"name": "[A-Za-z_0-9]*Cancel[A-Za-z_0-9]*"'
   ```
3. **Add two fields to the Contact data stream.** Data Cloud > Data Streams > `Contact` (Salesforce
   CRM connector) > Edit > Add Fields > tick `Current_Term_Effective_Date__c` and
   `Current_Term_Expiration_Date__c` > Save. Wait for the next refresh. In Salesforce Setup >
   Object Manager > Contact > Set History Tracking, enable both (check you are under the 20-field
   cap first; 18 were changing in the last 30 days). These are not used by the first training run
   but are the gate for replacing the estimated term-position features later.

## Phase 1. Snapshot calendar data stream (15 minutes)

1. Data Cloud > Data Streams > New > **Upload File** (Other / CSV) > choose
   `transforms/Churn_Snapshot_Calendar.csv`.
2. Object: new, label `Churn Snapshot Calendar`, API name `Churn_Snapshot_Calendar`, category
   **Other**, primary key `Snapshot_Key`.
3. Field types: `Snapshot_Date` = Date (format `yyyy-MM-dd`), `Snapshot_Key` = Text. Deploy.
4. After it loads, confirm the lake object name:
   `sf sobject list -o blueowl-prod --sobject all | grep -i snapshot`. If it is not exactly
   `Churn_Snapshot_Calendar__dll`, edit `LOAD_CAL` in `transforms/build_transform_json.py`,
   re-run it, and use the new JSON.
5. Monthly maintenance: upload a one-row CSV for the new month to the same stream (append).

## Phase 2. Build the training transform (half a day)

Data Cloud > Data Transforms > New > **Batch Data Transform** > name
`Churn PIT Training Set` (API name `ChurnPITTrainingSet`), data space `default`.

Work through the appendix row by row. Conventions on the canvas:

- **Input Data** node: click Select Data, pick the object, then tick only the columns listed.
- **Transform** node: for each row in a formula table, click the column menu > Formula
  > Custom Formula, set the type and precision, type the column name exactly, paste the
  expression. Keep them in the listed order because later formulas reference earlier ones.
- **Join** node: pick the join type, set the keys, set the right-side prefix ("qualifier") to the
  name given, then under the right-side columns untick the ones listed as "drop".
- **Filter** node: add the conditions with the operator shown.
- **Aggregate** node: Group Rows By the listed columns, then add each aggregation with the
  exact output name.
- Cross join: there is no Cross option, so each branch adds a constant column `xk = 1` and
  does an **Inner** join on `xk`. That is what every "x snapshot" join in the appendix is.

Order of work:

1. Row A (calendar) first; its last node is the right side of four joins.
2. Row B up to and including **Labels and tenure**.
3. Rows C, D, E in full, each ending in an Aggregate.
4. Back on row B: the three left joins (`+ app`, `+ email`, `+ tickets`), then **Final features**,
   then the Output node.
5. **Output node**: Output Type = Data Lake Object, Create New, label `Churn PIT Training Set`,
   API name `Churn_PIT_Training_Set`, category Other, primary key `Row_Key__c`, write mode
   Overwrite. Map the columns exactly as the appendix table (the builder auto-suffixes `__c`).
6. Save. Run once (Run Now). A first run on 26 snapshots takes 20 to 60 minutes.
7. Schedule: on the transform record set Run Frequency = Monthly, day 2, after the Contact
   stream's refresh window.

If you prefer to load the JSON instead of clicking, try
`sf api request rest "/services/data/v64.0/ssot/data-transforms" -o blueowl-prod -X POST --body @transforms/Churn_PIT_Training_Set.api.json`.
The endpoint is beta; if it rejects the body, the canvas build is the fallback and the appendix is
the spec.

### Sanity checks before any training (run from the CLI once the DLO is mapped to a DMO, see phase 3)

```
SELECT Snapshot_Key__c, COUNT(Row_Key__c), SUM(Label_60__c), SUM(Censored__c) FROM Churn_PIT_Training_Set__dlm GROUP BY Snapshot_Key__c ORDER BY Snapshot_Key__c
SELECT COUNT(Row_Key__c) FROM Churn_PIT_Training_Set__dlm WHERE Max_Feature_Date__c > Snapshot_Date__c
SELECT Tenure_Bucket__c, COUNT(Row_Key__c), SUM(Label_60__c) FROM Churn_PIT_Training_Set__dlm WHERE Censored__c = 0 GROUP BY Tenure_Bucket__c
```

Pass lines: 6,500 to 8,500 rows per snapshot; Label_60 rate 3 to 8% every month after removing
censored rows; the leakage query returns 0; the `lt6mo` bucket has the highest label rate. If the
label rate is near zero for early snapshots, `Cancellation_Reason__c` was not populated back
then; start the calendar later.

## Phase 3. Expose the training set to Model Builder (30 minutes)

Model Builder trains on data model objects, not lake objects.

1. Data Cloud > Data Model > New > **Custom** > from existing DLO > pick
   `Churn_PIT_Training_Set` > label `Churn PIT Training Set` > map all fields one-to-one
   (names stay the same) > primary key `Row_Key__c` > Save. Result: `Churn_PIT_Training_Set__dlm`.
2. Build the training view. Model Builder has no row filter, so create a second batch transform
   `Churn PIT Training Set Train`: Input Data = `Churn_PIT_Training_Set__dlm`, one Filter node
   with `Censored__c = 0` AND `Snapshot_Key__c <= 202604`, Output = new DLO
   `Churn_PIT_Training_Set_Train`, then map it to a DMO the same way. Schedule it after the main
   transform.
3. Same pattern for the holdout: `Churn PIT Training Set Holdout` with `Censored__c = 0` AND
   `Snapshot_Key__c >= 202605`. This is what you will score in phase 5 to validate.

## Phase 4. Train in Einstein Studio (1 hour plus training time)

1. Data Cloud > Einstein Studio > Models > New > **Build a model from scratch**
   (Model Builder). Name `Voluntary Churn 60d v1`.
2. **Goal.** Data source = `Churn_PIT_Training_Set_Train__dlm`. Predict `Label_60__c`.
   Outcome type: Binary classification. Goal: maximize the value `1`.
3. **Variables.** Deselect: `Row_Key__c`, `Contact_Id__c`, `Snapshot_Date__c`,
   `Snapshot_Key__c`, `Label_90__c`, `Censored__c`, `Reason__c`, `Max_Feature_Date__c`.
   For v1 also deselect the current-value columns `Days_To_Renewal__c`,
   `Days_Since_Renewal_Offer__c`, `Lifetime_Savings__c`, `Telematics_Discount__c`,
   `Policy_Renewal_Rate__c` (they are only point-in-time for the newest snapshot). Everything else
   stays: tenure, policy days, tenure bucket, estimated term position, app, email, tickets.
4. **Algorithm.** Leave on Auto (XGBoost). Do not enable class balancing for v1.
5. Turn on **Explanations** (prediction factors) if the toggle is offered; it is what gives the
   "why" per contact.
6. Train. Note the reported metrics but do not quote them: Model Builder splits rows at random,
   and the same contact appears in many snapshots on both sides.
7. Activate the model when training finishes.

## Phase 5. Score the holdout and validate (half a day)

1. Einstein Studio > the model > **Predictions** > New > Batch > source
   `Churn_PIT_Training_Set_Holdout__dlm` > output new DMO `Voluntary_Churn_Holdout_Scores`
   (keep `Row_Key__c`, `Contact_Id__c`, `Snapshot_Key__c`, the prediction column, and the top
   factor columns) > Run.
2. Pull and test:
   ```
   sf data query -o blueowl-prod -q "SELECT Row_Key__c, Label_60_prediction__c FROM Voluntary_Churn_Holdout_Scores__dlm" --result-format csv > holdout_scores.csv
   sf data query -o blueowl-prod -q "SELECT Row_Key__c, Label_60__c, Reason__c, Tenure_Bucket__c, Tenure_Days__c FROM Churn_PIT_Training_Set_Holdout__dlm" --result-format csv > holdout_labels.csv
   ```
   Join on `Row_Key__c` and reuse the AUC, decile and within-tenure code in
   `scripts/churn_score_validation.py` (the `auc`, `auc_se` and decile blocks apply unchanged).
3. Pass lines, from the runbook: overall AUC >= 0.68 and >= 0.05 above tenure alone on the same
   rows; >= 0.60 inside each tenure bucket; high-premium >= 0.70, replacement-of-carrier >= 0.65,
   insured-request >= 0.60; monotonic deciles with top decile >= 2.5x base; top-decile overlap
   between consecutive snapshots >= 60%.
4. **Compliance proxy check.** When the Payment Stability Score field sync (DS-3265) lands,
   Spearman between the new score and PSS must be under 0.2, and the share of contacts with a
   non-pay notice in the prior 90 days inside the top decile must be within 5 points of their book
   share. If either fails, the score is acting as a credit proxy; go back to phase 4 and remove the
   responsible variables.
5. If it fails on the voluntary sub-reasons, the fix is data (real term dates, premium change at
   renewal from the policy system), not algorithm settings. Record the result either way in a
   dated file in this folder.

## Phase 6. Production scoring and the Contact field (half a day)

1. **Scoring transform.** Data Transforms > open `Churn PIT Training Set` > Save As
   `Churn PIT Scoring Set`. Changes: on row A add a Filter after the calendar input,
   `Snapshot_Key = <current month key>` (update monthly, or add a formula column
   `is_latest` with `date_trunc('month', now())` logic and filter on it); on row B delete the
   `Censored` dependency nothing else, keep all label columns (they will be 0 for the current month
   and are ignored); Output = new DLO `Churn_PIT_Scoring_Set`, map to a DMO. Schedule on the 1st
   after the Contact stream refresh.
2. **Prediction job.** Einstein Studio > model > Predictions > New > Batch > source
   `Churn_PIT_Scoring_Set__dlm` > output DMO `Voluntary_Churn_Score` with `Contact_Id__c`,
   the prediction, and the top three factor columns > schedule after the scoring transform.
   (The old setup did the same thing with an AI Functions node inside the scoring transform; either
   works, the separate job is easier to re-point when v2 ships.)
3. **Contact field.** Setup > Object Manager > Contact > New Field > Number(5,2)
   `Voluntary_Churn_Risk_Score__c`, plus Text(255) `Voluntary_Churn_Top_Factors__c`. Enable
   history tracking on the score field **before** the first write.
4. **Write-back.** Data Cloud > Data Actions, or the Contact enrichment "Copy Fields": source
   `Voluntary_Churn_Score__dlm`, key `Contact_Id__c` = Contact Id, map prediction x 100 to the
   score field and the factors to the text field. Run after the prediction job.
5. **Bands.** After the first production run:
   ```
   SELECT Voluntary_Churn_Risk_Score__c FROM Contact WHERE Voluntary_Churn_Risk_Score__c != null ORDER BY Voluntary_Churn_Risk_Score__c DESC
   ```
   High = top decile, Moderate = deciles 2 and 3. Write the cut points into the batch note and
   into `Customer360PersonaBatch` when it is switched over.
6. **Journey entry.** Keep the non-pay exclusion in the journey entry criteria (recent non-pay
   notice), not in the score, until Insurance answers the open question on chronic non-payers.
7. Run two monthly batches and re-validate each with the holdout method before pointing the
   persona batch, the Wave dataset and the Churn Risk activation journey at the new field. Then
   retire `ChurnRiskScoreOutput` and `ChurnRiskScoreNormalizedOutput`.

## Phase 7. Monthly operations

| When | What |
|---|---|
| 1st | Contact stream refresh, scoring transform, prediction job, write-back, band cut points |
| 2nd | Calendar row for the new month, training transform, train/holdout views |
| Each batch | Validation script row, compliance proxy check, top-decile overlap with last month |
| Quarterly | Retrain on all closed snapshots as vN+1; promote only if it beats the live model on the same holdout |

## Appendix: every canvas node, left to right

Generated from `transforms/Churn_PIT_Training_Set.json`. Build the rows in the order A, B, C, D, E; row B's joins at the end need rows C to E finished first.


### Row A: calendar

**Snapshot calendar** (Input Data): `Churn_Snapshot_Calendar__dll` (dataLakeObject), columns: `Snapshot_Date__c`, `Snapshot_Key__c`

**Calendar keys** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `Snap_Date` | DATETIME | `Snapshot_Date__c` |
| 2 | `Snap_Key` | TEXT | `Snapshot_Key__c` |
| 3 | `xk` | NUMBER (18,0) | `1` |


### Row B: contact book, labels, assembly

**Contact** (Input Data): `Contact__dll` (dataLakeObject), columns: `Id__c`, `AccountId__c`, `Account_Id2_c__c`, `Customer_Number_c__c`, `CreatedDate__c`, `Policy_Effective_Date_c__c`, `Cancel_Date_c__c`, `Cancellation_Reason_c__c`, `Policy_Renewal_Date_c__c`, `Renewal_Offer_Date_c__c`, `Policy_Renewal_Rate_c__c`, `Lifetime_Savings_c__c`, `Telematic_Discount_Numeric__c`

**Contacts with a policy** (Filter): `Id__c` STARTS_WITH ['003'] AND `Policy_Effective_Date_c__c` IS_NOT_NULL

**Contact join key** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `xk` | NUMBER (18,0) | `1` |

**Contact x snapshot** (Join): INNER, left keys `['xk']` = right keys `['xk']`, right-side prefix `Cal`; drop from right side: `['Cal.xk', 'Cal.Snapshot_Date__c', 'Cal.Snapshot_Key__c']`

**Active-book flag** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `In_Book` | NUMBER (18,0) | `case when Policy_Effective_Date_c__c <= "Cal.Snap_Date" and CreatedDate__c <= "Cal.Snap_Date" and (Cancel_Date_c__c is null or Cancel_Date_c__c > "Cal.Snap_Date") then 1 else 0 end` |

**Keep in-book rows** (Filter): `In_Book` EQUAL ['1']

**Labels and tenure** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `Cancel_In_60d` | NUMBER (18,0) | `case when Cancel_Date_c__c > "Cal.Snap_Date" and Cancel_Date_c__c <= "Cal.Snap_Date" + INTERVAL 60 DAY then 1 else 0 end` |
| 2 | `Cancel_In_90d` | NUMBER (18,0) | `case when Cancel_Date_c__c > "Cal.Snap_Date" and Cancel_Date_c__c <= "Cal.Snap_Date" + INTERVAL 90 DAY then 1 else 0 end` |
| 3 | `Preventable` | NUMBER (18,0) | `case when Cancellation_Reason_c__c in ('Due to high premium','Replacement of insurance carrier','Insured request - other','App issue / UX','Due to poor customer service','Due to poor claims service') then 1 else 0 end` |
| 4 | `Label_60` | NUMBER (18,0) | `case when Cancel_In_60d = 1 and Preventable = 1 then 1 else 0 end` |
| 5 | `Label_90` | NUMBER (18,0) | `case when Cancel_In_90d = 1 and Preventable = 1 then 1 else 0 end` |
| 6 | `Censored` | NUMBER (18,0) | `case when Cancel_In_60d = 1 and Preventable = 0 then 1 else 0 end` |
| 7 | `Reason` | TEXT | `case when Cancel_In_90d = 1 then Cancellation_Reason_c__c else null end` |
| 8 | `Row_Key` | TEXT | `concat(Id__c, '_', "Cal.Snap_Key")` |
| 9 | `Tenure_Days` | NUMBER (18,0) | `datediff("Cal.Snap_Date", CreatedDate__c)` |
| 10 | `Policy_Days` | NUMBER (18,0) | `datediff("Cal.Snap_Date", Policy_Effective_Date_c__c)` |
| 11 | `Tenure_Bucket` | TEXT | `case when Tenure_Days < 180 then 'lt6mo' when Tenure_Days < 365 then '6to12mo' when Tenure_Days < 730 then '1to2y' else '2yplus' end` |
| 12 | `Days_Into_Term_Est` | NUMBER (18,0) | `pmod(Policy_Days, 182)` |
| 13 | `Days_To_Term_End_Est` | NUMBER (18,0) | `182 - pmod(Policy_Days, 182)` |
| 14 | `Days_To_Renewal` | NUMBER (18,0) | `case when Policy_Renewal_Date_c__c >= "Cal.Snap_Date" then datediff(Policy_Renewal_Date_c__c, "Cal.Snap_Date") else null end` |
| 15 | `Days_Since_Renewal_Offer` | NUMBER (18,0) | `case when Renewal_Offer_Date_c__c <= "Cal.Snap_Date" then datediff("Cal.Snap_Date", Renewal_Offer_Date_c__c) else null end` |

**+ app** (Join): LEFT_OUTER, left keys `['Account_Id2_c__c', 'Cal.Snap_Key']` = right keys `['Account_Id__c', 'Snap_Key_App']`, right-side prefix `App`; drop from right side: `['App.Account_Id__c', 'App.Snap_Key_App']`

**+ email** (Join): LEFT_OUTER, left keys `['Id__c', 'Cal.Snap_Key']` = right keys `['et4ae5_Contact_c__c', 'Snap_Key_Email']`, right-side prefix `Email`; drop from right side: `['Email.et4ae5_Contact_c__c', 'Email.Snap_Key_Email']`

**+ tickets** (Join): LEFT_OUTER, left keys `['Customer_Number_c__c', 'Cal.Snap_Key']` = right keys `['Customer_Number_c__c', 'Snap_Key_Tkt']`, right-side prefix `Tkt`; drop from right side: `['Tkt.Customer_Number_c__c', 'Tkt.Snap_Key_Tkt']`

**Final features** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `App_Events_30d_F` | NUMBER (18,0) | `coalesce("App.App_Events_30d", 0)` |
| 2 | `App_Events_90d_F` | NUMBER (18,0) | `coalesce("App.App_Events_90d", 0)` |
| 3 | `Days_Since_Last_App_Event` | NUMBER (18,0) | `case when "App.Last_App_Event" is null then 9999 else datediff("Cal.Snap_Date", "App.Last_App_Event") end` |
| 4 | `Email_Sends_90d_F` | NUMBER (18,0) | `coalesce("Email.Email_Sends_90d", 0)` |
| 5 | `Email_Opens_30d_F` | NUMBER (18,0) | `coalesce("Email.Email_Opens_30d", 0)` |
| 6 | `Email_Opens_90d_F` | NUMBER (18,0) | `coalesce("Email.Email_Opens_90d", 0)` |
| 7 | `Email_Clicks_90d_F` | NUMBER (18,0) | `coalesce("Email.Email_Clicks_90d", 0)` |
| 8 | `Email_Open_Rate_90d` | NUMBER (5,4) | `case when coalesce("Email.Email_Sends_90d", 0) = 0 then null else coalesce("Email.Email_Opens_90d", 0) / "Email.Email_Sends_90d" end` |
| 9 | `Days_Since_Last_Email_Event` | NUMBER (18,0) | `case when "Email.Last_Email_Event" is null then 9999 else datediff("Cal.Snap_Date", "Email.Last_Email_Event") end` |
| 10 | `Tickets_90d_F` | NUMBER (18,0) | `coalesce("Tkt.Tickets_90d", 0)` |
| 11 | `Days_Since_Last_Ticket` | NUMBER (18,0) | `case when "Tkt.Last_Ticket" is null then 9999 else datediff("Cal.Snap_Date", "Tkt.Last_Ticket") end` |
| 12 | `Max_Feature_Date` | DATETIME | `greatest("App.Last_App_Event", "Email.Last_Email_Event", "Tkt.Last_Ticket")` |

**Churn_PIT_Training_Set** (Output): write to `Churn_PIT_Training_Set__dll` (dataLakeObject), mode OVERWRITE, primary key `Row_Key__c`. Column mapping:

| Source column | Target field |
|---|---|
| `Row_Key` | `Row_Key__c` |
| `Id__c` | `Contact_Id__c` |
| `Cal.Snap_Date` | `Snapshot_Date__c` |
| `Cal.Snap_Key` | `Snapshot_Key__c` |
| `Label_60` | `Label_60__c` |
| `Label_90` | `Label_90__c` |
| `Censored` | `Censored__c` |
| `Reason` | `Reason__c` |
| `Tenure_Days` | `Tenure_Days__c` |
| `Tenure_Bucket` | `Tenure_Bucket__c` |
| `Policy_Days` | `Policy_Days__c` |
| `Days_Into_Term_Est` | `Days_Into_Term_Est__c` |
| `Days_To_Term_End_Est` | `Days_To_Term_End_Est__c` |
| `Days_To_Renewal` | `Days_To_Renewal__c` |
| `Days_Since_Renewal_Offer` | `Days_Since_Renewal_Offer__c` |
| `Policy_Renewal_Rate_c__c` | `Policy_Renewal_Rate__c` |
| `Lifetime_Savings_c__c` | `Lifetime_Savings__c` |
| `Telematic_Discount_Numeric__c` | `Telematics_Discount__c` |
| `App_Events_30d_F` | `App_Events_30d__c` |
| `App_Events_90d_F` | `App_Events_90d__c` |
| `Days_Since_Last_App_Event` | `Days_Since_Last_App_Event__c` |
| `Email_Sends_90d_F` | `Email_Sends_90d__c` |
| `Email_Opens_30d_F` | `Email_Opens_30d__c` |
| `Email_Opens_90d_F` | `Email_Opens_90d__c` |
| `Email_Clicks_90d_F` | `Email_Clicks_90d__c` |
| `Email_Open_Rate_90d` | `Email_Open_Rate_90d__c` |
| `Days_Since_Last_Email_Event` | `Days_Since_Last_Email_Event__c` |
| `Tickets_90d_F` | `Tickets_90d__c` |
| `Days_Since_Last_Ticket` | `Days_Since_Last_Ticket__c` |
| `Max_Feature_Date` | `Max_Feature_Date__c` |


### Row C: mobile app events

**Mobile app events** (Input Data): `MobileApp_c_00D3h0000068eod__dlm` (dataModelObject), columns: `Account_Id__c`, `Event_Timestamp_UTC__c`, `Event_Name__c`

**App join key** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `xk` | NUMBER (18,0) | `1` |

**App x snapshot** (Join): INNER, left keys `['xk']` = right keys `['xk']`, right-side prefix `Cal`; drop from right side: `['Cal.xk', 'Cal.Snapshot_Date__c', 'Cal.Snapshot_Key__c']`

**App windows** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `App_Before_Snap` | NUMBER (18,0) | `case when Event_Timestamp_UTC__c <= "Cal.Snap_Date" then 1 else 0 end` |
| 2 | `App_30` | NUMBER (18,0) | `case when Event_Timestamp_UTC__c > "Cal.Snap_Date" - INTERVAL 30 DAY and Event_Timestamp_UTC__c <= "Cal.Snap_Date" then 1 else 0 end` |
| 3 | `App_90` | NUMBER (18,0) | `case when Event_Timestamp_UTC__c > "Cal.Snap_Date" - INTERVAL 90 DAY and Event_Timestamp_UTC__c <= "Cal.Snap_Date" then 1 else 0 end` |
| 4 | `Snap_Key_App` | TEXT | `"Cal.Snap_Key"` |

**Events before snapshot** (Filter): `App_Before_Snap` EQUAL ['1']

**App per contact-snapshot** (Aggregate): group by `['Account_Id__c', 'Snap_Key_App']`; SUM(`App_30`) as `App_Events_30d`; SUM(`App_90`) as `App_Events_90d`; MAX(`Event_Timestamp_UTC__c`) as `Last_App_Event`


### Row D: email (Individual Email Results)

**Individual Email Results** (Input Data): `IndividualEmailResults__dll` (dataLakeObject), columns: `et4ae5_Contact_c__c`, `et4ae5_DateSent_c__c`, `et4ae5_DateOpened_c__c`, `et4ae5_Opened_c__c`, `et4ae5_Clicked_c__c`, `et4ae5_NumberOfUniqueClicks_c__c`

**Contact sends only** (Filter): `et4ae5_Contact_c__c` STARTS_WITH ['003'] AND `et4ae5_DateSent_c__c` IS_NOT_NULL

**Email join key** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `xk` | NUMBER (18,0) | `1` |

**Email x snapshot** (Join): INNER, left keys `['xk']` = right keys `['xk']`, right-side prefix `Cal`; drop from right side: `['Cal.xk', 'Cal.Snapshot_Date__c', 'Cal.Snapshot_Key__c']`

**Email windows** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `Email_Before_Snap` | NUMBER (18,0) | `case when et4ae5_DateSent_c__c <= "Cal.Snap_Date" then 1 else 0 end` |
| 2 | `Email_Sent_90` | NUMBER (18,0) | `case when et4ae5_DateSent_c__c > "Cal.Snap_Date" - INTERVAL 90 DAY then 1 else 0 end` |
| 3 | `Email_Open_30` | NUMBER (18,0) | `case when et4ae5_Opened_c__c = true and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) > "Cal.Snap_Date" - INTERVAL 30 DAY and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) <= "Cal.Snap_Date" then 1 else 0 end` |
| 4 | `Email_Open_90` | NUMBER (18,0) | `case when et4ae5_Opened_c__c = true and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) > "Cal.Snap_Date" - INTERVAL 90 DAY and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) <= "Cal.Snap_Date" then 1 else 0 end` |
| 5 | `Email_Click_90` | NUMBER (18,0) | `case when et4ae5_Clicked_c__c = true and et4ae5_DateSent_c__c > "Cal.Snap_Date" - INTERVAL 90 DAY then 1 else 0 end` |
| 6 | `Email_Event_Date` | DATETIME | `case when et4ae5_Opened_c__c = true and et4ae5_DateOpened_c__c <= "Cal.Snap_Date" then et4ae5_DateOpened_c__c else et4ae5_DateSent_c__c end` |
| 7 | `Snap_Key_Email` | TEXT | `"Cal.Snap_Key"` |

**Sends before snapshot** (Filter): `Email_Before_Snap` EQUAL ['1']

**Email per contact-snapshot** (Aggregate): group by `['et4ae5_Contact_c__c', 'Snap_Key_Email']`; SUM(`Email_Sent_90`) as `Email_Sends_90d`; SUM(`Email_Open_30`) as `Email_Opens_30d`; SUM(`Email_Open_90`) as `Email_Opens_90d`; SUM(`Email_Click_90`) as `Email_Clicks_90d`; MAX(`Email_Event_Date`) as `Last_Email_Event`


### Row E: Zendesk tickets

**Zendesk tickets** (Input Data): `Zen_Desk_Ticket_Gold__dlm` (dataModelObject), columns: `Customer_Number_c__c`, `Created_at_c__c`, `Ticket_type_c__c`

**Ticket join key** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `xk` | NUMBER (18,0) | `1` |

**Ticket x snapshot** (Join): INNER, left keys `['xk']` = right keys `['xk']`, right-side prefix `Cal`; drop from right side: `['Cal.xk', 'Cal.Snapshot_Date__c', 'Cal.Snapshot_Key__c']`

**Ticket windows** (Transform node, add these custom formula columns in order):

| # | Column name | Type | Formula |
|---|---|---|---|
| 1 | `Tkt_Before_Snap` | NUMBER (18,0) | `case when Created_at_c__c <= "Cal.Snap_Date" then 1 else 0 end` |
| 2 | `Tkt_90` | NUMBER (18,0) | `case when Created_at_c__c > "Cal.Snap_Date" - INTERVAL 90 DAY and Created_at_c__c <= "Cal.Snap_Date" then 1 else 0 end` |
| 3 | `Snap_Key_Tkt` | TEXT | `"Cal.Snap_Key"` |

**Tickets before snapshot** (Filter): `Tkt_Before_Snap` EQUAL ['1']

**Tickets per contact-snapshot** (Aggregate): group by `['Customer_Number_c__c', 'Snap_Key_Tkt']`; SUM(`Tkt_90`) as `Tickets_90d`; MAX(`Created_at_c__c`) as `Last_Ticket`

