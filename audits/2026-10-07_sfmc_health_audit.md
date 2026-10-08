# Marketing Cloud health audit: journeys, automations, data extensions

Business unit: B2C Lifecycle Marketing (MID 110007736). Pulled 2026-10-07 via the read-only API package.
Scope: 75 published journeys (of 254), 92 automations and their 200+ query activities, 718 data extensions,
triggered-send definitions and lifetime send summaries, and 24 hours of Journey Builder activity history.
Nothing was changed in Marketing Cloud. Collector and checks: `c360-sfdx/scripts/sfmc_audit_collect.py`,
`sfmc_audit_checks.py`.

Severity: **High** = contacts are being missed, messages are failing, or something runs against a broken
target every day. **Medium** = wasted runs, risk, or something that needs an owner's decision.
**Low** = hygiene.

## High

### 1. Two quote journeys fail most of their first email
| Journey | Step that fails | Failures / 24h | Fail share (4-hour sample) | Error |
| --- | --- | --- | --- | --- |
| AC_CoveragesQuote_September2026 | AC_CoveragesQuote_ES1_04062026_V | 613 | 96 of 114 (84%) | 180008 "no valid subscribers" / 27 "excluded by Suppression logic" |
| AC_VehiclesQuoteStepJourney_July2026 | AC_VehiclesQuoteStep_ES1_04062026_V | 141 | 16 of 30 (53%) | same |

Only the ES1 step fails, which is the first email on the "Email + SMS" branch (leads with a mobile number and
no SMS opt-out). The "Email only" branch's E1 step succeeds. In the Coverages journey the ES1 and ES2 steps use a
different sender profile (`cc46c27d…`) from every other email in the journey (`766ab7e0…`); in the Vehicles
journey ES1 is configured identically to the working E1, so the sender profile is a lead, not the whole answer.
Both steps send to publication list 559 with no suppression list set at the journey level.
**Check:** open the ES1 email activity in each journey and compare its delivery options with E1; then look at
whether the leads on the Email + SMS branch are unsubscribed from list 559 or on an auto-suppression list.
Until fixed, most coverages-step and vehicles-step leads with a phone get no email nudge.

### 2. Renters journeys have sent nothing for 17 months
- **EN_RentersCrossSell_May2025**: 260 messages sitting in the queue of email step E2 since 2025-05-12, 0 sent.
  All four of its triggered-send definitions (Jan and May 2025) have zero sends since at least 2026-09-01.
  The journey still receives contacts every day (entry table 134 rows, fed by Master Customer Journey Daily
  Sends) and the activity log shows the email steps "completing", which here means queued, not sent.
- **EN_RentersSavedQuote_May2025**: 0 sends ever since publication (2025-05-12); fed daily (27 rows).
**Decision needed:** if renters cross-sell is still a thing, the stuck queue and definitions need to be
reset in Email Studio; if not, stop both journeys and remove their steps from the Master automation.

### 3. A 2023 journey re-processes 5,000 contacts every day and fails 110 updates
**Update Customer Review V2 to TRUE** (published 2023-07-21, MultipleEntries) runs on its own daily schedule
against the static table `Customer_Reviews_Ongoing` (5,116 rows, nothing writes to it). In a one-hour sample
it completed 9,277 activities, and every day its Update Contact step fails 110 times with
"Cannot insert the value NULL into column 'email'" on `Customer_Reviews_Ongoing_V2`. The automation that once
fed it (Customer Review Journey) has been paused since 2023-07-31. **Stop the journey.**

### 4. An automation injects into a Draft journey every day
**SMS Data** (scheduled daily) injects into **SMS Creation**, which is a Draft (v2). Journey Builder rejects
every contact: 47 validation failures in the last 24 hours. Either publish the journey or remove the step.

### 5. The unsubscribe-management automation targets a table that no longer exists
**Unsubbed Email Address Management** (scheduled daily, last run today 18:28) has one query step whose target
`unsub_emailaddress_stage` is missing by name and by id, followed by a data-copy step. The query joins
`ent._subscribers` to unsubscribed records by email address, i.e. it propagates unsubscribes across duplicate
subscriber keys. With the target gone the step cannot run. The API cannot read automation run results, so
**confirm in Automation Studio's activity log**; if it has been failing since the table was deleted,
unsubscribes have not been propagating.

### 6. Automations that feed journeys which are not running
| Automation (status) | Injects into | Journey state | Audience rows |
| --- | --- | --- | --- |
| AC_TrialModeRequote (daily) | AC_TrialModeReQuoteJourney_July2025 | no journey of that name exists | 1,015 |
| EN_HandsOffPhoneChallenge (daily) | EN_Intro_to_Streak_Tokens_Journey_June2025 | Draft v3 | 2,246 |
| OB_PermissionSetting (daily) | OB_PermissionSettings_January2024 | Draft v3 | 243 |
| Master Customer Journey Daily Sends | EN_AndroidNoTripsIssue_January2024 | Stopped v2 | n/a |
| Master Customer Journey Daily Sends | RE_CustomerAppStoreReviews_February2024 | no journey; draft RE_CustomerAppStoreReviews_April2026 exists | 0 |
| Master Customer Journey Daily Sends | RE_RateIncreaseRenewalJourney_October2026 | Draft v15 (being built) | 20 |
| AC_QuoteSteps (every 15 min) | AC_CoveragesQuote_July2024 | Draft v11 | 6 |
| AC_QuoteSteps (every 15 min) | AC_PurchaseQuote_April2024 | Draft v14 | n/a |

The trial-mode requote, intro streak tokens and permission-settings audiences are built daily and go nowhere.
If those communications are meant to be live, their journeys need publishing; if not, the steps are dead
weight that also makes the Master automation's run history noisy.

### 7. New journeys that have never sent
| Journey | Published | Entry table rows now | Sends, last 14 days |
| --- | --- | --- | --- |
| EN_TDLINewCustomers_September2026 | 2026-09-08 | 0 | 0 (2 ever) |
| EN_TDLIRenewingCustomers_Ongoing_September2026 | 2026-09-08 | 0 | 0 (1 ever) |
| EN_DigitalWalletExpiration_April2026 | 2026-04-13 | 0 | 0 ever |
| AC_OutofStateQuoteFlowJourney_October2025 | 2025-10-23 | n/a (Salesforce object trigger) | 0 ever |

The OneTime TDLI sibling sends 30 to 70 a day, so the Master automation and the journeys work; the two
Ongoing/New queries simply return no rows. Digital Wallet Expiration's query returns nothing and its exit table
`LFCL-Digital-Wallet-Pass-Added-Last-3-Days` has no writer. Either the SQL filters are wrong or these audiences
genuinely do not exist yet.

### 8. Seven test journeys are published
`AC_CoveragesQuote_June2025 TEST`, `TEST-SMS-AC_SavedQuote_March2024 (Copy)`, `Test SMS Review`,
`TESTPRE-AC_PurchaseQuote_Aug2025 (Copy)`, `Test_TR_NonPaymentJourney_February2026 (Copy)`,
`TEST-AC_PurchaseQuoteStepJourney_February2026 (Copy)`, `TEST_AC_CoveragesQuote_June2026`.
All have manual (EmailAudience) entry, so nothing feeds them automatically, but **TEST_AC_CoveragesQuote_June2026
has sent 9,133 real emails** (none in the last 14 days). Stop them so a stray injection cannot send.

### 9. Already known and still open
Next Best Action: about half of call-channel leads never get a call task because the channel is read before
the lead is re-scored (fix agreed: 2-hour wait plus a mirror data extension). HiGoals: cohort gate and
transition-flag defects, partly fixed on 2026-10-07.

## Medium

- **Zombie scheduled journeys from 2022–2023.** `Day 1–4 Completed MB Challenge` (published 2023-02-21,
  daily schedule, Amplitude cohort tables) processed about 2,000 contacts in a sampled hour;
  `Update Lead Engagement Score` and `Update Contact Engagement Score` (2022) run daily on
  `Einstein_MC_Predictive_Scores`. `DE_SMSOptOut_July2024` processes roughly 10,000 contacts an hour from a
  201,434-row table. Confirm each is still wanted; they are the heaviest load in the account.
- **One automation carries 20 journeys.** Master Customer Journey Daily Sends runs 20 queries in step 1 and then
  21 journey injections in sequence. A failure in step 1 stops every onboarding, renewal, birthday,
  anniversary, push and TDLI injection for the day, and the exit tables `EXIT_AllCanceledCustomers` (69,940) and
  `EXIT_AllCurrentCustomers` (5,912) that 25 journeys use to exit are refreshed in that same step. Worth splitting.
- **AC_ReviewQuoteStepJourney_September2026** entry table is a 3-day snapshot that is empty between runs; fine,
  but it means the journey cannot be re-run from history.
- **Journey Entry Throttling Automation** has been paused since 2025-10-01; AC_QuoteSteps also rebuilds
  `Emails_Sent_Last_14_Days`, so throttling still works, but two writers for one table is fragile.
- **Name drift.** 20 automation steps still carry 2024 journey names (e.g. `OB_WelcomeJourney_December2023`
  feeds `OB_WelcomeJourney_July2026`). Harmless, since steps bind by id, but it makes the automations hard to read.
- **Eight queries point at tables that no longer exist**, all in paused, inactive or never-run automations
  (AZ_Abandon_Quote_Copy, Contact_Salesforce_update, Master_Import_FTP_Daily, Migrate Prefs,
  Test_quote_journey, Unsubscribed - Automation 04172020). Only the Unsubbed one above is live.

## Low (hygiene)

- 7 automations stuck in "Building" with no run ever (Success Kit Automation, AZ_Abandon_Quote_Copy,
  ER_Permissions_Motion_Location, Example Automation - 05282020, JRH Test automation,
  Welcome_Journey_Train_Your_App, Zarchive Automation Abandon Cart 210819); 14 "Ready" and 13
  "InactiveTrigger" automations last run 2020–2024.
- 19 two-path decision splits whose second path has no criteria. They act as remainders because Journey Builder
  evaluates paths in order, so they are not bugs, but a labelled "Remainder" path is clearer
  (e.g. "Push Enabled", "Android", "Bundled", "$50 reward").
- `RE_NewsLetterContactBuild_September2025` still carries a 50/50 random split (one-off from 2025-09-29).
- Older versions' triggered-send definitions remain Active next to the live ones (RE_Anniversary,
  Year in Review, Rate Change Win-Back). Harmless unless something re-uses them.

## What looks healthy
Non-payment, review-quote (NBA), re-engagement, drivers/compare/discovery/saved-quote nurtures, onboarding
welcome/success-kit/countdown, monthly driving stats, hands-off phone challenge, accident detection and HiGoals
announcement all have running feeders, live definitions and sends in the last 14 days. No automation feeding a
published journey is in Error or Paused. Triggered-send bounce rates on live definitions are under 2%.

## Method notes
Journey history in this tenant ignores journey filters and caps at 10,000 rows, so failure counts are from
24 hours in 4-hour slices and success rates from a 4-hour sample. "Live" triggered-send definitions are matched
by step-name prefix and creation date equal to the version's publish date. Data-extension ModifiedDate is a
schema date, not a data refresh date, so staleness was judged by row counts and send events, not by it.
