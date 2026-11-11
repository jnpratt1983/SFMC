# Pipeline

Five stdlib-only Python scripts turn live metadata into `data/dictionary.json` (read by the site at build time), `data/search-index.json` (loaded in the browser for search), a dated snapshot in `data/snapshots/` and `data/changelog.json`.

| Script | Source | What it pulls |
|---|---|---|
| `pull_salesforce.py` | REST describe, Tooling `CustomField`, `FieldDefinition`, Metadata API | Every field on Lead, Contact, Account, Bill__c, Monthly_Driving_Stat__c with type, picklists, formula, description, help text, created/modified; the Data Cloud package-kit field maps (`DataSrcDataModelFieldMap`); Flows and Apex that name a `__dlm`/`__cio` object |
| `pull_datacloud.py` | `/ssot/*` Connect API | Data streams with field mappings, DLO and DMO metadata, calculated insights (SQL included), segments with criteria, activations, data graphs, data actions, transforms, identity resolution rules |
| `pull_sfmc.py` | Marketing Cloud REST + SOAP | Published journeys (`extras=all`), their event definitions, all automations and SQL query activities, data extensions (fields for the `*_Salesforce` synced DEs, journey entry DEs and query targets), and the email / push / SMS assets used by published journeys |
| `pull_models.py` | `/ssot/data-transforms`, `/ssot/machine-learning/configured-models`, SOQL | For the models in `models/*.json`: transform last runs, run history and schedules, Einstein Studio model status and inputs, and the freshness and row-count checks each model file declares |
| `build.py` | the raw JSON above | Resolves usage and writes the outputs |

Run everything with `bash pipeline/refresh.sh` (or `npm run refresh`). Raw pulls land in `pipeline/raw/` (git-ignored) and the scripts are incremental enough to re-run freely.

## Credentials

* Salesforce: `sf org display -o blueowl-prod` locally, or `SF_ACCESS_TOKEN` + `SF_INSTANCE_URL`. The Metadata API step shells out to the `sf` CLI, so the CLI must be installed and authenticated (`SF_ORG` picks the alias).
* Marketing Cloud: `MC_CLIENT_ID`, `MC_CLIENT_SECRET`, `MC_AUTH_BASE` (optional `MC_MID`) as environment variables, or the same `export` lines in `~/.config/sfmc/env`. The installed package needs read scopes on journeys, automations, data extensions, email and documents/images.

## How usage is resolved

Marketing Cloud (per object `O`, synced DE `O_Salesforce`):

1. A field is **synced** when the DE has a column with the same API name.
2. A **SQL query** uses the field when its text references the synced DE (`ent.O_Salesforce`, `[O_Salesforce]`, with or without alias) and the column name. Qualified references (`alias.Column`) are attributed to the right table; unqualified ones to every synced table in the query that has the column.
3. A **journey** uses the field when
   * a query in the chain that fills its entry data extension uses it (queries targeting the entry DE, then queries targeting those queries' staging DEs, up to three levels),
   * a decision split, entry filter, Sales Cloud activity, Update Contact Data activity, email (subject, preheader, HTML, content blocks), push or SMS references a column of the entry DE or does a `Lookup` on a synced DE. Entry-DE columns are attributed to a field only through an object whose synced DE appears in the chain, or when the column is a custom field name unique to one object,
   * the journey is triggered by a Salesforce data event on the object (event fields and filter fields are read directly).
4. Only journeys with status Published (or Sent) are traced. Stopped and Draft journeys are counted in the overview only.

Data Cloud:

1. The CRM data stream mapping gives Salesforce field → DLO column.
2. DLO column → DMO field comes from the package-kit field maps for standard fields. Custom fields are matched by name against the DMOs the kit maps the object to, plus any DMO sharing at least `AUTO_DMO_MIN_MATCHES` custom field names with the stream, plus `DMO_OVERRIDES` in `build.py`. Exact name, DLO-style name (`Field_c__c`) and a normalized comparison (case and underscores ignored) are tried in that order; the field page shows which rule applied.
3. Calculated insight SQL, segment include/exclude criteria, identity resolution match and reconciliation rules, data graph fields, data action projections and activation record schemas are scanned for `DMO.field` references and attributed back through step 2.
4. A calculated insight is "used" by the segments whose criteria reference it, other insights whose SQL references it, data graphs that include it, data actions that project it, activations of those segments, and any Flow or Apex class that names it. Reads through the query API, Tableau or CRM Analytics are not visible.

Known gaps: data transform definitions are not exposed by the API; Marketing Cloud content blocks referenced by `ContentBlockById` inside an email are not fetched; a DE column that was renamed in SQL (`SELECT Field__c AS other`) is resolved only as the original name.
