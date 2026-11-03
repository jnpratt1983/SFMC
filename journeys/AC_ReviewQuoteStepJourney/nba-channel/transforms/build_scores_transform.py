"""Batch data transform ChannelScores: the three Model Builder prediction DMOs -> Channel_Scores__dll
(Lead_Id__c, Email_Score__c, SMS_Score__c, Call_Score__c as 0-100, Scored_At__c). One copy-field enrichment then
writes the three scores to the Lead. Prediction DMO/column names are set below; adjust if the jobs were named differently."""
import json, sys
SMS   = ("SMS_Click_Prediction__dlm",   "PredictedClicked_14d")
EMAIL = ("Email_Prediction__dlm",  "PredictedOpened_First_Email")
PHONE = ("Phone_Prediction__dlm", "PredictedCalled_Us_30d")
for i, a in enumerate(sys.argv[1:]):          # optional overrides: dmo:prefix for sms, email, phone
    d, p = a.split(":"); [SMS, EMAIL, PHONE][i] = (d, p)
    if i == 0: SMS = (d, p)
    if i == 1: EMAIL = (d, p)
    if i == 2: PHONE = (d, p)
NAME, LBL, OUT = "ChannelScores", "Channel Scores", "Channel_Scores__dlm"
nodes, ui_nodes, ui_conn = {}, {}, []
def load(nid, dmo, prefix, label, top):
    nodes[nid] = {"action":"load","sources":[],"parameters":{"dataset":{"name":dmo,"type":"dataModelObject"},
                  "fields":["PrimaryObjectPk__c", f"{prefix}1__c", f"{prefix}1Value__c", f"{prefix}2__c", f"{prefix}2Value__c"],
                  "sampleDetails":{"type":"TopN","sortBy":[]}}}
    ui_nodes[nid] = {"label":label,"type":"LOAD_DATASET","top":top,"left":112,"parameters":{"sampleSize":500,"sampleDetails":{"type":"TopN"},"dataspace":"default"}}
def formula(nid, src, name, expr, label, btype="Number", scale=2):
    f = {"businessType":btype,"defaultValue":"","formulaExpression":expr,"label":label,"name":name}
    if btype == "Number": f.update({"precision":18,"scale":scale,"type":"NUMBER"})
    elif btype == "Text": f.update({"precision":255,"type":"TEXT"})
    else: f.update({"type":"DATETIME","format":"yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"})
    nodes[nid] = {"action":"formula","sources":[src],"parameters":{"expressionType":"SQL","fields":[f]}}
def score_expr(prefix):
    # probability of the positive class (1), whichever slot it landed in; scaled 0-100
    return f"round(100 * case when {prefix}1__c like '1%' then {prefix}1Value__c else {prefix}2Value__c end, 2)"
# three loads, each reduced to (key, score)
load("LOAD_SMS", SMS[0], SMS[1], "SMS click prediction", 60)
formula("F_SMS_KEY", "LOAD_SMS", "SMS_Lead_Id__c", "PrimaryObjectPk__c", "Lead Id (sms)", "Text")
formula("F_SMS", "F_SMS_KEY", "SMS_Score__c", score_expr(SMS[1]), "SMS Score")
load("LOAD_EMAIL", EMAIL[0], EMAIL[1], "Email open prediction", 250)
formula("F_EMAIL_KEY", "LOAD_EMAIL", "Email_Lead_Id__c", "PrimaryObjectPk__c", "Lead Id (email)", "Text")
formula("F_EMAIL", "F_EMAIL_KEY", "Email_Score__c", score_expr(EMAIL[1]), "Email Score")
load("LOAD_PHONE", PHONE[0], PHONE[1], "Phone preference prediction", 440)
formula("F_PHONE_KEY", "LOAD_PHONE", "Phone_Lead_Id__c", "PrimaryObjectPk__c", "Lead Id (phone)", "Text")
formula("F_PHONE", "F_PHONE_KEY", "Call_Score__c", score_expr(PHONE[1]), "Call Score")
# joins: sms is the spine (every scored lead is in all three; left joins keep partial runs)
nodes["JOIN_E"] = {"action":"join","sources":["F_SMS","F_EMAIL"],"parameters":{"joinType":"LEFT_OUTER","leftKeys":["SMS_Lead_Id__c"],"rightKeys":["Email_Lead_Id__c"],"rightQualifier":"E"},"schema":{"fields":[],"slice":{"fields":[],"ignoreMissingFields":True,"mode":"DROP"}}}
nodes["JOIN_P"] = {"action":"join","sources":["JOIN_E","F_PHONE"],"parameters":{"joinType":"LEFT_OUTER","leftKeys":["SMS_Lead_Id__c"],"rightKeys":["Phone_Lead_Id__c"],"rightQualifier":"P"},"schema":{"fields":[],"slice":{"fields":[],"ignoreMissingFields":True,"mode":"DROP"}}}
formula("F_OUT_KEY", "JOIN_P", "Lead_Id__c", "SMS_Lead_Id__c", "Lead Id", "Text")
formula("F_OUT_EMAIL", "F_OUT_KEY", "Email_Score_Out__c", '"E.Email_Score__c"', "Email Score")
formula("F_OUT_PHONE", "F_OUT_EMAIL", "Call_Score_Out__c", '"P.Call_Score__c"', "Call Score")
formula("F_OUT_TS", "F_OUT_PHONE", "Scored_At__c", "now()", "Scored At", "DateTime")
for n in ("JOIN_E","JOIN_P"): ui_nodes[n] = {"label":n,"type":"JOIN","top":60,"left":600}
ui_nodes["T_SMS"] = {"label":"SMS score","type":"TRANSFORM","top":60,"left":392,"graph":{"F_SMS_KEY":{"label":"key","type":"FORMULA","top":0,"left":0},"F_SMS":{"label":"score","type":"FORMULA","top":0,"left":0}},"connectors":[{"source":"LOAD_SMS","target":"F_SMS_KEY"},{"source":"F_SMS_KEY","target":"F_SMS"}]}
ui_nodes["T_EMAIL"] = {"label":"Email score","type":"TRANSFORM","top":250,"left":392,"graph":{"F_EMAIL_KEY":{"label":"key","type":"FORMULA","top":0,"left":0},"F_EMAIL":{"label":"score","type":"FORMULA","top":0,"left":0}},"connectors":[{"source":"LOAD_EMAIL","target":"F_EMAIL_KEY"},{"source":"F_EMAIL_KEY","target":"F_EMAIL"}]}
ui_nodes["T_PHONE"] = {"label":"Phone score","type":"TRANSFORM","top":440,"left":392,"graph":{"F_PHONE_KEY":{"label":"key","type":"FORMULA","top":0,"left":0},"F_PHONE":{"label":"score","type":"FORMULA","top":0,"left":0}},"connectors":[{"source":"LOAD_PHONE","target":"F_PHONE_KEY"},{"source":"F_PHONE_KEY","target":"F_PHONE"}]}
ui_nodes["T_OUT"] = {"label":"Output columns","type":"TRANSFORM","top":60,"left":880,"graph":{k:{"label":k,"type":"FORMULA","top":0,"left":0} for k in ("F_OUT_KEY","F_OUT_EMAIL","F_OUT_PHONE","F_OUT_TS")},"connectors":[{"source":"JOIN_P","target":"F_OUT_KEY"},{"source":"F_OUT_KEY","target":"F_OUT_EMAIL"},{"source":"F_OUT_EMAIL","target":"F_OUT_PHONE"},{"source":"F_OUT_PHONE","target":"F_OUT_TS"}]}
out_fields = [{"isPrimaryKey":True,"label":"Lead Id","name":"Lead_Id__c","type":"Text"},
              {"isPrimaryKey":False,"label":"Email Score","name":"Email_Score__c","type":"Number"},
              {"isPrimaryKey":False,"label":"SMS Score","name":"SMS_Score__c","type":"Number"},
              {"isPrimaryKey":False,"label":"Call Score","name":"Call_Score__c","type":"Number"},
              {"isPrimaryKey":False,"label":"Scored At","name":"Scored_At__c","type":"DateTime"}]
maps = [{"sourceField":"Lead_Id__c","targetField":"Lead_Id__c"},{"sourceField":"Email_Score_Out__c","targetField":"Email_Score__c"},
        {"sourceField":"SMS_Score__c","targetField":"SMS_Score__c"},{"sourceField":"Call_Score_Out__c","targetField":"Call_Score__c"},{"sourceField":"Scored_At__c","targetField":"Scored_At__c"}]
nodes["OUTPUT0"] = {"action":"outputD360","sources":["F_OUT_TS"],"parameters":{"dedupOrder":[],"fieldsMappings":maps,"name":OUT,"type":"dataModelObject","writeMode":"OVERWRITE"}}
ui_nodes["OUTPUT0"] = {"label":LBL,"type":"OUTPUT","top":60,"left":1160}
ui_conn = [{"source":"LOAD_SMS","target":"T_SMS"},{"source":"LOAD_EMAIL","target":"T_EMAIL"},{"source":"LOAD_PHONE","target":"T_PHONE"},{"source":"T_SMS","target":"JOIN_E"},{"source":"T_EMAIL","target":"JOIN_E"},{"source":"JOIN_E","target":"JOIN_P"},{"source":"T_PHONE","target":"JOIN_P"},{"source":"JOIN_P","target":"T_OUT"},{"source":"T_OUT","target":"OUTPUT0"}]
definition = {"label":LBL,"name":NAME+"Definition","version":"56.0","type":"STL","nodes":nodes,"outputDataObjects":[{"category":"Other","label":LBL,"name":OUT,"type":"dataModelObject","fields":out_fields}],"ui":{"nodes":ui_nodes,"connectors":ui_conn,"hiddenColumns":[]}}
api = {"label":LBL,"name":NAME,"dataSpaceName":"default","type":"BATCH","description":"Three channel model probabilities (positive class, 0-100) per scored lead, for the copy-field enrichment to Lead. Built 2026-11-03.","definitions":[definition]}
json.dump(api, open("pit/ChannelScores.api.json","w"), indent=1); print("written; inputs:", SMS, EMAIL, PHONE)
