"""
Point-in-time rebuild of the three NBA training sets from Lead field history.
value_at(lead, t) = OldValue of the earliest LeadHistory row for that field with CreatedDate > t,
                    else the lead's current value (from the insight row).
Coverage: LeadHistory starts 2025-05-02, so events before that keep current values only where noted.
Outputs pit/*.csv ready for a Data Cloud upload data stream.
"""
import pandas as pd, numpy as np, sys
H = pd.read_csv("pit/leadhistory.csv", dtype=str, usecols=["LeadId","Field","OldValue","NewValue","CreatedDate"])
H["CreatedDate"] = pd.to_datetime(H["CreatedDate"], utc=True, format="ISO8601")
H = H.sort_values("CreatedDate")
COVER = pd.Timestamp("2025-05-02", tz="UTC")
FIELDS = {  # history field -> insight column
    "Max_Quote_Step__c": "Max_Quote_Step__c",
    "Declined__c": "Declined__c",
    "Credit_Score__c": "Credit_Score__c",
    "Vehicle_Make__c": "Vehicle_Make__c",
    "et4ae5__HasOptedOutOfMobile__c": "Mobile_Opt_Out__c",
}
purch = H[(H.Field == "purchased__c") & (H.NewValue.str.lower() == "true")].groupby("LeadId").CreatedDate.min().rename("purchased_at")

def to_num(s):  return pd.to_numeric(s, errors="coerce")
def to_bool01(s): return s.astype(str).str.lower().map({"true":1,"false":0,"1":1,"0":0})

def rebuild(name, event_col, label_cols, keep_before_coverage):
    df = pd.read_pickle(f"pit/{name}.pkl")
    df["Event_At__c"] = pd.to_datetime(df[event_col].astype(str).str.replace(" UTC", "", regex=False), utc=True, errors="coerce")
    df = df.sort_values("Event_At__c")
    covered = df["Event_At__c"] >= COVER
    for hf, col in FIELDS.items():
        if col not in df.columns: continue
        h = H[H.Field == hf][["LeadId","CreatedDate","OldValue"]].sort_values("CreatedDate")
        m = pd.merge_asof(df[["Lead_Id__c","Event_At__c"]].reset_index(), h, left_on="Event_At__c", right_on="CreatedDate",
                          left_by="Lead_Id__c", right_by="LeadId", direction="forward", allow_exact_matches=False).set_index("index")
        old = m["OldValue"]
        cur = df[col]
        if col in ("Declined__c","Mobile_Opt_Out__c"):
            pit = to_bool01(old).where(old.notna(), to_num(cur))
        elif col in ("Max_Quote_Step__c","Credit_Score__c"):
            pit = to_num(old).where(old.notna(), to_num(cur))
        else:
            pit = old.where(old.notna(), cur)
        if not keep_before_coverage:
            pit = pit.where(covered, np.nan)
        df[col] = pit
        print(f"  {name}: {col:<20} changed after event on {old.notna().sum():>7} rows", flush=True)
    # drop leads that had already bought before the event
    df = df.merge(purch, left_on="Lead_Id__c", right_index=True, how="left")
    bought_before = df["purchased_at"].notna() & (df["purchased_at"] <= df["Event_At__c"])
    print(f"  {name}: dropping {bought_before.sum()} rows already purchased before the event", flush=True)
    df = df[~bought_before].drop(columns=["purchased_at"])
    # current-state columns with no history: remove so the model cannot use them
    for c in ("Email_Opt_Out__c","Saved_Quote__c","App_Downloaded__c","Purchased__c","Currently_Insured__c"):
        if c in df.columns: df = df.drop(columns=[c])
    if not keep_before_coverage:
        df = df[covered.reindex(df.index).fillna(False)]
    out = f"pit/{name.replace('__cio','')}_PIT.csv"
    df.to_csv(out, index=False)
    print(f"  {name}: wrote {out} {df.shape}; positives:", {c: int(to_num(df[c]).sum()) for c in label_cols if c in df.columns}, flush=True)

rebuild("Email_Response_Training_Set__cio", "First_Send_At__c", ["Opened_First_Email__c","Clicked_First_Email__c"], keep_before_coverage=False)
rebuild("SMS_Response_Training_Set__cio",   "SMS_Sent_At__c",   ["Clicked_14d__c","Clicked_30d__c"],              keep_before_coverage=True)
rebuild("Phone_Response_Training_Set__cio", "Lead_Created__c",  ["Called_Us_30d__c","Called_Us_90d__c"],          keep_before_coverage=False)
