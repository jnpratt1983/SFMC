# TR_NonPaymentJourney: has it provided lift?

Analysis date: 2026-10-16. Journey: `TR_NonPaymentJourney_February2026` (v12, Published 2026-07-02), fed by automation `TR_NonPaymentJourney` (daily 06:00 server time). Data: Salesforce `Bill__c` non-pay records (Jan 2024 to Oct 2026), Marketing Cloud send/open/click/bounce events for every TR_NonPayment triggered send since launch, 29 days of journey history, and the journey's version history.

## Summary

**Yes, since the full sequence went live on 2026-06-10.** The non-pay cure rate (share of non-pay notices that clear instead of cancelling) is 73.5% for July to September 2026, against 70.9% for February to May 2026 and 69.1% for the four months before launch. That is +2.6 ± 1.0 points on the raw before/after comparison. In 2024 and 2025 the July to September cure rate ran 3.3 to 3.8 points *below* February to May, so the seasonally adjusted lift is closer to +6 points.

Where the lift comes from is specific:

- **The late-stage messages do the work.** Day-by-day cure curves for the treated period and the two untreated comparison periods are identical for the first six days after the notice. They diverge only on days 7 to 9, immediately after the T+7 email ("update your payment method to keep your policy active") and the T+8 and T+9 SMS. The T+3 email ("late payments happen...") produces no detectable change in payment timing, and neither does the T+3 SMS.
- **First-time non-payers respond; repeat non-payers do not.** Among episodes still unpaid when dunning starts, first-time non-payers cleared 51.0% in the treated period versus 40.5% in the reminder-only period (+10.5 ± 2.5 points). Repeat non-payers moved from about 68% to 70%, inside the noise.
- **The pre-due T-5 reminder shows at most a small effect on non-pay incidence.** Months with the reminder on ran 0.5 to 1.5 points below the same months of 2025 in the share of bills going non-pay; the May to June gap, when the reminder was off, matched 2025.

In volume terms the journey is adding roughly 30 (raw) to 70 (seasonally adjusted) cleared non-pay episodes per month on a base of about 1,180 notices.

Two things limit the result today:

1. **Half of the time since launch was not actually treated.** From February 5 to April 19 only the T-5 reminder sent, because the early exit criterion dropped every contact after the first email. From May 1 to June 9 nothing sent at all. The full sequence has run only since June 10.
2. **17% of unpaid episodes never receive a dunning message**, mostly repeat non-payers whose contact is still parked in the journey's trailing 2 to 3 week waits from the previous billing cycle and therefore cannot re-enter. Fixing that is the cheapest way to add lift.

An earlier cut (2026-10-02) concluded the journey added at most about 1 point. It compared May (journey off) with the surrounding live months, but the live months before June had no dunning emails either, so both sides of that comparison were untreated.

## 1. What the journey does

Entry is not "non-pay customers". The entry query (`TR_NonPay_01272026`, step 2 of the automation) selects **every bill whose invoice due date is 5 days away**, excluding renters policies (policy number ending in R), about 160 contacts a day. The journey then waits for the payment to fail.

| Step | Timing (relative to invoice due date T) | Days after the non-pay notice | Who gets it |
|---|---|---|---|
| E1 / SE1 "quick reminder: your auto payment coming up" | T-5 (entry) | 6 days before | everyone entering; SMS also if `SMS_Policy_Opt_In__c` and phone present (74% of entrants) |
| 8-day wait, then exit check | T+3 | day 2 | anyone in `NonPay_Paid` exits (paid on or after due date, cleared, or contact has a cancel date) |
| E2 / SE2 "late payments happen, but please prevent your policy cancellation" | T+3, 12:00 UTC | day 2 | still unpaid |
| E3 / ES3 "update your payment method to keep your HiRoad policy active" | T+7 | day 6 | still unpaid |
| SE3, SE4 SMS | T+8, T+9 (AZ); T+12, T+13 (RI) | days 7 and 8 (AZ); 11 and 12 (RI) | still unpaid |
| Cancellation | T+10 (AZ); T+14 (RI) | day 9 (AZ); day 13 (RI) | |
| Trailing wait | 2 to 3 weeks | | contact stays in the journey, blocking re-entry |

The non-pay notice is created the day after the due date at about 09:00 UTC; the journey's emails go out at 06:00 server time (12:00 UTC). Entry mode is single entry across all versions, so a contact already in the journey cannot be re-injected.

## 2. What actually sent

Weekly send counts from the Marketing Cloud `SentEvent` object, by step:

| Period | T-5 reminder | T+3 | T+7 | Journey version and cause |
|---|---|---|---|---|
| 2026-02-05 to 02-10 | yes | 0 | 0 | v2 |
| 2026-02-11 to 02-17 | 0 | 0 | 0 | stopped |
| 2026-02-18 to 04-19 | ~1,250/week | 0 | 0 | v3 to v9: exit criterion was "`Nonpay_Cancel_Notice_Created_At__c` is not null" on the entry DE. That column is aliased from `Non_pay_cancel_date__c`, which is populated for every row, so every contact exited after E1. v8 (03-30) switched the exit to `NonPay_Paid` but still produced no T+3 sends |
| 2026-04-20 to 04-30 | yes | 338 + 153 | 51 | v10 (04-21): 8-day wait before the exit check, first dunning sends |
| 2026-05-01 to 06-09 | 0 | 0 | 0 | no sends at all (v11 created 04-30; automation not producing entries) |
| 2026-06-10 to now | ~1,100/week | ~200/week | ~140/week | v11, then v12 (07-02, adds renters exclusion to the exit) |

Totals since launch: 34,931 T-5, 4,105 T+3, 2,312 T+7 emails. Bounce rates 0.6% to 0.9%.

## 3. Method

- **Episode** = one contact and one non-pay notice date (bills on the same day for the same contact are merged; 3% of notices). Renters policies excluded to match the journey. Cleared = `Nonpay_Cleared_At__c` set and not followed by a cancellation.
- **First-time** = no non-pay notice for that contact in the prior 120 days.
- Email events are joined to episodes by Contact Id (the SubscriberKey) and by step window around the due date. Marketing Cloud SOAP `EventDate` is server time (UTC-6) and was shifted to UTC.
- **Comparison periods** (notices dated): June 12 to September 30 2025 (no journey of any kind), February 18 to April 15 2026 (T-5 reminder only), June 12 to September 30 2026 (full sequence). October 2026 episodes are still resolving and are excluded.
- Clear timestamps at 07:00, 09:00 and 10:00 UTC are automated batch stamps (about 40% of clears) and are dropped from the hour-level timing checks.
- No holdout exists (barred by compliance), so every comparison here is before/after or across periods. The strongest evidence is the shape of the cure curve, which is hard to explain with season or trend alone.

## 4. Results

### 4.1 Monthly cure rate and message coverage

| Notice month | Episodes | Cleared | First-time cleared | Got T-5 | Got T+3 | Got T+7 |
|---|---|---|---|---|---|---|
| 2025-10 | 1,531 | 68.9% | 60.0% | 0% | 0% | 0% |
| 2025-11 | 1,400 | 68.1% | 58.7% | 0% | 0% | 0% |
| 2025-12 | 1,513 | 69.9% | 59.6% | 0% | 0% | 0% |
| 2026-01 | 1,386 | 69.6% | 59.1% | 0% | 0% | 0% |
| 2026-02 | 1,151 | 71.0% | 62.3% | 20% | 0% | 0% |
| 2026-03 | 1,306 | 70.4% | 55.9% | 99% | 0% | 0% |
| 2026-04 | 1,156 | 71.4% | 63.4% | 99% | 2% | 4% |
| 2026-05 | 1,313 | 70.8% | 61.3% | 21% | 0% | 0% |
| 2026-06 | 1,209 | 71.5% | 66.6% | 51% | 42% | 20% |
| 2026-07 | 1,199 | 72.8% | 65.2% | 99% | 58% | 39% |
| 2026-08 | 1,158 | 73.5% | 65.5% | 94% | 75% | 49% |
| 2026-09 | 1,187 | 74.1% | 65.2% | 95% | 74% | 49% |

T+3 coverage of 74% is the ceiling for a working sequence: 19% of episodes pay before the T+3 send and exit correctly. The remaining gap is section 5.

### 4.2 Season-matched comparison

July to September versus February to May of the same year:

| Year | Feb to May | Jul to Sep | Change | First-time change |
|---|---|---|---|---|
| 2024 (old RE journey ran Jun to Sep) | 75.8% (n 10,830) | 72.1% (n 7,916) | −3.8 ± 0.7 | −7.3 ± 1.1 |
| 2025 (no journey) | 67.7% (n 7,704) | 64.4% (n 5,472) | −3.3 ± 0.8 | −4.5 ± 1.4 |
| 2026 (reminder only, then full sequence) | 70.9% (n 4,926) | 73.5% (n 3,544) | **+2.6 ± 1.0** | **+4.7 ± 1.8** |

Both prior years show a summer dip of 3 to 4 points; 2026 shows a rise. The book has also been shrinking (bills per month 14,600 in early 2024, 7,000 now) and the cure rate has trended up since mid-2025, so the +6 point season-adjusted figure is an upper bound rather than a point estimate.

### 4.3 Day-by-day cure curves (Arizona, cancellation on day 9)

Daily clear probability among episodes still unresolved at the start of the day:

| Day after notice | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | Final cleared |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Message sent (treated period) | | | T+3 email, SMS | | | | T+7 email | SMS | SMS | cancel | |
| 2025 Jun to Sep, no journey (n 5,782) | 6.1 | 10.9 | 9.3 | 8.4 | 7.5 | 8.1 | 8.3 | 7.1 | 6.5 | 10.0 | 61.0% |
| 2026 Feb to Apr, reminder only (n 2,042) | 7.1 | 12.8 | 11.5 | 8.5 | 8.7 | 8.3 | 9.3 | 7.9 | 9.8 | 12.3 | 67.4% |
| 2026 Jun to Sep, full sequence (n 3,814) | 6.7 | 11.9 | 10.9 | 10.2 | 8.9 | 7.3 | 9.4 | **11.2** | **14.0** | **16.9** | 71.1% |

Cumulative cleared by the end of day 6 is 45.8% / 50.1% / 49.7% for the three periods, so the full sequence and the reminder-only period are level until the T+7 email. All of the 3.7 point gap between them opens on days 7 to 9.

Hour-level check: in the six hours after the T+3 send, treated episodes clear at 3.6 per 1,000 at-risk hours; the reminder-only period clears at 3.3 per 1,000 in the same clock window on the same day. That bump is time of day, not the email. After the T+7 send the treated rate is 5.1 versus 3.7, and in the 48 to 72 hours after it (the SMS days) 8.5 versus 4.1.

### 4.4 Conditional on reaching the dunning stage

Episodes still unpaid at the start of day 3 (about three quarters of all episodes):

| Period | At-risk episodes | Cleared | First-time cleared | Repeat cleared |
|---|---|---|---|---|
| 2025 Jun to Sep | 5,060 | 52.8 ± 0.7% | 38.8 ± 1.1% | ~61% |
| 2026 Feb to Apr (reminder only) | 1,662 | 58.2 ± 1.2% | 40.5 ± 2.0% | ~68% |
| 2026 Jun to Sep (full sequence) | 3,154 | 63.2 ± 0.9% | **51.0 ± 1.5%** | ~70% |

### 4.5 Pre-due reminder and non-pay incidence

Share of all bills (whole book, by due month) that went non-pay, 2026 versus 2025:

| Months | 2025 | 2026 | Reminder status | Difference |
|---|---|---|---|---|
| Feb to Apr | 22.1% | 21.7% | on | −0.5 ± 0.4 |
| May to Jun | 23.3% | 23.5% | off (May 1 to Jun 9) | +0.2 ± 0.5 |
| Jul to Sep | 23.3% | 21.7% | on | −1.5 ± 0.4 |

Consistent with a small reduction (roughly 1 point of incidence, 4% relative) when the reminder is on, but the July figure includes a one-month billing bump and the evidence is weak.

### 4.6 Engagement

Treated-period episodes (June 12 to September 30 2026):

| Step | Sent to | Unique open | Unique click |
|---|---|---|---|
| T-5 | 92.8% of episodes | 63.5% | 4.7% |
| T+3 | 67.8% | 58.5% | 5.0% |
| T+7 | 42.8% | 54.2% | 6.0% |

Among at-risk T+3 recipients, openers cleared 69.4% and non-openers 58.5%; clickers 85.4%. Those gaps are selection (engaged customers pay), not effect, and should not be read as lift. Open rates are inflated by mail privacy proxies.

### 4.7 SMS

74% of entrants take the SMS & Email path (29-day journey history: 3,572 of 4,828 entries). In those 29 days the journey sent 3,572 SE1, 642 SE2, 359 SE3 and 306 SE4 messages. Among at-risk T+3 recipients, the SMS path cleared 65.7% and the email-only path 63.0%; the paths differ by opt-in, so this is not a clean SMS effect. The timing evidence in 4.3 is the better indicator that the SMS days matter.

## 5. Coverage gap

In the treated period 3,261 episodes were still unpaid when the T+3 send was due; 559 (17%) got no T+3 email, 69% of them repeat non-payers. Tracing the 46 most recent such episodes through journey history:

- 29 (63%): the contact was rejected at entry with `CurrentlyWaitingInSameInteraction`, still sitting in the previous cycle's trailing 2 to 3 week wait. A monthly biller who went through the whole sequence last month cannot enter this month.
- 11 (24%): entered, got T-5, then exited at the 8-day check although the bill was unpaid. `NonPay_Paid` matches any bill in the 21-day window with a payment on or after its due date, so a second policy or partial payment can trigger it. Not pinned down.
- 2: no journey history rows.

A stale `Cancel_Date__c` on the contact (also an exit condition) was checked and is not a cause: only 4 of the 559 contacts had a cancel date that predates the notice.

Separately, 7% of episodes in the period received no T-5 either; the same re-entry block is the likely reason.

## 6. Recommendations

1. **Keep the sequence running.** The lift is real, concentrated in the T+7 email and the T+8/T+9 SMS, and strongest for first-time non-payers.
2. **Remove or shorten the trailing waits** (3 weeks, 2 weeks, 10 days) so contacts leave the journey right after the last message. The exit criteria and single-entry mode already prevent duplicate sends within a cycle. This should recover most of the 17% of unpaid episodes currently missed.
3. **Investigate the unpaid exits at the 8-day check.** Candidate fix: key `NonPay_Paid` on policy number plus due date rather than on contact.
4. **Test the "keep your policy active" framing earlier.** The T+3 message ("late payments happen") moves nothing; the cancellation-focused message at T+7 does. Moving that framing to T+3 for first-time non-payers can be read off the day 2 to 4 hazard without a holdout.
5. **Monitor with the cure curve, not open rates.** Monthly cure rate by first-time/repeat and the day 7 to 9 hazard are the signals that reflect the journey's effect; the Lifecycle Watch agent can carry them.

## 7. Caveats

- No holdout, so all estimates are period comparisons; the raw +2.6 and the season-adjusted +6 bracket the likely effect.
- The customer base shrank by half since 2024 and the cure rate has trended up since mid-2025, which inflates any before/after comparison. The cure-curve shape (identical through day 6) is the main defence against that.
- Clear timestamps are partly batch-stamped; the hour-level checks exclude those hours but the daily curves include them.
- The earlier `RE_PreNonPaymentJourney` / `RE_PostNonPaymentJourney` (June to September 2024) showed no lift in the 2024 monthly series.

## 8. Reproduce

Scripts in `scripts/`:

- `pull_events.py`: SOAP retrieve of Sent/Open/Click/Bounce events for every TR_NonPayment triggered send since 2026-02-01 (uses the read-only `MC` client from `c360-sfdx/scripts/lifecycle_watch.py`).
- `pull_history.py`: journey history in daily windows (the search endpoint caps at 10,000 rows per window).
- `de_rows.py`: row dump of the entry DE and `NonPay_Paid` with correct property parsing.
- `nonpay_episodes.py`: the episode join and all tables above.
- `01_cleared_nonpay_contacts_21day_lookback.sql`, `02_TR_NonPay_01272026.sql`: the automation's two query activities as live on 2026-10-16.

Bills extract: `sf data query -o blueowl-prod` on `Bill__c` where `Non_pay__c = true` and the notice date is from 2024-01-01 (set `SF_ORG_MAX_QUERY_LIMIT` above 70,000). Aggregates used in the tables are in `data/monthly.json`, `data/cure_curves.json`, `data/incidence_by_due_month.json` and `data/sends_by_day.json`. Row-level files contain contact Ids and are not committed.
