# Quanata Data Dictionary

A living, Quanata-branded data dictionary for the HiRoad Salesforce org: every field on **Lead, Contact, Account, Bill and Monthly Driving Stats**, with where each one is used in **Marketing Cloud journeys** (down to the email, push, SMS, decision split and SQL query) and in **Data Cloud** (stream, data lake object, model object fields, calculated insights, segments, identity rules, data graphs, data actions, activations). It also lists every **calculated insight** with its SQL and where it is used.

Built with Next.js (static export) and Tailwind, hosted on Vercel, refreshed monthly by a GitHub Action.

## Run locally

```bash
cd data-dictionary
npm install
npm run dev          # http://localhost:3000
npm run build        # static site in out/
npm run refresh      # re-pull metadata and rebuild data/ (needs Salesforce CLI auth + Marketing Cloud creds)
```

## Deploy to Vercel

This site lives in the `data-dictionary/` folder of the SFMC repo.

1. In Vercel, **Add New → Project**, import `jnpratt1983/SFMC`.
2. Set **Root Directory** to `data-dictionary`. Framework preset **Next.js** is detected; nothing else to change (static export, output directory `out`).
3. Every push to `main` that touches `data-dictionary/` deploys. The monthly refresh commits to `main`, so the site updates itself.

## Monthly refresh

`.github/workflows/data-dictionary-refresh.yml` (at the repo root) runs on the 1st of each month (and on demand from the Actions tab). It needs these repository secrets:

| Secret | Value |
|---|---|
| `SFDX_AUTH_URL` | from `sf org display -o blueowl-prod --verbose --json` → `sfdxAuthUrl` (an integration user is better than a personal login) |
| `MC_CLIENT_ID`, `MC_CLIENT_SECRET`, `MC_AUTH_BASE` | the Marketing Cloud installed package used for audits (same values as `~/.config/sfmc/env`) |
| `MC_MID` | optional business unit MID |

The action pulls, rebuilds `data/`, verifies `npm run build`, and commits. The **Changes** page shows what was added or removed against the previous snapshot.

To refresh by hand: `npm run refresh`, then commit `data/`. The refresh log lists any field that has no entry in `definitions/`; add one there and rebuild.

## Layout

```
app/                      Next.js routes (home, objects, fields, journeys, queries, calculated-insights, data-cloud, changes)
components/               Header, search, field table, shared UI
lib/data.ts               typed access to data/dictionary.json
data/dictionary.json      the dictionary (generated)
data/search-index.json    compact index for the search box (generated)
data/snapshots/, changelog.json   monthly diffs (generated)
pipeline/                 pull + build scripts (see pipeline/README.md)
definitions/              hand-maintained field definitions, one JSON per object (see definitions/README.md)
public/brand/             Quanata logo SVGs
```

## Brand

Follows the Quanata identity standards: Inter everywhere; Carbon `#24263A` and Dust `#F4F3F0` as base; Qurple `#BB29BB` only for lines and highlights, never fills; Electricity, Ash and Seafoam as secondary accents; the grayscale set for rules and secondary text. Dark mode uses Carbon surfaces. Tokens live in `app/globals.css`.
