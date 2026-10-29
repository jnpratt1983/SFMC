# RE_ChurnRetention: content spec v2 (2026-10-21)

One email at R-21, one push at R-14, one thank-you at R+7. Content blocks switch on `ChurnReason` and
`MailingState`; the Band and Track decide only who gets the push. Supersedes the 2026-10-20 spec, which had
a rate-change email at T-45 with the dollar change in it.

## Rules that shape every block (Insurance via Irene, 2026-10-21)

1. **No premium amounts, no price change, no rate figures.** The Heads Up email already carries the
   rate message under the same rule. `OfferChange` is on the entry DE for reporting and is never rendered.
2. **Discount and savings dollars are allowed.** The existing R-30 email shows the monthly Safe Driving
   Discount in dollars. `LifetimeSavings` is the value line.
3. Nothing about payment status, non-pay, credit, the score or the band.
4. The message is an action the customer can take, not an explanation of the rate: a coverage and
   deductible check-in in the app. The copy never says "cheaper" or promises a lower rate.
5. TDLI customers (`RatingVersion` starts `azV12`): the discount is locked for the whole next term, so no
   block says the discount can change this term. One true line: this term's driving sets the next term's discount.
6. Email and app push only.

## Fields on the entry DE that the templates read

| Field | Source | Use |
|---|---|---|
| `ChurnReason` | `Contact.Voluntary_Churn_Reason__c` | block selection |
| `MailingState` | Contact | AZ / RI sub-block |
| `RatingVersion` | latest `Renewal_Offer__c` | TDLI line vs monthly-model line |
| `LifetimeSavings` | `Contact.Lifetime_Savings__c` | value line, shown when > 0 |
| `DrivingScore` | `Contact.Voluntary_Churn_Driving_Score__c` | DISCOUNT_EROSION and LOW_SAVINGS personalisation |
| `DiscountChange` | `Contact.Voluntary_Churn_Discount_Change__c` | dollars of monthly earned discount, latest cycle minus ~3 cycles earlier; DISCOUNT_EROSION, monthly model only |
| `FirstName` | Contact | greeting |

## R-21 email: "Does your coverage still fit how you drive?"

Shared frame for every reason: greeting, one paragraph that names the term end in three weeks, the
value line (lifetime savings), one reason-specific block, one CTA to the coverage review in the app, a
plain customer care line. Subject line by reason, tested as the first A/B.

| Reason | Live count 2026-10-20 | Subject line | Reason block (the only part that changes) | State sub-block |
|---|---|---|---|---|
| **PRICE_SHOCK** | 986 | Does your coverage still fit how you drive? | Coverages and deductibles drift as cars, commutes and household change. A two-minute review in the app shows what you are carrying and what each piece does. For TDLI: your Safe Driving Discount is locked for the full next term; this term's driving sets the one after. For monthly model: your discount is earned each month from your driving. | none |
| **LOW_SAVINGS** | 37 | What you have saved with HiRoad so far | Savings meter with `LifetimeSavings`; how the driving score turns into the discount; same coverage review CTA. | none |
| **GENERAL** | 2,545 | Does your coverage still fit how you drive? | PRICE_SHOCK block without the TDLI/monthly line. | none |
| **DISCOUNT_EROSION** | 459 | Your discount moved. Here is what moves it back | Monthly model only (RI and legacy AZ): discount fell $`DiscountChange` a month over three cycles; the two subscores that fell; most drivers recover it within two cycles. TDLI customers get the PRICE_SHOCK block instead. | RI: HiGoals rewards progress. AZ: safe-driving discount. |
| **NEW_CUSTOMER** | 2,447 | Three things to set up before your first term ends | App setup checklist (permissions, trip logging, digital wallet). TDLI: your first locked discount is set from this term's driving. | RI: HiGoals. AZ: safe-driving discount. |
| **DISENGAGED** | 1,404 | Is your coverage still right? | Plain-text check-in, one question, the coverage review link, lots of white space. | none |

Live counts are the whole scored book, not the entry population.

## R-14 push: "Your coverage review is ready"

Eligible: TREAT arm, app opened, and (`Band = 'HIGH'` or `Track = 'ENGAGE'`). Two variants:

- ENGAGE reasons: "Three weeks to your new term. Your coverage review takes two minutes."
- Everyone else eligible: "Your term ends in two weeks. Make sure your coverage still fits."

Deep link to the coverage review. No amounts of any kind.

## R+7 thank-you (journey `RE_ChurnRetention_Renewed`)

"Thanks for staying with HiRoad." Lifetime savings line, one app tip by reason (ENGAGE: trip logging;
others: digital wallet). No amounts beyond the savings figure.

## AMPscript skeleton (R-21 template)

```
%%[
  SET @reason  = AttributeValue("ChurnReason")
  SET @state   = AttributeValue("MailingState")
  SET @rv      = AttributeValue("RatingVersion")
  SET @tdli    = IIF(Substring(@rv, 1, 5) == "azV12", "true", "false")
  SET @savings = AttributeValue("LifetimeSavings")
  SET @score   = AttributeValue("DrivingScore")
  SET @disc    = AttributeValue("DiscountChange")
  IF Empty(@reason) THEN SET @reason = "GENERAL" ENDIF
  IF @reason == "DISCOUNT_EROSION" AND @tdli == "true" THEN SET @reason = "PRICE_SHOCK" ENDIF
]%%
%%[ IF NOT Empty(@savings) AND @savings > 0 THEN ]%%
  <p>Since you joined, safe driving has saved you $%%=FormatNumber(@savings,"N0")=%%.</p>
%%[ ENDIF ]%%
%%[ IF @reason == "PRICE_SHOCK" THEN ]%%
  %%=ContentBlockByKey("RE_Churn_CoverageFit")=%%
  %%=ContentBlockByKey(IIF(@tdli == "true", "RE_Churn_TDLI_Line", "RE_Churn_Monthly_Line"))=%%
%%[ ELSEIF @reason == "LOW_SAVINGS" THEN ]%%
  %%=ContentBlockByKey("RE_Churn_LowSavings")=%%
%%[ ELSEIF @reason == "DISCOUNT_EROSION" THEN ]%%
  %%=ContentBlockByKey(IIF(@state == "RI", "RE_Churn_Erosion_RI", "RE_Churn_Erosion_AZ"))=%%
  %%[ IF NOT Empty(@score) THEN ]%% <p>Your driving score this cycle: %%=FormatNumber(@score,"N0")=%%.</p> %%[ ENDIF ]%%
%%[ ELSEIF @reason == "NEW_CUSTOMER" THEN ]%%
  %%=ContentBlockByKey(IIF(@state == "RI", "RE_Churn_New_RI", "RE_Churn_New_AZ"))=%%
%%[ ELSEIF @reason == "DISENGAGED" THEN ]%%
  %%=ContentBlockByKey("RE_Churn_Disengaged")=%%
%%[ ELSE ]%%
  %%=ContentBlockByKey("RE_Churn_CoverageFit")=%%
%%[ ENDIF ]%%
```

Content block keys: `RE_Churn_CoverageFit`, `RE_Churn_TDLI_Line`, `RE_Churn_Monthly_Line`,
`RE_Churn_LowSavings`, `RE_Churn_Erosion_AZ`, `RE_Churn_Erosion_RI`, `RE_Churn_New_AZ`, `RE_Churn_New_RI`,
`RE_Churn_Disengaged`. Nine blocks, one template, two push variants.

## Review path

Irene reviews the R-21 copy first, then Insurance reviews every block. The reviewer checklist: no premium or
rate figure anywhere, no "cheaper" or "lower rate" promise, no mention of payment, credit, score or band,
TDLI line only on azV12 records.
