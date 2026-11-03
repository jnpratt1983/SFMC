SELECT
  ssot__Lead__dlm.ssot__Id__c AS Lead_Id__c,
  ssot__Lead__dlm.NBA_Test_Arm__c AS Test_Arm__c,
  ssot__Lead__dlm.NBA_Assignment__c AS Assignment__c,
  CASE WHEN ssot__Lead__dlm.NBA_Test_Arm__c IN ('CALL_SMS', 'CALL') THEN 1 ELSE 0 END AS Call_Arm__c,
  CASE WHEN ssot__Lead__dlm.NBA_Test_Arm__c IN ('CALL_SMS', 'SMS') THEN 1 ELSE 0 END AS SMS_Arm__c,
  ssot__Lead__dlm.ssot__StateProvinceId__c AS State__c,
  ssot__Lead__dlm.Previous_Insurance__c AS Previous_Insurance__c,
  ssot__Lead__dlm.Vehicle_Make__c AS Vehicle_Make__c,
  ssot__Lead__dlm.UTM_Source__c AS UTM_Source__c,
  ssot__Lead__dlm.UTM_Medium__c AS UTM_Medium__c,
  ssot__Lead__dlm.ssot__LeadSourceId__c AS Lead_Source__c,
  ssot__Lead__dlm.Publisher__c AS Publisher__c,
  CASE WHEN ssot__Lead__dlm.Declined__c = TRUE THEN 1 ELSE 0 END AS Declined__c,
  CASE WHEN ssot__Lead__dlm.Saved_Quote__c = TRUE THEN 1 ELSE 0 END AS Saved_Quote__c,
  CASE WHEN ssot__Lead__dlm.Currently_Insured_Status__c = TRUE THEN 1 ELSE 0 END AS Currently_Insured__c,
  CASE WHEN ssot__Lead__dlm.App_Downloaded__c = TRUE THEN 1 ELSE 0 END AS App_Downloaded__c,
  CASE WHEN ssot__Lead__dlm.Purchased__c = TRUE THEN 1 ELSE 0 END AS Purchased__c,
  MAX(ssot__Lead__dlm.NBA_Entry_At__c) AS Entry_At__c,
  MAX(ssot__Lead__dlm.ssot__CreatedDate__c) AS Lead_Created__c,
  MAX(DATEDIFF(ssot__Lead__dlm.NBA_Entry_At__c, ssot__Lead__dlm.ssot__CreatedDate__c)) AS Days_Create_To_Entry__c,
  MAX(ssot__Lead__dlm.NBA_Entry_Email_Model_Score__c) AS Entry_Email_Model_Score__c,
  MAX(ssot__Lead__dlm.NBA_Entry_Call_Score__c) AS Entry_Call_Score__c,
  MAX(ssot__Lead__dlm.NBA_Entry_Email_Score__c) AS Entry_Email_Score__c,
  MAX(ssot__Lead__dlm.NBA_Entry_SMS_Score__c) AS Entry_SMS_Score__c,
  MAX(ssot__Lead__dlm.Max_Quote_Step__c) AS Max_Quote_Step__c,
  MAX(ssot__Lead__dlm.Credit_Score__c) AS Credit_Score__c,
  SUM(CASE WHEN ssot__EmailEngagement__dlm.ssot__EmailName__c LIKE 'AC_Review%' AND ssot__EmailEngagement__dlm.Opened__c = TRUE THEN 1 ELSE 0 END) AS Review_Emails_Opened__c,
  SUM(CASE WHEN ssot__EmailEngagement__dlm.ssot__EmailName__c LIKE 'AC_Review%' THEN 1 ELSE 0 END) AS Review_Emails_Sent__c,
  COUNT(ssot__Lead__dlm.ssot__Id__c) AS Row_Count__c
FROM ssot__Lead__dlm
LEFT JOIN ssot__EmailEngagement__dlm ON (ssot__EmailEngagement__dlm.ssot__LeadlId__c = ssot__Lead__dlm.ssot__Id__c AND ssot__EmailEngagement__dlm.ssot__SentDateTm__c >= ssot__Lead__dlm.NBA_Entry_At__c)
WHERE ssot__Lead__dlm.NBA_Test_Arm__c IN ('CALL_SMS', 'CALL', 'SMS')
  AND ssot__Lead__dlm.NBA_Assignment__c = 'RANDOM'
  AND DATEDIFF(NOW(), ssot__Lead__dlm.NBA_Entry_At__c) >= 30
GROUP BY Lead_Id__c, Test_Arm__c, Assignment__c, Call_Arm__c, SMS_Arm__c, State__c, Previous_Insurance__c, Vehicle_Make__c, UTM_Source__c, UTM_Medium__c, Lead_Source__c, Publisher__c, Declined__c, Saved_Quote__c, Currently_Insured__c, App_Downloaded__c, Purchased__c
