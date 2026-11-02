/*
 Channel_Uplift_Training_Set__cio -- training rows from the 2x2 factorial channel test.
 Built 2026-11-02 as a spec; it depends on the new Lead fields written by the test journey:
   NBA_Test_Arm__c          'CALL_SMS' | 'CALL' | 'SMS' | 'EMAIL'   (set by the routing log sync)
   NBA_Entry_At__c          journey entry timestamp
   NBA_Entry_Call_Score__c, NBA_Entry_Email_Score__c, NBA_Entry_SMS_Score__c  (legacy scores at entry,
                            kept only to test the old model's interaction; drop once retired)
 Those fields must be added to the CRM connector so they appear on ssot__Lead__dlm (names below assume
 the connector keeps the API name).

 One row per test lead whose 30-day window is in the past. Label Purchased_30d__c.
 Train four Model Builder binary models on filtered copies of this insight (T-learner):
   Purchase_Given_Call     : rows WHERE Call_Arm__c = TRUE
   Purchase_Given_NoCall   : rows WHERE Call_Arm__c = FALSE
   Purchase_Given_SMS      : rows WHERE SMS_Arm__c = TRUE
   Purchase_Given_NoSMS    : rows WHERE SMS_Arm__c = FALSE
 Score all leads with all four; Call_Uplift = P(call) - P(no call), SMS_Uplift = P(sms) - P(no sms).
 Exclude Call_Arm__c / SMS_Arm__c themselves from the features of each model (they are constant per model).
*/
SELECT
  l.ssot__Id__c                                  AS Lead_Id__c,
  l.NBA_Test_Arm__c                              AS Test_Arm__c,
  CASE WHEN l.NBA_Test_Arm__c IN ('CALL_SMS','CALL') THEN TRUE ELSE FALSE END AS Call_Arm__c,
  CASE WHEN l.NBA_Test_Arm__c IN ('CALL_SMS','SMS')  THEN TRUE ELSE FALSE END AS SMS_Arm__c,
  l.NBA_Entry_At__c                              AS Entry_At__c,
  HOUR(l.NBA_Entry_At__c)                        AS Entry_Hour__c,
  DAYOFWEEK(l.NBA_Entry_At__c)                   AS Entry_Day_Of_Week__c,
  DATEDIFF(l.NBA_Entry_At__c, l.ssot__CreatedDate__c) AS Days_Create_To_Entry__c,
  l.NBA_Entry_Call_Score__c                      AS Legacy_Call_Score__c,
  l.NBA_Entry_Email_Score__c                     AS Legacy_Email_Score__c,
  l.NBA_Entry_SMS_Score__c                       AS Legacy_SMS_Score__c,
  l.Max_Quote_Step__c                            AS Max_Quote_Step__c,
  l.Declined__c                                  AS Declined__c,
  l.Saved_Quote__c                               AS Saved_Quote__c,
  l.ssot__StateProvinceId__c                     AS State__c,
  l.Previous_Insurance__c                        AS Previous_Insurance__c,
  l.Currently_Insured_Status__c                  AS Currently_Insured_Status__c,
  l.Vehicle_Make__c                              AS Vehicle_Make__c,
  l.UTM_Source__c                                AS UTM_Source__c,
  l.UTM_Medium__c                                AS UTM_Medium__c,
  l.ssot__LeadSourceId__c                        AS Lead_Source__c,
  l.Publisher__c                                 AS Publisher__c,
  l.Credit_Score__c                              AS Credit_Score__c,
  l.App_Downloaded__c                            AS App_Downloaded__c,
  MONTH(l.NBA_Entry_At__c)                       AS Entry_Month__c,
  -- opened the first test email within 3 days of entry (observed response, allowed: it is after entry but before most purchases; drop if it leaks)
  MAX(CASE WHEN e.Opened__c AND DATEDIFF(e.ssot__SentDateTm__c, l.NBA_Entry_At__c) BETWEEN 0 AND 3 THEN TRUE ELSE FALSE END) AS Opened_First_Email__c,
  MAX(CASE WHEN l.Purchased__c = TRUE AND DATEDIFF(l.Purchased_Date__c, l.NBA_Entry_At__c) BETWEEN -1 AND 30 THEN TRUE ELSE FALSE END) AS Purchased_30d__c
FROM ssot__Lead__dlm l
LEFT JOIN ssot__EmailEngagement__dlm e ON e.ssot__LeadlId__c = l.ssot__Id__c AND e.ssot__EmailName__c LIKE 'AC_Review%'
WHERE l.NBA_Test_Arm__c IS NOT NULL
  AND DATEDIFF(NOW(), l.NBA_Entry_At__c) >= 31
GROUP BY l.ssot__Id__c, l.NBA_Test_Arm__c, l.NBA_Entry_At__c, l.ssot__CreatedDate__c, l.NBA_Entry_Call_Score__c,
         l.NBA_Entry_Email_Score__c, l.NBA_Entry_SMS_Score__c, l.Max_Quote_Step__c, l.Declined__c, l.Saved_Quote__c,
         l.ssot__StateProvinceId__c, l.Previous_Insurance__c, l.Currently_Insured_Status__c, l.Vehicle_Make__c,
         l.UTM_Source__c, l.UTM_Medium__c, l.ssot__LeadSourceId__c, l.Publisher__c, l.Credit_Score__c, l.App_Downloaded__c
