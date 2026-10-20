#!/usr/bin/env python3
"""Generates the Data Cloud batch data transform definition for Churn_PIT_Training_Set.

Format matches what GET /services/data/v64.0/ssot/data-transforms/<name> returns for the
existing ChurnRiskTrainingSetNormalized transform (Data Prep recipe nodes, version 56.0, type STL).

Outputs (next to this script):
  Churn_PIT_Training_Set.json       readable definition (formulas unescaped)
  Churn_PIT_Training_Set.api.json   POST body for /ssot/data-transforms (raw SQL formulas; the API escapes them on storage)
  Churn_Snapshot_Calendar.csv       26 monthly snapshot rows to load as a CSV data stream

Run: python3 build_transform_json.py
"""
import csv, html, json, os, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
WITH_OFFERS = "--without-offers" not in sys.argv   # the Renewal_Offer__c lake object must exist before the offers branch can be posted
SUFFIX = "" if WITH_OFFERS else ".nooffers"
SNAP = '"Cal.Snap_Date"'
SNAPKEY = '"Cal.Snap_Key"'
PREVENTABLE = "('Due to high premium','Replacement of insurance carrier','Insured request - other','App issue / UX','Due to poor customer service','Due to poor claims service')"

nodes, ui_nodes, ui_conn = {}, {}, []

def load(nid, name, dtype, fields, label, top, left):
    nodes[nid] = {"action": "load", "sources": [], "parameters": {"dataset": {"name": name, "type": dtype}, "fields": fields,
                  "sampleDetails": {"type": "TopN"}}}
    ui_nodes[nid] = {"label": label, "type": "LOAD_DATASET", "top": top, "left": left, "parameters": {"sampleSize": 500, "sampleDetails": {"type": "TopN"}, "dataspace": "default"}}

def filt(nid, src, exprs, label, top, left, logic=None):
    p = {"filterExpressions": exprs}
    if logic: p["filterBooleanLogic"] = logic
    nodes[nid] = {"action": "filter", "sources": [src], "parameters": p}
    ui_nodes[nid] = {"label": label, "type": "FILTER", "top": top, "left": left}

def num_field(name, expr, label=None, precision=18, scale=0):
    return {"businessType": "Number", "defaultValue": "", "formulaExpression": expr, "label": label or name.replace("_", " "), "name": name, "precision": precision, "scale": scale, "type": "NUMBER"}
def text_field(name, expr, label=None, precision=255):
    return {"businessType": "Text", "defaultValue": "", "formulaExpression": expr, "label": label or name.replace("_", " "), "name": name, "precision": precision, "type": "TEXT"}
def date_field(name, expr, label=None):
    return {"businessType": "DateTime", "defaultValue": "", "format": "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", "formulaExpression": expr, "label": label or name.replace("_", " "), "name": name, "type": "DATETIME"}

def transform(uid, src, fields, label, top, left, description=""):
    """Chain one formula node per field inside one UI Transform node. Returns last node id."""
    prev = src; graph = {}; conns = []
    for i, f in enumerate(fields):
        nid = f"{uid}_F{i}"
        nodes[nid] = {"action": "formula", "sources": [prev], "parameters": {"expressionType": "SQL", "fields": [f]}}
        graph[nid] = {"parameters": {"type": "BASE_FORMULA_UI"}, "label": f["label"]}
        if prev != src: conns.append({"source": prev, "target": nid})
        prev = nid
    ui_nodes[uid] = {"label": label, "description": description, "type": "TRANSFORM", "top": top, "left": left, "graph": graph, "connectors": conns}
    return prev

def join(nid, left, right, lkeys, rkeys, qual, jtype, label, top, left_px, drop=None):
    nodes[nid] = {"action": "join", "sources": [left, right], "parameters": {"joinType": jtype, "leftKeys": lkeys, "rightKeys": rkeys, "rightQualifier": qual},
                  "schema": {"fields": [], "slice": {"fields": drop or [], "ignoreMissingFields": True, "mode": "DROP"}}}
    ui_nodes[nid] = {"label": label, "type": "JOIN", "top": top, "left": left_px}

def aggregate(uid, src, groupings, aggs, label, top, left):
    ex, ag = f"{uid}_EXTRACT", f"{uid}_AGG"
    nodes[ex] = {"action": "extractGrains", "sources": [src], "parameters": {"grainExtractions": []}}
    nodes[ag] = {"action": "aggregate", "sources": [ex], "parameters": {"aggregations": aggs, "groupings": groupings, "nodeType": "STANDARD"}}
    numeric = [{"name": a["name"], "newProperties": {"typeProperties": {"precision": 18, "scale": 0, "type": "NUMBER"}}} for a in aggs if a["action"] in ("SUM", "COUNT")]
    if numeric: nodes[ag]["schema"] = {"fields": numeric}
    ui_nodes[uid] = {"label": label, "description": "", "type": "AGGREGATE", "top": top, "left": left, "graph": {ex: None, ag: None}, "connectors": [{"source": ex, "target": ag}]}
    return ag

def ui_link(a, b): ui_conn.append({"source": a, "target": b})

# ---------------------------------------------------------------- calendar (row 0)
load("LOAD_CAL", "Churn_Snapshot_Calendar__dll", "dataLakeObject", ["Snapshot_Date__c", "Snapshot_Key__c"], "Snapshot calendar", 60, 112)
cal_last = transform("T_CAL", "LOAD_CAL", [
    date_field("Snap_Date", "to_timestamp(Snapshot_Date__c)", "Snap Date (timestamp so it compares with event datetimes)"),
    text_field("Snap_Key", "date_format(Snapshot_Date__c, 'yyyyMM')", "Snap Key (yyyyMM, derived from the date; the stream's Snapshot_Key__c landed as Number)", 10),
    num_field("xk", "1", "Cross-join key"),
], "Calendar keys", 60, 392, "Snapshot date, key, and a constant join key for the cross join")
ui_link("LOAD_CAL", "T_CAL")

# ---------------------------------------------------------------- contact book (row 1)
load("LOAD_CON", "Contact__dll", "dataLakeObject", ["Id__c", "AccountId__c", "account_id_c__c", "Customer_Number_c__c", "CreatedDate__c", "Policy_Effective_Date_c__c",
     "Cancel_Date_c__c", "Cancellation_Reason_c__c", "Policy_Renewal_Date_c__c", "Renewal_Offer_Date_c__c", "Policy_Renewal_Rate_c__c",
     "Lifetime_Savings_c__c", "Telematic_Discount_Numeric__c", "Current_Term_Effective_Date_c__c", "Current_Term_Expiration_Date_c__c",
     "Last_App_Open_Date_c__c", "Monthly_Safe_Driving_Discount_c__c"], "Contact", 250, 112)
filt("FILTER_CON", "LOAD_CON", [
    {"field": "Id__c", "operands": ["003"], "operator": "STARTS_WITH", "type": "TEXT"},
    {"field": "Policy_Effective_Date_c__c", "operands": [], "operator": "IS_NOT_NULL", "type": "DATETIME"}], "Contacts with a policy", 250, 392, "1 AND 2")
ui_link("LOAD_CON", "FILTER_CON")
con_k = transform("T_CON_K", "FILTER_CON", [num_field("xk", "1", "Cross-join key")], "Contact join key", 250, 672)
ui_link("FILTER_CON", "T_CON_K")
join("JOIN_BOOK", con_k, cal_last, ["xk"], ["xk"], "Cal", "INNER", "Contact x snapshot", 250, 952, drop=["Cal.xk", "Cal.Snapshot_Date__c", "Cal.Snapshot_Key__c"])
ui_link("T_CON_K", "JOIN_BOOK"); ui_link("T_CAL", "JOIN_BOOK")
book = transform("T_BOOK", "JOIN_BOOK", [
    num_field("In_Book", f"case when Policy_Effective_Date_c__c <= {SNAP} and CreatedDate__c <= {SNAP} and (Cancel_Date_c__c is null or Cancel_Date_c__c > {SNAP}) then 1 else 0 end", "In book at snapshot"),
], "Active-book flag", 250, 1232, "Policy in force on the snapshot date and not yet cancelled")
filt("FILTER_BOOK", book, [{"field": "In_Book", "operands": ["1"], "operator": "EQUAL", "type": "NUMBER"}], "Keep in-book rows", 250, 1512)
ui_link("JOIN_BOOK", "T_BOOK"); ui_link("T_BOOK", "FILTER_BOOK")
if WITH_OFFERS:
    # ---------------------------------------------------------------- renewal offers (row F): Renewal_Offer__c captured by the Account flow, point-in-time
    load("LOAD_OFFER", "Renewal_Offer_c_00D3h0000068eod__dll", "dataLakeObject", ["Account_c__c", "Offer_Date_c__c", "Increase_Amount_Dollars_c__c", "Policy_Renewal_Rate_c__c", "Prior_Rate_c__c", "Increase_Percent_c__c", "Rating_Version_c__c"], "Renewal offers", 1010, 112)
    off_k = transform("T_OFFER_K", "LOAD_OFFER", [num_field("xk", "1", "Cross-join key")], "Offer join key", 1010, 392)
    ui_link("LOAD_OFFER", "T_OFFER_K")
    join("JOIN_OFFER_CAL", off_k, cal_last, ["xk"], ["xk"], "Cal", "INNER", "Offer x snapshot", 1010, 672, drop=["Cal.xk", "Cal.Snapshot_Date__c", "Cal.Snapshot_Key__c"])
    ui_link("T_OFFER_K", "JOIN_OFFER_CAL"); ui_link("T_CAL", "JOIN_OFFER_CAL")
    off_f = transform("T_OFFER_W", "JOIN_OFFER_CAL", [
        num_field("Offer_In_Window", f"case when Offer_Date_c__c <= {SNAP} and Offer_Date_c__c > {SNAP} - INTERVAL 60 DAY then 1 else 0 end", "Offer issued in the 60 days before the snapshot"),
        text_field("Snap_Key_Offer", SNAPKEY, "Snap key (offer)", 10),
    ], "Offer window", 1010, 952)
    filt("FILTER_OFFER", off_f, [{"field": "Offer_In_Window", "operands": ["1"], "operator": "EQUAL", "type": "NUMBER"}], "Offers in window", 1010, 1232)
    ui_link("JOIN_OFFER_CAL", "T_OFFER_W"); ui_link("T_OFFER_W", "FILTER_OFFER")
    off_agg = aggregate("AGG_OFFER", "FILTER_OFFER", ["Account_c__c", "Snap_Key_Offer"], [
        {"action": "MAX", "label": "Latest offer date", "name": "Latest_Offer_Date", "source": "Offer_Date_c__c"}], "Latest offer per account-snapshot", 1010, 1512)
    ui_link("FILTER_OFFER", "AGG_OFFER")
    # bring the latest offer's values back: join the aggregate to the offer rows on account + date
    join("JOIN_OFFER_LATEST", off_agg, "LOAD_OFFER", ["Account_c__c", "Latest_Offer_Date"], ["Account_c__c", "Offer_Date_c__c"], "Off", "LEFT_OUTER", "Latest offer values", 1010, 1792, drop=["Off.Account_c__c", "Off.Offer_Date_c__c"])
    ui_link("AGG_OFFER", "JOIN_OFFER_LATEST"); ui_link("LOAD_OFFER", "JOIN_OFFER_LATEST")
    join("JOIN_ACCT", "FILTER_BOOK", "JOIN_OFFER_LATEST", ["AccountId__c", "Cal.Snap_Key"], ["Account_c__c", "Snap_Key_Offer"], "Acct", "LEFT_OUTER", "+ renewal offer", 250, 1652, drop=["Acct.Account_c__c", "Acct.Snap_Key_Offer"])
    ui_link("JOIN_OFFER_LATEST", "JOIN_ACCT"); ui_link("FILTER_BOOK", "JOIN_ACCT")
labels = transform("T_LABELS", "JOIN_ACCT" if WITH_OFFERS else "FILTER_BOOK", [
    num_field("Cancel_In_60d", f"case when Cancel_Date_c__c > {SNAP} and Cancel_Date_c__c <= {SNAP} + INTERVAL 60 DAY then 1 else 0 end", "Cancel within 60d"),
    num_field("Cancel_In_90d", f"case when Cancel_Date_c__c > {SNAP} and Cancel_Date_c__c <= {SNAP} + INTERVAL 90 DAY then 1 else 0 end", "Cancel within 90d"),
    num_field("Preventable", f"case when Cancellation_Reason_c__c in {PREVENTABLE} then 1 else 0 end", "Preventable voluntary reason"),
    num_field("Label_60", "case when Cancel_In_60d = 1 and Preventable = 1 then 1 else 0 end", "Label 60d"),
    num_field("Label_90", "case when Cancel_In_90d = 1 and Preventable = 1 then 1 else 0 end", "Label 90d"),
    num_field("Censored", "case when Cancel_In_60d = 1 and Preventable = 0 then 1 else 0 end", "Censored (non-pay, company, unpreventable in window)"),
    text_field("Reason", "case when Cancel_In_90d = 1 then Cancellation_Reason_c__c else null end", "Reason (evaluation only)"),
    text_field("Row_Key", f"concat(Id__c, '_', {SNAPKEY})", "Row key", 40),
    num_field("Tenure_Days", f"datediff({SNAP}, CreatedDate__c)", "Tenure days"),
    num_field("Policy_Days", f"datediff({SNAP}, Policy_Effective_Date_c__c)", "Days since policy effective"),
    text_field("Tenure_Bucket", "case when Tenure_Days < 180 then 'lt6mo' when Tenure_Days < 365 then '6to12mo' when Tenure_Days < 730 then '1to2y' else '2yplus' end", "Tenure bucket", 10),
    num_field("Days_Into_Term_Est", "Policy_Days - 182 * floor(Policy_Days / 182)", "Days into term (estimated from 6-month terms)"),
    num_field("Days_To_Term_End_Est", "182 - (Policy_Days - 182 * floor(Policy_Days / 182))", "Days to term end (estimated)"),
    num_field("Days_To_Renewal", f"case when Policy_Renewal_Date_c__c >= {SNAP} then datediff(Policy_Renewal_Date_c__c, {SNAP}) else null end", "Days to renewal (CURRENT VALUE: valid for latest snapshot only)"),
    num_field("Days_Into_Term", f"case when Current_Term_Effective_Date_c__c <= {SNAP} and Current_Term_Expiration_Date_c__c > {SNAP} then datediff({SNAP}, Current_Term_Effective_Date_c__c) else null end", "Days into term (real; null when the current term was not in force at the snapshot)"),
    num_field("Days_To_Term_End", f"case when Current_Term_Effective_Date_c__c <= {SNAP} and Current_Term_Expiration_Date_c__c > {SNAP} then datediff(Current_Term_Expiration_Date_c__c, {SNAP}) else null end", "Days to term end (real; same rule)"),
    num_field("Days_Since_Last_App_Open", f"case when Last_App_Open_Date_c__c is null or Last_App_Open_Date_c__c > {SNAP} then null else datediff({SNAP}, Last_App_Open_Date_c__c) end", "Days since last app open (Contact field; null if after snapshot)"),
    *([num_field("Renewal_Offer_Change_Dollars", '"Acct.Off.Increase_Amount_Dollars_c__c"', "Renewal offer change $ (latest offer in the 60 days before the snapshot; point-in-time from Renewal_Offer__c)", 10, 2)] if WITH_OFFERS else []),
    *([num_field("Renewal_Offer_Rate", '"Acct.Off.Policy_Renewal_Rate_c__c"', "Renewal offer monthly rate", 10, 2)] if WITH_OFFERS else []),
    *([num_field("Renewal_Offer_Change_Pct", '"Acct.Off.Increase_Percent_c__c"', "Renewal offer change %", 10, 2)] if WITH_OFFERS else []),
    *([num_field("Days_Since_Renewal_Offer_PIT", f'case when "Acct.Latest_Offer_Date" is null then null else datediff({SNAP}, "Acct.Latest_Offer_Date") end', "Days since the latest offer (point-in-time)")] if WITH_OFFERS else []),
    *([text_field("Renewal_Rating_Version", '"Acct.Off.Rating_Version_c__c"', "Rating version on the offer", 40)] if WITH_OFFERS else []),
    num_field("Days_Since_Renewal_Offer", f"case when Renewal_Offer_Date_c__c <= {SNAP} then datediff({SNAP}, Renewal_Offer_Date_c__c) else null end", "Days since renewal offer (CURRENT VALUE)"),
], "Labels and tenure", 250, 1792, "60/90-day preventable-voluntary labels, censoring flag, tenure and term-position features")
ui_link("JOIN_ACCT" if WITH_OFFERS else "FILTER_BOOK", "T_LABELS")

# ---------------------------------------------------------------- app events (row 2)
load("LOAD_APP", "MobileApp_c_00D3h0000068eod__dll", "dataLakeObject", ["Account_Id_c__c", "Event_Timestamp_UTC_c__c", "Event_Name_c__c"], "Mobile app events", 440, 112)
app_k = transform("T_APP_K", "LOAD_APP", [num_field("xk", "1", "Cross-join key")], "App join key", 440, 392)
ui_link("LOAD_APP", "T_APP_K")
join("JOIN_APP_CAL", app_k, cal_last, ["xk"], ["xk"], "Cal", "INNER", "App x snapshot", 440, 672, drop=["Cal.xk", "Cal.Snapshot_Date__c", "Cal.Snapshot_Key__c"])
ui_link("T_APP_K", "JOIN_APP_CAL"); ui_link("T_CAL", "JOIN_APP_CAL")
app_f = transform("T_APP_W", "JOIN_APP_CAL", [
    num_field("App_Before_Snap", f"case when Event_Timestamp_UTC_c__c <= {SNAP} then 1 else 0 end", "Event before snapshot"),
    num_field("App_30", f"case when Event_Timestamp_UTC_c__c > {SNAP} - INTERVAL 30 DAY and Event_Timestamp_UTC_c__c <= {SNAP} then 1 else 0 end", "App event in 30d"),
    num_field("App_90", f"case when Event_Timestamp_UTC_c__c > {SNAP} - INTERVAL 90 DAY and Event_Timestamp_UTC_c__c <= {SNAP} then 1 else 0 end", "App event in 90d"),
    text_field("Snap_Key_App", SNAPKEY, "Snap key (app)", 10),
], "App windows", 440, 952)
filt("FILTER_APP", app_f, [{"field": "App_Before_Snap", "operands": ["1"], "operator": "EQUAL", "type": "NUMBER"}], "Events before snapshot", 440, 1232)
ui_link("JOIN_APP_CAL", "T_APP_W"); ui_link("T_APP_W", "FILTER_APP")
app_agg = aggregate("AGG_APP", "FILTER_APP", ["Account_Id_c__c", "Snap_Key_App"], [
    {"action": "SUM", "label": "App events 30d", "name": "App_Events_30d", "source": "App_30"},
    {"action": "SUM", "label": "App events 90d", "name": "App_Events_90d", "source": "App_90"},
    {"action": "MAX", "label": "Last app event", "name": "Last_App_Event", "source": "Event_Timestamp_UTC_c__c"}], "App per contact-snapshot", 440, 1512)
ui_link("FILTER_APP", "AGG_APP")

# ---------------------------------------------------------------- email engagement (row 3): Individual Email Results (Marketing Cloud Connect)
load("LOAD_EMAIL", "IndividualEmailResults__dll", "dataLakeObject", ["et4ae5_Contact_c__c", "et4ae5_DateSent_c__c", "et4ae5_DateOpened_c__c", "et4ae5_Opened_c__c", "et4ae5_Clicked_c__c", "et4ae5_NumberOfUniqueClicks_c__c"], "Individual Email Results", 630, 112)
filt("FILTER_EMAIL0", "LOAD_EMAIL", [
    {"field": "et4ae5_Contact_c__c", "operands": ["003"], "operator": "STARTS_WITH", "type": "TEXT"},
    {"field": "et4ae5_DateSent_c__c", "operands": [], "operator": "IS_NOT_NULL", "type": "DATETIME"}], "Contact sends only", 630, 392, "1 AND 2")
ui_link("LOAD_EMAIL", "FILTER_EMAIL0")
em_k = transform("T_EMAIL_K", "FILTER_EMAIL0", [num_field("xk", "1", "Cross-join key")], "Email join key", 630, 672)
ui_link("FILTER_EMAIL0", "T_EMAIL_K")
join("JOIN_EMAIL_CAL", em_k, cal_last, ["xk"], ["xk"], "Cal", "INNER", "Email x snapshot", 630, 952, drop=["Cal.xk", "Cal.Snapshot_Date__c", "Cal.Snapshot_Key__c"])
ui_link("T_EMAIL_K", "JOIN_EMAIL_CAL"); ui_link("T_CAL", "JOIN_EMAIL_CAL")
em_f = transform("T_EMAIL_W", "JOIN_EMAIL_CAL", [
    num_field("Email_Before_Snap", f"case when et4ae5_DateSent_c__c <= {SNAP} then 1 else 0 end", "Send before snapshot"),
    num_field("Email_Sent_90", f"case when et4ae5_DateSent_c__c > {SNAP} - INTERVAL 90 DAY then 1 else 0 end", "Sent in 90d"),
    num_field("Email_Open_30", f"case when et4ae5_Opened_c__c = true and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) > {SNAP} - INTERVAL 30 DAY and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) <= {SNAP} then 1 else 0 end", "Opened in 30d"),
    num_field("Email_Open_90", f"case when et4ae5_Opened_c__c = true and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) > {SNAP} - INTERVAL 90 DAY and coalesce(et4ae5_DateOpened_c__c, et4ae5_DateSent_c__c) <= {SNAP} then 1 else 0 end", "Opened in 90d"),
    num_field("Email_Click_90", f"case when et4ae5_Clicked_c__c = true and et4ae5_DateSent_c__c > {SNAP} - INTERVAL 90 DAY then 1 else 0 end", "Clicked in 90d (attributed to send date)"),
    date_field("Email_Event_Date", f"case when et4ae5_Opened_c__c = true and et4ae5_DateOpened_c__c <= {SNAP} then et4ae5_DateOpened_c__c else et4ae5_DateSent_c__c end", "Email event date (open if before snapshot, else send)"),
    text_field("Snap_Key_Email", SNAPKEY, "Snap key (email)", 10),
], "Email windows", 630, 1232)
filt("FILTER_EMAIL", em_f, [{"field": "Email_Before_Snap", "operands": ["1"], "operator": "EQUAL", "type": "NUMBER"}], "Sends before snapshot", 630, 1512)
ui_link("JOIN_EMAIL_CAL", "T_EMAIL_W"); ui_link("T_EMAIL_W", "FILTER_EMAIL")
em_agg = aggregate("AGG_EMAIL", "FILTER_EMAIL", ["et4ae5_Contact_c__c", "Snap_Key_Email"], [
    {"action": "SUM", "label": "Emails sent 90d", "name": "Email_Sends_90d", "source": "Email_Sent_90"},
    {"action": "SUM", "label": "Email opens 30d", "name": "Email_Opens_30d", "source": "Email_Open_30"},
    {"action": "SUM", "label": "Email opens 90d", "name": "Email_Opens_90d", "source": "Email_Open_90"},
    {"action": "SUM", "label": "Email clicks 90d", "name": "Email_Clicks_90d", "source": "Email_Click_90"},
    {"action": "MAX", "label": "Last email event", "name": "Last_Email_Event", "source": "Email_Event_Date"}], "Email per contact-snapshot", 630, 1792)
ui_link("FILTER_EMAIL", "AGG_EMAIL")

# ---------------------------------------------------------------- support tickets (row 4)
load("LOAD_TICKET", "Zen_Desk_Ticket__dll", "dataLakeObject", ["Customer_Number_c__c", "Created_at_c__c", "Ticket_type_c__c"], "Zendesk tickets", 820, 112)
tk_k = transform("T_TKT_K", "LOAD_TICKET", [num_field("xk", "1", "Cross-join key")], "Ticket join key", 820, 392)
ui_link("LOAD_TICKET", "T_TKT_K")
join("JOIN_TKT_CAL", tk_k, cal_last, ["xk"], ["xk"], "Cal", "INNER", "Ticket x snapshot", 820, 672, drop=["Cal.xk", "Cal.Snapshot_Date__c", "Cal.Snapshot_Key__c"])
ui_link("T_TKT_K", "JOIN_TKT_CAL"); ui_link("T_CAL", "JOIN_TKT_CAL")
tk_f = transform("T_TKT_W", "JOIN_TKT_CAL", [
    num_field("Tkt_Before_Snap", f"case when Created_at_c__c <= {SNAP} then 1 else 0 end", "Ticket before snapshot"),
    num_field("Tkt_90", f"case when Created_at_c__c > {SNAP} - INTERVAL 90 DAY and Created_at_c__c <= {SNAP} then 1 else 0 end", "Ticket in 90d"),
    text_field("Snap_Key_Tkt", SNAPKEY, "Snap key (ticket)", 10),
], "Ticket windows", 820, 952)
filt("FILTER_TKT", tk_f, [{"field": "Tkt_Before_Snap", "operands": ["1"], "operator": "EQUAL", "type": "NUMBER"}], "Tickets before snapshot", 820, 1232)
ui_link("JOIN_TKT_CAL", "T_TKT_W"); ui_link("T_TKT_W", "FILTER_TKT")
tk_agg = aggregate("AGG_TKT", "FILTER_TKT", ["Customer_Number_c__c", "Snap_Key_Tkt"], [
    {"action": "SUM", "label": "Tickets 90d", "name": "Tickets_90d", "source": "Tkt_90"},
    {"action": "MAX", "label": "Last ticket", "name": "Last_Ticket", "source": "Created_at_c__c"}], "Tickets per contact-snapshot", 820, 1512)
ui_link("FILTER_TKT", "AGG_TKT")

# ---------------------------------------------------------------- assemble (row 1, right side)
join("JOIN_F_APP", labels, app_agg, ["account_id_c__c", "Cal.Snap_Key"], ["Account_Id_c__c", "Snap_Key_App"], "App", "LEFT_OUTER", "+ app", 250, 2072, drop=["App.Account_Id_c__c", "App.Snap_Key_App"])
ui_link("T_LABELS", "JOIN_F_APP"); ui_link("AGG_APP", "JOIN_F_APP")
join("JOIN_F_EMAIL", "JOIN_F_APP", em_agg, ["Id__c", "Cal.Snap_Key"], ["et4ae5_Contact_c__c", "Snap_Key_Email"], "Email", "LEFT_OUTER", "+ email", 250, 2352, drop=["Email.et4ae5_Contact_c__c", "Email.Snap_Key_Email"])
ui_link("JOIN_F_APP", "JOIN_F_EMAIL"); ui_link("AGG_EMAIL", "JOIN_F_EMAIL")
join("JOIN_F_TKT", "JOIN_F_EMAIL", tk_agg, ["Customer_Number_c__c", "Cal.Snap_Key"], ["Customer_Number_c__c", "Snap_Key_Tkt"], "Tkt", "LEFT_OUTER", "+ tickets", 250, 2632, drop=["Tkt.Customer_Number_c__c", "Tkt.Snap_Key_Tkt"])
ui_link("JOIN_F_EMAIL", "JOIN_F_TKT"); ui_link("AGG_TKT", "JOIN_F_TKT")
final = transform("T_FINAL", "JOIN_F_TKT", [
    num_field("App_Events_30d_F", 'coalesce("App.App_Events_30d", 0)', "App events 30d (final)"),
    num_field("App_Events_90d_F", 'coalesce("App.App_Events_90d", 0)', "App events 90d (final)"),
    num_field("Days_Since_Last_App_Event", f'case when "App.Last_App_Event" is null then 9999 else datediff({SNAP}, "App.Last_App_Event") end', "Days since last app event"),
    num_field("Email_Sends_90d_F", 'coalesce("Email.Email_Sends_90d", 0)', "Emails sent 90d (final)"),
    num_field("Email_Opens_30d_F", 'coalesce("Email.Email_Opens_30d", 0)', "Email opens 30d (final)"),
    num_field("Email_Opens_90d_F", 'coalesce("Email.Email_Opens_90d", 0)', "Email opens 90d (final)"),
    num_field("Email_Clicks_90d_F", 'coalesce("Email.Email_Clicks_90d", 0)', "Email clicks 90d (final)"),
    num_field("Email_Open_Rate_90d", 'case when coalesce("Email.Email_Sends_90d", 0) = 0 then null else coalesce("Email.Email_Opens_90d", 0) / "Email.Email_Sends_90d" end', "Email open rate 90d", 5, 4),
    num_field("Days_Since_Last_Email_Event", f'case when "Email.Last_Email_Event" is null then 9999 else datediff({SNAP}, "Email.Last_Email_Event") end', "Days since last email event"),
    num_field("Tickets_90d_F", 'coalesce("Tkt.Tickets_90d", 0)', "Tickets 90d (final)"),
    num_field("Days_Since_Last_Ticket", f'case when "Tkt.Last_Ticket" is null then 9999 else datediff({SNAP}, "Tkt.Last_Ticket") end', "Days since last ticket"),
    date_field("Max_Feature_Date", 'case when "App.Last_App_Event" is not null and ("Email.Last_Email_Event" is null or "App.Last_App_Event" >= "Email.Last_Email_Event") and ("Tkt.Last_Ticket" is null or "App.Last_App_Event" >= "Tkt.Last_Ticket") then "App.Last_App_Event" when "Email.Last_Email_Event" is not null and ("Tkt.Last_Ticket" is null or "Email.Last_Email_Event" >= "Tkt.Last_Ticket") then "Email.Last_Email_Event" else "Tkt.Last_Ticket" end', "Max feature date (audit: must be <= Snap_Date)"),
    *([num_field("Offer_After_Snapshot", f'case when "Acct.Latest_Offer_Date" > {SNAP} then 1 else 0 end', "Audit: offer dated after snapshot (must be 0)")] if WITH_OFFERS else []),
], "Final features", 250, 2912, "Null-safe counts, recency, and the leakage audit column")
ui_link("JOIN_F_TKT", "T_FINAL")

mappings = [
    ("Row_Key", "Row_Key__c"), ("Id__c", "Contact_Id__c"), ("Cal.Snap_Date", "Snapshot_Date__c"), ("Cal.Snap_Key", "Snapshot_Key__c"),
    ("Label_60", "Label_60__c"), ("Label_90", "Label_90__c"), ("Censored", "Censored__c"), ("Reason", "Reason__c"),
    ("Tenure_Days", "Tenure_Days__c"), ("Tenure_Bucket", "Tenure_Bucket__c"), ("Policy_Days", "Policy_Days__c"),
    ("Days_Into_Term_Est", "Days_Into_Term_Est__c"), ("Days_To_Term_End_Est", "Days_To_Term_End_Est__c"),
    ("Days_To_Renewal", "Days_To_Renewal__c"), ("Days_Since_Renewal_Offer", "Days_Since_Renewal_Offer__c"),
    ("Days_Into_Term", "Days_Into_Term__c"), ("Days_To_Term_End", "Days_To_Term_End__c"), ("Days_Since_Last_App_Open", "Days_Since_Last_App_Open__c"),
    ("Monthly_Safe_Driving_Discount_c__c", "Monthly_Safe_Driving_Discount__c"),
    *([("Renewal_Offer_Change_Dollars", "Renewal_Offer_Change_Dollars__c"), ("Renewal_Offer_Rate", "Renewal_Offer_Rate__c")] if WITH_OFFERS else []),
    *([("Renewal_Offer_Change_Pct", "Renewal_Offer_Change_Pct__c"), ("Renewal_Rating_Version", "Renewal_Rating_Version__c"),
    ("Days_Since_Renewal_Offer_PIT", "Days_Since_Renewal_Offer_PIT__c")] if WITH_OFFERS else []),
    ("Policy_Renewal_Rate_c__c", "Policy_Renewal_Rate__c"), ("Lifetime_Savings_c__c", "Lifetime_Savings__c"), ("Telematic_Discount_Numeric__c", "Telematics_Discount__c"),
    ("App_Events_30d_F", "App_Events_30d__c"), ("App_Events_90d_F", "App_Events_90d__c"), ("Days_Since_Last_App_Event", "Days_Since_Last_App_Event__c"),
    ("Email_Sends_90d_F", "Email_Sends_90d__c"), ("Email_Opens_30d_F", "Email_Opens_30d__c"), ("Email_Opens_90d_F", "Email_Opens_90d__c"), ("Email_Clicks_90d_F", "Email_Clicks_90d__c"),
    ("Email_Open_Rate_90d", "Email_Open_Rate_90d__c"), ("Days_Since_Last_Email_Event", "Days_Since_Last_Email_Event__c"),
    ("Tickets_90d_F", "Tickets_90d__c"), ("Days_Since_Last_Ticket", "Days_Since_Last_Ticket__c"), ("Max_Feature_Date", "Max_Feature_Date__c"), *([("Offer_After_Snapshot", "Offer_After_Snapshot__c")] if WITH_OFFERS else []),
]
nodes["OUTPUT0"] = {"action": "outputD360", "sources": [final], "parameters": {"dedupOrder": [], "fieldsMappings": [{"sourceField": s, "targetField": t} for s, t in mappings],
                    "name": "Churn_PIT_Training_Set__dll", "type": "dataLakeObject", "writeMode": "OVERWRITE"}}
ui_nodes["OUTPUT0"] = {"label": "Churn_PIT_Training_Set", "type": "OUTPUT", "top": 250, "left": 3192}
ui_link("T_FINAL", "OUTPUT0")

types = {"Renewal_Rating_Version__c": "Text", "Row_Key__c": "Text", "Contact_Id__c": "Text", "Snapshot_Date__c": "DateTime", "Snapshot_Key__c": "Text", "Reason__c": "Text", "Tenure_Bucket__c": "Text", "Max_Feature_Date__c": "DateTime"}
out_fields = [{"isPrimaryKey": t == "Row_Key__c", "label": t[:-3].replace("_", " "), "name": t, "type": types.get(t, "Number")} for s, t in mappings]
definition = {"label": "Churn PIT Training Set", "name": "ChurnPITTrainingSet", "version": "56.0", "type": "STL", "nodes": nodes,
              "outputDataObjects": [{"category": "Other", "label": "Churn PIT Training Set", "name": "Churn_PIT_Training_Set__dll", "type": "dataLakeObject", "fields": out_fields}],
              "ui": {"nodes": ui_nodes, "connectors": ui_conn, "hiddenColumns": []}}

# sanity: every source exists
for k, v in nodes.items():
    for s in v["sources"]:
        assert s in nodes, f"{k} -> missing source {s}"
for c in ui_conn:
    assert c["source"] in ui_nodes and c["target"] in ui_nodes, c

json.dump(definition, open(os.path.join(HERE, f"Churn_PIT_Training_Set{SUFFIX}.json"), "w"), indent=2)

def escape_formulas(obj):
    if isinstance(obj, dict):
        return {k: (html.escape(v, quote=True).replace("'", "&#39;") if k == "formulaExpression" else escape_formulas(v)) for k, v in obj.items()}
    if isinstance(obj, list): return [escape_formulas(x) for x in obj]
    return obj
api_body = {"label": "Churn PIT Training Set", "name": "ChurnPITTrainingSet", "dataSpaceName": "default", "type": "BATCH",
            "description": "Point-in-time training set: monthly snapshots of the active book labelled on preventable voluntary cancellation in the following 60/90 days",
            "definitions": [definition]}  # the POST validator wants raw SQL; the GET response shows it HTML-escaped
json.dump(api_body, open(os.path.join(HERE, f"Churn_PIT_Training_Set{SUFFIX}.api.json"), "w"), indent=2)

with open(os.path.join(HERE, "Churn_Snapshot_Calendar.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Snapshot_Date", "Snapshot_Key"])
    y, m = 2024, 7
    while (y, m) <= (2026, 8):
        w.writerow([date(y, m, 1).isoformat(), f"{y}{m:02d}"]); m += 1
        if m == 13: y, m = y + 1, 1
print("nodes:", len(nodes), "| ui nodes:", len(ui_nodes), "| connectors:", len(ui_conn), "| output fields:", len(out_fields))
