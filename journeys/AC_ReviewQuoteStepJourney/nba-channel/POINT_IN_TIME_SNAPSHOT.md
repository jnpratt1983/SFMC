# Point-in-time training sets for the channel models

Built 2026-11-03 after the top-features check showed current-state fields leaking into the models
(opt-out after opening, funnel step after the email). The Lead object in Data Cloud holds today's values
only, so "as of the first email" has to be rebuilt from Lead field history.

## Where the history is

Salesforce Lead field history tracking (`LeadHistory`) has recorded these fields since 2025-05-02:
`Max_Quote_Step__c`, `Declined__c`, `Credit_Score__c`, `Vehicle_Make__c`, `et4ae5__HasOptedOutOfMobile__c`,
`purchased__c` (8.4M rows, ~4.0M on those six). Not tracked: `HasOptedOutOfEmail`, `Saved_Quote__c`,
`App_Downloaded__c`, so those are removed from the point-in-time sets rather than guessed.
`LeadHistory` is not available through the Data Cloud CRM connector, so the rebuild runs outside Data Cloud.

## The rule

For a lead and an event time t (first quote email for the email model, first text for the SMS model, creation
for the phone model), the value of a tracked field at t is the `OldValue` of the earliest history row for that
field created after t; if the field never changed after t, the current value stands. Leads that had already
purchased before t are dropped.

## The build

1. `sf data export bulk` of `LeadHistory` (five columns, six fields, since 2025-05-01) to `leadhistory.csv`.
2. The three training insights pulled in full over the query API (50k rows a page).
3. `build_pit.py` (session scratchpad `nba/pit/`, copied to this folder as `pit_build.py`) applies the rule with a
   forward `merge_asof` per field and writes:

| File | Event | Rows kept | Notes |
|---|---|---|---|
| `Email_Response_Training_Set_PIT.csv` | first AC_ email | first sends on/after 2025-05-02 | current-state-only columns removed |
| `SMS_Response_Training_Set_PIT.csv` | first text | whole label window; funnel fields blank for texts before 2025-05-02 | CatBoost treats blank as missing |
| `Phone_Response_Training_Set_PIT.csv` | lead creation | leads created on/after 2025-05-02 | |

## Built 2026-11-03 (files in `data-cloud/nba-channel/pit/`, 40-56 MB each, not in the SFMC repo)

| File | Rows | Positives | What the rebuild changed |
|---|---|---|---|
| `Email_Response_Training_Set_PIT.csv` | 150,757 first sends since 2025-05-02 | 48,296 opened (32.0%), 4,003 clicked | quote step rewound on 14,180 rows, mobile opt-out on 15,797; 845 leads that had bought before the email dropped |
| `SMS_Response_Training_Set_PIT.csv` | 163,404 texted leads (window flag marks the 87k usable ones) | 7,775 clicked in 14 days (6,522 inside the window) | 4,019 text-born leads dropped (the self-click artifact); quote step rewound on 11,046 |
| `Phone_Response_Training_Set_PIT.csv` | 176,428 leads created since 2025-05-02 | 4,719 phoned us in 30 days (2.7%) | mobile opt-out rewound on 69,808 rows, declined on 16,899; coverage artifact gone by construction |

Columns removed because history does not track them: `Email_Opt_Out__c`, `Saved_Quote__c`, `App_Downloaded__c`,
`Currently_Insured__c`, and `Purchased__c` (an outcome). `Event_At__c` is the point in time of each row.

## Loading into Data Cloud and retraining

1. Data Cloud > Data Streams > New > Upload File (or the Ingestion API connector), one stream per CSV, category
   Other, primary key `Lead_Id__c`. Let the stream create its lake object; map it to a new DMO of the same name
   (`Email_Response_Training_Set_PIT`, etc.) with every column.
2. Model Builder, training data = the PIT DMO:
   | Model | Filter | Target | Exclude |
   |---|---|---|---|
   | Email open | none | `Opened_First_Email__c` | Lead_Id, Clicked_First_Email, First_Email_Name, First_Send_At, Event_At, Days_Create_To_Send, Send_Hour, Send_Rows, Lead_Created |
   | SMS click | `Label_Window__c` = 1 | `Clicked_14d__c` | Lead_Id, SMS_Name, SMS_Sent_At, Event_At, First_Click_Lead_At, SMS_Hour, Days_Create_To_SMS, Clicked_30d, Label_Window, Row_Count, Lead_Created, Lead_Created_Month, SMS_Status_Code |
   | Phone preference | none | `Called_Us_30d__c` | Lead_Id, Called_Us_90d, First_Call_At, Event_At, Days_Create_To_Call, Lead_Created, Lead_Created_Month, Row_Count |
   Expect lower AUCs than the first versions (0.665 / 0.732 / 0.805); those were partly leakage. The gate stays 0.58.
3. Scoring stays on `Email_Response_Scoring_Set__cio`: a lead created in the last 14 days is close enough to its
   own point in time, and the scoring columns match the PIT columns by name.
4. Retrain on a schedule by re-running steps 1-3 of the build; the history keeps accruing.

## Forward-looking alternative

`Lead_Score_Snapshot__c` (daily, leads created in the last 30 days, live since 2026-10-28) already stores
`Max_Quote_Step__c` per day. Adding `Declined__c`, `Saved_Quote__c`, `App_Downloaded__c`, `Credit_Score__c` and the
two opt-outs to that flow would make future snapshots complete without the history reconstruction, including the
three fields history does not track.
