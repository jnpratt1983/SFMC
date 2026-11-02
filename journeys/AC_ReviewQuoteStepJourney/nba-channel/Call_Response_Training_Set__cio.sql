/*
 Call_Response_Training_Set__cio -- point-in-time training set for 'picks up / talks when we call'
 Built 2026-11-02. Dialect: Data Cloud Calculated Insight SQL (Spark style), same lead feature block as
 Email_Response_Training_Set__cio.

 Unit      : one row per Next Best Action call ticket. The router's SALESCLOUDACTIVITY step also emails
             Zendesk, which creates a ticket "New Lead- Next Best Action +<LeadId>" (Via Email, groups
             Senior CC Specialist / Next Best Action). Reps work the call from that ticket and write the
             outcome as an internal comment; some also tag next_best_action_answer / _no_answer.
             969 such tickets exist in Zen_Desk_Ticket_Bronze__dlm (2026-04 onward; Jan-Mar 2026 tasks
             made no ticket). Lead__c is set on 97%; the subject carries the 15-char lead id for the rest.
 Labels    : Call_Reached__c = tag next_best_action_answer, or an untagged comment that reads as a
             conversation (answered / spoke / said / already has coverage / not interested ...).
             Called__c       = false when the comment says the rep did not dial (ex-customer, DNC,
             bad / disconnected number). Train on Called__c = true only.
 Validated : 725 tickets created 2026 in CRM: tags answer 44, no_answer 414, untagged 267; comment rule
             on the untagged adds 57 reached. Reach rate 13.9% overall, 14.5% among called. Note is
             written a median 26 hours after the ticket, so wait 3 days before labelling.
 Size      : ~135 positives today, growing ~30 a month. Too small for Model Builder to ship a score;
             this insight exists so the label accrues and so the factorial test's call arm (which
             randomizes who gets called) can be read against it. Revisit at ~1,000 positives.
 Features  : lead attributes as of creation, plus email behaviour BEFORE the call ticket
             (Opened_Email_Before_Call__c, Clicked_Email_Before_Call__c, Emails_Before_Call__c) so the
             model can learn "never opens email -> reachable by phone" if that is real.
*/
SELECT
  z.Lead_Id__c                                         AS Lead_Id__c,
  z.Ticket_Id__c                                       AS Ticket_Id__c,
  z.Ticket_Created_At__c                               AS Ticket_Created_At__c,
  z.Contact_Type__c                                    AS Contact_Type__c,
  DATEDIFF(z.Ticket_Created_At__c, l.ssot__CreatedDate__c) AS Days_Create_To_Call__c,
  HOUR(l.ssot__CreatedDate__c)                         AS Lead_Hour__c,
  DAYOFWEEK(l.ssot__CreatedDate__c)                    AS Lead_Day_Of_Week__c,
  MONTH(l.ssot__CreatedDate__c)                        AS Lead_Created_Month__c,
  l.Max_Quote_Step__c                                  AS Max_Quote_Step__c,
  l.Declined__c                                        AS Declined__c,
  l.Saved_Quote__c                                     AS Saved_Quote__c,
  l.ssot__StateProvinceId__c                           AS State__c,
  l.Previous_Insurance__c                              AS Previous_Insurance__c,
  l.Currently_Insured_Status__c                        AS Currently_Insured_Status__c,
  l.Vehicle_Make__c                                    AS Vehicle_Make__c,
  l.UTM_Source__c                                      AS UTM_Source__c,
  l.UTM_Medium__c                                      AS UTM_Medium__c,
  l.ssot__LeadSourceId__c                              AS Lead_Source__c,
  l.Publisher__c                                       AS Publisher__c,
  l.Credit_Score__c                                    AS Credit_Score__c,
  l.Mobile_Opt_Out__c                                  AS Mobile_Opt_Out__c,
  l.Email_Opt_Out__c                                   AS Email_Opt_Out__c,
  CASE WHEN l.ssot__MobileContactPhoneId__c IS NOT NULL THEN TRUE ELSE FALSE END AS Has_Mobile__c,
  l.App_Downloaded__c                                  AS App_Downloaded__c,
  COUNT(DISTINCT CASE WHEN e.ssot__SentDateTm__c < z.Ticket_Created_At__c THEN e.ssot__Id__c END)                   AS Emails_Before_Call__c,
  MAX(CASE WHEN e.ssot__SentDateTm__c < z.Ticket_Created_At__c AND e.Opened__c  THEN TRUE ELSE FALSE END)           AS Opened_Email_Before_Call__c,
  MAX(CASE WHEN e.ssot__SentDateTm__c < z.Ticket_Created_At__c AND e.Clicked__c THEN TRUE ELSE FALSE END)           AS Clicked_Email_Before_Call__c,
  z.Called__c                                          AS Called__c,
  z.Call_Reached__c                                    AS Call_Reached__c
FROM (
  SELECT
    t.Id_c__c                                          AS Ticket_Id__c,
    t.Created_at_c__c                                  AS Ticket_Created_At__c,
    t.Contact_Type_list_c__c                           AS Contact_Type__c,
    -- Lead__c when the sync set it, else the 15-char id after "+" in the subject
    COALESCE(t.Lead__c, SUBSTRING(t.Subject_c__c, LOCATE('+', t.Subject_c__c) + 1, 15)) AS Lead_Id__c,
    CASE WHEN LOWER(t.Comments__c) LIKE '%no call%'      OR LOWER(t.Comments__c) LIKE '%not call%'
           OR LOWER(t.Comments__c) LIKE '%did not call%' OR LOWER(t.Comments__c) LIKE '%ex customer%'
           OR LOWER(t.Comments__c) LIKE '%ex-customer%'  OR LOWER(t.Comments__c) LIKE '%do not call%'
           OR LOWER(t.Comments__c) LIKE '%wrong number%' OR LOWER(t.Comments__c) LIKE '%not in service%'
           OR LOWER(t.Comments__c) LIKE '%disconnected number%' OR LOWER(t.Comments__c) LIKE '%number not%'
           OR LOWER(t.Comments__c) LIKE '%number did not work%' OR LOWER(t.Comments__c) LIKE '%already a customer%'
         THEN FALSE ELSE TRUE END                      AS Called__c,
    CASE WHEN t.Tags_c__c LIKE '%next_best_action_answer%' THEN TRUE
         WHEN t.Tags_c__c LIKE '%next_best_action_no_answer%' THEN FALSE
         WHEN LOWER(t.Comments__c) LIKE '%answered%'   OR LOWER(t.Comments__c) LIKE '%spoke%'
           OR LOWER(t.Comments__c) LIKE '%said %'       OR LOWER(t.Comments__c) LIKE '%told %'
           OR LOWER(t.Comments__c) LIKE '%talked%'      OR LOWER(t.Comments__c) LIKE '%went with%'
           OR LOWER(t.Comments__c) LIKE '%already has%' OR LOWER(t.Comments__c) LIKE '%already got%'
           OR LOWER(t.Comments__c) LIKE '%already secured%' OR LOWER(t.Comments__c) LIKE '%already purchased%'
           OR LOWER(t.Comments__c) LIKE '%not interested%' OR LOWER(t.Comments__c) LIKE '%shopping%'
           OR LOWER(t.Comments__c) LIKE '%will reach%'  OR LOWER(t.Comments__c) LIKE '%busy%'
           OR LOWER(t.Comments__c) LIKE '%interested%'  OR LOWER(t.Comments__c) LIKE '%declin%'
           OR LOWER(t.Comments__c) LIKE '%elsewhere%'   OR LOWER(t.Comments__c) LIKE '%another insurer%'
           OR LOWER(t.Comments__c) LIKE '%price%'       OR LOWER(t.Comments__c) LIKE '%coverage%'
         THEN TRUE ELSE FALSE END                      AS Call_Reached__c
  FROM Zen_Desk_Ticket_Bronze__dlm t
  WHERE t.Subject_c__c LIKE 'New Lead- Next Best Action%'
    AND DATEDIFF(NOW(), t.Created_at_c__c) >= 3
) z
JOIN ssot__Lead__dlm l ON l.ssot__Id__c = z.Lead_Id__c OR SUBSTRING(l.ssot__Id__c, 1, 15) = z.Lead_Id__c
LEFT JOIN ssot__EmailEngagement__dlm e ON e.ssot__LeadlId__c = l.ssot__Id__c AND e.ssot__EmailName__c LIKE 'AC_%'
GROUP BY z.Lead_Id__c, z.Ticket_Id__c, z.Ticket_Created_At__c, z.Contact_Type__c, l.ssot__CreatedDate__c,
         l.Max_Quote_Step__c, l.Declined__c, l.Saved_Quote__c, l.ssot__StateProvinceId__c, l.Previous_Insurance__c,
         l.Currently_Insured_Status__c, l.Vehicle_Make__c, l.UTM_Source__c, l.UTM_Medium__c, l.ssot__LeadSourceId__c,
         l.Publisher__c, l.Credit_Score__c, l.Mobile_Opt_Out__c, l.Email_Opt_Out__c, l.ssot__MobileContactPhoneId__c,
         l.App_Downloaded__c, z.Called__c, z.Call_Reached__c
