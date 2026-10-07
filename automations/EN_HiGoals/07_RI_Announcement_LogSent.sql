/* Step 5 - RI_Announcement_LogSent  (UNCHANGED - shown for completeness)
   Target: RI_Announcement_SendLog (Update)
   Note: this logs every IsRIEligible row, not actual sends. */
SELECT
    d.account_id__c AS ContactKey,
    CONVERT(DATE, GETDATE()) AS SentDate
FROM [EN_HiGoalsAnnoucement_AFAMP_07312025] d
WHERE d.IsRIEligible = 1
