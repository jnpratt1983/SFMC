/* DRAFT v3 addition to 01_RE_ChurnRetention_Entry.sql: driving-decline exclusion (Insurance 2026-10-29).
   Append to the WHERE clause. Uses the synced driving stats DE. A driver is excluded when the average of
   the four display subscores fell 5+ points between the latest PNI cycle and the cycle three back, and
   the latest cycle still has more than half the trips of the earlier one. Both cycles must have all four
   subscores, so missing data never excludes anyone.
   Also sets Arm to the constant 'TREAT' in the SELECT list (no holdout). */

    AND NOT EXISTS (
        SELECT 1
        FROM (
            SELECT d.customer_number__c,
                   ROW_NUMBER() OVER (PARTITION BY d.customer_number__c ORDER BY d.cycle_start__c DESC) AS rn,
                   d.n_trips_in_curr_month__c AS trips,
                   CASE WHEN d.subscore_display_safe_speeds_curr_month__c IS NULL
                          OR d.subscore_display_smooth_driving_curr_mon__c IS NULL
                          OR d.subscore_display_distracted_driving_curr__c IS NULL
                          OR d.subscore_display_driving_patterns_curr_m__c IS NULL THEN NULL
                        ELSE (d.subscore_display_safe_speeds_curr_month__c
                            + d.subscore_display_smooth_driving_curr_mon__c
                            + d.subscore_display_distracted_driving_curr__c
                            + d.subscore_display_driving_patterns_curr_m__c) / 4.0 END AS score
            FROM ENT.Monthly_Driving_Stat__c_Salesforce d
            WHERE d.driver_role__c = 'PNI'
        ) latest
        JOIN (
            SELECT d.customer_number__c,
                   ROW_NUMBER() OVER (PARTITION BY d.customer_number__c ORDER BY d.cycle_start__c DESC) AS rn,
                   d.n_trips_in_curr_month__c AS trips,
                   CASE WHEN d.subscore_display_safe_speeds_curr_month__c IS NULL
                          OR d.subscore_display_smooth_driving_curr_mon__c IS NULL
                          OR d.subscore_display_distracted_driving_curr__c IS NULL
                          OR d.subscore_display_driving_patterns_curr_m__c IS NULL THEN NULL
                        ELSE (d.subscore_display_safe_speeds_curr_month__c
                            + d.subscore_display_smooth_driving_curr_mon__c
                            + d.subscore_display_distracted_driving_curr__c
                            + d.subscore_display_driving_patterns_curr_m__c) / 4.0 END AS score
            FROM ENT.Monthly_Driving_Stat__c_Salesforce d
            WHERE d.driver_role__c = 'PNI'
        ) prior
          ON prior.customer_number__c = latest.customer_number__c AND prior.rn = 4
        WHERE latest.rn = 1
          AND latest.customer_number__c = c.Customer_Number__c
          AND latest.score IS NOT NULL AND prior.score IS NOT NULL
          AND prior.score - latest.score >= 5
          AND ISNULL(latest.trips, 0) > 0.5 * ISNULL(prior.trips, 0)
    )
