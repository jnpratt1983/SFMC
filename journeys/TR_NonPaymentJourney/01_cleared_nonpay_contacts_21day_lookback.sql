-- Query activity: cleared_nonpay_contacts_21day_lookback (automation TR_NonPaymentJourney, step 1)
-- Target DE: NonPay_Paid (Overwrite). Journey exit criterion reads this DE: Email is not null OR Id is not null.
-- As live on 2026-10-16; no change made. Note: matches any bill in the 21-day window paid on/after its due date, or any contact with a Cancel_date__c.

SELECT c.Id, c.SMS_Policy_Opt_In__c, c.Phone, c.email,
       b.non_pay__c, b.Nonpay_Cleared_At__c, b.Nonpay_Cancel_Notice_Created_At__c,
       b.Latest_Payment_Date__c, c.Cancel_date__c,
       b.Total_Payment_Amount__c, b.Invoice_Due_Date__c,
       b.policy_number__c
FROM ent.Contact_Salesforce c
INNER JOIN ent.Bill__c_Salesforce b
    ON c.Customer_Number__c = b.Customer_Number__c
WHERE b.Invoice_Due_Date__c >= DATEADD(day, -21, CAST(GETDATE() AS DATE))
    AND b.policy_number__c NOT LIKE '%R'
    AND (
        (b.Total_Payment_Amount__c > 0
            AND b.Latest_Payment_Date__c >= b.Invoice_Due_Date__c)
        OR b.Nonpay_Cleared_At__c IS NOT NULL
        OR c.Cancel_date__c IS NOT NULL
    )