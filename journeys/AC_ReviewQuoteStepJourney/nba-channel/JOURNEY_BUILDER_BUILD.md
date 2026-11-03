# AC_ReviewQuoteStepJourney v17: Journey Builder build, tile by tile

Mock-up with the canvas and this table: https://claude.ai/artifact/GHnYvrR8rBQpRRHFdD8Ueu (updated 2026-11-03).
Palette tiles used: Decision Split, Random Split, Join, Wait By Duration, Einstein STO, Email, SMS, Sales & Service Cloud (Lead update, Task).
"Journey Data" = a column of the entry data extension, the snapshot taken when the lead entered.

| Tile | Palette | Configuration | Value source |
|---|---|---|---|
| Entry Source | Data Extension | `AC_ReviewNBATest_AF_01272026` (key `1D148A47-9A8C-476B-9F8D-8E107D1F51BE`), filled by automation `AC_NBATEST` every 15 min (step 2 query, step 3 entry). Replace query `AC_ReviewNBA_v8` with `AC_ReviewNBA_v9`. Add five DE columns first: `Call_Score__c`, `Email_Score__c`, `SMS_Score__c` (Decimal 18,2), `Last_Channel_Scoring_Date__c` (Date), `MobilePhone` (Phone, harmless but unused). Entry gate in v9: `last_channel_scoring_date__c IS NOT NULL`, so no wait is needed. Settings unchanged: single entry across all versions, email = `Email`, mobile = `Mobile_Country_Code__c`. | Synchronized DE `Lead_Salesforce`; confirm the six fields are in the MC Connect Lead sync. |
| Decision Split "Channel availability" | Decision Split | Existing MCD-1 plus one outcome **at the top**: **Channel Availability** = `Mobile_Country_Code__c` is not equal to `1` (a formula: "1" + Phone, so a blank Phone yields exactly "1"; 605 of 605 blank-Phone leads in 90 days) AND `Mobile_Opt_Out_Date__c` is null AND `HasOptedOutOfEmail` is False -> Random Split. Remainder exits (v16's Email Only and SMS Only paths were dropped in the rebuild). `MobilePhone` is never populated on Lead and `DoNotCall` is not used; neither belongs in the criteria. | Journey Data |
| Random Split "Model / learning" | Random Split | Path 1 Model 50%, Path 2 Learning 50%. The only tile that changes in v18 (80 / 20). | Journey Builder |
| Update Lead "Assignment MODEL" / "Assignment RANDOM" | Sales & Service Cloud > Lead > Update | Lead where `Id` = Journey Data `Id`; `NBA_Assignment__c` = static `MODEL` / `RANDOM`. Placed before the Joins because after a Join the side is no longer known. | Static |
| Decision Split "Predicted channel" | Decision Split | Copy of MCD-4 with **is equal to** (not contains): `SMS + Email` -> Join SMS; `Call + Email` -> Join CALL; `Call + SMS + Email` -> Join CALL_SMS; Remainder (`Email Only`, returned when `Phone` is blank but `MobilePhone` is set) -> Join SMS. | Journey Data `predicted_channel__c` (Lead formula with thresholds 42.3 / 39.8) |
| Random Split "Learning arms" | Random Split | SMS 34%, CALL 33%, CALL_SMS 33% -> the three Joins. | Journey Builder |
| Join "SMS arm" / "CALL arm" / "CALL_SMS arm" | Join | Inputs: the matching Predicted channel outcome and the matching Learning arms outcome. Output: the arm's Update Lead. | n/a |
| Update Lead "Arm SMS" / "Arm CALL" / "Arm CALL_SMS" | Sales & Service Cloud > Lead > Update | `NBA_Test_Arm__c` = static arm; `NBA_Entry_Call_Score__c` = Journey Data `Call_Score__c`; `NBA_Entry_Email_Score__c` = Journey Data `Email_Score__c`; `NBA_Entry_SMS_Score__c` = Journey Data `SMS_Score__c`; `NBA_Entry_Email_Model_Score__c` = Journey Data `Email_Score__c`. `NBA_Entry_At__c` is stamped in Salesforce by a one-node record-triggered flow on Lead (when `NBA_Test_Arm__c` changes from blank, set `NBA_Entry_At__c` = now). | Entry snapshot |
| Update Lead "Arm INELIGIBLE" | Sales & Service Cloud > Lead > Update | On the Email & SMS outcome: `NBA_Test_Arm__c` = static `INELIGIBLE`. | Static |
| Email ES1 / ES2 / ES3 | Email | `AC_Review_ES1_04062026_V` (131338), `AC_Review_ES2_04062026_V` (131339), `AC_Review_ES3_04062026_V` (131340), same in every arm; copy from today's Email & SMS path. | Existing |
| SMS SE1 / SE2 / SE3 | SMS | `AC_Review_SE1_04062026_V` (422447), `AC_Review_SE2_01072026_V` (422448), `AC_Review_SE3_04062026_V` (422449); SMS and CALL_SMS arms only. The CALL arm sends no text. | Existing |
| Wait 2 hours -> Task "Call Lead- Next Best Action" | Wait By Duration, Sales & Service Cloud > Task | CALL and CALL_SMS arms after ES1 (and SE1). Same Task configuration as today's CC Call path; the Task fires flow `New_Lead_NBA_Test`, which opens the Zendesk "New Lead- Next Best Action" ticket with the Lead Id in the subject. | Existing |
| Wait 2 d, STO 12 h, Wait 4 d, STO 12 h, Wait 3 d | Wait By Duration, Einstein STO | Same durations, window and time zone as today's paths. | Existing |
| Exit criteria, Goal | Settings | Exit unchanged: contact appears in `EXIT_AllCurrentCustomers`, evaluated at every wait (the purchase signal). Add a Goal on the same filter. Publish v17, let v16 drain. | Existing |

Arm contents

| Arm | Day 0 | +2 h | Day 2 (after STO) | Day 6 (after STO) | Day 9 |
|---|---|---|---|---|---|
| SMS | ES1 + SE1 | | ES2 + SE2 | ES3 + SE3 | end |
| CALL | ES1 | Task + Zendesk ticket | ES2 | ES3 | end |
| CALL_SMS | ES1 + SE1 | Task + Zendesk ticket | ES2 + SE2 | ES3 + SE3 | end |

## Version 18, six months later

In Journey Builder: new version of v17, Random Split "Model / learning" = Model 80% / Learning 20%, publish. Nothing else moves.
Outside: retrain the three models on `Channel_Uplift_Training_Set` (random slice, purchased within 30 days of entry), re-tune the two thresholds in `Predicted_Channel__c`, and read the first six months first (purchase rate by arm within `NBA_Assignment__c = RANDOM`; MODEL vs RANDOM overall). Trigger: about 150 purchases per arm in the random slice and a retrained score that beats the current one out of time.

## Sales Cloud side, one small addition

Record-triggered flow on Lead, after save, when `NBA_Test_Arm__c` is changed and was blank: set `NBA_Entry_At__c` = `{!$Flow.CurrentDateTime}`. Journey Builder's Lead update has no reliable "now" for a date/time field.
