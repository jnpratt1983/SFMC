/* Step 1 - EN_HiGoals_Progress
   Target: EN_HiGoalsProgressCompletionFollowUp_AF_07312025 (Overwrite)
   Changes (2026-10-07 b): null Customer_Number__c / account_id__c excluded (fixes "Cannot insert a NULL value into a non-nullable column").
   Changes: cohort join removed (HiGoals is open to everyone);
            higoal_rewards_total__c added so the "$50 reward" split can evaluate. */
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
    a.HIGoal_DFDR_Goal__c,
    a.higoal_rewards_total__c
FROM ENT.Contact_Salesforce a
WHERE a.email IS NOT NULL
  AND a.Cancel_Date__c IS NULL
  AND a.Customer_Number__c IS NOT NULL   /* primary key on the target DE; 42 active contacts lack it */
  AND a.account_id__c IS NOT NULL        /* subscriber key for sends and journey entry; 143 lack it */
