# Einstein lead score: model read and journey test plan

- `TEST_PLAN.md`: how the score is tested in two AC_ journeys (Purchase: combination of scoring, 4Q26; Drivers: communication
  medium by propensity, 1Q27). Test assignment uses standard Campaigns filled by a Journey Builder Campaign Member activity;
  no custom Lead fields.
- `EARLY_READ_2026-11-10.md`: forward reads of the re-scored model (2026-11-09 onward), updated 11-12 and 11-16, plus the
  two data facts the reads turned up (the quote flow updates a Lead for only 24 hours; `purchased__c` flaps on ~1 in 5 purchasers).
- `scripts/lead_score_read.py`: point-in-time purchase read from `Lead_Score_Snapshot__c` (score bands vs quote step and lead age).
- `scripts/lead_score_return_read.py`: person-level read of purchase and "back to quote" (a new Lead with the same email or
  cookie ID, or a quote change inside the lead's first 24 hours). Emails are hashed in memory and never written to disk.

## Running

Both scripts call the `sf` CLI against the `blueowl-prod` alias and need pandas:

```
python3 -m venv venv && venv/bin/python -m pip install pandas
venv/bin/python -I lead-score-test/scripts/lead_score_read.py --window 7
venv/bin/python -I lead-score-test/scripts/lead_score_return_read.py --window-days 7
```

LeadHistory exports exceed the CLI's 50,000-row default; the return script sets `SF_ORG_MAX_QUERY_LIMIT` itself.
Weekly cadence: rerun both on Mondays; the plan's section 0 and the early-read doc carry the dated results.
