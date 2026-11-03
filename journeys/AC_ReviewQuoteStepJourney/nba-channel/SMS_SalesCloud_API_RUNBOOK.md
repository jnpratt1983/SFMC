# SMS texts into Sales Cloud by API: runbook

Replaces the `SMS Creation` journey (Once and done, records each person's first text only) with a
scheduled Apex job in Sales Cloud that pulls the deduplicated rows from Marketing Cloud and upserts one
`SMS__c` row per text. Sales Cloud stays the landing place; the CRM connector already carries `SMS__c`
into Data Cloud, so no Marketing Cloud connector credits are used.

Direction: **Sales Cloud pulls.** It uses the Named Credential `SFMC_Auth` that already exists in
blueowl-prod (legacy Password protocol, client id as username, merge fields in body) and the Remote Site
Setting `SFMC_REST`, the same pattern as `Customer360FeedController`. No secrets live in Marketing Cloud.

Volume after dedupe: about 480 texts a day, ~175k rows a year, ~350 MB of CRM storage a year
(2 KB per record). The raw tracking rows would be 2.2x that; the query below collapses them.

## 1. Marketing Cloud

Done 2026-11-02 over the API:
- Data extension `smsmessagetracking_v2` (customer key `smsmessagetracking_v2`, folder of the old one,
  primary key `SubscriberKey` + `SMSJobID`, same columns minus MessageText, not sendable).
- Query activity `SMSData_v2` (folder of `SMSData`, target `smsmessagetracking_v2`, Overwrite, the GROUP BY
  text from `SMS_Data_feed.md`). Run once by hand: 471 rows / 462 subscribers for 2026-11-01, against
  1,041 raw rows.

- `SMSData_v2` added as the second activity of step 1 in automation `SMS Data` (done in the UI
  2026-11-02, confirmed over the API; next run 2026-11-03 10:00 server time = 16:00 UTC).

Still to do in the UI:
1. After the Apex has run clean for a few days: remove step 2 (the `SMS Creation` journey entry) and
   stop journey `SMS Creation` v1. Optionally remove the old `SMSData` query and `smsmessagetracking`.
2. The Marketing Cloud installed package behind `SFMC_Auth` needs the scope Data Extensions > Read.
   Check in Setup > Installed Packages > (package) > API Integration.

## 2. Sales Cloud

Deployed to blueowl-prod 2026-11-03 00:4x UTC (deploy 0AfVt000002KRJ3KAO, 13 components, 5 tests, 0
failures) and scheduled (CronTrigger 08eVt00001yXjhj, job name `SMS Tracking Sync`).

| Component | Purpose |
|---|---|
| `objects/SMS__c/fields/SMS_Key__c` | Text 80, external id, unique. `SubscriberKey|SMSJobID`. |
| `objects/SMS_Sync_Setting__c` (hierarchy custom setting) | run log (`Last_Run_At__c`, `Last_Rows_Read__c`, `Last_Upserted__c`, `Last_Errors__c`, `Last_Error__c`) and overrides (`DE_Key__c`, `Chunk_Size__c`, `Batch_Pages__c`). |
| `classes/SMSTrackingSync` + `SMSTrackingSyncSchedule` | Queueable job plus its daily scheduler. Token, rowset pages of 2,500, map, upsert on `SMS_Key__c`, retry without lookups on a bad lead/contact id, chain to the next page, write the summary. |
| `classes/SMSTrackingSyncTest` | callout mocks: three texts, idempotent rerun, rowset failure, schedule, time parsing. |
| `permissionsets/SMS_Sync_Access` | read/edit on `SMS_Key__c`. Deployed fields carry no field-level security, so without this nobody but Apex can see the key. Assigned to jennifer.pratt; assign to the Data Cloud integration user too if the field should flow into the CRM data stream. |

Schedule: `System.schedule('SMS Tracking Sync', '0 30 16 * * ?', new SMSTrackingSyncSchedule());`
Apex cron runs in the scheduling user's timezone (Central), so 16:30 Central = 22:30 UTC in winter,
21:30 UTC in summer. Both are after the 16:00 UTC Marketing Cloud query, which is all that matters.
Do not move it earlier than 11:00 Central or the summer run would precede the query.

Re-deploy command if anything changes:
```
sf project deploy start -o blueowl-prod --test-level RunSpecifiedTests --tests SMSTrackingSyncTest \
  --source-dir force-app/main/default/objects/SMS__c/fields/SMS_Key__c.field-meta.xml \
  --source-dir force-app/main/default/objects/SMS_Sync_Setting__c \
  --source-dir force-app/main/default/classes/SMSTrackingSync.cls \
  --source-dir force-app/main/default/classes/SMSTrackingSyncSchedule.cls \
  --source-dir force-app/main/default/classes/SMSTrackingSyncTest.cls \
  --source-dir force-app/main/default/permissionsets/SMS_Sync_Access.permissionset-meta.xml
```

## 3. First run and checks

1. First run done 2026-11-03 00:45 UTC on the 2026-11-01 rows: Last Rows Read 471, Last Upserted 471, Last Errors 0,
   job 707Vt000040OR9c completed in 7 seconds. To rerun by hand: `System.enqueueJob(new SMSTrackingSync());` Yesterday's texts that already have an
   `SMS__c` row (the person's first text) get a second row with the new key; the legacy rows have no
   `SMS_Key__c` and are not touched.
2. In Sales Cloud:
   ```
   SELECT COUNT(Id) FROM SMS__c WHERE SMS_Key__c != null AND CreatedDate = TODAY
   SELECT Status__c, COUNT(Id) FROM SMS__c WHERE SMS_Key__c != null GROUP BY Status__c
   ```
3. `Last_Error__c` holds the first failure of the run. Typical: `Token 401` (installed package scope or
   secret), `Rowset 404` (DE key), `STRING_TOO_LONG` (field length). A bad lead or contact id on a row
   is retried without the lookup automatically. Apex Jobs in Setup shows the chained queueables.

## 4. Backfill (about six months, what the data view retains)

1. In Marketing Cloud, change the `SMSData` WHERE clause to a range, one month at a time:
   `CONVERT(DATE, CreateDateTime) BETWEEN '2026-05-01' AND '2026-05-31'`, and run the automation.
2. In Sales Cloud: `System.enqueueJob(new SMSTrackingSync());`. ~15k rows a month = 6 pages, 6 chained
   jobs. The upsert key keeps reruns idempotent, so overlapping windows are safe.
3. Restore the yesterday-only clause.
Backfilled rows carry `SMS_Key__c`, the legacy rows do not, so the two populations stay distinguishable.

## 5. Model package impact

- `SMS_Response_Training_Set__cio.sql` reads `SMS_c__dlm` as before. Add `AND SMS_Key_c__c IS NOT NULL`
  once the backfill is done if you want only the complete population.
- Delivery status comes back: `Status__c` is set from the Delivered / Undelivered flags.
- `Lead__c` / `Contact__c` are set from the subscriber key, so the lookups are populated on new rows.

## Alternative kept in the folder

`sfmc/SMS_To_SalesCloud.ssjs` is the push version (Script Activity in Marketing Cloud calling the Sales
Cloud composite upsert). It needs a Sales Cloud Connected App with the client credentials flow and a
secret stored in a Marketing Cloud data extension. Not needed now that the Named Credential exists.
