/*
 SMS_Response_Training_Set__cio -- point-in-time training set for 'clicks the link in our text'
 Built 2026-11-02. Dialect: Data Cloud Calculated Insight SQL (Spark style), same lead feature block as
 Email_Response_Training_Set__cio.

 How the label works
   Every quote-journey text carries a Bitly branded link that lands on quote.hiroad.com with
   utm_source=sfmc&utm_medium=sms&utm_campaign=<journey>&utm_content=<message>. The quote app writes
   those UTM values onto the Lead it creates for that session, once, at creation (checked: of 1,105
   leads created in 2026 with utm_medium = 'sms', none had received a text before they were created).
   So a lead with utm_medium = 'sms' is a NEW lead record spawned by a click on a text sent to an
   EARLIER lead of the same person. IndividualIdentityLink__dlm joins the two. The label is attached
   to the texted lead: Clicked_SMS_14d__c = a same-individual lead with utm_medium = 'sms' was created
   within 14 days after the text.
 Validated 2026-11-02 (Trino, queryv2): 51,566 leads texted an AC_ message Jan 1 - Oct 14 2026, all
   identity-linked; 504 (1.0%) have a click lead within 14 days, 562 within 30. By family: SavedQuote
   3.0%, QuoteDiscovery 1.6%, PurchaseQuote 1.2%, VehiclesQuoteStep 1.0%, Review 0.8%, CoveragesQuote
   0.7%, DriversQuoteStep 0.5%. Undercounts: a click that resumes an existing quote session creates no
   new lead, and SMS__c keeps one row per subscriber key (the latest text), so earlier texts to the
   same lead are invisible. Treat the rate as a floor; it is consistent across months, so it ranks.
 Unit      : one row per lead whose latest AC_ text is at least 15 days old.
 Size      : ~500 positives a year. Enough to read the SMS arm of the factorial test and to accrue;
   not enough to ship a score. Revisit at ~1,000 positives, or sooner if the texts switch to
   MobileConnect tracked links (per-subscriber click events, no identity hop needed).
*/
SELECT
  s.Lead_Id__c                                         AS Lead_Id__c,
  s.Unified_Individual_Id__c                           AS Unified_Individual_Id__c,
  s.SMS_Sent_At__c                                     AS SMS_Sent_At__c,
  s.SMS_Name__c                                        AS SMS_Name__c,
  s.SMS_Delivered__c                                   AS SMS_Delivered__c,
  DATEDIFF(s.SMS_Sent_At__c, l.ssot__CreatedDate__c)   AS Days_Create_To_SMS__c,
  HOUR(s.SMS_Sent_At__c)                               AS SMS_Hour__c,
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
  l.Email_Opt_Out__c                                   AS Email_Opt_Out__c,
  l.App_Downloaded__c                                  AS App_Downloaded__c,
  COUNT(DISTINCT CASE WHEN e.ssot__SentDateTm__c < s.SMS_Sent_At__c THEN e.ssot__Id__c END)                 AS Emails_Before_SMS__c,
  MAX(CASE WHEN e.ssot__SentDateTm__c < s.SMS_Sent_At__c AND e.Opened__c  THEN TRUE ELSE FALSE END)         AS Opened_Email_Before_SMS__c,
  MAX(CASE WHEN e.ssot__SentDateTm__c < s.SMS_Sent_At__c AND e.Clicked__c THEN TRUE ELSE FALSE END)         AS Clicked_Email_Before_SMS__c,
  -- label: a later lead of the same person, created from the sms link, within 14 days
  MAX(CASE WHEN l2.UTM_Medium__c = 'sms' AND l2.ssot__CreatedDate__c > s.SMS_Sent_At__c
            AND DATEDIFF(l2.ssot__CreatedDate__c, s.SMS_Sent_At__c) <= 14 THEN TRUE ELSE FALSE END)         AS Clicked_SMS_14d__c,
  MIN(CASE WHEN l2.UTM_Medium__c = 'sms' AND l2.ssot__CreatedDate__c > s.SMS_Sent_At__c
            AND DATEDIFF(l2.ssot__CreatedDate__c, s.SMS_Sent_At__c) <= 14 THEN l2.UTM_Campaign__c END)      AS Click_UTM_Campaign__c
FROM (
  SELECT
    m.SubscriberKey__c                                 AS Lead_Id__c,
    il.UnifiedRecordId__c                              AS Unified_Individual_Id__c,
    m.CreateDate__c                                    AS SMS_Sent_At__c,
    m.Name__c                                          AS SMS_Name__c,
    CASE WHEN m.Status__c IN ('Delivered', 'Delivered to handset', 'DeliveredToAggregator', 'AcceptedByCarrier', '')
         THEN TRUE ELSE FALSE END                      AS SMS_Delivered__c
  FROM SMS_c__dlm m
  JOIN IndividualIdentityLink__dlm il ON il.SourceRecordId__c = m.SubscriberKey__c
  WHERE m.Name__c LIKE 'AC_%'
    AND m.SubscriberKey__c LIKE '00Q%'
    AND m.CreateDate__c >= TIMESTAMP '2025-01-01 00:00:00'
    AND DATEDIFF(NOW(), m.CreateDate__c) >= 15
) s
JOIN ssot__Lead__dlm l                 ON l.ssot__Id__c = s.Lead_Id__c
LEFT JOIN IndividualIdentityLink__dlm il2 ON il2.UnifiedRecordId__c = s.Unified_Individual_Id__c
LEFT JOIN ssot__Lead__dlm l2           ON l2.ssot__Id__c = il2.SourceRecordId__c AND l2.ssot__Id__c <> s.Lead_Id__c
LEFT JOIN ssot__EmailEngagement__dlm e ON e.ssot__LeadlId__c = l.ssot__Id__c AND e.ssot__EmailName__c LIKE 'AC_%'
WHERE l.Internal_Traffic__c <> TRUE
GROUP BY s.Lead_Id__c, s.Unified_Individual_Id__c, s.SMS_Sent_At__c, s.SMS_Name__c, s.SMS_Delivered__c, l.ssot__CreatedDate__c,
         l.Max_Quote_Step__c, l.Declined__c, l.Saved_Quote__c, l.ssot__StateProvinceId__c, l.Previous_Insurance__c,
         l.Currently_Insured_Status__c, l.Vehicle_Make__c, l.UTM_Source__c, l.UTM_Medium__c, l.ssot__LeadSourceId__c,
         l.Publisher__c, l.Credit_Score__c, l.Email_Opt_Out__c, l.App_Downloaded__c
-- NOTE: the SMS log is mapped in Data Cloud as the lake object SMS_c__dll (fields SubscriberKey_c__c,
-- CreateDate_c__c, Name__c, Status_c__c). If no SMS_c__dlm data model object exists yet, map the DLO to a
-- custom DMO first, or point this query at the DLO field names.
