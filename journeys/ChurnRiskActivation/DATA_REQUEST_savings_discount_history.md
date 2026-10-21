# Data request: savings and discount history backfill

Written 2026-10-21. Owner: Jennifer Pratt. Recipient: Data Analytics. Purpose: give the churn model a
point-in-time view of what each customer was saving and what discount they carried, month by month, the
way `Renewal_Offer__c` now does for renewal offers and `Monthly_Driving_Stat__c` does for driving.

## Why we need it

Contact and Account hold only today's value of `Lifetime_Savings__c` and `Telematic_Discount__c`, refreshed
nightly (7,754 of 7,885 active customers have a lifetime savings figure; the two-year-plus customers average
$2,832, the newest average $98). Nothing records what those values were on any earlier date, so the model
cannot learn whether a customer's savings were shrinking before they left. Account field history began
tracking these fields on 2025-11-14, but Salesforce keeps field history for 18 months and
`Telematic_Discount__c` changes daily (4.68 million history rows), so it is neither durable nor usable
as a source. Driving-earned discount is already covered per cycle since 2023-05 by `Monthly_Driving_Stat__c`.
What is missing is the rated side: the discount actually applied to premium and the dollars it saved.

## What to send (copy this to Data Analytics)

> We are building a customer-month savings history object in Salesforce, loaded once from your side and
> then kept current by a scheduled flow. Please produce one CSV with **one row per customer per policy
> month**, for **every customer who has ever held a HiRoad policy in AZ or RI, cancelled customers
> included**, from **2023-05-01 (or policy inception if later) through 2026-09-30**. Survivorship matters:
> if the file only covers customers still active today, it is unusable.
>
> Columns, in this order, with these exact headers:
>
> | Header | Type | Definition |
> |---|---|---|
> | `External_Id__c` | text | `<Customer_Number>-<YYYYMM>`, unique per row, e.g. `C-643403698-202605` |
> | `Customer_Number__c` | text | HiRoad customer number as on Contact (`C-` prefix) |
> | `Policy_Number__c` | text | policy the month belongs to |
> | `Period_Start__c` | date, YYYY-MM-DD | first day of the policy month (billing cycle start) |
> | `Period_End__c` | date | last day of the policy month |
> | `Term_Effective_Date__c` | date | effective date of the term this month falls in |
> | `Standard_Premium__c` | number, 2 dp | that month's premium before any telematic discount |
> | `Telematic_Discount_Pct__c` | number, 2 dp | the rated discount percentage applied to that month's premium (0 to 100), i.e. what `Account.Telematic_Discount__c` showed at the time |
> | `Discount_Amount__c` | number, 2 dp | dollars removed by the discount that month (`Standard_Premium` minus `Net_Premium`) |
> | `Net_Premium__c` | number, 2 dp | premium actually charged; must tie to `Bill__c.Policy_Net_Bill_Amount__c` for the same month |
> | `Lifetime_Savings_To_Date__c` | number, 2 dp | running sum of `Discount_Amount__c` through `Period_End__c`; the last row per customer must equal today's `Account.Lifetime_Savings__c` within $1 |
> | `Earned_Discount_Pct__c` | number, 2 dp | the driving-earned discount for the cycle, if your source has it; leave blank if not |
> | `As_Of_Date__c` | date | the date the values were true in the source (the extraction or close date), never today |
>
> Format: UTF-8, comma separated, LF line endings, no thousands separators, no currency symbols, no
> blank header rows, blanks for unknown values. Expected volume is roughly 300,000 to 500,000 rows
> (about 25,000 customers times their months on book).
>
> Please also send, as a second small file, a monthly summary: for each `Period_Start__c`, the row count,
> the distinct customers, and the sum of `Discount_Amount__c`, so we can check coverage month by month.
>
> Three definitions we need you to confirm in writing: (1) which discount is "rated" versus "earned"
> when they differ (today Account shows 27.5 while Contact shows 0.25 for the same customer); (2) whether
> `Lifetime_Savings__c` is the sum of monthly discount dollars or is computed another way; (3) what the
> policy month boundary is (billing cycle versus calendar month). If the monthly savings figure is
> already a column in your warehouse, say which one so we can reconcile.

## What happens on our side

1. Create `Savings_History__c` with the fields above, `External_Id__c` as the external ID, and a
   lookup to Contact resolved by customer number on load (same pattern as `Renewal_Offer__c`).
2. Bulk upsert the CSV on `External_Id__c`; run the acceptance checks below.
3. Scheduled flow on the 1st of each month writes one row per active customer from the Account values
   (standard and net from the latest bill, discount from Account, lifetime savings from Account) so the
   history keeps growing without another request.
4. Add the object to the Data Cloud Salesforce CRM stream, join on `customer_number_c__c` as the driving
   stats do, and add six features to the training set: discount percentage latest and change over three
   months, discount dollars latest and change, lifetime savings at snapshot, savings per month of tenure.
5. Retrain as v4 once the file lands and renewal offers have 12 months of history; validate on the same
   held-out months.

## Acceptance checks

| Check | Pass condition |
|---|---|
| Coverage | 90%+ of customers active in each month from 2024-07 onward have a row |
| Cancelled customers present | row counts per month decline no faster than the book did |
| Lifetime tie-out | last row per customer within $1 of `Account.Lifetime_Savings__c` for 95%+ of active customers |
| Bill tie-out | `Net_Premium__c` within $1 of `Bill__c.Policy_Net_Bill_Amount__c` for 90%+ of matched months |
| Discount tie-out | latest month `Telematic_Discount_Pct__c` equals `Account.Telematic_Discount__c` for 95%+ |
| No future values | every `As_Of_Date__c` on or after `Period_End__c`, none after the extract date |
