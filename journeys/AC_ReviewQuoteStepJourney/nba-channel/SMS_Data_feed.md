# How `SMS__c` is fed, and why it records one text per person

Checked 2026-11-02. The object is live and written every day, but it keeps each subscriber's first
text only. Anything that counts texts or texted leads from `SMS__c` is undercounted by about 60%.

## The feed

| Piece | What it is |
|---|---|
| Automation | `SMS Data` (Marketing Cloud, BU 110007736), daily 10:00 server time (16:00 UTC), scheduled, last run 2026-11-02 10:00. |
| Step 1 | Query activity `SMSData` -> data extension `smsmessagetracking` (Overwrite): yesterday's rows from the `_smsmessagetracking` data view. 2026-11-01: 1,041 rows for 463 subscribers; only 474 distinct subscriber + message + time, because the data view carries ~2 rows per text (one per delivery receipt). |
| Step 2 | Journey `SMS Creation` v1, published 2023-04-19, entry source = that data extension, one activity: Salesforce Object `Create SMS__c` mapping Name, SubscriberKey__c, CreateDate__c, SMSStandardStatusCodeId__c and the rest. No lookup, no update. |
| Entry setting | **Once and done.** A subscriber key can enter this journey once in its lifetime. That is the defect: the second and every later text to the same person never reaches Salesforce. |
| Result | 206,193 rows = 206,193 distinct subscriber keys. 2026-11-01: 462 subscribers texted, 169 rows created (all 462 already had a row; 293 from an earlier text). Rows land at 16:01 UTC the next day under the `API SFMC User`. |
| Status | `Status__c` is not mapped (null on every 2026 row). Delivery is in `SMSStandardStatusCodeId__c`: 4000 delivered (94%), 4500 / 4505 undelivered, 2000 pending. |

A side effect worth knowing: the Review journey texts (`AC_Review_SE1/SE2/SE3`) go to leads who have
usually been texted earlier in the quote funnel, so most Review texts are missing from `SMS__c`, and
the SE1/SE2 counts there do not reflect what was sent.

## The fix

Recommended: replace the journey with a Script Activity that upserts one row per text into `SMS__c`
over the Sales Cloud REST API on an external id (`SMS_Key__c` = SubscriberKey|SMSJobID). Idempotent,
visible errors, backfill by widening a date window, no journey entry settings involved, and Sales
Cloud stays the landing place so the CRM connector carries it to Data Cloud without Marketing Cloud
connector credits. Script: `sfmc/SMS_To_SalesCloud.ssjs`; setup: `SMS_SalesCloud_API_RUNBOOK.md`.
The deduplicated query below is required for either path.

Fallback if the API path cannot be built soon (two changes, both in Marketing Cloud):

1. **Journey `SMS Creation`**: new version, Entry Settings -> "Re-entry anytime", publish, and stop
   v1. Nothing else in the journey changes. With re-entry on, every row in the staging data extension
   becomes an `SMS__c` row, so the staging query must be deduplicated first (step 2) or every text
   will create two or three rows.
2. **Query activity `SMSData`**: replace with the version below and give the data extension a primary
   key of `SubscriberKey` + `SMSJobID` so Overwrite cannot hold duplicates.

```sql
/* SMSData -> smsmessagetracking (Overwrite). One row per subscriber per text. */
SELECT
  SubscriberKey,
  SMSJobID,
  MAX(Name)                      AS Name,
  MIN(CreateDateTime)            AS CreateDateTime,
  MAX(SubscriberID)              AS SubscriberID,
  MAX(Description)               AS Description,
  MAX(SMSStandardStatusCodeId)   AS SMSStandardStatusCodeId,
  MAX(ShortCode)                 AS ShortCode,
  MAX(Mobile)                    AS Mobile,
  MAX(CASE WHEN Sent        = 1 THEN 1 ELSE 0 END) AS Sent,
  MAX(CASE WHEN Delivered   = 1 THEN 1 ELSE 0 END) AS Delivered,
  MAX(CASE WHEN Undelivered = 1 THEN 1 ELSE 0 END) AS Undelivered,
  MAX(MessageText)               AS MessageText,
  MAX(SendID)                    AS SendID
FROM _smsmessagetracking
WHERE CreateDateTime IS NOT NULL
  AND CONVERT(DATE, CreateDateTime) = DATEADD(day, -1, CONVERT(DATE, GETDATE()))
GROUP BY SubscriberKey, SMSJobID
```

Optional third change: map `Delivered` to `Status__c` in the Salesforce activity so the picklist is
populated again, or drop `Status__c` and read `SMSStandardStatusCodeId__c`.

## Backfill

`_smsmessagetracking` retains about six months. A one-off run of the same query with a wider date
window (and the journey on re-entry) recovers the texts since roughly May 2026 that the Once-and-done
setting dropped. Anything earlier is gone from Marketing Cloud and would have to come from Bitly link
counts or not at all.

## Why the tracking view has several rows per text

Checked on 2026-11-01's 1,041 rows = 483 texts. 252 texts have one row (all 151 characters or
shorter). 73 have two rows and are all exactly 153 characters, so those are concatenated messages
with one row per segment. 136 have three or four rows and 22 have nine, with short message bodies,
so those are repeated status rows, not segments. `GROUP BY SubscriberKey, SMSJobID` collapses both
kinds; the object should never hold segment rows.

## What this changes in the model package

- `SMS_Response_Training_Set__cio.sql` needs no change; it reads whatever `SMS__c` holds. Its
  denominators roughly double once the feed records every text, and the per-text click rate will drop
  because later texts in a sequence are clicked less than first ones.
- The factorial test's SMS arm cannot be read from `SMS__c` until the feed is fixed, because most
  test leads will already have an `SMS__c` row from an earlier text. Fix the feed before the test starts.
