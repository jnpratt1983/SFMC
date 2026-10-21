/* Query activity: RE_ChurnRetention_Entry_AF_10202026 (automation RE_ChurnRetention, step 1)
   Target DE: RE_ChurnRetention_Entry_AF_10202026 (Overwrite). Journey entry audience.
   v2 2026-10-21. Runs daily 10:00, after Master Customer Journey Daily Sends (09:00).
   One row per PNI contact whose term ends in exactly 27 days and who either received a new-term offer of
   more than $20 or 10% (tier 1, Band OFFER) or sits at or above the v3 top-decile cut (tier 2, Band HIGH).
   The offer is issued at R-32 and the existing Heads Up email lands by R-29, so entry at R-27 is always
   after both. HighCut comes from RE_ChurnRetention_Config_AF_10202026 (one row).
   Channels: email and app push only. No SMS columns are used.
   Arm: 50/50 random split assigned here (approved by compliance 2026-10-20), stratified by state.
   HOLDOUT rows enter the journey and take the no-send path; they keep every existing communication.
   New in v2: RatingVersion (from the latest offer) and LifetimeSavings (Contact). Both DEs need the columns. */
SELECT
    c.Id,
    c.Customer_Number__c,
    c.account_id__c,
    c.FirstName,
    c.Email,
    c.MailingState,
    c.HasOptedOutOfEmail,
    c.app_opened__c                                     AS AppOpened,
    c.Voluntary_Churn_Risk_Score__c                     AS Score,
    CASE WHEN c.Voluntary_Churn_Risk_Score__c >= cfg.HighCut THEN 'HIGH' ELSE 'OFFER' END AS Band,
    ISNULL(c.Voluntary_Churn_Reason__c, 'GENERAL')      AS ChurnReason,
    c.Voluntary_Churn_Offer_Change__c                   AS OfferChange,      /* reporting only, never rendered */
    c.Voluntary_Churn_Discount_Change__c                AS DiscountChange,
    c.Voluntary_Churn_Driving_Score__c                  AS DrivingScore,
    CONVERT(DECIMAL(10, 2), c.Lifetime_Savings__c)      AS LifetimeSavings,
    ro.Rating_Version__c                                AS RatingVersion,
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
CROSS JOIN [RE_ChurnRetention_Config_AF_10202026] cfg
/* latest captured offer for this account; the offer is issued at R-32 */
OUTER APPLY (
    SELECT TOP 1 o.Rating_Version__c, o.Increase_Amount_Dollars__c, o.Policy_Renewal_Rate__c, o.Offer_Date__c
    FROM ENT.Renewal_Offer__c_Salesforce o
    WHERE o.Account__c = c.AccountId
      AND o.Offer_Date__c >= DATEADD(DAY, -60, GETDATE())
    ORDER BY o.Offer_Date__c DESC) ro
WHERE
    c.Driver_Role__c = 'PNI'
    AND c.MailingState IN ('AZ', 'RI')
    AND ISNULL(c.canceled__c, 'false') NOT IN ('true', '1', 'Yes', 'Y')
    AND c.Cancel_Date__c IS NULL
    AND ISNULL(c.Pending_Cancel_Flag__c, 'false') NOT IN ('true', '1', 'Yes', 'Y')
    AND ISNULL(c.DNR_Flag__c, '') NOT IN ('true', '1', 'Yes', 'Y')
    AND CAST(c.Current_Term_Expiration_Date__c AS DATE) = CAST(DATEADD(DAY, 27, GETDATE()) AS DATE)
    /* entry tiers (decision 2026-10-20): tier 1 = new-term price change from the captured offer;
       tier 2 = v3 model top decile. HighCut is the v3 top-decile cut from the latest batch. */
    AND (
            ro.Increase_Amount_Dollars__c > 20
         OR (ro.Policy_Renewal_Rate__c - ro.Increase_Amount_Dollars__c > 0
             AND 100.0 * ro.Increase_Amount_Dollars__c / (ro.Policy_Renewal_Rate__c - ro.Increase_Amount_Dollars__c) > 10)
         OR c.Voluntary_Churn_Risk_Score__c >= cfg.HighCut
        )
    /* non-pay exclusion: a bill flagged non-pay (the real notice) invoiced in the last 90 days.
       Non_pay_cancel_date__c is populated on every bill and is NOT a notice; do not use it here. */
    AND NOT EXISTS (
        SELECT 1 FROM ENT.Bill__c_Salesforce b
        WHERE b.Customer_Number__c = c.Customer_Number__c
          AND b.non_pay__c IN ('true', '1', 'True')
          AND b.Invoice_Date__c >= DATEADD(DAY, -90, GETDATE()))
    AND NOT EXISTS (
        SELECT 1 FROM [TR_NonpaymentJourney_AF_01262026] np WHERE np.Id = c.Id)
    /* one entry per term */
    AND NOT EXISTS (
        SELECT 1 FROM [RE_ChurnRetention_History_AF_10202026] h
        WHERE h.Id = c.Id
          AND h.TermEndAtEntry = CAST(c.Current_Term_Expiration_Date__c AS DATE))
    /* safety check: no Rate Increase (Heads Up) send in the last 48 hours */
    AND NOT EXISTS (
        SELECT 1 FROM _Sent s
        JOIN _Job j ON j.JobID = s.JobID
        WHERE s.SubscriberKey = c.Id
          AND j.EmailName LIKE 'RE_%RateIncreaseRenewal%'
          AND s.EventDate >= DATEADD(HOUR, -48, GETDATE()))
    /* must be reachable on email or app push */
    AND (ISNULL(c.HasOptedOutOfEmail, 'false') NOT IN ('true', '1')
         OR c.app_opened__c = 'true')
