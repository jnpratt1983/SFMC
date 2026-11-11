/* AC_ReviewNBA_v9 -- entry query for AC_ReviewQuoteStepJourney v17.
   Automation AC_NBATEST (every 15 min): step 1 NBA_Lead_Channel_Current, step 2 THIS query (replace v8), step 3 journey entry.
   Target DE: AC_ReviewNBATest_AF_01272026 (Overwrite), key 1D148A47-9A8C-476B-9F8D-8E107D1F51BE.
   Before activating: add these columns to that DE -> Call_Score__c (Decimal 18,2), Email_Score__c (Decimal 18,2),
   SMS_Score__c (Decimal 18,2), Last_Channel_Scoring_Date__c (Date), DoNotCall (Boolean), MobilePhone (Phone 50).
   Confirm the same six are in the Marketing Cloud Connect Lead sync (Contact Builder > Data Sources > Synchronized > Lead).
   Changes from v8: the three scores and the scoring date are selected so the journey's Update Lead steps can stamp
   NBA_Entry_*_Score__c; DoNotCall and MobilePhone are selected so the journey's eligibility decision can use them.
   One filter added: last_channel_scoring_date__c IS NOT NULL, the entry gate. Scores land hourly and the automation runs
   every 15 minutes, so a lead enters at the first run after it is scored and the journey needs no wait before deciding
   (decision splits read Journey Data, the entry snapshot, so a wait inside the journey would not refresh the scores).
   Other filters unchanged (3-day creation window, 14-day email suppression). To widen the test population later, change
   DATEADD(day, -3, ...) to -7 and point the NOT EXISTS at a 7-day suppression DE (add a query next to
   emails_sent_last_14_days rather than editing it: every AC_ journey shares that DE).
   2026-11-11: 0053h000003B5ZYAA0 (Automated Process) added to the lastmodifiedbyid list. The Data Cloud score copy
   (Channel_Scores_Lead_default) stamps every scored lead as last modified by Automated Process each hour, which the
   original two-user list rejected unless Airbyte happened to touch the lead afterwards. */
SELECT
    c.id,
    c.email,
    c.cookieid__c,
    c.mobile_country_code__c,
    c.mobilephone                      AS MobilePhone,
    c.donotcall                        AS DoNotCall,
    c.firstname,
    c.lastname,
    c.createddate,
    c.max_quote_step__c,
    c.state__c,
    c.utm_source__c,
    c.landingpageid__c,
    c.lastmodifiedbyid,
    c.purchased__c,
    c.declined__c,
    c.saved_quote__c,
    c.hasoptedoutofemail,
    c.mobile_opt_out_date__c,
    c.projected_first_month_bill__c,
    c.quote_session_key__c,
    c.vehicle_make__c,
    c.vehicle_model__c,
    c.First_Month_Discount_Amount__c,
    c.predicted_channel__c,
    c.call_score__c                    AS Call_Score__c,
    c.email_score__c                   AS Email_Score__c,
    c.sms_score__c                     AS SMS_Score__c,
    c.last_channel_scoring_date__c     AS Last_Channel_Scoring_Date__c
FROM ent.Lead_Salesforce c
WHERE (c.max_quote_step__c = '5.0' OR c.max_quote_step__c = '5.5')
  AND c.createddate >= DATEADD(day, -3, GETDATE())
  AND c.lastmodifiedbyid IN ('0053h000005MGvoAAG', '0053h000007viW9AAI', '0053h000003B5ZYAA0')
  AND c.recordtypeid = '0123h000000VF9DAAW'
  AND (c.saved_quote__c = 'FALSE' OR c.saved_quote__c = 'False' OR c.saved_quote__c = '0')
  AND LOWER(c.landingpageid__c) NOT LIKE '%compare%'
  AND LOWER(c.landingpageid__c) NOT LIKE '%renters%'
  AND c.email IS NOT NULL
  AND c.predicted_channel__c IS NOT NULL
  AND c.last_channel_scoring_date__c IS NOT NULL
  AND c.purchased__c = 'FALSE'
  AND c.declined__c = 'FALSE'
  AND NOT EXISTS (
      SELECT 1
      FROM Emails_Sent_Last_14_Days e
      WHERE e.emailaddress = c.email
  )
