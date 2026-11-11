# Field definitions

One JSON file per object (`Lead.json`, `Contact.json`, `Account.json`, `Bill__c.json`,
`Monthly_Driving_Stat__c.json`). Each maps a field API name to its plain-English
definition:

```json
{
  "Projected_First_Month_Bill__c": {
    "definition": "The estimated first-month premium shown on the quote, used in quote-abandon emails and the Review NBA query.",
    "confidence": "high"
  }
}
```

- `definition` is what the site shows at the top of the field page and in the
  field tables. Keep it to one to three sentences.
- `confidence` is `high`, `medium` or `low`. Anything below `high` is flagged on
  the field page so reviewers know to check it. Delete the key once reviewed.

The build (`pipeline/build.py`) overlays these on the Salesforce metadata. When a
field has no entry here, the site falls back to the Salesforce field description,
and if that is empty too the page says "No definition yet". The monthly refresh
log lists every field that is missing a definition, so new fields show up there
after each run.

The first draft (2026-11-11) was generated from each field's label, type, formula,
picklist values, the Marketing Cloud SQL and journey activities that read it, and
the Data Cloud insights it feeds. Edit freely; the files are the source of truth.
