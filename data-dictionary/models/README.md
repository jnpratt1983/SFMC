# Models

One JSON file per predictive model. The site's **Models** section (`/models/`) is built from these files plus a live
health pull (`pipeline/pull_models.py`).

What is maintained by hand here, and what is pulled:

| Part of the file | Source | Notes |
|---|---|---|
| `summary`, `predicts`, `population`, `usedFor`, `owner`, `stage`, `version` | hand | plain-English description |
| `components` | hand + pulled | `apiName` is the Einstein Studio configured-model name; status and input list are pulled |
| `outputs` | hand | `Object.Field` keys; each field page links back to the model |
| `chain` | hand + pulled | steps in run order; a step with `transform` gets last run, runs in 24 h and schedule from Data Cloud |
| `consumers` | hand | a `name` equal to a published journey's name becomes a link |
| `validation`, `quality` | hand | newest result first; add a row after every read and move `quality.nextReview` |
| `checks` | hand (thresholds) + pulled (observations) | see below |
| `manualTasks` | hand | the upkeep calendar; move `nextDue` forward after doing a task; leave it out for event-driven tasks |
| `openItems`, `docs` | hand | |

## Check types

- `model_enabled`: `model` = configured-model API name; passes when Einstein Studio reports Enabled.
- `transform_run`: `transform` = Data Cloud transform name; passes when the last run succeeded within `maxAgeHours`.
- `soql_max`: `soql` must return one value aliased `m` (a date or datetime); passes when it is within `maxAgeHours`.
- `row_match`: counts rows in objects `a` and `b`; passes when they differ by at most `tolerancePct` percent.

A model shows **Running** when every check passes, **Needs attention** when any fails, **Not checked** when the health
pull has not run. Checks are a reading at refresh time. For a current reading: `npm run refresh:models` (Salesforce CLI
auth only, about 20 seconds), then commit `data/`.

## Adding a model

Copy one of the files, change `id` (it becomes the URL), fill it in, run `npm run refresh:models`. Custom Einstein Studio
models that are enabled but have no file here are listed at the bottom of the Models page as "Enabled, not documented".
