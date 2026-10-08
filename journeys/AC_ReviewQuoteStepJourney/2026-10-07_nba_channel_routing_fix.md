# Next Best Action: why half the "Call + Email" leads never get a call task, and the fix

Journey: AC_ReviewQuoteStepJourney_September2026 (Published v14, business unit "B2C Lifecycle Marketing", MID 110007736).
Feeder automations: AC_QuoteSteps and AC_NBATEST (query activity AC_ReviewNBA_v8, every 15 minutes, into DE
AC_ReviewNBATest_AF_01272026). Investigated 2026-10-07 from the Marketing Cloud API (read-only) and the
Salesforce Lead object. Nothing has been changed in Marketing Cloud yet; this document is the change request.

## Summary

Next Best Action (NBA) is the channel split inside the Review-step journey. A Data Cloud model writes
`Predicted_Channel__c` on the Lead (Call + Email / SMS + Email / Email Only). The journey reads that value from
the entry data extension and routes "Call + Email" leads to a branch that creates the Salesforce task
"Call Lead- Next Best Action", which the contact center works from Zendesk.

Only about 45% of leads that are "Call + Email" at the time they enter the journey ever get that task.
The cause is a timing race, not a model or data problem: the lead is re-scored minutes after it reaches
quote step 5, but the journey has already snapshotted the earlier prediction and routed the lead to the
Email/SMS branch.

**Fix:** stop routing on the snapshot. Add a 2-hour wait on the Email & SMS branch before the channel split
and make the split evaluate the lead's *current* predicted channel. Because the child business unit cannot see
custom synced Lead fields in Contact Builder, the current value has to be staged into a standard data
extension by a query activity and linked in Contact Builder (details below).

## How the routing works today

```
AC_QuoteSteps / AC_NBATEST (every 15 min, :00 :15 :30 :45 CST)
  AC_ReviewNBA_v8 SQL reads ent.Lead_Salesforce (Marketing Cloud Connect sync, ~15 min lag)
  -> DE AC_ReviewNBATest_AF_01272026  (3-day snapshot incl. predicted_channel__c)
  -> journey entry

Journey
  split 1 "Email Only / Email & SMS / SMS Only / Remainder"   (email present? Mobile_Opt_Out_Date__c null?)
    Email & SMS branch
      split 2 "Email / SMS / CC Call / Remainder"              (Journey Data: entry-DE predicted_channel__c)
        CC Call branch:  EMAIL ES1 -> SALESCLOUDACTIVITY "Call Lead- Next Best Action" (Task on the Lead)
```

Only the CC Call path under Email & SMS creates a task. Leads on the Email Only path (mobile opt-out), SMS Only
(no email) or Remainder never reach it by design. Versions v11 to v13 also had a random control split
(10%, then 50/50) that sent control leads down the generic path with no call; v14 (2026-09-17) removed it.

## Root cause: the entry snapshot carries a stale prediction

| Group (v14 Call + Email entrants on the Email & SMS path) | Last channel scoring relative to journey entry | Re-scored after entry |
| --- | --- | --- |
| Got the call task | 0.3 to 1.5 h **before** entry (median 0.6 h) | 0% |
| No call task | at or **after** entry (median 0.2 h after) | 65% |

Leads are scored at creation (around quote step 1) and re-scored at the next hourly batch after new attributes
arrive. Reaching step 5 brings new attributes, so a lead's prediction typically changes to "Call + Email" at the
first :05 to :10 after it hits step 5. Meanwhile AC_NBATEST fires every 15 minutes and reads the synced Lead,
which itself lags Salesforce by about 15 minutes. If the lead reaches step 5 between scoring batches, the
15-minute query picks up the pre-re-score value (SMS + Email or Email Only), the journey routes on it, and the
lead becomes "Call + Email" only minutes later. The same pattern holds in v11 and v12-v13.

Timing changes alone cannot fix this: whatever minute the automation runs, some leads will reach step 5 just
before a scoring batch and enter before their re-score. Shifting to date-level "scored before entry" checks is
also not enough; the gap is measured in minutes.

Why the retroactive channel cannot be recovered: `Predicted_Channel__c` has no field history, and Data Cloud's
`Lead_Multi_Channel_Scoring__dlm` keeps only the latest batch. `Last_Channel_Scoring_Date__c` versus entry
time (first SentEvent, Marketing Cloud UTC-6) is the only clean separator.

Downstream of the task the pipeline is clean: since June 2026, 100% of tasks became a Zendesk
"New Lead- Next Best Action" ticket the same or next day.

## The fix (decision 2026-10-07)

Build a new version of AC_ReviewQuoteStepJourney_September2026 with these changes on the Email & SMS branch.

1. **Wait by Duration: 2 hours** immediately before the channel split. The first email moves after the split,
   so "Call + Email" leads get their first email about 2 hours later than today. The delay is accepted; the
   15-minute entry cadence stays as it is.
2. **Channel split reads Contact Data, not Journey Data.** Change the three conditions from the entry DE's
   `predicted_channel__c` to the lead's current predicted channel, exposed through Contact Builder (step 3).
   Conditions stay "contains Call + Email" / "contains SMS + Email" / "contains Email Only".
3. **Stage the current prediction in a standard DE.** In the child BU, linking the synchronized Lead DE
   (`Lead_Salesforce_SHARED`) in a Contact Builder attribute group exposes only the 11 default fields
   (Id, Email, Status, Converted*Id, CreatedById, LastModifiedById, MasterRecordId, OwnerId, IndividualId),
   even in a brand-new group. Custom synced fields such as `Predicted_Channel__c` are not available to the
   split directly. Workaround, entirely inside the child BU:
   - New DE **AC_LeadChannelScore_Current** (primary key `Id`, text 18; fields `Predicted_Channel__c` text 50,
     `Last_Channel_Scoring_Date__c` date, `Call_Score__c` / `Email_Score__c` / `SMS_Score__c` decimal,
     `Refreshed_At` date). Not sendable.
   - New query activity **AC_LeadChannelScore_Current** as the *first* step of AC_NBATEST (every 15 minutes),
     update type Overwrite. SQL in `AC_LeadChannelScore_Current.sql` beside this file.
   - New Contact Builder attribute group **Lead Scoring** linking AC_LeadChannelScore_Current to the contact on
     Contact Key = Id (one-to-one). Journey Contact Key is the Lead Id (00Q...), so the link is direct.
   - Point the channel split at Lead Scoring > AC_LeadChannelScore_Current > Predicted_Channel__c.

   Alternative that needs an enterprise-BU admin: re-save the Lead field selection in Synchronized Data
   Sources at the parent (MID 110006745) so the custom fields propagate, then relink the synced DE. The
   existing link in attribute group "Contact Data - Synchronized" still only shows the fields from when it was
   first created, and only one published journey ("Update Push Enabled Field") depends on it.
4. **Record channel at routing.** Add an Update Contact activity on each branch after the split writing to a
   new DE **AC_ReviewNBA_Routing** (Lead Id primary key, `Routed_Channel`, `Routed_At`, `Journey_Version`).
   Re-scoring keeps overwriting `Predicted_Channel__c`, so without this the group a lead was actually routed to
   is lost and the test cannot be measured. (The entry DE has `Variation_Name__c` and Optimizely fields that
   were meant for this and are unused; writing the branch there is an acceptable substitute.)
5. **Salesforce side, optional but cheap:** enable field history tracking on `Predicted_Channel__c`
   (LeadHistory tracks about 13 custom fields today, under the 20-field limit).

An alternative that avoids the 2-hour wait was considered and rejected for now: a Lead field
`Reached_Review_At__c` set by a flow when `Max_Quote_Step__c` becomes 5, synced to Marketing Cloud, with the
feeder SQL requiring `Last_Channel_Scoring_Date__c > Reached_Review_At__c`. It delays the first email by about
an hour for everyone and needs a Salesforce deployment.

## What to check after the new version is published

- Task coverage: among entrants whose predicted channel is "Call + Email" at the split, the share with a
  "Call Lead- Next Best Action" task should rise from about 45% to close to 100% of the Email & SMS path.
- Zendesk volume: "New Lead- Next Best Action" tickets have run at about 2.5 per day (538 leads called in
  7 months). Expect roughly double once coverage is fixed; confirm the contact center can absorb it.
- AC_LeadChannelScore_Current row count: leads created in the last 14 days with a prediction, refreshed
  every 15 minutes; `Refreshed_At` should never be older than 30 minutes.
- Spot-check 20 CC Call entrants: `Predicted_Channel__c` in AC_ReviewNBA_Routing equals the Lead value at
  routing time and `Last_Channel_Scoring_Date__c` is before `Routed_At`.

## Why this matters for measuring NBA

The purpose of NBA is the Data Cloud model predicting how a lead wants to be contacted, so the test is
match versus mismatch, not "do calls work". Today's data cannot answer it:

- Only about 45% of "Call + Email" entrants were treated as intended, and the untreated half is the
  late-scored group, so tasked versus untasked comparisons are confounded.
- The randomized window (v12-v13, 50/50) gives NBA arm 12.9% purchase (n=202) versus control 18.1% (n=525),
  -5.2 +/- 5.7 points: not significant, and the NBA arm was itself only half-treated.
- The call-answer sample is tiny (30 answered, 254 no answer, 254 untagged); connect rate is about 10.6%.
- Email opens are flat across predicted channels (50 to 52%), and Email_Score tracks purchase propensity
  downward rather than channel responsiveness, so "Email Only" largely marks low-intent leads.

After the fix, with channel-at-routing recorded, measure purchase (`purchased__c`) within 14 days of entry by
routed branch. If a holdout is wanted without withholding contact, randomize call-eligible leads between
"Call + Email" and "SMS + Email"; everyone is still contacted.

A list of the 113 v14 "Call + Email" entrants that received no task (Lead Ids, entry date, last scoring time)
was given to the journey owner separately; it is not in this repository.
