SELECT
  Zen_Desk_Ticket_Bronze__dlm.Lead__c AS Lead_Id__c,
  Zen_Desk_Ticket_Bronze__dlm.Id_c__c AS Ticket_Id__c,
  Zen_Desk_Ticket_Bronze__dlm.Contact_Type_list_c__c AS Contact_Type__c,
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
  CASE WHEN ssot__Lead__dlm.App_Downloaded__c = TRUE THEN 1 ELSE 0 END AS App_Downloaded__c,
  CASE WHEN ssot__Lead__dlm.Purchased__c = TRUE THEN 1 ELSE 0 END AS Purchased__c,
  CASE WHEN LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%no call%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%not call%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%ex customer%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%ex-customer%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%do not call%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%wrong number%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%not in service%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%number not%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%number did not work%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%already a customer%' THEN 0 ELSE 1 END AS Called__c,
  CASE WHEN Zen_Desk_Ticket_Bronze__dlm.Tags_c__c LIKE '%next_best_action_answer%' THEN 1 WHEN Zen_Desk_Ticket_Bronze__dlm.Tags_c__c LIKE '%next_best_action_no_answer%' THEN 0 WHEN LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%answered%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%spoke%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%said %' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%told %' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%talked%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%went with%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%already has%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%already got%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%already secured%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%already purchased%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%not interested%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%shopping%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%will reach%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%busy%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%interested%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%declin%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%elsewhere%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%another insurer%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%price%' OR LOWER(Zen_Desk_Ticket_Bronze__dlm.Comments__c) LIKE '%coverage%' THEN 1 ELSE 0 END AS Call_Reached__c,
  MAX(Zen_Desk_Ticket_Bronze__dlm.Created_at_c__c) AS Ticket_Created_At__c,
  MAX(ssot__Lead__dlm.ssot__CreatedDate__c) AS Lead_Created__c,
  MAX(DATEDIFF(Zen_Desk_Ticket_Bronze__dlm.Created_at_c__c, ssot__Lead__dlm.ssot__CreatedDate__c)) AS Days_Create_To_Call__c,
  MAX(HOUR(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Hour__c,
  MAX(DAYOFWEEK(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Day_Of_Week__c,
  MAX(MONTH(ssot__Lead__dlm.ssot__CreatedDate__c)) AS Lead_Created_Month__c,
  MAX(ssot__Lead__dlm.Max_Quote_Step__c) AS Max_Quote_Step__c,
  MAX(ssot__Lead__dlm.Credit_Score__c) AS Credit_Score__c,
  SUM(CASE WHEN ssot__EmailEngagement__dlm.ssot__SentDateTm__c < Zen_Desk_Ticket_Bronze__dlm.Created_at_c__c THEN 1 ELSE 0 END) AS Emails_Before_Call__c,
  SUM(CASE WHEN ssot__EmailEngagement__dlm.ssot__SentDateTm__c < Zen_Desk_Ticket_Bronze__dlm.Created_at_c__c AND ssot__EmailEngagement__dlm.Opened__c = TRUE THEN 1 ELSE 0 END) AS Opens_Before_Call__c,
  SUM(CASE WHEN ssot__EmailEngagement__dlm.ssot__SentDateTm__c < Zen_Desk_Ticket_Bronze__dlm.Created_at_c__c AND ssot__EmailEngagement__dlm.Clicked__c = TRUE THEN 1 ELSE 0 END) AS Clicks_Before_Call__c,
  COUNT(Zen_Desk_Ticket_Bronze__dlm.Id_c__c) AS Row_Count__c
FROM Zen_Desk_Ticket_Bronze__dlm
JOIN ssot__Lead__dlm ON (ssot__Lead__dlm.ssot__Id__c = Zen_Desk_Ticket_Bronze__dlm.Lead__c)
LEFT JOIN ssot__EmailEngagement__dlm ON (ssot__EmailEngagement__dlm.ssot__LeadlId__c = ssot__Lead__dlm.ssot__Id__c AND ssot__EmailEngagement__dlm.ssot__EmailName__c LIKE 'AC_%')
WHERE Zen_Desk_Ticket_Bronze__dlm.Subject_c__c LIKE 'New Lead- Next Best Action%'
  AND Zen_Desk_Ticket_Bronze__dlm.Lead__c <> ''
  AND DATEDIFF(NOW(), Zen_Desk_Ticket_Bronze__dlm.Created_at_c__c) >= 3
GROUP BY Lead_Id__c, Ticket_Id__c, Contact_Type__c, State__c, Previous_Insurance__c, Vehicle_Make__c, UTM_Source__c, UTM_Medium__c, Lead_Source__c, Publisher__c, Email_Opt_Out__c, Declined__c, Saved_Quote__c, Currently_Insured__c, Mobile_Opt_Out__c, App_Downloaded__c, Purchased__c, Called__c, Call_Reached__c
