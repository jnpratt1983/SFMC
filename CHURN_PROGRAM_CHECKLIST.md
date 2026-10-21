# Voluntary churn program: end-to-end checklist

Status as of 2026-10-21 00:45 UTC (2026-10-20 evening Chicago). Checked items are built and verified;
unchecked items are still needed, with the owner. Folder references are in this repo unless stated.

## 1. Decisions and governance

- [x] Insurance (Jennifer Kellett, Sandy): retrain without non-pay; voluntary churn only (DS-3265 option 2)
- [x] Compliance: 50/50 randomized holdout approved for the retention journey (2026-10-20)
- [x] Model's non-pay correlation accepted; v3 ships as is (2026-10-20)
- [x] Journey has no call tasks (no call resources, 2026-10-19)
- [x] Scope: Arizona and Rhode Island, which is the whole book
- [ ] Insurance: are chronic non-payers excluded from all retention outreach or only this journey? (sets the entry filter; currently any non-pay notice in 90 days excludes) — Insurance
- [ ] Insurance: is "Insured request - other" preventable? (currently counted as preventable) — Insurance
- [ ] Insurance content review of the eight content blocks and the exclusion rule — Insurance

## 2. Salesforce (blueowl-prod)

- [x] `Renewal_Offer__c` custom object, nine fields, external key AccountId + offer date (`force-app/.../objects/Renewal_Offer__c` in c360-sfdx)
- [x] Flow `Renewal Offer Capture` on Account, active (fires when the renewal offer date is set or changes)
- [x] 7,606 historical offers backfilled from AccountHistory (Oct 2025 to Oct 2026), bulk upsert, 0 failures
- [x] Contact fields: `Voluntary_Churn_Risk_Score__c`, `_Band__c`, `_Scored_At__c`, `_Top_Factors__c` (history tracked; Contact is at the 20-field history cap), `_Reason__c`, `_Offer_Change__c`, `_Discount_Change__c`, `_Driving_Score__c`
- [x] First write-back to Contact: 7,878 contacts scored 2026-10-20 (High 795, Moderate 1,568, Low 5,515)
- [x] Monthly write-back scheduled: launchd `com.hiroad.churn-writeback` on Jennifer's Mac, 2nd of the month 07:00 Chicago, `~/Desktop/c360-sfdx/scripts/run_churn_writeback.sh`, logs in `~/Library/Logs/churn/`
- [x] Data Cloud connector permission set reads the new Contact, Account, Renewal Offer and driving fields
- [x] Marketing Cloud sync user (API SFMC User, System Administrator) reads all new fields
- [ ] Verify the flow captured the first live offers after the nightly batch (~03:47 UTC 2026-10-21): `SELECT COUNT(Id) FROM Renewal_Offer__c WHERE CreatedDate > 2026-10-20T21:00:00Z` — Claude, morning of 2026-10-21
- [ ] Add the Voluntary Churn fields to the Contact page layout so agents can see score, band and reason — Salesforce admin, optional
- [ ] After two production batches: point `Customer360PersonaBatch`, the Customer 360 component (`Customer360Controller` still reads `Churn_Risk_Score__c`) and the Wave dataset at the new fields in one change; then disable `ChurnRiskScoreOutput` and `ChurnRiskScoreNormalizedOutput` — Jennifer with Claude, December

## 3. Data Cloud

- [x] Streams: Contact (term dates, last app open, safe-driving discount added), Account (four renewal-offer fields), `Renewal_Offer__c` (streaming), `Monthly_Driving_Stat__c` (219,710 rows), `Churn_Snapshot_Calendar` (54 rows, 2024-07 to 2028-12, no monthly maintenance)
- [x] Training transform `ChurnPITTrainingSet` (API-created; offers, driving, bills, email by address, app, tickets; closed-window calendar filter; `Churn_Reason__c`), 237,980 rows over 26 snapshots, leakage audit 0
- [x] Views `ChurnPITTrainV3` / `ChurnPITHoldoutV3` (179,196 / 25,419 rows, 51 columns); V1 and V2 views still exist
- [x] Data model objects mapped: train and holdout V1, V2, V3; `Churn_PIT_Scoring_Set`
- [x] Scoring transform `ChurnPITScoringSet` (one snapshot at run time, 7,878 active contacts, runs daily)
- [x] Models in Einstein Studio: v1 (0.579), v2 (0.599), v3 (0.627, production); holdout scores V1, V2, V3
- [x] Production predict job `Voluntary Churn 60d v3 - Production Scoring`, Streaming, output `Voluntary_Churn_Score`
- [ ] Re-map `Churn_PIT_Scoring_Set` DMO to add `Churn_Reason__c` (only needed if a DMO consumer wants the reason; the write-back reads the lake object) — Jennifer, optional
- [ ] Clean up V1/V2 artifacts: `ChurnPITTrain`, `ChurnPITHoldout`, `ChurnPITTrainV2`, `ChurnPITHoldoutV2` and their lake objects and DMOs; `Voluntary_Churn_Holdout_Scores` and `_V2`; the v1 and v2 models — Jennifer, optional
- [ ] Set the training transform and views to monthly instead of daily (harmless as is) — optional

## 4. Analysis and documentation (this repo, `journeys/ChurnRiskActivation`)

- [x] Normalized score validation (2026-10-16): AUC 0.59, worse than tenure
- [x] v1, v2, v3 holdout validation reports; decision memo (the renewal offer is the prediction)
- [x] Retrain runbook, build guide, transform generator (`build_transform_json.py`), view builder, `validate_holdout.py`, `write_back_scores.py`, `churn_score_validation.py`
- [x] Journey spec, test plan with power table, content spec, DE schemas, three query activities, `create_des.py`
- [ ] Re-validate the live score against the first two production months' outcomes (expect ~0.63) — Claude, December and January
- [ ] Re-run the power table once the journey's actual monthly entrants are known — Claude, after month 1

## 5. Marketing Cloud

- [x] Marketing Cloud Connect sync: seven `Voluntary_Churn_*` fields, both term dates, driver role, DNR on `Contact_Salesforce`; `Renewal_Offer__c_Salesforce`; `Monthly_Driving_Stat__c_Salesforce`
- [x] Data extensions in Airflow Data: `RE_ChurnRetention_Config_AF_10202026` (row: HighCut 59.99, ModerateCut 49.05, batch 2026-10-20), `_Entry_AF_10202026` (sendable on Id), `_History_AF_10202026`, `_Exit_AF_10202026`
- [ ] Query activities from `journeys/RE_ChurnRetention/01..03_*.sql` and automation `RE_ChurnRetention` daily 06:30 (entry Overwrite, history Append, exit Overwrite) — Jennifer or Claude via API
- [ ] Run the entry query once and confirm 5 to 10 rows a day with the expected mix of OFFER and HIGH bands — Claude can verify by API
- [ ] Eight content blocks and the email template with the AMPscript switch (`CONTENT_SPEC.md`); subject lines per reason — Jennifer
- [ ] Two push templates for DISCOUNT_EROSION and NEW_CUSTOMER — Jennifer
- [ ] Journey `RE_ChurnRetention_<Month>2026`: entry source, decision splits on Arm then Band then channel, step timings per track, exit on the exit DE, goal "not cancelled 30 days after term end" — Jennifer
- [ ] Thank-you journey `RE_ChurnRetention_Renewed` fed by the exit DE's RENEWED rows — Jennifer
- [ ] Add the journey to the lifecycle-watch list (`lifecycle-watch.md`, `scripts/lifecycle_watch.py` in c360-sfdx) once published — Claude
- [ ] Launch in AZ and RI with the 50/50 split after Insurance sign-off — Jennifer

## 6. Measurement, after launch (`journeys/RE_ChurnRetention/TEST_PLAN.md`)

- [ ] Gate 1, first four weeks: entrants per day, zero entrants with a non-pay notice in 90 days, sends within 24 hours, exits within a day, nobody stuck in a wait, unsubscribe rate under 0.5%
- [ ] Gate 2, monthly: validation row per batch, cut points copied into the config DE (the write-back prints them)
- [ ] Interim reads at months 4 and 8 of entries; final read on 12 months of entries, stratified by state, tenure and band
- [ ] Quarterly: retrain on closed snapshots; promote only if it beats v3 on the same holdout

## 7. Known constraints to keep in mind

- Contact is at the 20-field history-tracking cap; nothing else on Contact can be tracked without retiring a field.
- Offers before 2025-11 do not exist anywhere; the price feature's training history starts there.
- Email history in Individual Email Results is thin for 2024 and 2025 even after matching on address.
- The v3 top decile carries more non-pay history than the rest (35% vs 23% in 90 days), driven by invoice count and premium level; accepted, and the journey's 90-day non-pay exclusion governs targeting.
- Pull requests merge fast in this repo; every batch of commits gets its own PR.
