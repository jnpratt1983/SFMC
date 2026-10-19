/* Query activity: RE_ChurnRetention_Entry (automation RE_ChurnRetention, step 1)
   Target DE: RE_ChurnRetention_Entry (Overwrite). Journey entry audience.
   Runs daily 06:30. One row per PNI contact whose term ends in exactly 45 days and who the
   voluntary-churn model flags. Band cut points come from RE_ChurnRetention_Config (one row). */
SELECT
    c.Id,
    c.Customer_Number__c,
    c.account_id__c,
    c.FirstName,
    c.Email,
    c.Phone,
    c.MailingState,
    c.HasOptedOutOfEmail,
    c.et4ae5__HasOptedOutOfMobile__c,
    c.SMS_Policy_Opt_In__c,
    c.Voluntary_Churn_Risk_Score__c                     AS Score,
    CASE WHEN c.Voluntary_Churn_Risk_Score__c >= cfg.HighCut THEN 'HIGH' ELSE 'MODERATE' END AS Band,
    c.Voluntary_Churn_Top_Factors__c                    AS TopFactors,
    CASE
        WHEN c.Voluntary_Churn_Top_Factors__c LIKE '%Ticket%'  OR c.Voluntary_Churn_Top_Factors__c LIKE '%Support%'  THEN 'SERVICE'
        WHEN c.Voluntary_Churn_Top_Factors__c LIKE '%Renewal%' OR c.Voluntary_Churn_Top_Factors__c LIKE '%Savings%'
          OR c.Voluntary_Churn_Top_Factors__c LIKE '%Discount%' OR c.Voluntary_Churn_Top_Factors__c LIKE '%Premium%'  THEN 'PRICE'
        WHEN c.Voluntary_Churn_Top_Factors__c LIKE '%App%'     OR c.Voluntary_Churn_Top_Factors__c LIKE '%Trip%'
          OR c.Voluntary_Churn_Top_Factors__c LIKE '%Driving%' THEN 'ENGAGE'
        ELSE 'DEFAULT'
    END                                                 AS Track,
    CAST(c.Current_Term_Expiration_Date__c AS DATE)     AS TermEndAtEntry,
    CAST(c.Current_Term_Effective_Date__c AS DATE)      AS TermStartAtEntry,
    DATEDIFF(DAY, c.CreatedDate, GETDATE())             AS TenureDays,
    GETDATE()                                           AS EntryDate
FROM ENT.Contact_Salesforce c
CROSS JOIN [RE_ChurnRetention_Config] cfg
WHERE
    c.Driver_Role__c = 'PNI'
    AND c.MailingState IN ('AZ', 'RI')
    AND ISNULL(c.canceled__c, 'false') NOT IN ('true', '1', 'Yes', 'Y')
    AND c.Cancel_Date__c IS NULL
    AND ISNULL(c.Pending_Cancel_Flag__c, 'false') NOT IN ('true', '1', 'Yes', 'Y')
    AND ISNULL(c.DNR_Flag__c, '') NOT IN ('true', '1', 'Yes', 'Y')
    AND CAST(c.Current_Term_Expiration_Date__c AS DATE) = CAST(DATEADD(DAY, 45, GETDATE()) AS DATE)
    AND c.Voluntary_Churn_Risk_Score__c IS NOT NULL
    AND (
            c.Voluntary_Churn_Risk_Score__c >= cfg.HighCut
         OR (c.Voluntary_Churn_Risk_Score__c >= cfg.ModerateCut AND DATEDIFF(DAY, c.CreatedDate, GETDATE()) < 365)
        )
    /* non-pay exclusions: any notice in the last 90 days, on Contact or on any bill */
    AND (c.Nonpay_Cancel_Notice_Created_At__c IS NULL
         OR c.Nonpay_Cancel_Notice_Created_At__c < DATEADD(DAY, -90, GETDATE()))
    AND NOT EXISTS (
        SELECT 1 FROM ENT.Bill__c_Salesforce b
        WHERE b.Customer_Number__c = c.Customer_Number__c
          AND b.Non_pay_cancel_date__c >= DATEADD(DAY, -90, GETDATE()))
    AND NOT EXISTS (
        SELECT 1 FROM [TR_NonpaymentJourney_AF_01262026] np WHERE np.Id = c.Id)
    /* one entry per term */
    AND NOT EXISTS (
        SELECT 1 FROM [RE_ChurnRetention_History] h
        WHERE h.Id = c.Id
          AND h.TermEndAtEntry = CAST(c.Current_Term_Expiration_Date__c AS DATE))
    /* must be reachable on at least one channel */
    AND (ISNULL(c.HasOptedOutOfEmail, 'false') NOT IN ('true', '1')
         OR (ISNULL(c.et4ae5__HasOptedOutOfMobile__c, 'false') NOT IN ('true', '1') AND c.SMS_Policy_Opt_In__c IN ('true', '1', 'Yes', 'Y')))
