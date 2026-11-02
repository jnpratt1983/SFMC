/*
 Email_Response_Scoring_Set__cio -- leads created in the last 14 days, same feature columns as the
 training set, no label. Email_Domain__c comes from the Lead's email contact point instead of the
 engagement row. Refresh hourly after the CRM lead sync. Built 2026-11-02.
*/
SELECT
  l.ssot__Id__c                                  AS Lead_Id__c,
  il.UnifiedRecordId__c                          AS Unified_Individual_Id__c,
  0                                              AS Days_Create_To_Send__c,
  HOUR(l.ssot__CreatedDate__c)                   AS Send_Hour__c,
  HOUR(l.ssot__CreatedDate__c)                   AS Lead_Hour__c,
  DAYOFWEEK(l.ssot__CreatedDate__c)              AS Lead_Day_Of_Week__c,
  MONTH(l.ssot__CreatedDate__c)                  AS Lead_Created_Month__c,
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
  l.Mobile_Opt_Out__c                            AS Mobile_Opt_Out__c,
  l.Email_Opt_Out__c                             AS Email_Opt_Out__c,
  MIN(SUBSTRING(cpe.ssot__EmailAddress__c, POSITION('@' IN cpe.ssot__EmailAddress__c) + 1)) AS Email_Domain__c,
  CASE WHEN l.ssot__MobileContactPhoneId__c IS NOT NULL THEN TRUE ELSE FALSE END AS Has_Mobile__c,
  l.App_Downloaded__c                            AS App_Downloaded__c,
  COUNT(DISTINCT CASE WHEN n.ssot__CreatedDate__c < l.ssot__CreatedDate__c THEN n.ssot__Id__c END)                 AS Prior_Leads__c,
  COUNT(DISTINCT CASE WHEN p.ssot__SentDateTm__c < l.ssot__CreatedDate__c THEN p.ssot__Id__c END)                   AS Prior_Sends__c,
  COUNT(DISTINCT CASE WHEN p.ssot__SentDateTm__c < l.ssot__CreatedDate__c AND p.Opened__c  THEN p.ssot__Id__c END)  AS Prior_Opens__c,
  COUNT(DISTINCT CASE WHEN p.ssot__SentDateTm__c < l.ssot__CreatedDate__c AND p.Clicked__c THEN p.ssot__Id__c END)  AS Prior_Clicks__c
FROM ssot__Lead__dlm l
JOIN IndividualIdentityLink__dlm il  ON il.SourceRecordId__c = l.ssot__Id__c
JOIN IndividualIdentityLink__dlm il2 ON il2.UnifiedRecordId__c = il.UnifiedRecordId__c
JOIN ssot__Lead__dlm n               ON n.ssot__Id__c = il2.SourceRecordId__c
LEFT JOIN ssot__ContactPointEmail__dlm cpe ON cpe.ssot__Id__c = l.ssot__ContactPointEmailId__c
LEFT JOIN ssot__EmailEngagement__dlm p ON p.ssot__LeadlId__c = n.ssot__Id__c
WHERE DATEDIFF(NOW(), l.ssot__CreatedDate__c) <= 14
  AND l.Internal_Traffic__c <> TRUE
GROUP BY l.ssot__Id__c, il.UnifiedRecordId__c, l.ssot__CreatedDate__c, l.Max_Quote_Step__c, l.Declined__c, l.Saved_Quote__c,
         l.ssot__StateProvinceId__c, l.Previous_Insurance__c, l.Currently_Insured_Status__c, l.Vehicle_Make__c, l.UTM_Source__c,
         l.UTM_Medium__c, l.ssot__LeadSourceId__c, l.Publisher__c, l.Credit_Score__c, l.Mobile_Opt_Out__c, l.Email_Opt_Out__c,
         l.ssot__MobileContactPhoneId__c, l.App_Downloaded__c
