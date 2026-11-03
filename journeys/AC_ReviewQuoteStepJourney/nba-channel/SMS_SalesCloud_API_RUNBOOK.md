# SMS texts into Sales Cloud by API: runbook

Replaces the `SMS Creation` journey (Once and done, records each person's first text only) with a
Script Activity that upserts one `SMS__c` row per text. Sales Cloud stays the landing place; the CRM
connector already carries `SMS__c` into Data Cloud, so no Marketing Cloud connector credits are used.

Volume after dedupe: about 480 texts a day, ~175k rows a year, ~350 MB of CRM storage a year
(2 KB per record). The raw tracking rows would be 2.2x that; the query below collapses them.

## 1. Sales Cloud (once)

1. Deploy `force-app/main/default/objects/SMS__c/fields/SMS_Key__c.field-meta.xml` (Text 80, external
   id, unique). Key = `SubscriberKey|SMSJobID`.
2. Connected App: Setup > App Manager > New Connected App. Enable OAuth, scopes `api` and
   `refresh_token, offline_access`, tick **Enable Client Credentials Flow**. After save: Manage >
   Edit Policies > Client Credentials Flow > Run As = `API SFMC User` (apisfmc@hiroad.com), which
   already owns today's rows. Copy the consumer key and secret.
3. Field-level security for that user: Read/Edit on `SMS__c` fields `SMS_Key__c`, `Name`,
   `SubscriberKey__c`, `CreateDate__c`, `Description__c`, `ShortCode__c`, `SMSStandardStatusCodeId__c`,
   `Status__c`, `Lead__c`, `Contact__c`.
4. Optional: Setup > Bulk Data Load Jobs is not involved; the script uses the REST composite
   collections endpoint, 200 records a call, about 3 calls a day.

## 2. Marketing Cloud (once)

1. Data extensions (Data Extensions > `Automations/SMS Data` folder):
   - `SalesCloud_API_Config`: Name (Text 50, PK), LoginUrl (Text 100), ClientId (Text 255),
     ClientSecret (Text 255), ApiVersion (Text 10). One row: `Prod`, `https://login.salesforce.com`
     (or the My Domain URL), key, secret, `v64.0`. Restrict the folder to admins; the secret is in clear
     text here, which is the Marketing Cloud norm absent a secrets store.
   - `SMS_SalesCloud_Errors`: RunAt (Date), SMSKey (Text 80), ErrorCode (Text 100), Message (Text 1000).
   - `SMS_SalesCloud_Log`: RunAt (Date, PK), RowsRead (Number), Upserted (Number), Errors (Number),
     Note (Text 500).
2. Data extension `smsmessagetracking`: add a primary key on `SubscriberKey` + `SMSJobID` (create a
   new DE `smsmessagetracking_v2` with the same columns plus the key, and repoint the query; existing
   DEs cannot have keys added).
3. Query activity `SMSData`: replace the text with the GROUP BY version in `SMS_Data_feed.md`
   (one row per subscriber per SMS job; this is what removes the segment and status duplicates).
   Target `smsmessagetracking_v2`, Overwrite.
4. Script Activity `SMS_To_SalesCloud`: paste `sfmc/SMS_To_SalesCloud.ssjs`. Set `SOURCE_DE` to the
   new DE name if it changed.
5. Automation `SMS Data`: step 1 stays the query; replace step 2 (`SMS Creation` journey entry) with
   the Script Activity. Save. Stop journey `SMS Creation` v1.

## 3. First run and checks

1. Run the automation once by hand. Expect `SMS_SalesCloud_Log` to show RowsRead ~480, Upserted ~480,
   Errors 0. Yesterday's texts that already have an `SMS__c` row (the person's first text) get a
   second row with the new key; nothing is updated in place because the old rows have no `SMS_Key__c`.
2. In Sales Cloud:
   ```
   SELECT COUNT(Id) FROM SMS__c WHERE SMS_Key__c != null AND CreatedDate = TODAY
   SELECT Status__c, COUNT(Id) FROM SMS__c WHERE SMS_Key__c != null GROUP BY Status__c
   ```
3. Errors land in `SMS_SalesCloud_Errors` with the Salesforce error code. Typical first-run errors:
   `INVALID_FIELD_FOR_INSERT_UPDATE` (field-level security), `STRING_TOO_LONG` (Name over 80),
   `INVALID_CROSS_REFERENCE_KEY` (subscriber key is a deleted or converted lead; harmless, the row is
   still written without the lookup on the retry below).
   If lookups fail often, change the script to drop `Lead__c`/`Contact__c` on the retry.

## 4. Backfill (about six months, what the data view retains)

1. Temporarily change the `SMSData` WHERE clause to a range, one month at a time:
   `CONVERT(DATE, CreateDateTime) BETWEEN '2026-05-01' AND '2026-05-31'`.
2. Run the automation. The upsert key keeps reruns idempotent, so overlapping windows are safe.
3. Restore the yesterday-only clause.
Each month is ~15k rows, ~75 API calls. Rows the old journey already wrote are not touched; the
backfilled rows carry `SMS_Key__c`, the legacy rows do not, so the two populations stay distinguishable.

## 5. Model package impact

- `SMS_Response_Training_Set__cio.sql` reads `SMS_c__dlm` as before. Add `AND SMS_Key_c__c IS NOT NULL`
  once the backfill is done if you want only the complete population, or leave it and accept the
  first-text-only legacy rows for 2025.
- Delivery status comes back: `Status__c` is set from the Delivered / Undelivered flags.
- `Lead__c` / `Contact__c` are set from the subscriber key, so the lookups are populated on new rows.
