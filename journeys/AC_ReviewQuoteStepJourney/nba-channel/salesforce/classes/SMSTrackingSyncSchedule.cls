/** Daily scheduler for SMSTrackingSync. System.schedule('SMS Tracking Sync', '0 30 16 * * ?', new SMSTrackingSyncSchedule()); */
public with sharing class SMSTrackingSyncSchedule implements Schedulable {
    public void execute(SchedulableContext sc) {
        System.enqueueJob(new SMSTrackingSync());
    }
}
