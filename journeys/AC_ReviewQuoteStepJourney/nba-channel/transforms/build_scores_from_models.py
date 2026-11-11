"""Batch data transform ChannelScores, rewired 2026-11-11: reads the DMO written by the UI-built model transform
Channel_Scores_Models (three AI nodes over Channel_Scoring_Set__dlm) and publishes Channel_Scores__dlm, which the
copy-field enrichment Channel_Scores_Lead_default writes to Lead. The AI-node prediction of a binary model is already
P(class 1) x 100, so the scores are only rounded. Source is Channel_Scores_Field_v2__dlm; the first output object,
Channel_Scores_Field__dlm, is empty and unused (its only run failed)."""
import json
SRC = "Channel_Scores_Field_v2__dlm"
SMS, EMAIL, CALL = ("Predicted_SMS_CM_12l_eo_predicted_column__c", "Predicted_Opened_First_predicted_column__c",
                    "Predicted_Call_CM_12l_e_predicted_column__c")
KQ = "KQ_Lead_Id11__c"
NAME, LBL, OUT = "ChannelScores", "Channel Scores", "Channel_Scores__dlm"
nodes = {"LOAD_M": {"action": "load", "sources": [], "parameters": {"dataset": {"name": SRC, "type": "dataModelObject"},
         "fields": ["Lead_Id__c", KQ, SMS, EMAIL, CALL], "sampleDetails": {"type": "TopN", "sortBy": []}}}}
def formula(nid, src, name, expr, label, btype="Number"):
    f = {"businessType": btype, "defaultValue": "", "formulaExpression": expr, "label": label, "name": name}
    if btype == "Number": f.update({"precision": 18, "scale": 2, "type": "NUMBER"})
    elif btype == "Text": f.update({"precision": 255, "type": "TEXT"})
    else: f.update({"type": "DATETIME", "format": "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"})
    nodes[nid] = {"action": "formula", "sources": [src], "parameters": {"expressionType": "SQL", "fields": [f]}}
formula("F_KQ", "LOAD_M", "KQ_Lead_Id__c", KQ, "Key Qualifier Lead Id", "Text")
formula("F_SMS", "F_KQ", "SMS_Score__c", f"round({SMS}, 2)", "SMS Score")
formula("F_EMAIL", "F_SMS", "Email_Score_Out__c", f"round({EMAIL}, 2)", "Email Score")
formula("F_CALL", "F_EMAIL", "Call_Score_Out__c", f"round({CALL}, 2)", "Call Score")
formula("F_OUT_TS", "F_CALL", "Scored_At__c", "now()", "Scored At", "DateTime")
maps = [{"sourceField": s, "targetField": t} for s, t in (("KQ_Lead_Id__c", "KQ_Lead_Id__c"), ("Lead_Id__c", "Lead_Id__c"),
        ("Email_Score_Out__c", "Email_Score__c"), ("SMS_Score__c", "SMS_Score__c"), ("Call_Score_Out__c", "Call_Score__c"),
        ("Scored_At__c", "Scored_At__c"))]
nodes["OUTPUT0"] = {"action": "outputD360", "sources": ["F_OUT_TS"], "parameters": {"dedupOrder": [], "fieldsMappings": maps,
                    "name": OUT, "type": "dataModelObject", "writeMode": "OVERWRITE"}}
steps = ["F_KQ", "F_SMS", "F_EMAIL", "F_CALL", "F_OUT_TS"]
ui_nodes = {"LOAD_M": {"label": "Channel Scores Models output", "type": "LOAD_DATASET", "top": 112, "left": 112,
                       "parameters": {"sampleSize": 500, "sampleDetails": {"type": "TopN"}, "dataspace": "default"}},
            "T_OUT": {"label": "Scores", "type": "TRANSFORM", "top": 112, "left": 392,
                      "graph": {k: {"label": k, "type": "FORMULA", "top": 0, "left": 0} for k in steps},
                      "connectors": [{"source": a, "target": b} for a, b in zip(["LOAD_M"] + steps[:-1], steps)]},
            "OUTPUT0": {"label": LBL, "type": "OUTPUT", "top": 112, "left": 672}}
out_fields = [{"isPrimaryKey": False, "label": "Key Qualifier Lead Id", "name": "KQ_Lead_Id__c", "type": "Text"},
              {"isPrimaryKey": True, "keyQualifierField": "KQ_Lead_Id__c", "label": "Lead Id", "name": "Lead_Id__c", "type": "Text"},
              {"isPrimaryKey": False, "label": "Email Score", "name": "Email_Score__c", "type": "Number"},
              {"isPrimaryKey": False, "label": "SMS Score", "name": "SMS_Score__c", "type": "Number"},
              {"isPrimaryKey": False, "label": "Call Score", "name": "Call_Score__c", "type": "Number"},
              {"isPrimaryKey": False, "label": "Scored At", "name": "Scored_At__c", "type": "DateTime"}]
definition = {"label": LBL, "name": NAME + "Definition", "version": "56.0", "type": "STL", "nodes": nodes,
              "outputDataObjects": [{"category": "Other", "label": LBL, "name": OUT, "type": "dataModelObject", "fields": out_fields}],
              "ui": {"nodes": ui_nodes, "connectors": [{"source": "LOAD_M", "target": "T_OUT"}, {"source": "T_OUT", "target": "OUTPUT0"}],
                     "hiddenColumns": []}}
api = {"label": LBL, "name": NAME, "dataSpaceName": "default", "type": "BATCH",
       "description": "Publishes the three channel scores (0-100) from the Channel_Scores_Models transform output to Channel_Scores__dlm for the copy-field enrichment to Lead. Rewired 2026-11-11.",
       "definitions": [definition]}
json.dump(api, open("ChannelScores_from_models.api.json", "w"), indent=1); print("written")
