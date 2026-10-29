# Spec v3 change list (DRAFT, held until the 2026-11-02 Insurance call confirms)

Decisions from Insurance (Kellett, Betz) 2026-10-29 and Jennifer's reply the same day:
no holdout of any length; exclude declining drivers from the journey and from training; no cadence or
channel test; everyone eligible gets the R-21 email and the R-14 push.

## 1. Entry query (`01_RE_ChurnRetention_Entry.sql`)

- `Arm` becomes the constant `'TREAT'`. Column stays so the history DE schema and the journey's
  history rows do not change. The `ROW_NUMBER() ... % 2` split is removed.
- New exclusion, the driving-decline rule, from `ENT.Monthly_Driving_Stat__c_Salesforce` (synced):
  average of the four display subscores, latest PNI cycle vs the cycle three back, down 5 or more,
  and latest trips greater than half the earlier trips. Draft SQL in `01_entry_v3_driving_exclusion.sql`.
  The rule fires only when both cycles have all four subscores, so missing data never excludes.
- Everything else unchanged: R-27 evaluation, tiers, non-pay 90-day exclusion, Heads Up 48-hour check,
  email-or-push reachability, `RatingVersion`, `LifetimeSavings`.

## 2. Journey Builder

- Remove the Arm decision split and the HOLDOUT lane. Canvas: entry, wait to R-21, STO, email, push
  eligibility split, wait to R-14, push, join, wait to R+30, exit.
- Exit criteria, goal and the `RE_ChurnRetention_Renewed` thank-you unchanged.

## 3. Content spec

- Remove the DISCOUNT_EROSION reason block, the `RE_Churn_Erosion_AZ/RI` content keys and the ENGAGE
  push variant that references the discount. Contacts tagged DISCOUNT_EROSION get `RE_Churn_CoverageFit`
  like PRICE_SHOCK and GENERAL. Eight blocks become six.
- `DiscountChange` stays on the entry DE for reporting; nothing renders it.
- Subject-line test by reason stays; it is the "simultaneous messaging test" Insurance asked for.

## 4. Test plan (`TEST_PLAN.md` v3, written in this PR; v2 moved to `TEST_PLAN_v2_holdout_appendix.md`)

- Primary reads, all labelled directional:
  1. Year-over-year term-end cohort: 60-day preventable cancel rate for entrants vs the same term-end
     weeks a year earlier, same tenure bucket, same state (the non-pay journey method).
  2. Cut-line comparison: entrants just above the tier-2 cut vs contacts just below it, same weeks,
     same tenure; and tier-1 offers just above $20 vs just below.
  3. Behavioral 90-day read (Irene): app session within 14 days, trips resumed within 30 days,
     coverage review completion within 7 days, vs the same measures for the just-below group.
- Gate 3 (randomized holdout), the power table and the O'Brien-Fleming interim plan move to an appendix
  titled "if a holdout is ever approved". Gates 1 and 2 unchanged.
- Calendar: launch week of 2026-11-16 if the copy review lands by 2026-11-09; first behavioral read
  2027-02; first retention read 2027-03 (entries Nov to Jan, outcomes through Feb).
- ANA-6132 updated to match.

## 5. Model retrain (v3.1)

- Training transform: add `Drv_Trips_Latest`, `Drv_Trips_Prior` (already computed per cycle window) and a
  row filter that drops rows where `Drv_Score_Latest - Drv_Score_Prior <= -5` and
  `Drv_Trips_Latest > 0.5 * Drv_Trips_Prior`. Scoring transform applies the same filter so excluded
  customers are not scored into the HIGH band.
- Retrain in Model Builder as v3.1, validate on the May to August 2026 holdout with `validate_holdout.py`,
  promote only if AUC >= 0.60 and top decile >= 2.0x (same as the Gate 2 bar). Expected effect: small;
  the excluded rows are about 5% of the book.
- Write-back script unchanged; cut points re-read from the new batch.

## 6. Checklist and summary

- Checklist section 1: add the 2026-10-29 Insurance decisions. Section 3: add the v3.1 retrain.
  Section 5: remove the Arm split item, add the driving exclusion to the entry query item. Section 6:
  replace holdout items with the three directional reads.
- Summary "recommendation" paragraph: remove the 50/50 sentence; add the exclusion rule and the
  directional read.
- Mockup page: remove the HOLDOUT lane and Arm split, remove the DISCOUNT_EROSION row and example send,
  update the volumes panel (no "treated after the 50/50" line), build order step 7 becomes the filter
  sign-off.

## 7. Data requests opened

- Driving feed to include non-PNI drivers (needed for "all drivers on a policy").
- How `earn_discount_curr_month__c` is calculated, so the 669 unexplained drops can be classified.
