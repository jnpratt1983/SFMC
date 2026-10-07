/* Step 3 (new, runs after RI_Transition_Flags) - EN_HiGoals_Progress_Inject
   Target: EN_HiGoalsProgress_Inject (Overwrite)  -- new sendable DE, see de/EN_HiGoalsProgress_Inject.md
   Purpose: the progress journey is injected from THIS DE instead of the full Progress DE.
            Only contacts with a reason to be messaged today are selected, so the journey
            needs no waits and nobody is ever rejected for sitting in one.
   Reasons (first match wins, in this order):
     Achieved        goal ended today, final score >= goal
     Missed          goal ended today, final score <  goal
     CompletedNotSet goal achieved two days ago and still no new goal
     Midpoint        active goal, day 4 since start (replaces the "4 days after start" waits;
                     the halfway / off-track splits evaluate on this day)
     NoGoalWeekly    no active goal, Mondays only (replaces the 7-day "No Goal Set" wait)
   Cadence lives here now; change the day-4 or Monday rules to change it. */
SELECT
    d.account_id__c,
    d.Added_Driver__c,
    d.App_Opened__c,
    d.Birthday_Month__c,
    d.Cancel_Date__c,
    d.MailingCity,
    d.CookieID__c,
    d.Created_Account__c,
    d.Customer_Number__c,
    d.Distracted_Driving__c,
    d.DNR_Flag__c,
    d.Driver_Role__c,
    d.driving_patterns__c,
    d.email,
    d.FirstName,
    d.Future_Flag__c,
    d.Inception_transaction_date__c,
    d.inception_transaction_timestamps_user__c,
    d.inception_transaction_timestamps_utc__c,
    d.Jurisdiction__c,
    d.Last_Known_Trip_Date__c,
    d.LastName,
    d.Lifetime_Savings__c,
    d.Logged_Trip__c,
    d.OS_Version__c,
    d.Pending_Cancel_Flag__c,
    d.Phone,
    d.Phone_Model__c,
    d.platform__c,
    d.Policy_Effective_Date__c,
    d.Policy_Number__c,
    d.MailingPostalcode,
    d.Property_Ownership_Status__c,
    d.Has_Renters__c,
    d.safe_speeds__c,
    d.smooth_driving__c,
    d.et4ae5__HasOptedOutOfMobile__c,
    d.MailingState,
    d.telematic_discount__c,
    d.upcoming_billing_date__c,
    d.Vehicle_Make__c,
    d.Vehicle_Model__c,
    d.Id,
    d.HIGoal_DFDR_Final_Focus_Score__c,
    d.HIGoal_DFDR_Completed__c,
    d.HIGoal_DFDR_Completion_Percentage__c,
    d.HIGoal_DFDR_Focus_Score__c,
    d.HIGoal_DFDR_Start_Date__c,
    d.HIGoal_DFDR_Goal__c,
    d.higoal_rewards_total__c,
    d.IsRIEligible,
    d.WeeksSinceInception,
    d.Achieved_Flag,
    d.Missed_Flag,
    d.CompletedNotSet_Flag,
    d.NewCommit_Flag,
    d.CommittedGoal,
    CASE
      WHEN d.Achieved_Flag = 1        THEN 'Achieved'
      WHEN d.Missed_Flag = 1          THEN 'Missed'
      WHEN d.CompletedNotSet_Flag = 1 THEN 'CompletedNotSet'
      WHEN d.HIGoal_DFDR_Start_Date__c IS NOT NULL
       AND DATEDIFF(DAY, d.HIGoal_DFDR_Start_Date__c, GETDATE()) = 4
                                      THEN 'Midpoint'
      WHEN d.HIGoal_DFDR_Start_Date__c IS NULL
       AND DATENAME(WEEKDAY, GETDATE()) = 'Monday'
                                      THEN 'NoGoalWeekly'
    END AS InjectReason,
    CONVERT(DATE, GETDATE()) AS InjectDate
FROM [EN_HiGoalsProgressCompletionFollowUp_AF_07312025] d
WHERE d.Achieved_Flag = 1
   OR d.Missed_Flag = 1
   OR d.CompletedNotSet_Flag = 1
   OR (d.HIGoal_DFDR_Start_Date__c IS NOT NULL
       AND DATEDIFF(DAY, d.HIGoal_DFDR_Start_Date__c, GETDATE()) = 4)
   OR (d.HIGoal_DFDR_Start_Date__c IS NULL
       AND DATENAME(WEEKDAY, GETDATE()) = 'Monday')
