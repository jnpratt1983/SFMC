# SFMC

Query activities and notes for HiRoad's Marketing Cloud Engagement tenant
(business unit "B2C Lifecycle Marketing", MID 110007736).

| Folder | Automation | Contents |
|---|---|---|
| automations/EN_HiGoals | EN_HiGoals (daily 09:00 PT) | the seven query activities, one file per step, with a README describing each change |
| journeys/AC_ReviewQuoteStepJourney | AC_NBATEST / AC_QuoteSteps (every 15 min) + AC_ReviewQuoteStepJourney_September2026 | Next Best Action channel-routing fix (2026-10-07): root cause of the missing call tasks, the journey change, and the staging query activity |
| audits | - | Marketing Cloud health audit 2026-10-07 and its read-only collector scripts |

Files are numbered in automation step order. Each file's header comment names the
query activity, its target data extension and update type, and what changed from the
version that was live when the file was written.
