-- Query activity: TR_NonPay_01272026 (automation TR_NonPaymentJourney, step 2)
-- Target DE: TR_NonpaymentJourney_AF_01262026 (Overwrite), the journey entry audience: every non-renters bill due in 5 days.
-- As live on 2026-10-16; no change made. Note: Nonpay_Cancel_Notice_Created_At__c here is an alias of Non_pay_cancel_date__c (populated for every row).

SELECT
    b.policy_number__c,
    b.Invoice_Due_Date__c,
    b.Non_pay_cancel_date__c AS Nonpay_Cancel_Notice_Created_At__c,
    b.non_pay__c,
    b.Policy_Net_Bill_Amount__c,
    b.Latest_Payment_Date__c,
    c.cohorts_l__c,
    b.Last_4_of_CC__c,
    b.Nonpay_Cleared_At__c,
    b.Customer_Number__c,
    c.Id,
    c.firstname,
    c.email,
    c.phone,
    c.MailingState,
    c.et4ae5__HasOptedOutOfMobile__c,
    c.SMS_Policy_Opt_In__c,
    c.account_id__c
FROM ENT.Bill__c_Salesforce b
INNER JOIN ENT.Contact_Salesforce c
    ON b.Customer_Number__c = c.Customer_Number__c
WHERE
    CAST(b.Invoice_Due_Date__c AS DATE) = CAST(DATEADD(day, 5, GETDATE()) AS DATE)
    AND b.policy_number__c NOT LIKE '%R'