/*
 Email_Response_Training_Set__cio -- point-in-time training set for 'will open the first quote-journey email'
 Built 2026-11-02. Dialect: Data Cloud Calculated Insight SQL (Spark style, DATEDIFF(end, start)),
 same identity join as Requote_30d_Training_Set__cio.

 Unit      : one row per lead created on/after 2025-01-01 that received its first AC_ (quote-step /
             review / re-engagement) email within 30 days of creation, and whose 7-day click window is
             fully in the past.
 Labels    : Opened_3d__c  = Opened__c on any AC_ email sent within 3 days of that first send
             Clicked_7d__c = Clicked__c on any AC_ email sent within 7 days of that first send
 Features  : lead attributes as of creation + prior-lead history. No current-state scores.
 Validated : ssot__EmailEngagement__dlm 2026 rows 367,679 with 133,401 opens; join key
             ssot__LeadlId__c = ssot__Lead__dlm.ssot__Id__c (3.56M of 3.84M rows carry a 00Q id).
*/
SELECT
  b.Lead_Id__c                                     AS Lead_Id__c,
  b.Unified_Individual_Id__c                       AS Unified_Individual_Id__c,
  b.First_Send_At__c                               AS First_Send_At__c,
  b.First_Email_Name__c                            AS First_Email_Name__c,
  b.Days_Create_To_Send__c                         AS Days_Create_To_Send__c,
  b.Send_Hour__c                                   AS Send_Hour__c,
  b.Lead_Hour__c                                   AS Lead_Hour__c,
  b.Lead_Day_Of_Week__c                            AS Lead_Day_Of_Week__c,
  b.Lead_Created_Month__c                          AS Lead_Created_Month__c,
  b.Max_Quote_Step__c                              AS Max_Quote_Step__c,
  b.Declined__c                                    AS Declined__c,
  b.Saved_Quote__c                                 AS Saved_Quote__c,
  b.State__c                                       AS State__c,
  b.Previous_Insurance__c                          AS Previous_Insurance__c,
  b.Currently_Insured_Status__c                    AS Currently_Insured_Status__c,
  b.Vehicle_Make__c                                AS Vehicle_Make__c,
  b.UTM_Source__c                                  AS UTM_Source__c,
  b.UTM_Medium__c                                  AS UTM_Medium__c,
  b.Lead_Source__c                                 AS Lead_Source__c,
  b.Publisher__c                                   AS Publisher__c,
  b.Credit_Score__c                                AS Credit_Score__c,
  b.Mobile_Opt_Out__c                              AS Mobile_Opt_Out__c,
  b.Email_Opt_Out__c                               AS Email_Opt_Out__c,
  b.Email_Domain__c                                AS Email_Domain__c,
  b.Has_Mobile__c                                  AS Has_Mobile__c,
  b.App_Downloaded__c                              AS App_Downloaded__c,
  b.Prior_Leads__c                                 AS Prior_Leads__c,
  b.Prior_Opens__c                                 AS Prior_Opens__c,
  b.Prior_Clicks__c                                AS Prior_Clicks__c,
  b.Prior_Sends__c                                 AS Prior_Sends__c,
  MAX(CASE WHEN e.Opened__c AND DATEDIFF(e.ssot__SentDateTm__c, b.First_Send_At__c) <= 3 THEN TRUE ELSE FALSE END)  AS Opened_3d__c,
  MAX(CASE WHEN e.Clicked__c AND DATEDIFF(e.ssot__SentDateTm__c, b.First_Send_At__c) <= 7 THEN TRUE ELSE FALSE END) AS Clicked_7d__c
FROM (
  SELECT
    l.ssot__Id__c                                  AS Lead_Id__c,
    il.UnifiedRecordId__c                          AS Unified_Individual_Id__c,
    l.ssot__CreatedDate__c                         AS Lead_Created__c,
    MIN(f.ssot__SentDateTm__c)                     AS First_Send_At__c,
    MIN(f.ssot__EmailName__c)                      AS First_Email_Name__c,
    DATEDIFF(MIN(f.ssot__SentDateTm__c), l.ssot__CreatedDate__c) AS Days_Create_To_Send__c,
    HOUR(MIN(f.ssot__SentDateTm__c))               AS Send_Hour__c,
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
    -- domain bucket from the engagement row (ssot__EmailDomainName__c), keeps the address itself out of the model
    MIN(f.ssot__EmailDomainName__c)                AS Email_Domain__c,
    CASE WHEN l.ssot__MobileContactPhoneId__c IS NOT NULL THEN TRUE ELSE FALSE END AS Has_Mobile__c,
    l.App_Downloaded__c                            AS App_Downloaded__c,
    COUNT(DISTINCT CASE WHEN n.ssot__CreatedDate__c < l.ssot__CreatedDate__c THEN n.ssot__Id__c END)                    AS Prior_Leads__c,
    COUNT(DISTINCT CASE WHEN p.ssot__SentDateTm__c < l.ssot__CreatedDate__c THEN p.ssot__Id__c END)                      AS Prior_Sends__c,
    COUNT(DISTINCT CASE WHEN p.ssot__SentDateTm__c < l.ssot__CreatedDate__c AND p.Opened__c  THEN p.ssot__Id__c END)     AS Prior_Opens__c,
    COUNT(DISTINCT CASE WHEN p.ssot__SentDateTm__c < l.ssot__CreatedDate__c AND p.Clicked__c THEN p.ssot__Id__c END)     AS Prior_Clicks__c
  FROM ssot__Lead__dlm l
  JOIN IndividualIdentityLink__dlm il  ON il.SourceRecordId__c = l.ssot__Id__c
  JOIN IndividualIdentityLink__dlm il2 ON il2.UnifiedRecordId__c = il.UnifiedRecordId__c
  JOIN ssot__Lead__dlm n               ON n.ssot__Id__c = il2.SourceRecordId__c
  -- first AC_ email to THIS lead within 30 days of creation
  JOIN ssot__EmailEngagement__dlm f    ON f.ssot__LeadlId__c = l.ssot__Id__c
                                      AND f.ssot__EmailName__c LIKE 'AC_%'
                                      AND f.ssot__IsTestSend__c <> 'true'
                                      AND DATEDIFF(f.ssot__SentDateTm__c, l.ssot__CreatedDate__c) BETWEEN 0 AND 30
  -- prior email history for any lead of the same individual
  LEFT JOIN ssot__EmailEngagement__dlm p ON p.ssot__LeadlId__c = n.ssot__Id__c
  WHERE l.ssot__CreatedDate__c >= TIMESTAMP '2025-01-01 00:00:00'
    AND l.Internal_Traffic__c <> TRUE
  GROUP BY l.ssot__Id__c, il.UnifiedRecordId__c, l.ssot__CreatedDate__c, l.Max_Quote_Step__c, l.Declined__c,
           l.Saved_Quote__c, l.ssot__StateProvinceId__c, l.Previous_Insurance__c, l.Currently_Insured_Status__c,
           l.Vehicle_Make__c, l.UTM_Source__c, l.UTM_Medium__c, l.ssot__LeadSourceId__c, l.Publisher__c,
           l.Credit_Score__c, l.Mobile_Opt_Out__c, l.Email_Opt_Out__c, l.ssot__MobileContactPhoneId__c, l.App_Downloaded__c
) b
-- every AC_ email to the lead in the 7 days after the first send, for the labels
JOIN ssot__EmailEngagement__dlm e ON e.ssot__LeadlId__c = b.Lead_Id__c
                                 AND e.ssot__EmailName__c LIKE 'AC_%'
                                 AND DATEDIFF(e.ssot__SentDateTm__c, b.First_Send_At__c) BETWEEN 0 AND 7
WHERE DATEDIFF(NOW(), b.First_Send_At__c) >= 8
GROUP BY b.Lead_Id__c, b.Unified_Individual_Id__c, b.First_Send_At__c, b.First_Email_Name__c, b.Days_Create_To_Send__c,
         b.Send_Hour__c, b.Lead_Hour__c, b.Lead_Day_Of_Week__c, b.Lead_Created_Month__c, b.Max_Quote_Step__c, b.Declined__c,
         b.Saved_Quote__c, b.State__c, b.Previous_Insurance__c, b.Currently_Insured_Status__c, b.Vehicle_Make__c,
         b.UTM_Source__c, b.UTM_Medium__c, b.Lead_Source__c, b.Publisher__c, b.Credit_Score__c, b.Mobile_Opt_Out__c,
         b.Email_Opt_Out__c, b.Email_Domain__c, b.Has_Mobile__c, b.App_Downloaded__c, b.Prior_Leads__c, b.Prior_Opens__c,
         b.Prior_Clicks__c, b.Prior_Sends__c
