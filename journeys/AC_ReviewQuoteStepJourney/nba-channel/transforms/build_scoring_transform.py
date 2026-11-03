"""Batch data transform: Lead__dll -> Channel_Scoring_Set__dll, the Model Builder prediction input for the three channel models.
Same columns as Email_Response_Scoring_Set__cio, computed in Spark SQL formulas (string functions allowed here)."""
import json
NAME, LBL, OUT = "ChannelScoringSet", "Channel Scoring Set", "Channel_Scoring_Set__dll"
nodes, ui_nodes, ui_conn = {}, {}, []
LOAD_FIELDS = ["Id__c","Email__c","CreatedDate__c","MobilePhone__c","Max_Quote_Step_num__c","Declined_c__c","Credit_Score_c__c","Vehicle_Make_c__c",
               "State__c","Previous_Insurance_c__c","utm_source_c__c","utm_medium_c__c","LeadSource__c","Publisher_c__c","et4ae5_HasOptedOutOfMobile_c__c","Internal_Traffic_c__c"]
nodes["LOAD0"] = {"action":"load","sources":[],"parameters":{"dataset":{"name":"Lead__dll","type":"dataLakeObject"},"fields":LOAD_FIELDS,
                  "sampleDetails":{"type":"TopN","sortBy":[]}}}
ui_nodes["LOAD0"] = {"label":"Lead","type":"LOAD_DATASET","top":60,"left":112,"parameters":{"sampleSize":500,"sampleDetails":{"type":"TopN"},"dataspace":"default"}}
def F(name, expr, btype, label, precision=18, scale=0):
    f = {"businessType": btype, "defaultValue": "", "formulaExpression": expr, "label": label, "name": name}
    if btype == "Number": f.update({"precision": precision, "scale": scale, "type": "NUMBER"})
    elif btype == "Text": f.update({"precision": precision if precision != 18 else 255, "type": "TEXT"})
    else: f.update({"type": "DATETIME", "format": "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"})
    return f
E = "lower(Email__c)"
fields = [
  F("Lead_Id__c", "Id__c", "Text", "Lead Id", 18),
  F("Email_Domain__c", f"case when Email__c is null or Email__c = '' then 'none' when {E} like '%@gmail.com' then 'gmail' when {E} like '%@yahoo.com' or {E} like '%@ymail.com' or {E} like '%@myyahoo.com' or {E} like '%@rocketmail.com' then 'yahoo' when {E} like '%@icloud.com' or {E} like '%@me.com' or {E} like '%@mac.com' then 'apple' when {E} like '%@hotmail.com' or {E} like '%@outlook.com' or {E} like '%@live.com' or {E} like '%@msn.com' then 'microsoft' when {E} like '%@aol.com' then 'aol' when {E} like '%@cox.net' or {E} like '%@comcast.net' or {E} like '%@att.net' or {E} like '%@sbcglobal.net' or {E} like '%@verizon.net' or {E} like '%@charter.net' then 'isp' when {E} like '%.edu' then 'edu' when {E} like '%@proton.me' or {E} like '%@protonmail.com' or {E} like '%@mail.com' then 'privacy' else 'other' end", "Text", "Email Domain", 20),
  F("State__c", "State__c", "Text", "State", 80),
  F("Previous_Insurance__c", "Previous_Insurance_c__c", "Text", "Previous Insurance"),
  F("Vehicle_Make__c", "Vehicle_Make_c__c", "Text", "Vehicle Make"),
  F("UTM_Source__c", "utm_source_c__c", "Text", "UTM Source"),
  F("UTM_Medium__c", "utm_medium_c__c", "Text", "UTM Medium"),
  F("Lead_Source__c", "LeadSource__c", "Text", "Lead Source"),
  F("Publisher__c", "Publisher_c__c", "Text", "Publisher"),
  F("Declined__c", "case when Declined_c__c = true then 1 else 0 end", "Number", "Declined"),
  F("Mobile_Opt_Out__c", "case when et4ae5_HasOptedOutOfMobile_c__c = true then 1 else 0 end", "Number", "Mobile Opt Out"),
  F("Has_Mobile__c", "case when MobilePhone__c is null or trim(MobilePhone__c) = '' then 0 else 1 end", "Number", "Has Mobile"),
  F("Lead_Hour__c", "hour(CreatedDate__c)", "Number", "Lead Hour"),
  F("Lead_Day_Of_Week__c", "dayofweek(CreatedDate__c)", "Number", "Lead Day Of Week"),
  F("Lead_Created_Month__c", "month(CreatedDate__c)", "Number", "Lead Created Month"),
  F("Max_Quote_Step__c", "Max_Quote_Step_num__c", "Number", "Max Quote Step", 18, 2),
  F("Credit_Score__c", "Credit_Score_c__c", "Number", "Credit Score", 18, 2),
  F("Lead_Created__c", "CreatedDate__c", "DateTime", "Lead Created"),
  F("Days_Since_Create__c", "datediff(now(), CreatedDate__c)", "Number", "Days Since Create"),
  F("Internal__c", "case when Internal_Traffic_c__c = true then 1 else 0 end", "Number", "Internal traffic"),
  F("Recent__c", "case when datediff(now(), CreatedDate__c) <= 14 then 1 else 0 end", "Number", "Created in the last 14 days"),
]
prev = "LOAD0"; conns = []
for i, f in enumerate(fields):
    nid = f"FORMULA{i}"
    nodes[nid] = {"action":"formula","sources":[prev],"parameters":{"expressionType":"SQL","fields":[f]}}
    conns.append({"source": prev, "target": nid}); prev = nid
nodes["FILTER0"] = {"action":"filter","sources":[prev],"parameters":{"filterBooleanLogic":"1 AND 2 AND 3",
    "filterExpressions":[{"field":"Recent__c","operands":["1"],"operator":"EQUAL","type":"NUMBER"},
                         {"field":"Internal__c","operands":["0"],"operator":"EQUAL","type":"NUMBER"},
                         {"field":"Id__c","operands":["00Q"],"operator":"STARTS_WITH","type":"TEXT"}]}}
ui_nodes["T0"] = {"label":"Scoring columns","type":"TRANSFORM","top":60,"left":392,"graph":{k:{"label":v["parameters"]["fields"][0]["label"],"type":"FORMULA","top":0,"left":0} for k,v in nodes.items() if v["action"]=="formula"},"connectors":conns}
ui_nodes["FILTER0"] = {"label":"Last 14 days, external, leads","type":"FILTER","top":60,"left":672}
out_fields = []; maps = []
TYPE = {"Number":"Number","Text":"Text","DateTime":"DateTime"}
for f in fields:
    if f["name"] in ("Internal__c", "Recent__c"): continue
    out_fields.append({"isPrimaryKey": f["name"]=="Lead_Id__c", "label": f["label"], "name": f["name"], "type": TYPE[f["businessType"]]})
    maps.append({"sourceField": f["name"], "targetField": f["name"]})
nodes["OUTPUT0"] = {"action":"outputD360","sources":["FILTER0"],"parameters":{"dedupOrder":[],"fieldsMappings":maps,"name":OUT,"type":"dataLakeObject","writeMode":"OVERWRITE"}}
ui_nodes["OUTPUT0"] = {"label":LBL,"type":"OUTPUT","top":60,"left":952}
ui_conn.extend([{"source":"LOAD0","target":"T0"},{"source":"T0","target":"FILTER0"},{"source":"FILTER0","target":"OUTPUT0"}])
definition = {"label":LBL,"name":NAME+"Definition","version":"56.0","type":"STL","nodes":nodes,
              "outputDataObjects":[{"category":"Other","label":LBL,"name":OUT,"type":"dataLakeObject","fields":out_fields}],
              "ui":{"nodes":ui_nodes,"connectors":ui_conn,"hiddenColumns":[]}}
api = {"label":LBL,"name":NAME,"dataSpaceName":"default","type":"BATCH","description":"Prediction input for the three channel models: leads created in the last 14 days with the same columns as Email_Response_Scoring_Set__cio. Built 2026-11-03.","definitions":[definition]}
json.dump(api, open("pit/ChannelScoringSet.api.json","w"), indent=1)
print("fields:", len(out_fields), "nodes:", len(nodes))
