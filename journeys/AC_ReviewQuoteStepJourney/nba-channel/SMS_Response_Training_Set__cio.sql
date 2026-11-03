SELECT
  ssot__MessageEngagement__dlm.Subscriber_Key__c AS Lead_Id__c,
  ssot__MessageEngagement__dlm.ssot__Name__c AS SMS_Name__c,
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
  CASE WHEN ssot__Lead__dlm.App_Downloaded__c = TRUE THEN 1 ELSE 0 END AS App_Downloaded__c,
  CASE WHEN ssot__Lead__dlm.Purchased__c = TRUE THEN 1 ELSE 0 END AS Purchased__c,
  CASE WHEN clicks.First_Click_Lead_At__c IS NOT NULL AND clicks.First_Click_Lead_At__c > ssot__MessageEngagement__dlm.Create_Date_Custom__c AND DATEDIFF(clicks.First_Click_Lead_At__c, ssot__MessageEngagement__dlm.Create_Date_Custom__c) <= 14 THEN 1 ELSE 0 END AS Clicked_14d__c,
  CASE WHEN clicks.First_Click_Lead_At__c IS NOT NULL AND clicks.First_Click_Lead_At__c > ssot__MessageEngagement__dlm.Create_Date_Custom__c AND DATEDIFF(clicks.First_Click_Lead_At__c, ssot__MessageEngagement__dlm.Create_Date_Custom__c) <= 30 THEN 1 ELSE 0 END AS Clicked_30d__c,
  CASE WHEN DATEDIFF(NOW(), ssot__MessageEngagement__dlm.Create_Date_Custom__c) >= 460 AND DATEDIFF(NOW(), ssot__MessageEngagement__dlm.Create_Date_Custom__c) <= 825 THEN 1 ELSE 0 END AS Label_Window__c,
  MAX(ssot__MessageEngagement__dlm.Create_Date_Custom__c) AS SMS_Sent_At__c,
  MAX(clicks.First_Click_Lead_At__c) AS First_Click_Lead_At__c,
  MAX(ssot__MessageEngagement__dlm.SMS_Status_Code_Id__c) AS SMS_Status_Code__c,
  MAX(ssot__Lead__dlm.ssot__CreatedDate__c) AS Lead_Created__c,
  MAX(DATEDIFF(ssot__MessageEngagement__dlm.Create_Date_Custom__c, ssot__Lead__dlm.ssot__CreatedDate__c)) AS Days_Create_To_SMS__c,
  MAX(HOUR(ssot__MessageEngagement__dlm.Create_Date_Custom__c)) AS SMS_Hour__c,
  MAX(HOUR(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Hour__c,
  MAX(DAYOFWEEK(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Day_Of_Week__c,
  MAX(MONTH(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Created_Month__c,
  MAX(ssot__Lead__dlm.Max_Quote_Step__c) AS Max_Quote_Step__c,
  MAX(ssot__Lead__dlm.Credit_Score__c) AS Credit_Score__c,
  COUNT(ssot__MessageEngagement__dlm.ssot__Id__c) AS Row_Count__c
FROM ssot__MessageEngagement__dlm
JOIN ssot__Lead__dlm ON (ssot__Lead__dlm.ssot__Id__c = ssot__MessageEngagement__dlm.Subscriber_Key__c)
LEFT JOIN IndividualIdentityLink__dlm ON (IndividualIdentityLink__dlm.SourceRecordId__c = ssot__Lead__dlm.ssot__Id__c)
LEFT JOIN (SELECT IndividualIdentityLink__dlm.UnifiedRecordId__c AS Unified_Id__c, MIN(ssot__Lead__dlm.ssot__CreatedDate__c) AS First_Click_Lead_At__c FROM ssot__Lead__dlm JOIN IndividualIdentityLink__dlm ON (IndividualIdentityLink__dlm.SourceRecordId__c = ssot__Lead__dlm.ssot__Id__c) WHERE ssot__Lead__dlm.UTM_Medium__c = 'sms' GROUP BY IndividualIdentityLink__dlm.UnifiedRecordId__c) AS clicks ON (clicks.Unified_Id__c = IndividualIdentityLink__dlm.UnifiedRecordId__c)
WHERE ssot__MessageEngagement__dlm.ssot__Name__c LIKE 'AC_%'
  AND ssot__MessageEngagement__dlm.Subscriber_Key__c LIKE '00Q%'
  AND DATEDIFF(NOW(), ssot__MessageEngagement__dlm.Create_Date_Custom__c) >= 15
  AND (ssot__Lead__dlm.UTM_Medium__c IS NULL OR ssot__Lead__dlm.UTM_Medium__c <> 'sms')
GROUP BY Lead_Id__c, SMS_Name__c, State__c, Previous_Insurance__c, Vehicle_Make__c, UTM_Source__c, UTM_Medium__c, Lead_Source__c, Publisher__c, Email_Opt_Out__c, Declined__c, Saved_Quote__c, Currently_Insured__c, App_Downloaded__c, Purchased__c, Clicked_14d__c, Clicked_30d__c, Label_Window__c
