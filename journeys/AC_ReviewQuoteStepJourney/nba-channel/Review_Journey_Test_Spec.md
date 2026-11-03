# AC_ReviewQuoteStepJourney: changes for the 2x2 channel test

Read from version 16 (published 2026-10-28) on 2026-11-02. Entry mode SingleEntryAcrossAllVersions,
entry source = automation audience DE `DEAudience-70da6667-...` filled by query `AC_ReviewNBA_v8`.

## What v16 actually does

```
entry -> wait 5 min -> MCD-1 "channel availability"
  Email Only  (email, mobile opted out)  -> E1 -> 2d -> STO -> E2 -> 4d -> STO -> E3 -> 3d        (no SMS, no call)
  Email & SMS (email, no mobile opt-out) -> MCD-4 "NBA split" on predicted_channel__c AT ENTRY
       Email Only   -> ES1            -> 2d -> STO -> ES2 + SE2 -> 4d -> STO -> ES3 + SE3 -> 3d
       SMS + Email  -> ES1 + SE1      -> 2d -> STO -> ES2 + SE2 -> 4d -> STO -> ES3 + SE3 -> 3d
       Call + Email -> ES1 -> 2h -> Call task (+ Zendesk ticket) -> 2d -> STO -> ES2 + SE2 -> 4d -> STO -> ES3 + SE3 -> 3d
       Remainder    -> 3d -> out
  SMS Only (no email)                   -> S1 -> 2d -> S2 -> 4d -> S3 -> 3d
  Remainder                             -> 1d -> out
```

Three things this means for the test:

1. The NBA arms differ only in the first touch. "Email Only" withholds SE1 and nothing else; the SMS
   and Call branches both get SE2 and SE3. Every arm receives the same three emails. The treatment
   contrast the model was judged on was one text or one call on day 0, which is why the holdout
   showed nothing.
2. There is no control since v14. The v11-v13 control was a separate generic email path, not the same
   creative with the channel removed, so even that comparison mixed creative with channel.
3. The exit criterion flattens to `Email is not null OR Id is not null OR Id is not null`, which reads
   as always true. It evidently is not (SE2/SE3 send), so it points at a DE whose rows mean
   "purchased". Confirm what it is before relying on it; the test needs a clean exit on purchase.

## The change: random 2x2 inside the Email & SMS branch

Replace MCD-4 (the predicted_channel__c split) with a random split, and make the four paths
identical except for the two factors.

| Arm (25% each) | Day 0 | Day 0 + 2h | Day 2 | Day 6 |
|---|---|---|---|---|
| EMAIL | ES1 | - | ES2 | ES3 |
| SMS | ES1 + SE1 | - | ES2 + SE2 | ES3 + SE3 |
| CALL | ES1 | Call task + Zendesk ticket | ES2 | ES3 |
| CALL_SMS | ES1 + SE1 | Call task + Zendesk ticket | ES2 + SE2 | ES3 + SE3 |

Same emails, same STO waits, same day offsets in all four. The only differences are whether texts go
out and whether the call task is created. A lead in EMAIL or CALL never receives a text in this
journey, which is new: today every Email & SMS lead gets SE2 and SE3.

Steps, in order:

1. **Eligibility at entry, not at the split.** In `AC_ReviewNBA_v8` (or in MCD-1) require Email not
   null, mobile present, `Mobile_Opt_Out_Date__c` null, `DoNotCall` false for the test population, so
   all four arms are possible for every entrant. Leads failing that go down the existing Email Only
   path with arm `INELIGIBLE` written (step 3) so they are excluded from the readout, not lost.
2. **Replace MCD-4 with RANDOMSPLIT, four outcomes 25/25/25/25**, labelled EMAIL / SMS / CALL /
   CALL_SMS. Nothing in the journey reads `predicted_channel__c` any more. (Two nested 50/50 splits
   work too; one four-way split keeps the arm visible in journey analytics.)
3. **Write the arm to the Lead immediately after the split**, one Salesforce "Update Lead" activity
   per arm: `NBA_Test_Arm__c` = arm, `NBA_Entry_At__c` = now, `NBA_Entry_Call_Score__c` /
   `NBA_Entry_Email_Score__c` / `NBA_Entry_SMS_Score__c` from the entry DE (add `Call_Score__c`,
   `Email_Score__c`, `SMS_Score__c` to the `AC_ReviewNBA_v8` select so the entry snapshot carries
   them), and later `NBA_Entry_Email_Model_Score__c` once the email response model scores. Five new
   Lead fields; add them to the CRM connector so Data Cloud sees them. Also write the same row to a
   DE `AC_ReviewNBA_TestLog` (Update Contact activity) for SFMC-side counts.
4. **Build the four paths** by copying the existing Call + Email path (ES1 -> 2h -> SALESCLOUDACTIVITY
   -> 2d -> STO -> ES2 -> 4d -> STO -> ES3 -> 3d) and adding or removing SE1/SE2/SE3 and the call
   step per the table. Keep the 2-hour wait before the task. Keep the Zendesk email in the task
   activity; the ticket is the call record (`Call_Response_Training_Set__cio.sql`).
5. **Exit on purchase.** Exit criterion = `purchased__c` true or `Max_Quote_Step__c` = 7.0 (whatever
   the current exit actually resolves to, made explicit), evaluated at every wait, so no one is texted
   or called after buying. Add a Goal on the same condition for Journey Builder's own arm-level
   conversion view.
6. **Entry mode stays SingleEntryAcrossAllVersions.** One arm per lead for the life of the test.
7. **Publish as v17, leave v16 running** so its contacts finish; no new entrants reach v16 because the
   entry source moves with the published version.
8. **Do not route on any score during the test**, including the new email response score. Log it
   (step 3), do not act on it.

Optional: give the SMS arm and the CALL_SMS arm different Bitly links (same destination,
`utm_content=sms_arm` / `utm_content=callsms_arm`) so Bitly's per-link counts also split by arm.
Not required; `NBA_Test_Arm__c` on the Lead already identifies the arm for the per-lead label.

## Sample size and duration

About 450 Email & SMS entrants a month today, so ~112 per arm. The readout pools factors: CALL vs
no-call is 225 vs 225 a month. Detecting +3 points on an 11% base with 80% power needs ~1,700 per
side, about 8 months. To shorten it, widen the entry in `AC_ReviewNBA_v8`: the eligible pool
(step >= 5, email and phone, no opt-out) is ~1,726 a month and only 23% enter because of the 14-day
email suppression, the 3-day window and the step 6.0 exclusion. Lifting those to a 7-day suppression
and a 7-day window roughly doubles entrants and halves the test to about 4 months.

## Readout

`Channel_Uplift_Training_Set__cio.sql` reads `NBA_Test_Arm__c` and `NBA_Entry_At__c`, labels
purchase within 30 days from `Purchased_Date__c`, call reached from the Next Best Action ticket
comment, SMS click from the same-person `utm_medium = sms` lead. Primary metric: 30-day purchase,
CALL factor and SMS factor as main effects plus their interaction. Secondary: reach rate in the call
arms, click rate in the SMS arms, email open rate across all arms (should be equal; if not, the arms
are not balanced).
