SELECT
  ssot__Lead__dlm.ssot__Id__c AS Lead_Id__c,
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
  CASE WHEN ssot__Lead__dlm.Purchased__c = TRUE THEN 1 ELSE 0 END AS Purchased__c,
  CASE WHEN first_call.First_Call_At__c IS NOT NULL AND DATEDIFF(first_call.First_Call_At__c, ssot__Lead__dlm.ssot__CreatedDate__c) >= 0 AND DATEDIFF(first_call.First_Call_At__c, ssot__Lead__dlm.ssot__CreatedDate__c) <= 30 THEN 1 ELSE 0 END AS Called_Us_30d__c,
  CASE WHEN first_call.First_Call_At__c IS NOT NULL AND DATEDIFF(first_call.First_Call_At__c, ssot__Lead__dlm.ssot__CreatedDate__c) >= 0 AND DATEDIFF(first_call.First_Call_At__c, ssot__Lead__dlm.ssot__CreatedDate__c) <= 90 THEN 1 ELSE 0 END AS Called_Us_90d__c,
  MAX(ssot__Lead__dlm.ssot__CreatedDate__c) AS Lead_Created__c,
  MAX(first_call.First_Call_At__c) AS First_Call_At__c,
  MAX(DATEDIFF(first_call.First_Call_At__c, ssot__Lead__dlm.ssot__CreatedDate__c)) AS Days_Create_To_Call__c,
  MAX(HOUR(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Hour__c,
  MAX(DAYOFWEEK(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Day_Of_Week__c,
  MAX(MONTH(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Created_Month__c,
  MAX(ssot__Lead__dlm.Max_Quote_Step__c) AS Max_Quote_Step__c,
  MAX(ssot__Lead__dlm.Credit_Score__c) AS Credit_Score__c,
  COUNT(ssot__Lead__dlm.ssot__Id__c) AS Row_Count__c
FROM ssot__Lead__dlm
LEFT JOIN (SELECT Zen_Desk_Ticket_Bronze__dlm.Lead__c AS Lead_Id__c, MIN(Zen_Desk_Ticket_Bronze__dlm.Created_at_c__c) AS First_Call_At__c FROM Zen_Desk_Ticket_Bronze__dlm WHERE Zen_Desk_Ticket_Bronze__dlm.Lead__c <> '' AND Zen_Desk_Ticket_Bronze__dlm.Subject_c__c NOT LIKE 'New Lead- Next Best Action%' AND (Zen_Desk_Ticket_Bronze__dlm.Subject_c__c LIKE '%Call from%' OR Zen_Desk_Ticket_Bronze__dlm.Via_c__c = 'Api') GROUP BY Zen_Desk_Ticket_Bronze__dlm.Lead__c) AS first_call ON (first_call.Lead_Id__c = ssot__Lead__dlm.ssot__Id__c)
WHERE DATEDIFF(NOW(), ssot__Lead__dlm.ssot__CreatedDate__c) >= 31
  AND DATEDIFF(NOW(), ssot__Lead__dlm.ssot__CreatedDate__c) <= 1040
  AND (ssot__Lead__dlm.Internal_Traffic__c IS NULL OR ssot__Lead__dlm.Internal_Traffic__c = FALSE)
GROUP BY Lead_Id__c, State__c, Previous_Insurance__c, Vehicle_Make__c, UTM_Source__c, UTM_Medium__c, Lead_Source__c, Publisher__c, Email_Opt_Out__c, Declined__c, Saved_Quote__c, Currently_Insured__c, Mobile_Opt_Out__c, Has_Mobile__c, App_Downloaded__c, Purchased__c, Called_Us_30d__c, Called_Us_90d__c
