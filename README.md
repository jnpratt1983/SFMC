# SFMC

Query activities and notes for HiRoad's Marketing Cloud Engagement tenant
(business unit "B2C Lifecycle Marketing", MID 110007736).

| Folder | Automation | Contents |
|---|---|---|
| automations/EN_HiGoals | EN_HiGoals (daily 09:00 PT) | the seven query activities, one file per step, with a README describing each change |
| journeys/AC_ReviewQuoteStepJourney | AC_NBATEST / AC_QuoteSteps (every 15 min) + AC_ReviewQuoteStepJourney_September2026 | Next Best Action channel-routing fix (2026-10-07): root cause of the missing call tasks, the journey change, and the staging query activity |
| journeys/TR_NonPaymentJourney | TR_NonPaymentJourney (daily 06:00) + TR_NonPaymentJourney_February2026 | Non-pay journey lift analysis (2026-10-16): what actually sent since launch, cure-rate lift by period and day, coverage gap, the two entry/exit query activities, read-only collectors |
| journeys/ChurnRiskActivation | Churn Risk activation (Predicted Did Cancel V7), not yet launched | Out-of-time validation (2026-10-16) of `Normalized_Churn_Risk_Score__c` and `Churn_Risk_Score__c` against actual cancellations: AUCs vs tenure and persona baselines, band fit, training-set diagnosis, reproducible script and data |
| journeys/RE_ChurnRetention | RE_ChurnRetention (planned, daily 06:30) + RE_ChurnRetention_<Month>2026 | Renewal-window retention journey spec (2026-10-16): entry, suppression and exit query activities, DE schemas, tracks by churn factor, measurement without holdouts, prerequisites |
| audits | - | Marketing Cloud health audit 2026-10-07 and its read-only collector scripts |

Files are numbered in automation step order. Each file's header comment names the
query activity, its target data extension and update type, and what changed from the
version that was live when the file was written.
