-- Query activity: AC_LeadChannelScore_Current
-- Automation:     AC_NBATEST (every 15 minutes) - add as the FIRST step
-- Target DE:      AC_LeadChannelScore_Current (primary key Id), update type Overwrite
-- Purpose:        stage the lead's CURRENT predicted channel so the Review journey's channel split can
--                 read it through Contact Builder (attribute group "Lead Scoring", Contact Key = Id)
--                 instead of the stale snapshot in AC_ReviewNBATest_AF_01272026.
-- Note:           the child BU cannot expose custom synced Lead fields in Contact Builder directly, hence
--                 this copy. Verify Last_Channel_Scoring_Date__c and the three score fields are in the
--                 Lead sync; drop any column that is not.
-- Written 2026-10-07; nothing deployed yet.

SELECT
    l.Id,
    l.Predicted_Channel__c,
    l.Last_Channel_Scoring_Date__c,
    l.Call_Score__c,
    l.Email_Score__c,
    l.SMS_Score__c,
    GETDATE() AS Refreshed_At
FROM ent.Lead_Salesforce AS l
WHERE l.CreatedDate >= DATEADD(day, -14, GETDATE())
  AND l.Predicted_Channel__c IS NOT NULL
