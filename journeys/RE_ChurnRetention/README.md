# RE_ChurnRetention: renewal-window retention journey (spec, 2026-10-16)

Status: **design, not built.** Depends on the voluntary-churn model passing its holdout test
(`journeys/ChurnRiskActivation/BUILD_GUIDE.md`, phase 5) and on Insurance reviewing the content
and the exclusion rule. Replaces the "Churn Risk activation (Predicted Did Cancel V7)" placeholder
in the lifecycle-watch list.

## Why it is shaped this way

Preventable voluntary cancellations cluster at the renewal boundary: 23% land in the first 30 days
of a term and 17% in the last 35 days of one. High premium and switching carriers are 78% of them.
So this is a renewal-window journey that the model prioritises, not a "high score, send an email"
journey. Entry is 45 days before term end; everything is done within two weeks after the new term
starts. Non-pay customers are excluded at entry and exited on a new notice, per Insurance's
2026-10-16 decision that credit-based signals stay out of retention outreach.

## Automation: `RE_ChurnRetention` (daily 06:30, after `TR_NonPaymentJourney` at 06:00)

| Step | Query activity | Target DE | Update type |
|---|---|---|---|
| 1 | `01_RE_ChurnRetention_Entry.sql` | `RE_ChurnRetention_Entry` | Overwrite |
| 2 | `02_RE_ChurnRetention_Suppression.sql` | `RE_ChurnRetention_History` | Append |
| 3 | `03_RE_ChurnRetention_Exit.sql` | `RE_ChurnRetention_Exit` | Overwrite |

DE schemas are in `de/`. Band cut points live in `RE_ChurnRetention_Config` (one row) and are
updated after each monthly scoring batch, so the SQL never hard-codes a threshold.

## Entry rule (step 1)

A contact enters when all of these hold on the run date:

- Primary named insured (`Driver_Role__c = 'PNI'`), not cancelled, not pending cancel.
- Term ends in exactly 45 days (`Current_Term_Expiration_Date__c = today + 45`), so each contact
  is evaluated once per term.
- Score in the High band, **or** in the Moderate band with tenure under 12 months.
- **Exclusions:** any non-pay notice in the last 90 days (Contact or Bill); currently in the
  non-pay journey's entry DE; email opt-out for the email path and mobile opt-out for SMS; DNR
  flag; already in `RE_ChurnRetention_History` for this term end date.

Track is assigned in SQL from `Voluntary_Churn_Top_Factors__c`:

| Track | Top factor contains | Steps |
|---|---|---|
| `PRICE` | Renewal, Savings, Discount, Premium | T-45 email (savings earned, how the discount carries into the new term). T-30 SMS where consented. T-21 second email, different angle (what the discount is worth over the next term), only to non-openers of T-45. T+7 after renewal: thank-you. |
| `ENGAGE` | App, Trip, Driving | T-45 email plus app push. T-35 second push. T-21 email to non-openers. No SMS. Content differs by state: RI leads with HiGoals rewards progress; AZ (no HiGoals) leads with the safe-driving discount and trip tips. |
| `SERVICE` | Ticket, Support | No marketing email while a ticket is open. Wait until the open ticket count is zero (daily check against the Zendesk sync), then join `PRICE` at the next step. No task is created. |
| `DEFAULT` | anything else or blank | `PRICE` emails only. |

## Journey Builder settings

- Name `RE_ChurnRetention_<Month>2026`. Entry source: `RE_ChurnRetention_Entry`, scheduled
  daily after the automation. Re-entry: **single entry across all versions**. No trailing waits
  (the non-pay journey's trailing waits are why 63% of its traced contacts were stuck).
- First activity: a decision split on `Arm`. `HOLDOUT` goes straight to a wait that ends at T+30 and then exits; it sends nothing and has the same exit criteria, so both arms are tracked identically in `RE_ChurnRetention_History`. Approved by compliance 2026-10-20 as a 50/50 split. `TREAT` continues.
- Second split: `MailingState` (AZ / RI) for content; third split: `Track`; fourth split: channel, reusing the "Email Only / Email & SMS / SMS Only /
  Remainder" multi-criteria split from `AC_ReviewQuoteStepJourney` keyed on
  `HasOptedOutOfEmail`, `et4ae5__HasOptedOutOfMobile__c`, `SMS_Policy_Opt_In__c`.
- Email sends use Einstein STO (24 hours). SMS between 09:00 and 19:00 local.
- No call tasks and no Sales Cloud activities: the journey is email, SMS and push only
  (decision 2026-10-19, no call resources). If that changes, the T-21 step is where a task
  would go, using the "Call Lead- Next Best Action" activity pattern.
- **Exit criteria**, evaluated daily: contact is in `RE_ChurnRetention_Exit`. The exit DE holds
  anyone who cancelled, went pending cancel, received a new non-pay notice after entry (the
  non-pay journey takes over), or renewed (`Current_Term_Effective_Date__c` >= the term end
  recorded at entry). Renewed contacts get the thank-you email via a separate one-step journey
  `RE_ChurnRetention_Renewed` fed by the exit DE's `ExitReason = 'RENEWED'` rows, so the main
  journey can exit them cleanly.
- Goal: `Cancel_Date__c` is null 30 days after `TermEndAtEntry`.

## Content rules

- Nothing about payment status, non-pay, credit, or the score itself, in any track.
- Price track talks about the discount earned and what keeps it; it does not quote the new
  premium, which the policy system communicates.
- Insurance reviews every template before activation.

## Measurement (50/50 randomized holdout, approved 2026-10-20)

0. **Primary read.** Preventable voluntary cancellation by T+30 after term end, TREAT vs HOLDOUT from `RE_ChurnRetention_History` joined to Contact; stratified by state, tenure bucket and band. Interim looks at months 4 and 8 of entries, final read at month 12. See `TEST_PLAN.md`.
1. **Cut-line comparison (secondary).** 90-day cancel rate for contacts just above the High cut (entered)
   versus just below it (not entered), same term-end window, same tenure bucket.
2. **Year-over-year renewal cohort.** Daily retention curve for entered contacts' renewal cohort
   versus the same calendar window a year earlier, as done for the non-pay journey.
3. **Journey goal rate by track** and by factor, monthly, posted in the lifecycle-watch brief.
4. Read per-step open and click rates as engagement only, never as effect; survivorship by step
   was the trap in the non-pay analysis.

## Prerequisites

1. Marketing Cloud Connect sync adds to `Contact_Salesforce`: `Voluntary_Churn_Risk_Score__c`,
   `Voluntary_Churn_Top_Factors__c`, `Current_Term_Effective_Date__c`,
   `Current_Term_Expiration_Date__c`, `Nonpay_Cancel_Notice_Created_At__c`, `Driver_Role__c`
   (already synced), `DNR_Flag__c`. The entry query fails on the first missing field, which is
   the intended smoke test.
2. The three DEs and the config DE created from `de/`.
3. Model holdout pass, Insurance content review, pilot state (Arizona first, matching the
   Data Science payment-stability scope).

## Interim option if the model is late

Run the `PRICE` track only with entry = PNI, term end in 45 days, tenure under 12 months, no
score. Weak targeting, right timing, nothing touches payment data. Switch the entry query to the
scored rule when the model ships; the journey does not change.
