# EN_HiGoals automation - updated query activities (2026-10-07)

Paste each file's SQL into the matching Query Activity in Automation Studio (business unit
"B2C Lifecycle Marketing", automation EN_HiGoals). Target DE and update type stay as they are.

| Step | Query activity | File | Change |
|---|---|---|---|
| 1 | EN_HiGoals_Progress | 01 | cohort join removed; higoal_rewards_total__c added |
| 1 | EN_HiGoals_CompletionFollowUp | 02 | cohort join removed; impossible WHERE fixed (draft journey) |
| 2 | RI_Eligibility_Daily | 03 | unchanged |
| 2 | RI_Snapshot_Daily | 04 | scoped to the Progress DE |
| 3 | RI_Transition_Flags | 05 | goal end detected from StartDate, scored against yesterday's Goal |
| 3 | EN_HiGoals_Announcement_v2 | 06 | cohort join removed |
| 5 | RI_Announcement_LogSent | 07 | unchanged |

Audience after the change: every contact with an email and no Cancel_Date__c
(6,311 in Salesforce on 2026-10-07: AZ 5,286 / RI 1,007 / other 18) instead of the 2,246
in the stale Amplitude cohort HiGoals-Cohort_upwhwshj.
