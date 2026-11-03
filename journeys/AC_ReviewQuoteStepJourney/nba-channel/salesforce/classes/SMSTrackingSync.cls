/**
 * SMSTrackingSync
 *
 * Pulls the deduplicated SMS tracking rows that the Marketing Cloud automation "SMS Data" writes to the
 * data extension smsmessagetracking (one row per subscriber per SMS job, yesterday's sends) and upserts
 * them into SMS__c on SMS_Key__c = SubscriberKey|SMSJobID. Replaces the "SMS Creation" journey, whose
 * Once-and-done entry setting recorded each person's first text only.
 *
 * Auth: legacy Named Credential SFMC_Auth (Password protocol, client id as username, client secret as
 * password, merge fields in body) -> POST /v2/token, then the REST instance URL from the token response
 * (Remote Site Setting SFMC_REST). Same pattern as Customer360FeedController.
 *
 * Schedule once (anonymous Apex), 16:30 UTC, after the 16:00 UTC Marketing Cloud query:
 *   System.schedule('SMS Tracking Sync', '0 30 16 * * ?', new SMSTrackingSyncSchedule());
 * (Apex forbids one class implementing both Schedulable and Queueable, hence the small scheduler class.)
 * Backfill: widen the SMSData query window in Marketing Cloud, run that automation, then
 *   System.enqueueJob(new SMSTrackingSync());
 * Reruns are idempotent because of the external id.
 *
 * Times: Marketing Cloud returns CreateDateTime in server time (UTC-6, no DST). Converted to UTC here.
 */
public with sharing class SMSTrackingSync implements Queueable, Database.AllowsCallouts {

    public static final String DEFAULT_DE_KEY = 'smsmessagetracking_v2';   // keyed DE created 2026-11-02, filled by query SMSData_v2
    public static final Integer DEFAULT_PAGE_SIZE = 2500;
    public static final Integer DEFAULT_MAX_PAGES = 40;
    public static final Integer SERVER_OFFSET_HOURS = 6;
    @TestVisible private static final String DEFAULT_REST = 'https://mcc1cvpxyff-2m9gnqqpjc4qdg64.rest.marketingcloudapis.com/';

    // state carried across chained queueables
    private Integer page = 1;
    private String token;
    private String restBase;
    private Integer rowsRead = 0;
    private Integer upserted = 0;
    private Integer errors = 0;
    private String firstError;
    private Datetime startedAt;

    public SMSTrackingSync() {}

    // ---- Queueable: one page per execution ----
    public void execute(QueueableContext qc) {
        SMS_Sync_Setting__c cfg = SMS_Sync_Setting__c.getOrgDefaults();
        Integer pageSize = cfg.Chunk_Size__c == null ? DEFAULT_PAGE_SIZE : Integer.valueOf(cfg.Chunk_Size__c);
        Integer maxPages = cfg.Batch_Pages__c == null ? DEFAULT_MAX_PAGES : Integer.valueOf(cfg.Batch_Pages__c);
        String deKey = String.isBlank(cfg.DE_Key__c) ? DEFAULT_DE_KEY : cfg.DE_Key__c;
        if (startedAt == null) startedAt = Datetime.now();

        Boolean more = false;
        try {
            if (token == null) authenticate();
            Map<String, Object> body = fetchPage(deKey, page, pageSize);
            List<Object> items = (List<Object>) body.get('items');
            Integer total = body.get('count') == null ? 0 : (Integer) body.get('count');
            if (items == null) items = new List<Object>();
            rowsRead += items.size();
            upsertRows(toRecords(items));
            more = items.size() == pageSize && rowsRead < total && page < maxPages;
        } catch (Exception e) {
            errors++;
            if (firstError == null) firstError = e.getMessage();
            more = false;
        }

        if (more && !Test.isRunningTest()) {
            page++;
            System.enqueueJob(this);
        } else {
            writeSummary(cfg);
        }
    }

    // ---- Marketing Cloud ----
    private void authenticate() {
        HttpRequest req = new HttpRequest();
        req.setEndpoint('callout:SFMC_Auth/v2/token');
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json');
        req.setTimeout(60000);
        req.setBody('{"grant_type":"client_credentials","client_id":"{!$Credential.Username}","client_secret":"{!$Credential.Password}"}');
        HttpResponse res = new Http().send(req);
        if (res.getStatusCode() != 200) throw new SyncException('Token ' + res.getStatusCode() + ': ' + left(res.getBody(), 200));
        Map<String, Object> parsed = (Map<String, Object>) JSON.deserializeUntyped(res.getBody());
        token = (String) parsed.get('access_token');
        restBase = (String) parsed.get('rest_instance_url');
        if (String.isBlank(restBase)) restBase = DEFAULT_REST;
        if (!restBase.endsWith('/')) restBase += '/';
    }

    private Map<String, Object> fetchPage(String deKey, Integer p, Integer size) {
        HttpRequest req = new HttpRequest();
        req.setEndpoint(restBase + 'data/v1/customobjectdata/key/' + deKey + '/rowset?$page=' + p + '&$pageSize=' + size);
        req.setMethod('GET');
        req.setHeader('Authorization', 'Bearer ' + token);
        req.setTimeout(120000);
        HttpResponse res = new Http().send(req);
        if (res.getStatusCode() != 200) throw new SyncException('Rowset ' + res.getStatusCode() + ': ' + left(res.getBody(), 200));
        return (Map<String, Object>) JSON.deserializeUntyped(res.getBody());
    }

    // ---- mapping ----
    @TestVisible
    private static List<SMS__c> toRecords(List<Object> items) {
        List<SMS__c> out = new List<SMS__c>();
        Set<String> seen = new Set<String>();
        for (Object o : items) {
            Map<String, Object> item = (Map<String, Object>) o;
            Map<String, String> row = new Map<String, String>();
            for (String part : new List<String>{ 'keys', 'values' }) {
                Map<String, Object> m = (Map<String, Object>) item.get(part);
                if (m == null) continue;
                for (String k : m.keySet()) row.put(k.toLowerCase(), m.get(k) == null ? null : String.valueOf(m.get(k)));
            }
            String subKey = row.get('subscriberkey');
            String job = row.get('smsjobid');
            if (String.isBlank(subKey) || String.isBlank(job)) continue;
            String key = left(subKey + '|' + job, 80);
            if (seen.contains(key)) continue;   // defensive: query should already be one row per text
            seen.add(key);

            SMS__c r = new SMS__c();
            r.SMS_Key__c = key;
            r.Name = left(String.isBlank(row.get('name')) ? 'SMS' : row.get('name'), 80);
            r.SubscriberKey__c = left(subKey, 254);
            r.CreateDate__c = parseServerTime(row.get('createdatetime'));
            r.Description__c = String.isBlank(row.get('description')) ? null : left(row.get('description'), 254);
            r.ShortCode__c = String.isBlank(row.get('shortcode')) ? null : left(row.get('shortcode'), 100);
            if (!String.isBlank(row.get('smsstandardstatuscodeid'))) {
                try { r.SMSStandardStatusCodeId__c = Decimal.valueOf(row.get('smsstandardstatuscodeid')); } catch (Exception e) {}
            }
            Boolean delivered = isTrue(row.get('delivered'));
            Boolean undelivered = isTrue(row.get('undelivered'));
            r.Status__c = delivered ? 'Delivered' : (undelivered ? 'Undeliverable' : 'Enroute');
            if (subKey.startsWith('00Q') && (subKey.length() == 15 || subKey.length() == 18)) r.Lead__c = subKey;
            else if (subKey.startsWith('003') && (subKey.length() == 15 || subKey.length() == 18)) r.Contact__c = subKey;
            out.add(r);
        }
        return out;
    }

    /** "11/1/2026 3:32:00 PM" or "2026-11-01T15:32:00" in Marketing Cloud server time -> UTC Datetime. */
    @TestVisible
    private static Datetime parseServerTime(String s) {
        if (String.isBlank(s)) return null;
        s = s.trim();
        Datetime d;
        Pattern us = Pattern.compile('^(\\d{1,2})/(\\d{1,2})/(\\d{4})\\s+(\\d{1,2}):(\\d{2})(?::(\\d{2}))?\\s*(AM|PM)?$');
        Matcher m = us.matcher(s);
        if (m.matches()) {
            Integer hh = Integer.valueOf(m.group(4));
            String ap = m.group(7);
            if (ap == 'PM' && hh < 12) hh += 12;
            if (ap == 'AM' && hh == 12) hh = 0;
            d = Datetime.newInstanceGmt(Integer.valueOf(m.group(3)), Integer.valueOf(m.group(1)), Integer.valueOf(m.group(2)),
                                        hh, Integer.valueOf(m.group(5)), m.group(6) == null ? 0 : Integer.valueOf(m.group(6)));
        } else {
            try { d = (Datetime) JSON.deserialize('"' + s.replace(' ', 'T') + '"', Datetime.class); }
            catch (Exception e) { return null; }
            // JSON deserialize treats a zone-less string as GMT, which is what we want before the offset
        }
        return d.addHours(SERVER_OFFSET_HOURS);
    }

    private static Boolean isTrue(String v) {
        return v != null && (v.equalsIgnoreCase('true') || v == '1');
    }

    // ---- DML ----
    private void upsertRows(List<SMS__c> recs) {
        if (recs.isEmpty()) return;
        List<SMS__c> retry = new List<SMS__c>();
        Database.UpsertResult[] results = Database.upsert(recs, SMS__c.SMS_Key__c, false);
        for (Integer i = 0; i < results.size(); i++) {
            if (results[i].isSuccess()) { upserted++; continue; }
            Database.Error err = results[i].getErrors()[0];
            // a subscriber key that is not a live lead/contact id (deleted, converted, malformed): keep the
            // text, drop the lookup, try once more
            if (recs[i].Lead__c != null || recs[i].Contact__c != null) {
                SMS__c r = recs[i].clone(false, true, false, false);
                r.Lead__c = null; r.Contact__c = null;
                retry.add(r);
            } else {
                errors++;
                if (firstError == null) firstError = recs[i].SMS_Key__c + ': ' + err.getMessage();
            }
        }
        if (!retry.isEmpty()) {
            for (Database.UpsertResult ur : Database.upsert(retry, SMS__c.SMS_Key__c, false)) {
                if (ur.isSuccess()) upserted++;
                else { errors++; if (firstError == null) firstError = ur.getErrors()[0].getMessage(); }
            }
        }
    }

    private void writeSummary(SMS_Sync_Setting__c cfg) {
        cfg.Last_Run_At__c = startedAt;
        cfg.Last_Rows_Read__c = rowsRead;
        cfg.Last_Upserted__c = upserted;
        cfg.Last_Errors__c = errors;
        cfg.Last_Error__c = firstError == null ? null : left(firstError, 255);
        upsert cfg;
    }

    private static String left(String s, Integer n) {
        return s == null ? null : (s.length() > n ? s.substring(0, n) : s);
    }

    public class SyncException extends Exception {}
}
