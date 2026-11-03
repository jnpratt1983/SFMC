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

## The change: model-routed, with a learning slice (no holdout)

Decisions 2026-11-02: no email-only arm, and the journey keeps choosing the channel from a model,
the way the predicted channel field did. A pure random split is not the design; it is the data the
next model needs, so it runs as a small slice alongside the model-routed majority.

Revised 2026-11-03: three response models train on 2024-2026 history now and write into the existing
`Email_Score__c` / `SMS_Score__c` / `Call_Score__c`; `Predicted_Channel__c` stays the routing field with a new
formula (README "After training"): phone score above threshold -> `Call + Email`, SMS score above threshold ->
`SMS + Email`, both -> `Call + SMS + Email`, neither -> `SMS + Email`. So the model path of v17 IS the existing
`predicted_channel__c` decision (MCD-4) with one outcome added; the random split sits in front of it and the
Update Lead steps after it. The email-open rule below is the fallback if the phone and SMS models fail their
lift charts. The random slice remains for the purchase question and to audit the routing.

```
entry -> wait 5 min -> MCD-1 "channel availability" (unchanged)
  Email & SMS, mobile present, no opt-out, no DNC
     -> RANDOMSPLIT 80 / 20
          80%  -> DECISION on Email_Open_Likelihood__c (entry snapshot)
                    low  (bottom third)        -> CALL_SMS   "email will not reach them: call and text"
                    high (top two thirds)      -> SMS        "email reaches them: text alongside"
          20%  -> RANDOMSPLIT 34 / 33 / 33     -> SMS | CALL | CALL_SMS   (learning slice)
  other outcomes -> existing paths, arm INELIGIBLE
```

| Arm | Day 0 | Day 0 + 2h | Day 2 | Day 6 | Who lands here |
|---|---|---|---|---|---|
| SMS | ES1 + SE1 | - | ES2 + SE2 | ES3 + SE3 | model: high open likelihood; random: a third of the slice |
| CALL | ES1 | Call task + Zendesk ticket | ES2 | ES3 | random slice only |
| CALL_SMS | ES1 + SE1 | Call task + Zendesk ticket | ES2 + SE2 | ES3 + SE3 | model: low open likelihood; random: a third of the slice |

Same emails, same STO waits, same day offsets in all three. Every lead gets at least one outbound
channel. About 80% of leads get the model's choice from the first day; the 20% slice (roughly 90
leads a month) accrues unbiased call and text response labels and tests the routing rule itself:
if low-open-likelihood leads in the random slice do no better when called, the rule is wrong and
the threshold or the channel changes.

**What the channel label is.** Decision 2026-11-02: whether the rep reached the lead does not matter;
a missed call or a voicemail can lift on its own. So the label for a channel is purchase within 30
days after the lead was contacted on it, compared with leads like them who were not. That is the
uplift model (`Channel_Uplift_Training_Set__cio.sql`), and it is why the learning slice has to be
random: purchase after a call can only be compared with purchase without a call when who got called
did not depend on the lead. Reach rate, click rate and open rate remain as diagnostics and as model
features; none of them is a routing target.

**Version 18, the end state.** When the uplift models have enough purchases per arm in the random
slice, the 80% branch's decision reads the new predicted channel field on the Lead (the channel with
the highest purchase uplift for leads like this one, written by Model Builder), with one outcome per
channel, exactly like the old `predicted_channel__c` decision but on a label that means "bought after
being contacted this way". The learning slice stays, smaller if wanted, so the models keep getting
unbiased data and the routing keeps getting audited.

Steps, in order:

1. **Eligibility at entry, not at the split.** In `AC_ReviewNBA_v8` (or in MCD-1) require Email not
   null, mobile present, `Mobile_Opt_Out_Date__c` null, `DoNotCall` false for the test population, so
   all three arms are possible for every entrant. Leads failing that go down the existing Email Only
   path with arm `INELIGIBLE` written (step 4).
2. **Entry snapshot carries the scores.** Add `Email_Open_Likelihood__c` (the new model's output),
   `Call_Score__c`, `Email_Score__c`, `SMS_Score__c` to the `AC_ReviewNBA_v8` select, so the decision
   reads the value the lead had at entry and the Lead keeps a record of it.
3. **Replace MCD-4** (the `predicted_channel__c` decision) with: RANDOMSPLIT 80/20; on the 80% path a
   MULTICRITERIADECISION on `Email_Open_Likelihood__c` with two outcomes (low -> CALL_SMS, high ->
   SMS; threshold = the score at the bottom third of the training set, written in the activity name so
   it is visible); on the 20% path a RANDOMSPLIT 34/33/33 to SMS / CALL / CALL_SMS. Nothing reads
   `predicted_channel__c` any more.
4. **Write the assignment to the Lead immediately after**, one Salesforce "Update Lead" activity per
   landing point (five of them): `NBA_Test_Arm__c` = SMS | CALL | CALL_SMS, `NBA_Assignment__c` =
   MODEL | RANDOM, `NBA_Entry_At__c` = now, `NBA_Entry_Email_Model_Score__c` and the three legacy
   entry scores. Seven new Lead fields (deployed 2026-11-03, permission set `NBA_Test_Access`); add them to the CRM connector `Lead` data stream. Mirror the row to a DE
   `AC_ReviewNBA_TestLog` (Update Contact) for SFMC-side counts.
5. **Build the three paths** by copying the existing Call + Email path (ES1 -> 2h -> SALESCLOUDACTIVITY
   -> 2d -> STO -> ES2 -> 4d -> STO -> ES3 -> 3d) and adding or removing SE1/SE2/SE3 and the call step
   per the table. Model-routed and random leads share the same three paths; only the Update Lead step
   before the path differs. Keep the 2-hour wait and the Zendesk email on the task.
6. **Exit on purchase.** Exit criterion = `purchased__c` true or `Max_Quote_Step__c` = 7.0, evaluated
   at every wait. Add a Goal on the same condition.
7. **Entry mode stays SingleEntryAcrossAllVersions.** One assignment per lead.
8. **Publish as v17, leave v16 running** so its contacts finish.
9. **Prerequisite**: the email response model must be scoring leads into `Email_Open_Likelihood__c`
   before v17 publishes (README setup steps 1-3). Until then, publish v17 with the 80% branch routing
   everyone to SMS, so the only live change is the learning slice.

## Sample size and duration

About 450 Email & SMS entrants a month today: ~360 model-routed, ~90 in the learning slice (~30 per
arm). Three readouts, each on its own clock:

- Routing rule check (does low open likelihood + call beat low open likelihood + text only): read
  inside the random slice, needs about 400 low-likelihood leads per arm for a 5-point difference, so
  widen the entry query (7-day suppression and window, roughly doubles entrants) or raise the slice
  to 30% for the first months.
- Uplift labels for the next models: purchase within 30 days per arm, random slice only. At a 20%
  slice that is ~90 leads and ~10 purchases a month across three arms, which is years, not months.
  Run the slice at 50% for the first six months (every lead still gets a channel; it only changes how
  the channel is picked) and widen the entry query: ~450 random leads a month, ~150 per arm, ~17
  purchases per arm per month. An arm-level answer in about a year; a per-lead model later.
- Diagnostics that read within a month: reach rate in the call arms (~14%), click floor in the text
  arms (~1%), open rate across arms (should be equal; if not, the arms are not balanced).
- Purchase effect of the whole v17 against v16: before/after on 30-day purchase, no holdout.

## Readout

`Channel_Uplift_Training_Set__cio.sql` reads `NBA_Test_Arm__c` and `NBA_Entry_At__c`, labels
purchase within 30 days from `Purchased_Date__c`, call reached from the Next Best Action ticket
comment, SMS click from the same-person `utm_medium = sms` lead. Primary metric: 30-day purchase by arm within the random slice (`NBA_Assignment__c = RANDOM`);
model-routed leads are reported separately and never pooled with the slice. Secondary: reach, click and open rates as diagnostics only.
