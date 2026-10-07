/* Step 2 - RI_Snapshot_Daily
   Target: HiGoal_Snapshot_History (Update; PK Id + SnapshotDate)
   Changes: scoped to the contacts in the Progress DE (the actual HiGoals audience)
            instead of every RI/AZ contact ever synced. Cuts ~93k rows/day to ~6.3k.
            Runs after step 1, so the Progress DE is already today's audience. */
SELECT
  c.Id,
  CONVERT(DATE, GETDATE())           AS SnapshotDate,
  c.HIGoal_DFDR_Start_Date__c        AS StartDate,
  c.HIGoal_DFDR_Goal__c              AS Goal,
  c.HIGoal_DFDR_Final_Focus_Score__c AS FinalFocusScore
FROM ent.Contact_Salesforce c
JOIN [EN_HiGoalsProgressCompletionFollowUp_AF_07312025] d ON d.Id = c.Id
