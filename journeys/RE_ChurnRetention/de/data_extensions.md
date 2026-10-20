# Data extensions for RE_ChurnRetention

All in the B2C Lifecycle Marketing BU, folder `Journeys/RE_ChurnRetention`. SubscriberKey = Contact Id.

## RE_ChurnRetention_Config (one row, edited after each monthly scoring batch)

| Field | Type | Notes |
|---|---|---|
| ConfigKey | Text(20), PK | `current` |
| HighCut | Decimal(5,2) | start of the v3 top decile from the latest batch (58.29 on the Aug 2026 holdout) |
| ModerateCut | Decimal(5,2) | start of decile 3 (reporting only; entry does not use it) |
| BatchDate | Date | scoring batch the cuts came from |

## RE_ChurnRetention_Entry (Overwrite daily; journey entry source)

| Field | Type |
|---|---|
| Id | Text(18), PK, SubscriberKey |
| Customer_Number__c | Text(50) |
| account_id__c | Text(50) |
| FirstName | Text(100) |
| Email | EmailAddress(254) |
| Phone | Phone |
| MailingState | Text(10) |
| HasOptedOutOfEmail | Text(10) |
| et4ae5__HasOptedOutOfMobile__c | Text(10) |
| SMS_Policy_Opt_In__c | Text(10) |
| Score | Decimal(5,2) |
| Band | Text(10): HIGH (model tier) or OFFER (price tier) |
| TopFactors | Text(255) |
| ChurnReason | Text(20): PRICE_SHOCK, DISCOUNT_EROSION, NEW_CUSTOMER, DISENGAGED, LOW_SAVINGS, GENERAL |
| OfferChange | Decimal(10,2), nullable |
| DiscountChange | Decimal(10,2), nullable |
| DrivingScore | Decimal(10,2), nullable |
| Track | Text(10) |
| TermEndAtEntry | Date |
| TermStartAtEntry | Date |
| TenureDays | Number |
| EntryDate | Date |
| Arm | Text(10): TREAT or HOLDOUT |

## RE_ChurnRetention_History (Append; suppression and reporting)

Fields: Id (Text 18), TermEndAtEntry (Date), EntryDate (Date), Band, Track, Score, TopFactors, Arm.
Primary key: Id + TermEndAtEntry. Retention: keep all rows; it is the measurement spine.

## RE_ChurnRetention_Exit (Overwrite daily; journey exit criteria)

Fields: Id (Text 18, PK), TermEndAtEntry (Date), ExitReason (Text 20: CANCELLED, PENDING_CANCEL, NONPAY, RENEWED), ExitDate (Date).
The `RE_ChurnRetention_Renewed` thank-you journey uses this DE filtered to `ExitReason = 'RENEWED'`.
