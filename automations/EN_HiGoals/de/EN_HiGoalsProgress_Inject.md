# Data extension: EN_HiGoalsProgress_Inject

New sendable DE that the progress journey is injected from. Same shape as
EN_HiGoalsProgressCompletionFollowUp_AF_07312025 (the Progress DE) plus two columns.
Create it in Contact Builder in the same folder as the Progress DE (category 189602,
"B2C Lifecycle Marketing" BU).

**Fastest way:** open the Progress DE, use *Create from existing* (or copy the DE), name it
`EN_HiGoalsProgress_Inject`, then add the two columns at the bottom. Settings to match:

| Setting | Value |
|---|---|
| Is Sendable | Yes |
| Is Testable | Yes |
| Sendable relationship | `account_id__c` relates to Subscribers on **Subscriber Key** |
| Primary keys | `Customer_Number__c`, `email`, `Id` (same as the Progress DE) |
| Data retention | none (the query overwrites it daily) |

Columns, in order. Types are the Progress DE's own.

| Column | Type | Length | Notes |
|---|---|---|---|
| Added_Driver__c | Boolean | | |
| App_Opened__c | Boolean | | |
| Birthday_Month__c | Number | | |
| Cancel_Date__c | Date | | |
| MailingCity | Text | 50 | |
| CookieID__c | Text | 254 | |
| Created_Account__c | Boolean | | |
| Customer_Number__c | Text | 50 | primary key |
| Distracted_Driving__c | Boolean | | |
| DNR_Flag__c | Boolean | | |
| Driver_Role__c | Text | 50 | |
| driving_patterns__c | Text | 50 | |
| email | EmailAddress | 254 | primary key |
| FirstName | Text | 50 | |
| Future_Flag__c | Boolean | | |
| Inception_transaction_date__c | Date | | |
| inception_transaction_timestamps_user__c | Date | | |
| inception_transaction_timestamps_utc__c | Date | | |
| Jurisdiction__c | Text | 50 | |
| Last_Known_Trip_Date__c | Date | | |
| LastName | Text | 50 | |
| Lifetime_Savings__c | Text | 50 | |
| Logged_Trip__c | Boolean | | |
| OS_Version__c | Text | 50 | |
| Pending_Cancel_Flag__c | Boolean | | |
| Phone | Phone | | |
| Phone_Model__c | Text | 100 | |
| platform__c | Text | 50 | |
| Policy_Effective_Date__c | Date | | |
| Policy_Number__c | Text | 50 | |
| MailingPostalcode | Text | 20 | |
| Property_Ownership_Status__c | Text | 50 | |
| safe_speeds__c | Text | 50 | |
| smooth_driving__c | Text | 50 | |
| et4ae5__HasOptedOutOfMobile__c | Boolean | | |
| MailingState | Text | 50 | |
| telematic_discount__c | Text | 50 | |
| upcoming_billing_date__c | Text | 50 | |
| Vehicle_Make__c | Text | 100 | |
| Vehicle_Model__c | Text | 100 | |
| Id | Text | 18 | primary key |
| account_id__c | Text | 50 | sendable field |
| Has_Renters__c | Text | 50 | |
| HIGoal_DFDR_Completed__c | Boolean | | |
| HIGoal_DFDR_Start_Date__c | Date | | |
| HIGoal_DFDR_Focus_Score__c | Decimal | 18,2 | |
| HIGoal_DFDR_Goal__c | Decimal | 18,2 | |
| HIGoal_DFDR_Final_Focus_Score__c | Decimal | 18,2 | |
| HIGoal_DFDR_Completion_Percentage__c | Number | | |
| higoal_rewards_total__c | Decimal | 18,2 | |
| IsRIEligible | Boolean | | |
| WeeksSinceInception | Number | | |
| Achieved_Flag | Number | | |
| Missed_Flag | Number | | |
| CompletedNotSet_Flag | Boolean | | |
| NewCommit_Flag | Number | | |
| CommittedGoal | Number | | |
| **InjectReason** | Text | 30 | new. Achieved / Missed / CompletedNotSet / Midpoint / NoGoalWeekly |
| **InjectDate** | Date | | new. Day the row was selected; handy for QA |

If you copy the DE instead of building it by hand, text lengths come across automatically
and only the two bold rows need adding. Lengths above are the Progress DE's where the API
reports them; where it does not, they are safe defaults.
