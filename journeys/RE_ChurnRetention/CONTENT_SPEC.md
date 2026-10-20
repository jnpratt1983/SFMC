# RE_ChurnRetention: dynamic content spec (2026-10-20)

One journey, one email template per step, one push template, with content blocks switched by three
fields that arrive on every entrant from the Data Cloud scoring batch via Contact:

| Field on the entry DE | Source | Values |
|---|---|---|
| `ChurnReason` | `Contact.Voluntary_Churn_Reason__c`, written monthly from the scoring transform's `Churn_Reason__c` | PRICE_SHOCK, DISCOUNT_EROSION, NEW_CUSTOMER, DISENGAGED, LOW_SAVINGS, GENERAL |
| `Band` | entry query | OFFER (tier 1, price rule) or HIGH (tier 2, v3 top decile) |
| `MailingState` | Contact | AZ, RI |
| `OfferChange` | `Contact.Voluntary_Churn_Offer_Change__c` (renewal offer $/month change, last 60 days) | number or blank |
| `DiscountChange` | `Contact.Voluntary_Churn_Discount_Change__c` (earned discount, latest cycle vs ~3 months earlier) | number or blank |
| `DrivingScore` | `Contact.Voluntary_Churn_Driving_Score__c` (mean of the four display subscores, latest cycle) | number or blank |

The reason is assigned in the transform with a fixed priority, so every customer has exactly one:
price shock (renewal offer > $20 or > 10%, or net premium up > $20 in 3 months), then discount erosion
(earned discount down 5+ points or driving score down 5+), then new customer (tenure < 180 days), then
disengaged (no app event in 60 days and no email open in 90), then low savings (earned discount under 5),
else general. Measured churn by reason is in the validation reports; price shock is 11 to 21%, discount
erosion 7%, the rest 5 to 6%.

## Content matrix

| Reason | What the data says | Mindset | Email angle (T-45) | App / push | Offer or action | CTA | Creative note |
|---|---|---|---|---|---|---|---|
| **PRICE_SHOCK** | Offered +$20 or +10% at renewal, or premium up $20+ in 3 months. 11% cancel under $50, 21% above. | "It went up and nobody told me why" | What changed in your rate and what you control: discount earned, how it carries into the new term, the two habits that move it most. Show the dollar change only if `OfferChange` is present. | "Your renewal is 45 days out. Your discount is worth $X this term." | Rate review or coverage check-in; discount recovery if driving data exists | See my renewal | Numbers up front, no marketing tone, one chart: premium vs discount |
| **DISCOUNT_EROSION** | Earned discount or driving score fell 5+ points over 3 cycles. 7.2% cancel. | "I'm being penalised" | Your discount and what moves it; the two trips habits that help most. Personalise with `DrivingScore` and `DiscountChange`. | Trip tips and how to keep the app tracking reliably | Discount recovery challenge for 30 days | Check my driving score | Driving score dial trending up; RI adds the HiGoals angle |
| **NEW_CUSTOMER** | Under 180 days tenure; 26% all-cause, 7.7% preventable. | Has not felt the value yet, still comparing | Welcome back to your policy: three things to set up in the app | Your first month of driving: what telematics already shows | Loyalty perk unlock or safe-driving discount preview | Open the app / complete setup | Phone with app onboarding checklist |
| **DISENGAGED** | No app event in 60 days and no email open in 90. 5.6% cancel. | Quiet churn, lukewarm | Short plain-text check-in: is your coverage still right? | One thing you may not know your policy does | One-question survey or preference update | Tell us what you need | Minimal, single illustration, lots of white space |
| **LOW_SAVINGS** | Earned discount under 5 points. Does not see the savings; price-shopping likely. | "What am I getting" | Your savings so far, in dollars; how your driving score turns into your rate | Savings meter with the customer's number | Rate review offer or coverage check-in | See my savings | Savings meter |
| **GENERAL** | None of the above triggered; entered on the model tier. | Unknown | The PRICE_SHOCK email without the dollar line | Standard renewal reminder | None | See my renewal | Default template |

Band changes intensity, not message: HIGH gets the T-21 follow-up email and the T-30 SMS; OFFER
gets T-45 and T+7 only unless the reason is PRICE_SHOCK, which always gets the full sequence.
State changes one block: RI references HiGoals rewards in DISCOUNT_EROSION and NEW_CUSTOMER; AZ
references the safe-driving discount.

## Journey Builder wiring

1. Entry DE columns `ChurnReason`, `Band`, `MailingState`, `OfferChange`, `DiscountChange`,
   `DrivingScore` are selected in the entry query from Contact; no decision split needed for reason.
2. One decision split on `Arm` (holdout), one on `Band` (intensity), one on channel consent. Reason
   and state are handled inside the templates, not by splits, which keeps the canvas at four paths.
3. Email template: six AMPscript content blocks keyed on `ChurnReason`, with a state sub-block where
   noted. Skeleton:

```
%%[
  SET @reason = AttributeValue("ChurnReason")
  SET @state  = AttributeValue("MailingState")
  SET @offer  = AttributeValue("OfferChange")
  SET @disc   = AttributeValue("DiscountChange")
  SET @score  = AttributeValue("DrivingScore")
  IF Empty(@reason) THEN SET @reason = "GENERAL" ENDIF
]%%
%%[ IF @reason == "PRICE_SHOCK" THEN ]%%
  %%=ContentBlockByKey("RE_Churn_PriceShock")=%%
  %%[ IF NOT Empty(@offer) AND @offer > 0 THEN ]%% <p>Your renewal offer is $%%=FormatNumber(@offer,"N2")=%% a month higher than your current rate.</p> %%[ ENDIF ]%%
%%[ ELSEIF @reason == "DISCOUNT_EROSION" THEN ]%%
  %%=ContentBlockByKey(IIF(@state == "RI", "RE_Churn_Erosion_RI", "RE_Churn_Erosion_AZ"))=%%
  %%[ IF NOT Empty(@score) THEN ]%% <p>Your driving score this cycle: %%=FormatNumber(@score,"N0")=%%.</p> %%[ ENDIF ]%%
%%[ ELSEIF @reason == "NEW_CUSTOMER" THEN ]%%
  %%=ContentBlockByKey(IIF(@state == "RI", "RE_Churn_New_RI", "RE_Churn_New_AZ"))=%%
%%[ ELSEIF @reason == "DISENGAGED" THEN ]%%
  %%=ContentBlockByKey("RE_Churn_Disengaged")=%%
%%[ ELSEIF @reason == "LOW_SAVINGS" THEN ]%%
  %%=ContentBlockByKey("RE_Churn_LowSavings")=%%
%%[ ELSE ]%%
  %%=ContentBlockByKey("RE_Churn_General")=%%
%%[ ENDIF ]%%
```

4. Content block keys to create in Content Builder: `RE_Churn_PriceShock`, `RE_Churn_Erosion_AZ`,
   `RE_Churn_Erosion_RI`, `RE_Churn_New_AZ`, `RE_Churn_New_RI`, `RE_Churn_Disengaged`,
   `RE_Churn_LowSavings`, `RE_Churn_General`. Eight blocks, one template.
5. Push (Engage reasons only): same `ChurnReason` attribute on the MobilePush contact, two message
   variants (DISCOUNT_EROSION, NEW_CUSTOMER), everything else gets no push.
6. Subject lines by reason, tested as the first A/B in the journey:
   PRICE_SHOCK "What changed in your rate, and what you control";
   DISCOUNT_EROSION "Your discount moved. Here is how to move it back";
   NEW_CUSTOMER "Three things to set up before your first renewal";
   DISENGAGED "Is your coverage still right?";
   LOW_SAVINGS "Your savings so far, in dollars";
   GENERAL "Your renewal is 45 days out".

## Insurance review

Every block is reviewed before activation. None mentions payment status, credit, the score, or the
band. PRICE_SHOCK shows the offered change only when it is present on the record and never quotes
the new premium itself, which the policy system communicates.
