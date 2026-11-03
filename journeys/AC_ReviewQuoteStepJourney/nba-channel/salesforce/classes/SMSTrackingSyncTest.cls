@IsTest
private class SMSTrackingSyncTest {

    private class Mock implements HttpCalloutMock {
        Integer rowsetStatus = 200;
        public HttpResponse respond(HttpRequest req) {
            HttpResponse res = new HttpResponse();
            res.setHeader('Content-Type', 'application/json');
            if (req.getEndpoint().contains('/v2/token')) {
                res.setStatusCode(200);
                res.setBody('{"access_token":"tok","rest_instance_url":"https://example.rest.marketingcloudapis.com/","expires_in":1079}');
            } else if (req.getEndpoint().contains('/rowset')) {
                res.setStatusCode(rowsetStatus);
                res.setBody(rowsetStatus == 200 ? rowset() : '{"message":"boom"}');
            } else {
                res.setStatusCode(404);
                res.setBody('{}');
            }
            return res;
        }
    }

    private static Lead lead;

    private static String rowset() {
        return '{"count":3,"page":1,"pageSize":2500,"items":[' +
            '{"keys":{"subscriberkey":"' + lead.Id + '","smsjobid":"JOB-1"},"values":{"name":"AC_Review_SE1_01072026_VA","createdatetime":"11/1/2026 3:32:00 PM","description":"Delivered to handset","smsstandardstatuscodeid":"4000","shortcode":"73753","sent":"True","delivered":"True","undelivered":"False"}},' +
            '{"keys":{"subscriberkey":"' + lead.Id + '","smsjobid":"JOB-2"},"values":{"name":"AC_Review_SE2_01072026_VB","createdatetime":"2026-11-01T09:05:00","description":"","smsstandardstatuscodeid":"4505","shortcode":"73753","sent":"True","delivered":"False","undelivered":"True"}},' +
            '{"keys":{"subscriberkey":"00Q000000000000XXX","smsjobid":"JOB-3"},"values":{"name":"AC_SavedQuote_SE1_12012025_V","createdatetime":"11/1/2026 11:59:00 PM","smsstandardstatuscodeid":"2000","delivered":"False","undelivered":"False"}}' +
            ']}';
    }

    @TestSetup
    static void setup() {
        insert new Lead(LastName = 'Texted', Company = 'HiRoad', Phone = '4805551212');
    }

    @IsTest
    static void upsertsOneRowPerTextAndLogsSummary() {
        lead = [SELECT Id FROM Lead LIMIT 1];
        Test.setMock(HttpCalloutMock.class, new Mock());
        Test.startTest();
        System.enqueueJob(new SMSTrackingSync());
        Test.stopTest();

        List<SMS__c> rows = [SELECT SMS_Key__c, Name, Status__c, CreateDate__c, Lead__c, SMSStandardStatusCodeId__c FROM SMS__c ORDER BY SMS_Key__c];
        System.assertEquals(3, rows.size(), 'three texts, three rows');
        Map<String, SMS__c> byKey = new Map<String, SMS__c>();
        for (SMS__c r : rows) byKey.put(r.SMS_Key__c, r);

        SMS__c first = byKey.get(lead.Id + '|JOB-1');
        System.assertEquals('Delivered', first.Status__c);
        System.assertEquals(lead.Id, first.Lead__c, 'lead lookup set from subscriber key');
        System.assertEquals(Datetime.newInstanceGmt(2026, 11, 1, 21, 32, 0), first.CreateDate__c, 'server time 15:32 -> 21:32 UTC');
        System.assertEquals(4000, first.SMSStandardStatusCodeId__c);

        SMS__c second = byKey.get(lead.Id + '|JOB-2');
        System.assertEquals('Undeliverable', second.Status__c);
        System.assertEquals(Datetime.newInstanceGmt(2026, 11, 1, 15, 5, 0), second.CreateDate__c, 'ISO form also shifted');

        // bad lead id: row is still written, without the lookup
        SMS__c third = byKey.get('00Q000000000000XXX|JOB-3');
        System.assertNotEquals(null, third);
        System.assertEquals('Enroute', third.Status__c);

        SMS_Sync_Setting__c cfg = SMS_Sync_Setting__c.getOrgDefaults();
        System.assertEquals(3, cfg.Last_Rows_Read__c);
        System.assertEquals(3, cfg.Last_Upserted__c);
        System.assertEquals(0, cfg.Last_Errors__c);
    }

    @IsTest
    static void rerunIsIdempotent() {
        lead = [SELECT Id FROM Lead LIMIT 1];
        Test.setMock(HttpCalloutMock.class, new Mock());
        insert new SMS__c(SMS_Key__c = lead.Id + '|JOB-1', Name = 'old', SubscriberKey__c = lead.Id);
        Test.startTest();
        System.enqueueJob(new SMSTrackingSync());
        Test.stopTest();
        System.assertEquals(3, [SELECT COUNT() FROM SMS__c]);
        System.assertEquals('AC_Review_SE1_01072026_VA', [SELECT Name FROM SMS__c WHERE SMS_Key__c = :(lead.Id + '|JOB-1')].Name, 'existing row updated, not duplicated');
    }

    @IsTest
    static void rowsetFailureIsLoggedNotThrown() {
        lead = [SELECT Id FROM Lead LIMIT 1];
        Mock m = new Mock(); m.rowsetStatus = 500;
        Test.setMock(HttpCalloutMock.class, m);
        Test.startTest();
        System.enqueueJob(new SMSTrackingSync());
        Test.stopTest();
        SMS_Sync_Setting__c cfg = SMS_Sync_Setting__c.getOrgDefaults();
        System.assertEquals(1, cfg.Last_Errors__c);
        System.assert(cfg.Last_Error__c.startsWith('Rowset 500'), cfg.Last_Error__c);
        System.assertEquals(0, [SELECT COUNT() FROM SMS__c]);
    }

    @IsTest
    static void schedulableEnqueuesTheJob() {
        lead = [SELECT Id FROM Lead LIMIT 1];
        Test.setMock(HttpCalloutMock.class, new Mock());
        Test.startTest();
        String jobId = System.schedule('SMS Tracking Sync test', '0 30 16 * * ?', new SMSTrackingSyncSchedule());
        Test.stopTest();
        System.assertNotEquals(null, jobId);
    }

    @IsTest
    static void parsesServerTimeForms() {
        System.assertEquals(Datetime.newInstanceGmt(2026, 1, 5, 6, 0, 0), SMSTrackingSync.parseServerTime('1/5/2026 12:00:00 AM'));
        System.assertEquals(Datetime.newInstanceGmt(2026, 1, 5, 18, 0, 0), SMSTrackingSync.parseServerTime('1/5/2026 12:00:00 PM'));
        System.assertEquals(null, SMSTrackingSync.parseServerTime(''));
        System.assertEquals(null, SMSTrackingSync.parseServerTime('not a date'));
    }
}
