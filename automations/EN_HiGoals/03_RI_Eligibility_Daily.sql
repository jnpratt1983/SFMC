/* Step 2 - RI_Eligibility_Daily  (UNCHANGED - shown for completeness)
   Target: EN_HiGoalsProgressCompletionFollowUp_AF_07312025 (Update) */
SELECT
  d.Id,
  d.Customer_Number__c,
  d.email,
  d.account_id__c,
  FLOOR(DATEDIFF(DAY, c.Policy_Effective_Date__c, GETDATE()) / 7) + 1 AS WeeksSinceInception,
  CASE WHEN c.MailingState = 'RI'
        AND c.Driver_Role__c = 'PNI'
        AND FLOOR(DATEDIFF(DAY, c.Policy_Effective_Date__c, GETDATE())/7)+1 >= 5
        AND ISNULL(c.higoal_rewards_total__c, 0) < 50
       THEN 1 ELSE 0 END AS IsRIEligible
FROM [EN_HiGoalsProgressCompletionFollowUp_AF_07312025] d
JOIN ent.Contact_Salesforce c ON c.Id = d.Id
