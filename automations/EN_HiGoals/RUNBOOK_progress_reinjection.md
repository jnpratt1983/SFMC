# Runbook: stop daily re-injection colliding with waits in the progress journey

Automation: `EN_HiGoals` · Journey: `EN_HiGoalsProgressCompletion_August2026` (v3, SingleEntryAcrossAllVersions)
Written 2026-10-07. Do the steps in order; each one is safe to stop after.

## Why

Step 4 injects every contact in the Progress DE (about 6,300 after the cohort fix) into the
journey every morning at 09:00 PT. Almost every path ends in a 1-day wait that expires a few
minutes *after* the next injection, so each contact is accepted on alternate days at best.
"No Goal Set" is a 7-day wait and "Off Track" waits up to 4 days. A contact sitting in any
wait is rejected (`CurrentlyWaitingInSameInteraction`). The completion flags are 1 for one
day only, so about half of goal completions land on a rejected day and are lost.

The fix moves *when to message* out of the journey and into a query. The journey receives
only contacts with a reason to hear from us today, sends, and exits them within minutes.

Expected daily injection after the change (measured on the active audience, Sep 1 to Oct 6):

| Reason | Contacts per day |
|---|---|
| Achieved + Missed (goal ended today) | 21 to 53, median 32 |
| CompletedNotSet | a subset of the achieved count from two days earlier |
| Midpoint (day 4 of a goal) | 21 to 53, median 31 |
| NoGoalWeekly (Mondays only) | about 6,100 |

Every other day the injection is under 150 contacts.

## Step 1. Create the injection DE (Contact Builder)

Build `EN_HiGoalsProgress_Inject` exactly as described in `de/EN_HiGoalsProgress_Inject.md`.
Easiest: copy the Progress DE and add the two new columns `InjectReason` (Text 30) and
`InjectDate` (Date). Confirm *Is Sendable* with `account_id__c` related to Subscriber Key.

Check: the DE exists, is sendable, and has the 57 listed columns plus the two new ones (61 if you copied the Progress DE, which also carries three unused columns: cohorts_l__c, push_enabled__c, higoal_current_goal_reward_amount__c; they do no harm).

## Step 2. Add the injection query to the automation (Automation Studio)

1. Open `EN_HiGoals` and click *Edit*.
2. In **step 3**, add a new activity: *SQL Query* → *Create New Query Activity*.
   Name `EN_HiGoals_Progress_Inject`, external key the same.
3. Paste `08_EN_HiGoals_Progress_Inject.sql`. Target DE `EN_HiGoalsProgress_Inject`,
   data action **Overwrite**. Save.
4. Make sure the three step-3 activities run in this order, left to right:
   `RI_Transition_Flags` → `EN_HiGoals_Announcement_v2` → `EN_HiGoals_Progress_Inject`.
   Activities inside a step run in parallel in Automation Studio, so if the UI does not let
   you order them, put `EN_HiGoals_Progress_Inject` in its **own new step** between the
   current step 3 and the journey injection. It must run *after* `RI_Transition_Flags`.
5. Save the automation. Do not run it yet.

Check: run only the new query activity from the query's *Run Once* button, then open
`EN_HiGoalsProgress_Inject` and confirm rows have an `InjectReason`. On a non-Monday expect
tens of rows, not thousands.

## Step 3. Create a new version of the progress journey (Journey Builder)

1. Open `EN_HiGoalsProgressCompletion_August2026` → *New Version*. This creates v4 as a draft.
2. Click the entry source (Data Extension). Choose *Change entry source*, select
   `EN_HiGoalsProgress_Inject`, keep *Automation* as the schedule type, and pick `EN_HiGoals`
   as the automation. Contact key must resolve to `account_id__c` (it will, because that is
   the DE's sendable field). Leave the entry filter empty: the query already did the filtering.
3. Leave **Settings → Contact Entry** on *Re-entry only after exiting*. Do not pick
   *Re-entry anytime*, which would allow the same contact to be in the journey twice.
4. Delete every wait activity. There are 23 of them. Specifically:
   - RI branch: the 7-day wait on *No Goal Set*; the *4 days after HIGoal_DFDR_Start_Date__c*
     wait on *Off Track*; the 1-day wait on *Remainder*; every trailing 1-day wait after a
     push or email.
   - AZ branch: the 7-day wait on *No Goal Set*; the *4 days after start date* wait on
     *Off Track*; the 1-day wait **before** the push on *Completed* (it delays the completion
     message a day; if you want that delay back, it belongs in the query, not here); every
     trailing 1-day wait.
   After deleting a wait, reconnect the activity before it to the activity after it (or to
   the end if it was the last one). Each path should read: split → push → email (where there
   is one) → end.
5. Leave the decision splits exactly as they are. The flags and fields they test are in the
   injection DE unchanged. Optional simplification for later: split on `InjectReason` instead.
6. *Validate*, then *Activate / Publish* v4. v3 stops accepting new contacts; anyone still in
   a v3 wait finishes their v3 path, which is fine.

Check: the canvas has no wait activities; the entry source card names `EN_HiGoalsProgress_Inject`.

## Step 4. Re-point the automation's journey step (Automation Studio)

Publishing v4 with a new entry DE creates a new entry event. The automation's step 4 still
points at the old one (`EN_HiGoalsProgressCompletion_July2025`, event key
`DEAudience-e14d4750-da43-2e39-442b-69a2d50e8ca8`).

1. Open `EN_HiGoals` → *Edit*.
2. In **step 4**, delete the existing journey activity.
3. Add activity → *Journey Audience* (data extension entry). Pick the v4 entry event for
   `EN_HiGoalsProgressCompletion_August2026`; it is listed under the new DE's name.
4. Save. Confirm the step order is still: 1 Progress + CompletionFollowUp · 2 Eligibility +
   Snapshot · 3 Flags + Announcement + Inject · 4 Progress journey · 5 LogSent ·
   6 Announcement journey.

Check: the step-4 activity shows the injection DE name.

## Step 5. Run once and verify

Run the automation with *Run Once* before 10 PM Pacific (the snapshot stamps the server
date, which is Central time).

1. `EN_HiGoalsProgress_Inject` row count is small on a weekday, about 6,100 on a Monday.
2. Journey Builder → v4 → *Entry* shows accepted contacts equal to that row count, with no
   `CurrentlyWaitingInSameInteraction` rejections.
3. Tomorrow: contacts whose goal ended today appear with `Achieved_Flag` or `Missed_Flag` = 1
   in the Progress DE **and** in the injection DE with `InjectReason` Achieved or Missed, and
   the completion triggered sends show sends for the day.

## Rollback

Re-publish v3 (it is still there) and put the old journey activity back in step 4 of the
automation. The injection query and DE can stay; nothing else reads them.

## Cadence knobs

All timing is in `08_EN_HiGoals_Progress_Inject.sql`:

- Midpoint check-in: `DATEDIFF(DAY, d.HIGoal_DFDR_Start_Date__c, GETDATE()) = 4`
- No-goal nudge: `DATENAME(WEEKDAY, GETDATE()) = 'Monday'`
- CompletedNotSet lag: two days, set in `05_RI_Transition_Flags.sql`
