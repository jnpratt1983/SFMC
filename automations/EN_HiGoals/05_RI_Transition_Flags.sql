/* Step 3 - RI_Transition_Flags
   Target: EN_HiGoalsProgressCompletionFollowUp_AF_07312025 (Update)
   Changes: a goal end is now detected from StartDate disappearing or changing
            (yesterday had one, today it is gone or different) and scored against
            yesterday's Goal. The old test (FinalFocusScore NULL yesterday, set today)
            only ever fired for a contact's FIRST goal, because FinalFocusScore is
            never cleared afterwards; and it needed CommittedGoal, which step 1 wipes.
            No CommittedGoal carry-over is needed any more. */
SELECT
  d.Id,
  d.Customer_Number__c,
  d.email,
  d.account_id__c,

  /* a goal ended today */
  CASE WHEN h1.StartDate IS NOT NULL
        AND (h0.StartDate IS NULL OR h0.StartDate <> h1.StartDate)
        AND h0.FinalFocusScore IS NOT NULL
        AND h0.FinalFocusScore >= h1.Goal
       THEN 1 ELSE 0 END AS Achieved_Flag,

  CASE WHEN h1.StartDate IS NOT NULL
        AND (h0.StartDate IS NULL OR h0.StartDate <> h1.StartDate)
        AND h0.FinalFocusScore IS NOT NULL
        AND h0.FinalFocusScore <  h1.Goal
       THEN 1 ELSE 0 END AS Missed_Flag,

  /* a goal started today (or replaced yesterday's) */
  CASE WHEN h0.StartDate IS NOT NULL
        AND (h1.StartDate IS NULL OR h1.StartDate <> h0.StartDate)
       THEN 1 ELSE 0 END AS NewCommit_Flag,

  /* the goal the flags were judged against (today's, or the one that just ended) */
  CASE WHEN h1.StartDate IS NOT NULL
        AND (h0.StartDate IS NULL OR h0.StartDate <> h1.StartDate)
       THEN h1.Goal ELSE h0.Goal END AS CommittedGoal,

  /* achieved two days ago and still no new goal: fires once, on day +2 */
  CASE WHEN h3.StartDate IS NOT NULL
        AND h2.StartDate IS NULL
        AND h1.StartDate IS NULL
        AND h0.StartDate IS NULL
        AND h0.FinalFocusScore IS NOT NULL
        AND h0.FinalFocusScore >= h3.Goal
       THEN 1 ELSE 0 END AS CompletedNotSet_Flag

FROM [EN_HiGoalsProgressCompletionFollowUp_AF_07312025] d
LEFT JOIN HiGoal_Snapshot_History h0
  ON h0.Id = d.Id AND h0.SnapshotDate = CONVERT(DATE, GETDATE())
LEFT JOIN HiGoal_Snapshot_History h1
  ON h1.Id = d.Id AND h1.SnapshotDate = CONVERT(DATE, DATEADD(DAY, -1, GETDATE()))
LEFT JOIN HiGoal_Snapshot_History h2
  ON h2.Id = d.Id AND h2.SnapshotDate = CONVERT(DATE, DATEADD(DAY, -2, GETDATE()))
LEFT JOIN HiGoal_Snapshot_History h3
  ON h3.Id = d.Id AND h3.SnapshotDate = CONVERT(DATE, DATEADD(DAY, -3, GETDATE()))
