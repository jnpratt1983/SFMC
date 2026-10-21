# RE_ChurnRetention: term-end retention layer (spec v2, 2026-10-21)

Status: **design, not built.** v2 replaces the 2026-10-16 spec after reading the live lifecycle flow in
Marketing Cloud and aligning with Irene Stolyarov (lifecycle comms) on 2026-10-21. Model holdout passed
(v3, 0.627, `../ChurnRiskActivation/2026-10-20_v3_holdout_validation.md`). Still needs Insurance review
of the R-21 copy. Replaces the "Churn Risk activation (Predicted Did Cancel V7)" placeholder in the
lifecycle-watch list.

## What changed in v2 and why

| v1 (2026-10-16) | v2 (2026-10-21) | Reason |
|---|---|---|
| Entry at T-45 | Entry at **R-27** | The new-term offer is issued at R-32 and the existing Heads Up email lands at R-28/29. At T-45 no offer exists yet, so tier 1 could never fire. |
| T-45 email about the rate change, with the dollar change | **R-21 coverage check-in**, no premium or price-change amounts | Insurance already removed dollar totals from the Rate Increase email; the Heads Up email owns the rate message. A second rate email is a duplicate. |
| T-30 SMS, T-21 second email | **R-14 app push, HIGH band only** | No SMS (channel decision 2026-10-21). One follow-up, in the app where the coverage review lives. |
| Four tracks with different step counts | Same R-21 slot for every track; content differs by reason | Nothing may send inside the existing window (R-54 to R-28). |
| Entry DE without rating version | `RatingVersion` on entry and history | Results read legacy vs TDLI separately from week one. |

## The existing window this layer sits behind

All of these run from the automation `Master Customer Journey Daily Sends` at 09:00. Read from the live
queries and journeys on 2026-10-21; R = term end date (`Policy_Renewal_Date__c`).

| Day | Send | Audience |
|---|---|---|
| R-54 | `EN_TDLIR-54_E1` "We're simplifying the Safe Driving Discount" | AZ transition cohort (effective before 2026-09-21, term ends 2026-11-09 to 2027-05-09), one time |
| R-47 | `EN_TDLIR-47_E2` reminder | same cohort |
| R-32 | Policy system issues the new-term offer (`Renewal_Offer_Date__c`) | everyone |
| R-30 | `RE_RenewalEmailJourney_08242026` picks up offers dated R-32, splits at $20 | PNI with any increase |
| R-30 | `EN_TDLIR-30_E3` "Your Safe Driving Discount is secured" | AZ, app opened, discount above zero |
| R-28/29 | `RE_AZTDLIRateIncreaseRenewal_E1` / `RE_RINonTDLIRateIncreaseRenewal_E1` "Heads Up: your rate is changing" after Einstein STO and a one-day wait | the $20-and-up group |
| R-28 to R | nothing | |

The layer fills the empty four weeks. It never sends before R-21.

## Constraints (Insurance via Irene, 2026-10-21)

- No renewed premium total, no exact price change, no rate amount in any copy. Discount and savings
  figures are allowed (the R-30 email shows the monthly Safe Driving Discount in dollars).
- Nothing about payment status, non-pay, credit, the score or the band.
- Email and app push only. No SMS. No call tasks.
- Do not add to or alter the renewing-customer flow; this is a separate journey measured on top of it.

## Automation: `RE_ChurnRetention` (daily 10:00, after `Master Customer Journey Daily Sends` at 09:00)

| Step | Query activity | Target DE | Update type |
|---|---|---|---|
| 1 | `01_RE_ChurnRetention_Entry.sql` | `RE_ChurnRetention_Entry_AF_10202026` | Overwrite |
| 2 | `02_RE_ChurnRetention_Suppression.sql` | `RE_ChurnRetention_History_AF_10202026` | Append |
| 3 | `03_RE_ChurnRetention_Exit.sql` | `RE_ChurnRetention_Exit_AF_10202026` | Overwrite |

DE schemas are in `de/`. Band cut points live in `RE_ChurnRetention_Config_AF_10202026` (one row), updated
after each monthly scoring batch. Two columns are new in v2 and must be added to the Entry and History DEs
before the queries run: `RatingVersion` Text(20) and `LifetimeSavings` Decimal(10,2) (Entry only).

## Entry rule (step 1)

A contact enters when all of these hold on the run date:

- Primary named insured, not cancelled, not pending cancel, AZ or RI.
- Term ends in exactly **27 days** (`Current_Term_Expiration_Date__c = today + 27`), one evaluation per term.
- **Tier 1 (Band OFFER):** the new-term offer, issued at R-32 and captured in `Renewal_Offer__c`, is more
  than $20 a month or more than 10% up. **Tier 2 (Band HIGH):** v3 score at or above the top-decile cut.
- **Exclusions:** non-pay bill in the last 90 days; in the non-pay journey's entry DE; DNR flag; already in
  history for this term end; a Rate Increase send in the last 48 hours (safety check on `_Sent`/`_Job`,
  satisfied by construction since Heads Up lands by R-29); not reachable on email or push.
- Reachable means email not opted out, or app opened (the push proxy the TDLI queries use).

Columns carried: `ChurnReason`, `Band`, `Track`, `MailingState`, `Arm`, `RatingVersion`, `LifetimeSavings`,
`OfferChange`, `DiscountChange`, `DrivingScore`, `TermEndAtEntry`. `OfferChange` is carried for reporting
and must never be rendered in copy.

## Steps

| Day | Step | Who | Channel |
|---|---|---|---|
| R-27 | Entry, Arm split, HOLDOUT to a silent wait | all entrants | |
| R-21 | **Coverage check-in email**, content block by `ChurnReason` and state | TREAT | email, Einstein STO 24h |
| R-14 | **Push** to the coverage review in the app | TREAT, Band HIGH, app opened | app push |
| R+7 | Thank-you | renewed exits, via `RE_ChurnRetention_Renewed` | email |
| R+30 | Exit for anyone still in | all | |

Tracks no longer change timing. `Track` stays on the DE (PRICE / ENGAGE / DEFAULT) for reporting and for
the push eligibility rule: ENGAGE reasons get the R-14 push at both bands, since their content is about the
app; PRICE reasons get it at HIGH only.

SERVICE handling: if a Zendesk ticket is open on the run date, entry is deferred to the next day the ticket
is closed, up to R-21. After R-21 the contact is skipped for this term.

## Journey Builder settings

- Name `RE_ChurnRetention_<Month>2026`. Entry source `RE_ChurnRetention_Entry_AF_10202026`, scheduled daily
  after the automation. Re-entry: **single entry across all versions**. No trailing waits.
- Split 1 on `Arm`: HOLDOUT waits until R+30 (wait by attribute on `TermEndAtEntry` plus 30) and exits with
  no sends; TREAT continues. Both arms get identical exit criteria and identical history rows.
- Wait until R-21 (wait by attribute `TermEndAtEntry` minus 21), email with STO.
- Split 2 on push eligibility (`Band = 'HIGH' OR Track = 'ENGAGE'`) and `app_opened__c = 'true'`; wait until
  R-14, push. Everyone else goes straight to the exit wait.
- Exit criteria evaluated daily: contact is in `RE_ChurnRetention_Exit_AF_10202026` (cancelled, pending
  cancel, new non-pay notice, renewed). RENEWED rows feed the one-step `RE_ChurnRetention_Renewed` thank-you.
- Goal: `Cancel_Date__c` is null 30 days after `TermEndAtEntry`.

## Measurement (50/50 randomized holdout, approved 2026-10-20)

Primary read: preventable voluntary cancellation within 60 days of entry, TREAT vs HOLDOUT, from history joined
to Contact; stratified by state, tenure bucket, band and **rating version**. Both arms receive the full existing
flow, so the read is the incremental effect of the layer. Details and timing in `TEST_PLAN.md`.

## Prerequisites

1. Add `RatingVersion` and `LifetimeSavings` to the Entry DE and `RatingVersion` to the History DE.
2. Query activities and the 10:00 automation; run the entry query once and confirm 5 to 10 rows a day.
3. Content from `CONTENT_SPEC.md`; Irene reviews the R-21 copy, then Insurance.
4. Launch in AZ and RI with the holdout; add to lifecycle watch.
