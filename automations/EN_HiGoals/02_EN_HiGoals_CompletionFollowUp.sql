/* Step 1 - EN_HiGoals_CompletionFollowUp
   Target: EN_HiGoalsCompletionFollowUp_AF_07312025 (Overwrite)
   Feeds the still-unpublished EN_HiGoalsCompletionFollowUp_August2026 draft.
   Changes: cohort join removed. The old WHERE required HIGoal_DFDR_Goal__c to be
            both NOT NULL and NULL, so it could never match; the goal that just ended
            is now read from HiGoal_Snapshot_History (Goal/StartDate are cleared in
            Salesforce on the day a goal ends). */
SELECT
    a.account_id__c,
    a.Added_Driver__c,
    a.App_Opened__c,
    a.Birthday_Month__c,
    a.Cancel_Date__c,
    a.MailingCity,
    a.CookieID__c,
    a.Created_Account__c,
    a.Customer_Number__c,
    a.Distracted_Driving__c,
    a.DNR_Flag__c,
    a.Driver_Role__c,
    a.driving_patterns__c,
    a.email,
    a.FirstName,
    a.Future_Flag__c,
    a.Inception_transaction_date__c,
    a.inception_transaction_timestamps_user__c,
    a.inception_transaction_timestamps_utc__c,
    a.Jurisdiction__c,
    a.Last_Known_Trip_Date__c,
    a.LastName,
    a.Lifetime_Savings__c,
    a.Logged_Trip__c,
    a.OS_Version__c,
    a.Pending_Cancel_Flag__c,
    a.Phone,
    a.Phone_Model__c,
    a.platform__c,
    a.Policy_Effective_Date__c,
    a.Policy_Number__c,
    a.MailingPostalcode,
    a.Property_Ownership_Status__c,
    a.Has_Renters__c,
    a.safe_speeds__c,
    a.smooth_driving__c,
    a.et4ae5__HasOptedOutOfMobile__c,
    a.MailingState,
    a.telematic_discount__c,
    a.upcoming_billing_date__c,
    a.Vehicle_Make__c,
    a.Vehicle_Model__c,
    a.Id,
    a.HIGoal_DFDR_Final_Focus_Score__c,
    a.HIGoal_DFDR_Completed__c,
    a.HIGoal_DFDR_Completion_Percentage__c,
    a.HIGoal_DFDR_Focus_Score__c,
    a.HIGoal_DFDR_Start_Date__c,
    a.HIGoal_DFDR_Goal__c
FROM ENT.Contact_Salesforce a
JOIN (
    SELECT h.Id, h.StartDate, h.Goal,
           ROW_NUMBER() OVER (PARTITION BY h.Id ORDER BY h.SnapshotDate DESC) AS rn
    FROM HiGoal_Snapshot_History h
    WHERE h.StartDate IS NOT NULL
) lg ON lg.Id = a.Id AND lg.rn = 1
WHERE a.email IS NOT NULL
  AND a.Cancel_Date__c IS NULL
  AND a.HIGoal_DFDR_Start_Date__c IS NULL                      /* no new goal set */
  AND GETDATE() >= DATEADD(day, 8, lg.StartDate)
  AND GETDATE() <  DATEADD(day, 9, lg.StartDate)
  AND (
        (a.HIGoal_DFDR_Final_Focus_Score__c IS NOT NULL
         AND a.HIGoal_DFDR_Final_Focus_Score__c >= lg.Goal)
        OR ISNULL(a.HIGoal_DFDR_Completion_Percentage__c, 0) >= 100
      )
