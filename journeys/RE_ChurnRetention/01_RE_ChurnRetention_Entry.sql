/* Query activity: RE_ChurnRetention_Entry (automation RE_ChurnRetention, step 1)
   Target DE: RE_ChurnRetention_Entry (Overwrite). Journey entry audience.
   Runs daily 06:30. One row per PNI contact whose term ends in exactly 45 days and who either received
   a renewal offer of more than $20 or 10% (tier 1) or sits in the v3 model's top decile with an offer in
   the last 60 days (tier 2). HighCut comes from RE_ChurnRetention_Config (one row). Requires the
   Renewal_Offer__c synced DE (Marketing Cloud Connect) and the Voluntary_Churn_Risk_Score__c field.
   Arm: 50/50 random split assigned here (approved by compliance 2026-10-20), stratified by state so
   AZ and RI are balanced in both arms. HOLDOUT rows enter the journey and take the no-send path;
   they keep every servicing communication. The arm is logged in RE_ChurnRetention_History. */
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
    CASE WHEN c.Voluntary_Churn_Risk_Score__c >= cfg.HighCut THEN 'HIGH' ELSE 'OFFER' END AS Band,
    c.Voluntary_Churn_Top_Factors__c                    AS TopFactors,
    ISNULL(c.Voluntary_Churn_Reason__c, 'GENERAL')      AS ChurnReason,
    c.Voluntary_Churn_Offer_Change__c                   AS OfferChange,
    c.Voluntary_Churn_Discount_Change__c                AS DiscountChange,
    c.Voluntary_Churn_Driving_Score__c                  AS DrivingScore,
    CASE ISNULL(c.Voluntary_Churn_Reason__c, 'GENERAL')
        WHEN 'PRICE_SHOCK' THEN 'PRICE' WHEN 'LOW_SAVINGS' THEN 'PRICE'
        WHEN 'DISCOUNT_EROSION' THEN 'ENGAGE' WHEN 'NEW_CUSTOMER' THEN 'ENGAGE'
        WHEN 'DISENGAGED' THEN 'ENGAGE' ELSE 'DEFAULT'
    END                                                 AS Track,
    CAST(c.Current_Term_Expiration_Date__c AS DATE)     AS TermEndAtEntry,
    CAST(c.Current_Term_Effective_Date__c AS DATE)      AS TermStartAtEntry,
    DATEDIFF(DAY, c.CreatedDate, GETDATE())             AS TenureDays,
    GETDATE()                                           AS EntryDate,
    CASE WHEN ROW_NUMBER() OVER (PARTITION BY c.MailingState ORDER BY NEWID()) % 2 = 0
         THEN 'TREAT' ELSE 'HOLDOUT' END                 AS Arm
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
    /* entry tiers (decision 2026-10-20): tier 1 = renewal price shock from the captured offer;
       tier 2 = v3 model top decile among customers with an offer in the last 60 days.
       Renewal_Offer__c is synced from Salesforce; HighCut is the v3 top-decile cut from the latest batch. */
    AND EXISTS (
        SELECT 1 FROM ENT.Renewal_Offer__c_Salesforce ro
        WHERE ro.Account__c = c.AccountId
          AND ro.Offer_Date__c >= DATEADD(DAY, -60, GETDATE())
          AND (
                ro.Increase_Amount_Dollars__c > 20
             OR (ro.Policy_Renewal_Rate__c - ro.Increase_Amount_Dollars__c > 0
                 AND 100.0 * ro.Increase_Amount_Dollars__c / (ro.Policy_Renewal_Rate__c - ro.Increase_Amount_Dollars__c) > 10)
             OR c.Voluntary_Churn_Risk_Score__c >= cfg.HighCut
          ))
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
