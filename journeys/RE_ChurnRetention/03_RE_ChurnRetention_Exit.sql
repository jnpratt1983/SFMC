/* Query activity: RE_ChurnRetention_Exit (automation RE_ChurnRetention, step 3)
   Target DE: RE_ChurnRetention_Exit (Overwrite). Journey exit criteria = "contact is in this DE".
   Evaluated against everyone entered in the last 75 days. ExitReason drives the thank-you
   journey (RENEWED) and reporting. Keyed on Id. */
SELECT
    h.Id,
    h.TermEndAtEntry,
    CASE
        WHEN c.Cancel_Date__c IS NOT NULL
          OR ISNULL(c.canceled__c, 'false') IN ('true', '1', 'Yes', 'Y')                     THEN 'CANCELLED'
        WHEN ISNULL(c.Pending_Cancel_Flag__c, 'false') IN ('true', '1', 'Yes', 'Y')          THEN 'PENDING_CANCEL'
        WHEN EXISTS (SELECT 1 FROM ENT.Bill__c_Salesforce b
                     WHERE b.Customer_Number__c = c.Customer_Number__c
                       AND b.non_pay__c IN ('true', '1', 'True')
                       AND b.Invoice_Date__c > h.EntryDate)                                    THEN 'NONPAY'
        WHEN CAST(c.Current_Term_Effective_Date__c AS DATE) >= h.TermEndAtEntry                THEN 'RENEWED'
    END                                                 AS ExitReason,
    GETDATE()                                           AS ExitDate
FROM [RE_ChurnRetention_History] h
JOIN ENT.Contact_Salesforce c ON c.Id = h.Id
WHERE h.EntryDate >= DATEADD(DAY, -75, GETDATE())
  AND (
        c.Cancel_Date__c IS NOT NULL
     OR ISNULL(c.canceled__c, 'false') IN ('true', '1', 'Yes', 'Y')
     OR ISNULL(c.Pending_Cancel_Flag__c, 'false') IN ('true', '1', 'Yes', 'Y')
     OR EXISTS (SELECT 1 FROM ENT.Bill__c_Salesforce b
                WHERE b.Customer_Number__c = c.Customer_Number__c
                  AND b.non_pay__c IN ('true', '1', 'True')
                  AND b.Invoice_Date__c > h.EntryDate)
     OR CAST(c.Current_Term_Effective_Date__c AS DATE) >= h.TermEndAtEntry
      )
