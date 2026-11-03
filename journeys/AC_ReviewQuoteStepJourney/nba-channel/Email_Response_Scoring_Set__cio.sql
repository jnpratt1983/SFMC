SELECT
  ssot__Lead__dlm.ssot__Id__c AS Lead_Id__c,
  ssot__EmailEngagement__dlm.ssot__EmailDomainName__c AS Email_Domain__c,
  ssot__Lead__dlm.ssot__StateProvinceId__c AS State__c,
  ssot__Lead__dlm.Previous_Insurance__c AS Previous_Insurance__c,
  ssot__Lead__dlm.Vehicle_Make__c AS Vehicle_Make__c,
  ssot__Lead__dlm.UTM_Source__c AS UTM_Source__c,
  ssot__Lead__dlm.UTM_Medium__c AS UTM_Medium__c,
  ssot__Lead__dlm.ssot__LeadSourceId__c AS Lead_Source__c,
  ssot__Lead__dlm.Publisher__c AS Publisher__c,
  ssot__Lead__dlm.Email_Opt_Out__c AS Email_Opt_Out__c,
  CASE WHEN ssot__Lead__dlm.Declined__c = TRUE THEN 1 ELSE 0 END AS Declined__c,
  CASE WHEN ssot__Lead__dlm.Saved_Quote__c = TRUE THEN 1 ELSE 0 END AS Saved_Quote__c,
  CASE WHEN ssot__Lead__dlm.Currently_Insured_Status__c = TRUE THEN 1 ELSE 0 END AS Currently_Insured__c,
  CASE WHEN ssot__Lead__dlm.Mobile_Opt_Out__c = TRUE THEN 1 ELSE 0 END AS Mobile_Opt_Out__c,
  CASE WHEN ssot__Lead__dlm.ssot__MobileContactPhoneId__c IS NOT NULL THEN 1 ELSE 0 END AS Has_Mobile__c,
  CASE WHEN ssot__Lead__dlm.App_Downloaded__c = TRUE THEN 1 ELSE 0 END AS App_Downloaded__c,
  MAX(ssot__Lead__dlm.ssot__CreatedDate__c) AS Lead_Created__c,
  MAX(HOUR(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Hour__c,
  MAX(DAYOFWEEK(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Day_Of_Week__c,
  MAX(MONTH(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Created_Month__c,
  MAX(ssot__Lead__dlm.Max_Quote_Step__c) AS Max_Quote_Step__c,
  MAX(ssot__Lead__dlm.Credit_Score__c) AS Credit_Score__c,
  MAX(DATEDIFF(NOW(), ssot__Lead__dlm.ssot__CreatedDate__c)) AS Days_Since_Create__c,
  COUNT(ssot__EmailEngagement__dlm.ssot__Id__c) AS Emails_So_Far__c,
  SUM(CASE WHEN ssot__EmailEngagement__dlm.Opened__c = TRUE THEN 1 ELSE 0 END) AS Opens_So_Far__c
FROM ssot__Lead__dlm
LEFT JOIN ssot__EmailEngagement__dlm ON (ssot__EmailEngagement__dlm.ssot__LeadlId__c = ssot__Lead__dlm.ssot__Id__c AND ssot__EmailEngagement__dlm.ssot__EmailName__c LIKE 'AC_%')
WHERE DATEDIFF(NOW(), ssot__Lead__dlm.ssot__CreatedDate__c) <= 14
  AND (ssot__Lead__dlm.Internal_Traffic__c IS NULL OR ssot__Lead__dlm.Internal_Traffic__c = FALSE)
GROUP BY Lead_Id__c, Email_Domain__c, State__c, Previous_Insurance__c, Vehicle_Make__c, UTM_Source__c, UTM_Medium__c, Lead_Source__c, Publisher__c, Email_Opt_Out__c, Declined__c, Saved_Quote__c, Currently_Insured__c, Mobile_Opt_Out__c, Has_Mobile__c, App_Downloaded__c
