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

## Loading into Data Cloud and retraining

1. Data Cloud > Data Streams > New > Upload File (or the Ingestion API connector), one stream per CSV, category
   Other, primary key `Lead_Id__c`. Let the stream create its lake object; map it to a new DMO of the same name
   (`Email_Response_Training_Set_PIT`, etc.) with every column.
2. Model Builder: same recipes as the README, training data = the PIT DMO. The exclusions shrink to the id, label
   and event-time columns, because the leaking fields are no longer in the set.
3. Scoring stays on `Email_Response_Scoring_Set__cio`: a lead created in the last 14 days is close enough to its
   own point in time, and the scoring columns match the PIT columns by name.
4. Retrain on a schedule by re-running steps 1-3 of the build; the history keeps accruing.

## Forward-looking alternative

`Lead_Score_Snapshot__c` (daily, leads created in the last 30 days, live since 2026-10-28) already stores
`Max_Quote_Step__c` per day. Adding `Declined__c`, `Saved_Quote__c`, `App_Downloaded__c`, `Credit_Score__c` and the
two opt-outs to that flow would make future snapshots complete without the history reconstruction, including the
three fields history does not track.
