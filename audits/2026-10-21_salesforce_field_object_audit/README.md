# Salesforce production field and object audit (blueowl-prod), 2026-10-21

Scope: every custom object in the org (111) and every custom field (876) on the 31 objects HiRoad actually works with: Contact, Lead, Account, Opportunity, Case, Task, Campaign, CampaignMember, User, AccountContactRelation and the 21 HiRoad-built custom objects. Managed-package fields on managed objects are covered at object level only.

For each field the audit measured whether it holds data, when the newest record with a value was created ("last new value"), and whether anything in the org reads it: Apex, triggers, active flows, validation rules, other formulas, CRM Analytics dataflows and recipes, LWC and Visualforce, workflow and duplicate rules, reports run in the last 12 months, page layouts and list views, the Marketing Cloud Connect sync (24 `*_Salesforce` data extensions) and the Data Cloud CRM connector (12 streams). Full per-field detail is in `field_audit.csv`; per-object detail in `object_audit.csv`.

## Headline findings

1. **Delete four empty objects now**: `Cookie__c` (16 fields, 0 rows), `Chatbot__c`, `Lead_Behavior__c`, `TestExternalObject__c`.
2. **Archive and delete four dormant HiRoad objects**: `Session_ID__c` (584,728 rows, feed stopped 2025-08-13, Rollup Helper trigger still active), `Records__c` (last row 2023-09), `Referral__c` (last row 2023-07), `Survey__c` (last row 2022-10, replaced by `Forsta_Survey__c`). Together with the dormant standard objects (Opportunity: one load on 2022-08-29; Case: 2 rows; Campaign: 28 rows from 2022; CampaignMember: 1 row) that is 102 custom fields nobody uses, and four Data Cloud streams still ingesting dead objects.
3. **Feeds that stopped silently while the object kept growing** (section 2). The ones that matter most:
   - `Streak__c.Contact__c` and `customer_number__c`: no streak created since 2025-10-22 carries a customer link, so a year of streaks cannot be joined to Contacts (Customer 360 LWC and the churn features read them).
   - `SMS__c.Lead__c` not set since 2025-06-09, `SMS__c.Status__c` since 2024-11-26; `ActionDateTime__c` and `Contact__c` were never populated although Customer360Controller reads them.
   - Lead trial-mode cluster (`Trial_Mode__c`, `Trip_Taken__c`, `App_Downloaded__c`, `Account_Created__c`, `Permissions_Enabled__c`, `Eligible_to_Re_quote__c`, `Eligibile_discount__c`, `Trial_Mode_Trip_Completion__c`, `Customer_Number__c`, `account_id__c`): nothing written since 2026-03-11.
   - `Lead.of_SMS_Delivered__c` (84% populated) nothing since 2025-08-06; `Lead.Current_Journey__c` (46%) since 2025-03-19; `Lead.Jurisdiction__c` (26%) since 2025-07-28; `Lead.Parent__c` (54%) since 2025-08-13.
   - `Individual` and `ContactPointEmail` (consent objects) stopped 2025-07-26.
   - `Meta_API_Log__c` has no row since 2026-09-25 although the Meta Conversions API trigger is active.
   - `Zen_Desk_Ticket__c.Email_Address__c` was only filled in the first CSV load (2025-11-06).
   - `Bill__c`: 10 columns added in 2025-10 and 2026-01 (`Authorization_Code__c`, `Billing_Cycle__c`, `Currency__c`, `Failure_Reason_Code__c`, `Payment_Method_Type__c`, `Source_System__c`, `Policy_Payment_Amount__c`, `Bill_Amount__c`, `Failure_Reason_Text__c`, `Payment_Amount__c`) have never received a value across 1.0M bills; the last three are read by Customer360Controller.
4. **147 field deprecation candidates** (section 3): 88 never populated and unreferenced, 36 stale for 12+ months and unreferenced, 23 formula fields referenced nowhere. 21 of the formulas are the Contact `*_Policy__c` set created 2025-11, which is on no layout, in no sync and in no automation.
5. **28 fields have no field-level security for anyone**, including System Administrator, so nothing can read them: the 25 `Journey_Monitor_*` fields deployed 2026-10-17 (grant FLS before the monitor runs) and `Case.Customer_Number__c`, `Claim__c.ClaimNumber__c`, `Account.rh2__Describe__c` (delete).
6. **Managed packages** (section 1b): LinkedIn Sales Navigator, Jira Cloud, mafaili, Address Picker for Flow, Lead Capture, Language Switcher, Launch Flow Modal, EasyDescribe, SalesforceIQ, Sales Insights and the Zendesk package show no data and no references. Nightfall DLP has 14 active triggers on every Lead/Contact DML but has never written a log row: confirm the subscription is live or uninstall. Rollup Helper's `PS_System_Maint` schedule was aborted 168 times in 30 days.
7. **Customer360Controller reads fields that are empty or dead** (`Bill__c.Payment_Amount__c`, `Bill_Amount__c`, `Failure_Reason_Text__c`; `Contact.Policy_Start_Date__c`, `Has_App__c`, `Underwriting_Score__c`, `PolicyStatus__c`, `Inception_Date__c`, `Policy_Renewal_Date__c`; `SMS__c.ActionDateTime__c`, `Contact__c`). Those sections of the LWC render blank; either restore the feeds or drop the reads.

Most of the remaining "review" rows (241 fields) are integration-written fields with no in-org consumer other than the MC sync or the Data Cloud stream; they are fine to keep but each one costs sync and ingest volume, so the MC and Data Cloud field lists are worth pruning against this CSV.

## Suggested order of work

1. Grant FLS on the Journey Monitor fields (blocks the monitor).
2. Fix or consciously retire the stopped feeds in section 2, starting with `Streak__c.Contact__c` and the Bill columns, then clean the Customer360Controller reads.
3. Delete the four empty objects and the three no-FLS fields; archive and delete the dormant objects; remove the Opportunity, Case, Campaign and CampaignMember Data Cloud streams.
4. Deprecate the section 3 fields in two waves: never-populated first (no data loss), then the stale set after a 30-day hide-from-layouts period. Remove each from the MC sync and Data Cloud stream first where flagged.
5. Uninstall the unused packages after confirming with their original owners.

## 1. Objects

### 1a. HiRoad custom objects and key standard objects

| Object | Records | First record | Last record created | Custom fields | MC sync | Data Cloud | Verdict | Notes |
|---|---:|---|---|---:|:-:|:-:|---|---|
| Contact | 92,591 | 2022-10-06 | 2026-10-21 | 169 | yes | yes | **ACTIVE** | Active. |
| Lead | 1,039,787 | 2021-02-10 | 2026-10-21 | 157 | yes | yes | **ACTIVE** | Active. |
| Account | 81,417 | 2021-11-15 | 2026-10-21 | 67 | yes | yes | **ACTIVE** | Active. |
| Bill__c | 1,014,462 | 2026-01-23 | 2026-10-21 | 40 | yes | yes | **ACTIVE** | Active (1.0M rows). 10 fields from the 2025-10/2026-01 schema additions have never received data, 3 of them are read by Customer360Controller. |
| MobileApp__c | 2,187,308 | 2024-09-25 | 2026-10-21 | 7 |  | yes | **ACTIVE** | Active (2.2M rows). |
| Monthly_Driving_Stat__c | 219,802 | 2023-05-09 | 2026-10-21 | 35 | yes | yes | **ACTIVE** | Active (219,802 rows). email_verified__c never populated. |
| Streak__c | 505,631 | 2023-06-07 | 2026-10-21 | 6 | yes |  | **ACTIVE** | Active (505k rows) but Contact__c and customer_number__c have not been set on any record created since 2025-10-22: new streaks cannot be joined to customers. |
| SMS__c | 203,716 | 2023-04-14 | 2026-10-21 | 9 | yes | yes | **ACTIVE** | Active, but Lead__c lookup not set since 2025-06-09 and Status__c not set since 2024-11-26; ActionDateTime__c and Contact__c never populated. |
| Zen_Desk_Ticket__c | 97,645 | 2025-11-06 | 2026-10-02 | 53 |  | yes | **ACTIVE** | Loaded by CSV (last 2026-10-02). Email_Address__c only populated in the first load (2025-11-06); later loads leave it blank. |
| Forsta_Survey__c | 302 | 2026-03-16 | 2026-10-20 | 138 |  | yes | **ACTIVE** | Live since 2026-03 (302 rows). 25 fields never populated and 22 empty fields referenced only by name; see field table. |
| Claim__c | 5,464 | 2024-02-01 | 2026-10-21 | 7 |  |  | **ACTIVE** | Active (5,464 rows). CloseDate__c and n_claim_close_period__c never populated; ClaimNumber__c has no FLS. |
| Renewal_Offer__c | 7,637 | 2026-10-20 | 2026-10-21 | 9 | yes | yes | **ACTIVE** | New 2026-10-20, flowing. |
| Process_Error__c | 56 | 2026-06-15 | 2026-10-20 | 11 |  |  | **ACTIVE** | Active, 56 rows since 2026-06. |
| Meta_API_Log__c | 1,309 | 2026-04-06 | 2026-09-25 | 7 |  |  | **ACTIVE** | Last log row 2026-09-25 although LeadMetaTrigger / MetaConversionsAPI are active. Verify the Meta Conversions API call is still firing. |
| Task | 1,046 | 2020-07-01 | 2026-10-21 | 0 |  |  | **ACTIVE** | Active (NBA call tasks). |
| Event | 264 | 2025-10-13 | 2026-10-16 | 0 |  |  | **ACTIVE** | 264 rows since 2025-10. |
| Journey_Monitor_Run__c | 0 |  |  | 11 |  |  | **EMPTY** | Deployed 2026-10-17, 0 rows; fields have no FLS even for System Administrator. Grant FLS via the permission set before the monitor runs. |
| Journey_Monitor_Result__c | 0 |  |  | 18 |  |  | **EMPTY** | Same as Journey_Monitor_Run__c. |
| Session_ID__c | 584,728 | 2021-12-18 | 2025-08-13 | 3 |  |  | **DORMANT 12+ months** | 584,728 rows; feed stopped 2025-08-13. Rollup Helper trigger RHX_Session_ID still fires. Archive and delete, or confirm the feed is meant to be off and remove the rollup. |
| Records__c | 22,821 | 2022-07-27 | 2023-09-05 | 28 |  |  | **DORMANT 12+ months** | 22,821 rows, 2022-07 to 2023-09. 28 fields, Contact lookups. Dormant; archive and delete. |
| Referral__c | 71 | 2022-06-28 | 2023-07-18 | 5 | yes |  | **DORMANT 12+ months** | 71 rows, last 2023-07; Lead.Referral_Record__c never populated. Dormant; delete with its Lead/Contact lookup fields. |
| Survey__c | 1,034 | 2021-11-15 | 2022-10-02 | 4 | yes |  | **DORMANT 12+ months** | 1,034 rows, last 2022-10. Superseded by Forsta_Survey__c (live since 2026-03). Archive and delete; also drop Survey__c_Salesforce from the MC sync. |
| Opportunity | 3,395 | 2022-08-29 | 2022-08-29 | 35 |  | yes | **DORMANT 12+ months** | 3,395 rows all created 2022-08-29 (one load). 35 custom fields, none in use. Dormant B2B experiment; also stop its Data Cloud stream. |
| Case | 2 | 2023-01-23 | 2024-05-08 | 23 | yes | yes | **DORMANT 12+ months** | 2 rows (2023-01, 2024-05). 23 custom fields. Not used; stop its Data Cloud stream. |
| Campaign | 28 | 2020-07-01 | 2022-10-07 | 1 |  | yes | **DORMANT 12+ months** | 28 rows, last 2022-10. Stop its Data Cloud stream. |
| CampaignMember | 1 | 2021-02-19 | 2021-02-19 | 1 |  | yes | **DORMANT 12+ months** | 1 row from 2021. Stop its Data Cloud stream. |
| Individual | 77,200 | 2021-11-13 | 2025-07-26 | 0 |  |  | **DORMANT 12+ months** | 77,200 rows, feed stopped 2025-07-26. |
| ContactPointEmail | 74,300 | 2021-11-13 | 2025-07-26 | 0 |  |  | **DORMANT 12+ months** | 74,300 rows, feed stopped 2025-07-26. |
| ContactPointPhone | 1 | 2021-11-13 | 2021-11-13 | 0 |  |  | **DORMANT 12+ months** | 1 row from 2021. |
| Cookie__c | 0 |  |  | 16 |  |  | **EMPTY** | 0 records; 16 fields; created 2023-01. Delete object. |
| Chatbot__c | 0 |  |  | 4 |  |  | **EMPTY** | 0 records; created 2024-10. Delete object. |
| Lead_Behavior__c | 0 |  |  | 1 |  |  | **EMPTY** | 0 records; 1 field; created 2025-07. Delete object. |
| TestExternalObject__c | 3 | 2023-04-13 | 2023-04-13 | 1 |  |  | **DORMANT 12+ months** | 3 test rows from 2023-04. Delete object. |

### 1b. Managed-package objects

| Namespace | Package | Objects | Rows (sum of queryable) | Last record | Evidence of use | Verdict |
|---|---|---:|---:|---|---|---|
| CFCRM10 | CRM Connector for Salesforce | 1 | 2 | 2026-03-03 | Forsta connector: 2 hashtable rows 2026-03, feeds Forsta_Survey__c | **KEEP** |
| ConnectorUtil | User Provisioning Connector Utils | 0 | 0 |  |  | **REVIEW** |
| DV_Flow_AP | Address Picker Autocomplete for Flow | 1 | 0 |  | Address picker for Flow: 0 settings rows, no flow references | **UNINSTALL** |
| EasyDescribe | EasyDescribe | 0 | 0 |  | no references | **UNINSTALL** |
| JCFS | Jira Cloud for Salesforce | 4 | 0 |  | Jira Cloud: 0 rows in all objects; referenced only on 3 page layouts | **UNINSTALL** |
| LID | SN for SFDC | 7 | 1 | 2023-11-30 | LinkedIn Sales Navigator: 1 OAuth row from 2023-11, 0 logs, 9 empty fields on Contact/Lead/Account + validation rule | **UNINSTALL** |
| MCCA5PROD | MarketingCloudConnectedApp | 0 | 0 |  | MC connected app | **KEEP** |
| OIQ | Sales Insights | 0 | 0 |  | Sales Insights: no references | **UNINSTALL** |
| SCSConnectedApp | SCS Connected App | 0 | 0 |  |  | **REVIEW** |
| SIQCloud | SalesforceIQ Cloud | 0 | 0 |  | SalesforceIQ: no references | **UNINSTALL** |
| SocialService | SocialCustomerService | 0 | 0 |  |  | **REVIEW** |
| UMsgConsentProd | UnifiedMessagingConsent | 0 | 0 |  | Unified Messaging Consent; Data Cloud ingest streams last ran 2025-04 | **REVIEW** |
| cdp_crm_dk1 | Sales Cloud | 0 | 0 |  | Data Cloud Sales Cloud kit | **KEEP** |
| cdp_mrktng_base | Salesforce CDP CRM Marketing Base | 0 | 0 |  | Data Cloud marketing base | **KEEP** |
| cdpactvstrgptnr | CDPAdvertising | 0 | 0 |  | CDP advertising activation credential object, no references | **REVIEW** |
| datacloudflow | Salesforce Data Cloud - Flow Integration | 0 | 0 |  | Data Cloud flow integration | **KEEP** |
| et4ae5 | Marketing Cloud | 25 | 3,855,237 | 2026-10-21 | Marketing Cloud Connect sync + 14 active triggers; IER feed daily | **KEEP** |
| mafaili | mafaili | 2 | 0 |  | 0 rows (2023-06) | **UNINSTALL** |
| michi7 | Language Switcher | 0 | 0 |  | Language Switcher: no references | **UNINSTALL** |
| mktg_dcr | Marketing Analytics | 0 | 0 |  | Marketing Analytics: no references | **REVIEW** |
| nfdlp | Nightfall DLP | 3 | 0 |  | Nightfall DLP: 14 active triggers on every DML, 0 ApexLog rows, no settings rows | **VERIFY subscription; uninstall if lapsed (triggers cost CPU on Lead/Contact DML)** |
| optimizely_dna | Optimizely DNA | 19 | 676,160 | 2026-10-21 | Daily experiment batches, 12 active triggers, Lead visitor ids written daily | **KEEP** |
| pies | Salesforce Connect Validator | 0 | 0 |  | Salesforce Connect Validator: 1 class reference | **REVIEW** |
| rh2 | Rollup Helper | 17 | 12 | 2025-06-10 | Rollup Helper: hourly batch, 10 triggers; but PS_System_Maint aborted 168 times and PS_ScheduledDispatcher 43 times in 30 days; test fields rh2__*Test__c on Contact/Account never used | **KEEP, fix the aborted schedule, delete rh2 test fields** |
| sf_chttr_apps | Salesforce Mobile Apps | 0 | 0 |  |  | **KEEP** |
| sf_com_apps | Salesforce Connected Apps | 0 | 0 |  |  | **KEEP** |
| sf_flowmodal | Launch Flow Modal | 0 | 0 |  | Launch Flow Modal: no references | **UNINSTALL** |
| sfleadcaphfprod | Lead Capture | 0 | 0 |  | Lead Capture: External_Lead_ID__c on Lead never populated | **UNINSTALL** |
| slackv2 | Slack | 11 | 182 | 2023-10-03 | 244 sendSubscriptionEvent jobs in 30 days (47 subscriptions) | **KEEP (review the 47 subscriptions)** |
| ssot | Salesforce Standard Data Model | 0 | 0 |  | Data Cloud standard model | **KEEP** |
| zdsf | Salesforce Integration for Zendesk | 0 | 0 |  | Zendesk integration package: no references (tickets arrive by CSV into Zen_Desk_Ticket__c) | **UNINSTALL** |

Unmanaged packages with no namespace (Graphics Pack, Generate Orders, AnyCalendar, CRM Dashboards, AppExchange Service & Support Dashboards, PRM dashboards): no object data; the only one with recent use is "What has changed in the last 7 days" (dashboard viewed 2026-10-21). The rest are uninstall candidates once their dashboards are confirmed unused.

## 2. Fields that stopped receiving data (still referenced)

"Last new value" is the CreatedDate of the newest record where the field is populated. The object itself is still receiving records, so a stale date means the writer stopped setting this field.

| Object | Field | Populated | Last new value | Still referenced by |
|---|---|---:|---|---|
| Account | `Inception_Date__c` | 1,339 (1.6%) | 2022-11-17 | Apex: Customer360Controller |
| Account | `Master_Record__c` | 1,293 (1.6%) | 2022-11-17 | Apex: MarkMasterLeadRecords;MarkMasterLeadRecordsTest; flows: Re_engaged; reports: Quote Conversions By Day All Time |
| Account | `Active_CA_NDA__c` | 1 (0.0%) | 2023-09-15 | CRM Analytics: X11222023Acct;X112723AcctOpp1 |
| Account | `Google_Drive_Documents__c` | 1 (0.0%) | 2023-09-15 | CRM Analytics: X11222023Acct;X112723AcctOpp1 |
| Contact | `PolicyStatus__c` | 1,626 (1.8%) | 2022-11-17 | Apex: Customer360Controller;Customer360Tests; formulas: Policy_Status_Policy__c;Status_HH_CC__c; CRM Analytics: Personas_and_Lead_Sources |
| Contact | `Purchased__c` | 1,627 (1.8%) | 2022-11-21 | Apex: LeadMetaTrigger;LeadPurchaseConversionBatchTest;MetaConversionsAPITest |
| Contact | `Session_ID__c` | 1 (0.0%) | 2022-12-31 | Apex: LeadConversionBatch;LeadConversionBatchTest;RHX_Session_ID;RHX_TEST_Se |
| Contact | `Current_Journey__c` | 1,372 (1.5%) | 2023-04-03 | workflow: Lead |
| Contact | `Inception_Date__c` | 1,236 (1.3%) | 2023-11-22 | Apex: Customer360Controller; formulas: Next_Year_Anniversary_Date__c;of_Years_Inforce__c |
| Contact | `Master_Record__c` | 18,876 (20.4%) | 2023-11-22 | Apex: MarkMasterLeadRecords;MarkMasterLeadRecordsTest; flows: Re_engaged |
| Contact | `et4ae5__HasOptedOutOfMobile__c` | 56 (0.1%) | 2024-02-09 | Apex: Customer360Controller; flows: JBSystemFlow_Lead |
| Forsta_Survey__c | `CLAIMS_MAX_DAYS_TO_FIRST_PAYMENT__c` | 1 (0.3%) | 2026-03-16 | reports: New Forsta Survey Report |
| Lead | `Converted_Source__c` | 2,951 (0.3%) | 2022-08-21 | Apex: Customer360Controller |
| Lead | `Referred_By_Lead__c` | 11 (0.0%) | 2022-09-16 | Apex: LeadReferredUpdateBatch;LeadReferredUpdateBatchTest |
| Lead | `Age_Range__c` | 4,491 (0.4%) | 2022-11-01 | reports: 90 Lead Report |
| Lead | `Campaignid__c` | 589 (0.1%) | 2022-11-06 | Apex: LeadConversionBatch;LeadConversionBatchTest; flows: JBSystemFlow_Lead |
| Lead | `Zipcode__c` | 140,033 (13.5%) | 2023-01-02 | workflow: Lead |
| Lead | `Test_Record__c` | 5 (0.0%) | 2024-04-17 | flows: Test_Update |
| Lead | `Site_Referred__c` | 110,811 (10.7%) | 2024-07-17 | Apex: LeadReferredUpdateBatch;LeadReferredUpdateBatchTest |
| Lead | `Current_Journey__c` | 478,444 (46.0%) | 2025-03-19 | workflow: Lead |
| Lead | `Inception_Date_Time__c` | 2 (0.0%) | 2025-06-10 | Apex: LeadActivityEvaluator;LeadActivityEvaluatorTest;LeadTrigger |
| Lead | `Last_Activity_Before_Conversion__c` | 2 (0.0%) | 2025-06-10 | Apex: LeadActivityEvaluator;LeadActivityEvaluatorTest |
| Lead | `Jurisdiction__c` | 271,227 (26.1%) | 2025-07-28 | Apex: Customer360Controller;Customer360Tests; flows: Update_AZ; reports: Leads By Week |
| Lead | `Recommended_Channel__c` | 4 (0.0%) | 2025-08-06 | Apex: Customer360Controller; formulas: Recommended_Channel_Image__c |
| Lead | `of_SMS_Delivered__c` | 876,880 (84.3%) | 2025-08-06 | Apex: Customer360Controller;Customer360Tests |
| Lead | `Parent__c` | 561,283 (54.0%) | 2025-08-13 | Apex: MarkMasterLeadRecords;MarkMasterLeadRecordsTest |
| Lead | `Disabled_At__c` | 150 (0.0%) | 2026-02-25 | flows: JBSystemFlow_Lead |
| Lead | `Customer_Number__c` | 3,770 (0.4%) | 2026-03-11 | Apex: Customer360Controller;Customer360Tests; flows: Assign_Contact_to_Bill;Create_Claim_from_Claim_Flag;Policy_to_Contact_ |
| Lead | `account_id__c` | 3,997 (0.4%) | 2026-03-11 | Apex: Customer360Controller |
| Meta_API_Log__c | `Error_Message__c` | 2 (0.2%) | 2026-04-06 | Apex: MetaConversionsAPI; flows: SUB_Create_Process_Error_Send_Email |
| SMS__c | `Status__c` | 44,396 (21.8%) | 2024-11-26 | Apex: Customer360Controller;Customer360Tests;MetaConversionsAPI;MetaConversi |
| SMS__c | `Lead__c` | 96,111 (47.2%) | 2025-06-09 | Apex: Customer360Controller;LeadActivityEvaluator;LeadActivityEvaluatorTest; |
| Streak__c | `Contact__c` | 159,799 (31.6%) | 2025-10-22 | Apex: Customer360Controller; flows: Assign_Contact_to_Bill;Create_Claim_from_Claim_Flag;Streak |
| Streak__c | `customer_number__c` | 184,904 (36.6%) | 2025-10-22 | Apex: Customer360Controller; flows: Policy_to_Contact_Association;Streak |

Feeds that stopped without any reference left behind (6-12 months, Lead trial-mode cluster and others):

| Object | Field | Populated | Last new value |
|---|---|---:|---|
| Lead | `Account_Created__c` | 3,765 (0.4%) | 2026-03-11 |
| Lead | `App_Downloaded__c` | 2,721 (0.3%) | 2026-03-07 |
| Lead | `Eligibile_discount__c` | 3,770 (0.4%) | 2026-03-11 |
| Lead | `Eligible_to_Re_quote__c` | 1,086 (0.1%) | 2026-03-05 |
| Lead | `Permissions_Enabled__c` | 1,999 (0.2%) | 2026-03-05 |
| Lead | `Trial_Mode_Trip_Completion__c` | 3,770 (0.4%) | 2026-03-11 |
| Lead | `Trial_Mode__c` | 12,304 (1.2%) | 2026-03-11 |
| Lead | `Trip_Taken__c` | 2,061 (0.2%) | 2026-03-05 |
| Lead | `mindful_driver__c` | 65,877 (6.3%) | 2025-12-11 |
| Account | `Non_Pay_Status__c` | 9,028 (11.1%) | 2025-11-08 |
| Zen_Desk_Ticket__c | `Email_Address__c` | 48,150 (49.3%) | 2025-11-06 |

## 3. Deprecation candidates

### Contact

**Never populated, not referenced by code, flows, validation rules, formulas, CRM Analytics or reports (22):** `Acknowledgment__c`, `Comments__c`, `CreatedDate__c`, `Entry_Date__c`, `Group__c`, `HIGoal_DFDR_Completed__c`, `Has_Auto__c`, `Inforce__c`, `Internal_Traffic__c`, `LID__LinkedIn_Member_Token__c`, `LID__No_longer_at_Company__c`, `Monthly_Safe_Driving_Discount__c`, `PolicyStatusCd__c`, `Policy_Purchase_Date__c`, `Term_Renewal_Rate__c`, `UpdatedDate__c`, `ZD_Email_Tag__c`, `of_Sessions__c`, `optimizely_dna__Visitor_Id__c`, `rh2__Describe__c`, `rh2__Integer_Test__c`, `total_earned_discount__c`

**Stale 12+ months and unreferenced (9):**

| Field | Populated | Last new value | Created |
|---|---:|---|---|
| `App_Version__c` | 5,150 (5.6%) | 2023-12-19 | 2023-12-19 |
| `Email_Verified__c` | 1 (0.0%) | 2023-05-30 | 2021-07-15 |
| `Gas_Buddy__c` | 232 (0.3%) | 2023-12-04 | 2023-09-26 |
| `Inception_transaction_date__c` | 22,450 (24.2%) | 2023-09-05 | 2021-03-09 |
| `Logged_Trip__c` | 11,352 (12.3%) | 2023-07-31 | 2021-03-09 |
| `OS_Version__c` | 12,138 (13.1%) | 2023-07-31 | 2023-05-04 |
| `Phone_Model__c` | 12,140 (13.1%) | 2023-07-31 | 2023-05-04 |
| `Primary_Contact__c` | 1 (0.0%) | 2023-09-15 | 2023-07-20 |
| `Typing_Date__c` | 1,069 (1.2%) | 2022-11-17 | 2023-02-10 |

**Formula fields referenced nowhere, not on any layout, not synced (21):** `Cancel_Date_Policy__c`, `Cancellation_Reason_Policy__c`, `Claim_Close_Date_Policy__c`, `Claim_Flag_Policy__c`, `Claim_Number_Policy__c`, `DNR_Flag_Policy__c`, `Effective_Date_Policy__c`, `Future_Flag_Policy__c`, `In_Force_Policy__c`, `Increase_Amount_Dollars_Policy__c`, `Lifetime_Savings_Policy__c`, `Offered_Rate_Change_Policy__c`, `Pending_Cancel_Flag_Policy__c`, `Policy_Renewal_Rate_Policy__c`, `Policy_Status_Policy__c`, `Renewal_Offer_Date_Policy__c`, `Underwriting_Score_Policy__c`, `Upcoming_Billing_Date_Policy__c`, `Vehicle_Make_Policy__c`, `Vehicle_Model_Policy__c`, `rh2__Formula_Test__c`

### Lead

**Never populated, not referenced by code, flows, validation rules, formulas, CRM Analytics or reports (20):** `CookieIDTimeDate__c`, `CreatedDate__c`, `Eligible_to_Requote_Label__c`, `FirstTripStartTime__c`, `Hard_Brake__c`, `Ind_id__c`, `Insurance_Status__c`, `LID__LinkedIn_Member_Token__c`, `LastTripEndTime__c`, `Most_likely_to_purchase__c`, `Projected_Bundled_Dollars_Off__c`, `Projected_Bundled_First_Month_Bill__c`, `Referral_Record__c`, `Resume_Link__c`, `Shopping__c`, `SourcePartner__c`, `UpdatedDate__c`, `of_Vehicles__c`, `platform__c`, `sfleadcaphfprod__External_Lead_ID__c`

**Stale 12+ months and unreferenced (27):**

| Field | Populated | Last new value | Created |
|---|---:|---|---|
| `City__c` | 142,192 (13.7%) | 2024-03-26 | 2021-10-26 |
| `County__c` | 139,333 (13.4%) | 2022-11-10 | 2021-10-26 |
| `Driver_Id__c` | 258 (0.0%) | 2024-06-12 | 2024-03-13 |
| `First_Trip_Taken__c` | 2 (0.0%) | 2023-07-06 | 2023-06-22 |
| `Gender__c` | 4,406 (0.4%) | 2021-12-01 | 2021-12-01 |
| `Hard_Turn__c` | 1 (0.0%) | 2024-03-26 | 2024-03-13 |
| `KeepPosted__c` | 6 (0.0%) | 2025-03-19 | 2025-03-11 |
| `Mindful_Driver_text__c` | 25,682 (2.5%) | 2024-12-03 | 2023-10-31 |
| `Over_Speeding__c` | 1 (0.0%) | 2024-03-26 | 2024-03-13 |
| `Permissions_Set_Date__c` | 2 (0.0%) | 2023-07-06 | 2023-06-22 |
| `Phone_Use__c` | 1 (0.0%) | 2024-03-26 | 2024-03-13 |
| `Previous_Insurance__c` | 231 (0.0%) | 2024-06-12 | 2024-03-13 |
| `Prospect_Segment__c` | 201,662 (19.4%) | 2023-11-29 | 2023-10-04 |
| `Publisher__c` | 239 (0.0%) | 2024-06-12 | 2024-03-13 |
| `Rapid_Acceleration__c` | 1 (0.0%) | 2024-03-26 | 2024-03-13 |
| `Referred_By__c` | 1 (0.0%) | 2023-07-28 | 2022-08-16 |
| `Score__c` | 1 (0.0%) | 2024-03-26 | 2024-03-13 |
| `Sent_to_CC__c` | 1,043 (0.1%) | 2024-12-05 | 2024-10-25 |
| `Street_Address__c` | 119,659 (11.5%) | 2024-03-26 | 2021-10-26 |
| `Sub_Status__c` | 1 (0.0%) | 2022-02-18 | 2021-09-16 |
| `Trial_Mode_Start_Date__c` | 2 (0.0%) | 2023-07-06 | 2023-06-22 |
| `Zip_Code__c` | 5,985 (0.6%) | 2024-03-26 | 2021-10-26 |
| `landing_page_url__c` | 159,447 (15.3%) | 2024-12-04 | 2023-01-19 |
| `numberoftrips__c` | 1 (0.0%) | 2024-03-26 | 2024-03-13 |
| `of_Sessions__c` | 157,503 (15.1%) | 2025-06-10 | 2021-12-17 |
| `of_Trips_Logged__c` | 2 (0.0%) | 2023-07-06 | 2023-06-22 |
| `totaldistance__c` | 1 (0.0%) | 2024-03-26 | 2024-03-13 |

**Formula fields referenced nowhere, not on any layout, not synced (1):** `WHCDB_Days_since_last_update_or_activity__c`

### Account

**Never populated, not referenced by code, flows, validation rules, formulas, CRM Analytics or reports (11):** `AcxHH_Link__c`, `Household_Status__c`, `Monthly_Rate_After_Discounts__c`, `Prompt_Builder_Summary__c`, `State_Farm_Customer__c`, `Status_HH_CC__c`, `Yesterday_Renewal_Rate_Increase_PCT__c`, `hh_id__c`, `hh_size__c`, `ind_id__c`, `rh2__testCurrency__c`

**Formula fields referenced nowhere, not on any layout, not synced (1):** `WHCDB_Days_since_last_update_or_activity__c`

**No field-level security for anyone, including System Administrator (1):** `rh2__Describe__c`

### Bill__c

**Never populated, not referenced by code, flows, validation rules, formulas, CRM Analytics or reports (7):** `Authorization_Code__c`, `Billing_Cycle__c`, `Currency__c`, `Failure_Reason_Code__c`, `Payment_Method_Type__c`, `Policy_Payment_Amount__c`, `Source_System__c`

### Claim__c

**Never populated, not referenced by code, flows, validation rules, formulas, CRM Analytics or reports (2):** `CloseDate__c`, `n_claim_close_period__c`

**No field-level security for anyone, including System Administrator (1):** `ClaimNumber__c`

### Monthly_Driving_Stat__c

**Never populated, not referenced by code, flows, validation rules, formulas, CRM Analytics or reports (1):** `email_verified__c`

### Forsta_Survey__c

**Never populated, not referenced by code, flows, validation rules, formulas, CRM Analytics or reports (25):** `CC_REP_ATTRS_1__c`, `CC_REP_ATTRS_2__c`, `CC_REP_ATTRS_4__c`, `CC_REP_ATTRS_5__c`, `CC_REP_ATTRS_6__c`, `NumEmailsSent__c`, `OPT_IN__c`, `OptOutDate__c`, `OptOut__c`, `RESOLVE_ISSUE__c`, `SurveyEndLink__c`, `hButtonText_next__c`, `hButtonText_ok__c`, `hContactInfo_ErrorMsgs_email2__c`, `hContactInfo_ErrorMsgs_email__c`, `hContactInfo_ErrorMsgs_name__c`, `hContactInfo_ErrorMsgs_phone__c`, `hContactInfo_ErrorMsgs_phone_email__c`, `hDeviceInfoCheck_3__c`, `hDeviceInfoCheck_4__c`, `hEncourage_Prompts_1__c`, `hEncourage_Prompts_2__c`, `hEncourage_Prompts_3__c`, `revised_0__c`, `revised_1__c`

## 4. Empty fields that code or automation still reads

These are either integration gaps (the writer never sends the column) or dead code paths. Fix the feed or remove the reference, then the field.

| Object | Field | Created | Read by |
|---|---|---|---|
| Contact | `BU__c` | 2021-02-08 | formulas: Contact__c |
| Contact | `Campaign_Id__c` | 2021-12-22 | Apex: LeadConversionBatch |
| Contact | `Has_App__c` | 2020-10-23 | Apex: Customer360Controller;Customer360Tests |
| Contact | `LID__LinkedIn_Company_Id__c` | 2023-11-30 | VR: LID__Check_Company_Id_Value |
| Contact | `LandingPageID__c` | 2021-12-22 | Apex: LeadConversionBatch;LeadConversionBatchTest |
| Contact | `Policy_Renewal_Date__c` | 2020-10-15 | Apex: Customer360Controller; formulas: Policy_Renewal_Date_Policy__c |
| Contact | `Policy_Start_Date__c` | 2020-10-22 | Apex: Customer360Controller;Customer360Tests |
| Contact | `Underwriting_Score__c` | 2022-12-15 | Apex: Customer360Controller; formulas: Underwriting_Score_Policy__c |
| Contact | `rh2__Currency_Test__c` | 2021-12-17 | formulas: rh2__Formula_Test__c |
| Lead | `LID__LinkedIn_Company_Id__c` | 2023-11-30 | VR: LID__Check_Company_Id_Value |
| Lead | `Push_to__c` | 2022-10-06 | workflow: Lead |
| Account | `Contact__c` | 2021-02-12 | Apex: Customer360Controller; flows: Assign_Contact_to_Bill;Create_Claim_from_Claim_Flag;Streak |
| Account | `DNR_Flag__c` | 2025-05-20 | Apex: Customer360Controller;Customer360Tests; formulas: DNR_Flag_Policy__c |
| Account | `Jira__c` | 2023-06-08 | CRM Analytics: X11222023Acct;X112723AcctOpp1 |
| Account | `LID__LinkedIn_Company_Id__c` | 2023-11-30 | VR: LID__Check_Company_Id_Value |
| Account | `NDA_CA_Link__c` | 2023-06-15 | CRM Analytics: X11222023Acct;X112723AcctOpp1 |
| Account | `Notes_summary__c` | 2024-06-04 | Apex: EnhancedNoteSummary2 |
| Account | `Reference_Links__c` | 2023-08-25 | CRM Analytics: X11222023Acct;X112723AcctOpp1 |
| Account | `Status_hh__c` | 2021-02-04 | formulas: Status_HH_CC__c |
| Bill__c | `Bill_Amount__c` | 2025-10-06 | Apex: Customer360Controller;Customer360Tests |
| Bill__c | `Failure_Reason_Text__c` | 2025-10-06 | Apex: Customer360Controller |
| Bill__c | `Payment_Amount__c` | 2025-10-06 | Apex: Customer360Controller;Customer360Tests |
| SMS__c | `ActionDateTime__c` | 2023-03-29 | Apex: Customer360Controller |
| SMS__c | `Contact__c` | 2023-03-29 | Apex: Customer360Controller; flows: Assign_Contact_to_Bill;Create_Claim_from_Claim_Flag;Streak |
| Forsta_Survey__c | `CC_REP_ATTRS_3__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `CLAIMS_FNOL_DATE1__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `CurrentEmailDate__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `CurrentEmailStatus__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `GoogleReviewsURL__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `InitialInviteDate__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `LastQAns__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `hButtonText_back__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `hDynamicText_Ex1_ForTranslation__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `hProjectID__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `hRespondentID__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `hScreened__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `invite_status__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_10__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_2__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_3__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_4__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_5__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_6__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_7__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_8__c` | 2026-03-16 | reports: New Forsta Survey Report |
| Forsta_Survey__c | `revised_9__c` | 2026-03-16 | reports: New Forsta Survey Report |

## 5. Field classification counts

| Object | Fields | Keep | Consumed downstream only | Deprecate | Stale, referenced | Empty but referenced | No FLS | Object dormant/empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Contact | 169 | 47 | 53 | 52 | 7 | 9 | 0 | 0 |
| Lead | 157 | 43 | 37 | 48 | 26 | 2 | 0 | 0 |
| Account | 67 | 28 | 12 | 12 | 5 | 8 | 1 | 0 |
| Bill__c | 40 | 12 | 18 | 7 | 0 | 3 | 0 | 0 |
| MobileApp__c | 7 | 5 | 2 | 0 | 0 | 0 | 0 | 0 |
| Monthly_Driving_Stat__c | 35 | 15 | 19 | 1 | 0 | 0 | 0 | 0 |
| Streak__c | 6 | 1 | 3 | 0 | 2 | 0 | 0 | 0 |
| SMS__c | 9 | 2 | 3 | 0 | 2 | 2 | 0 | 0 |
| Zen_Desk_Ticket__c | 53 | 13 | 39 | 0 | 1 | 0 | 0 | 0 |
| Forsta_Survey__c | 138 | 44 | 46 | 25 | 1 | 22 | 0 | 0 |
| Claim__c | 7 | 4 | 0 | 2 | 0 | 0 | 1 | 0 |
| Renewal_Offer__c | 9 | 8 | 1 | 0 | 0 | 0 | 0 | 0 |
| Process_Error__c | 11 | 7 | 4 | 0 | 0 | 0 | 0 | 0 |
| Meta_API_Log__c | 7 | 6 | 0 | 0 | 1 | 0 | 0 | 0 |
| User | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 |
| Opportunity | 35 | 0 | 0 | 0 | 0 | 0 | 0 | 35 |
| Case | 23 | 0 | 0 | 0 | 0 | 0 | 1 | 22 |
| Session_ID__c | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| Records__c | 28 | 0 | 0 | 0 | 0 | 0 | 0 | 28 |
| Referral__c | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| Survey__c | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| Cookie__c | 16 | 0 | 0 | 0 | 0 | 0 | 0 | 16 |
| Chatbot__c | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| Lead_Behavior__c | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| Journey_Monitor_Run__c | 11 | 0 | 0 | 0 | 0 | 0 | 10 | 1 |
| Journey_Monitor_Result__c | 18 | 0 | 0 | 0 | 0 | 0 | 15 | 3 |


## 6. Method and caveats

- Record counts come from the `limits/recordCount` endpoint (approximate for large objects) with `COUNT()` fallback. Activity dates are `ORDER BY CreatedDate DESC LIMIT 1` per object.
- Field population is `COUNT(Id), MAX(CreatedDate)` with `WHERE field != null`. Long-text fields cannot be filtered, so they were measured on the newest 20,000 records (column `measure`); for those, 0 means 0 in the sample. Geolocation compound fields are not measurable.
- References were found by retrieving the metadata (objects, 60 flows, 134 classes, 12 triggers, 157 layouts, 48 flexipages, workflows, 24 CRM Analytics assets) and grepping each field API name, plus the Tooling `MetadataComponentDependency` API (1,967 rows; under its 2,000-row cap per type). Fields with generic names (`Contact__c`, `Status__c`, `Email__c`, `Customer_Number__c`) can pick up references that belong to another object with the same field name; check the `apex`/`flows_active` columns before deleting those.
- Reports: all 595 reports were described through the Analytics API; a report counts as a reference only if it ran in the last 12 months (71 did). Dashboards are not inspected separately.
- Managed-package Apex bodies are hidden, so references from inside packages are invisible. External consumers (Airflow writers, Looker, SFMC query activities on the synced DEs, Data Cloud segments and transforms) were not inspected beyond sync and stream membership. Data Cloud renames custom fields on ingest (`Field_c` for `Field__c`); the mapping is handled in `compile.py`.
- History tables (`ContactHistory`, `LeadHistory`, `AccountHistory`) were used only as a cross-check; tracked-field last-change dates are in `field_audit.csv`.
- 30,068 of the 30,944 `CustomField` rows in the Tooling API belong to 1,261 Data Cloud internal object definitions (ids starting `9sd`), not CRM objects; they are excluded.

## Files

- `field_audit.csv`: one row per custom field with population, dates, every reference found, sync and stream membership, and the classification.
- `object_audit.csv`: one row per custom object and key standard object.
- `scripts/`: `sfh.py` (REST helper on the `sf` CLI token), `pop_stats.py`, `longtext_sample.py`, `report_fields.py`, `sfmc_sync_fields.py` (reads the synced DE schemas via SOAP, read-only), `compile.py` (classification and CSVs). All read-only against the org.
