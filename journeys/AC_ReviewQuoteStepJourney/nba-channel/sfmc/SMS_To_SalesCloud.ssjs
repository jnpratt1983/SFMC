<script runat="server">
/*
  SMS_To_SalesCloud -- Script Activity, step 2 of automation "SMS Data" (replaces journey "SMS Creation").
  Reads every row of data extension smsmessagetracking (already one row per text, see SMSData query)
  and upserts them into Sales Cloud SMS__c on SMS_Key__c = SubscriberKey|SMSJobID.

  Needs:
    DE SalesCloud_API_Config  (Name PK, LoginUrl, ClientId, ClientSecret, ApiVersion)  one row, Name = 'Prod'
    DE SMS_SalesCloud_Errors  (RunAt date, SMSKey text 80, ErrorCode text 100, Message text 1000)
    DE SMS_SalesCloud_Log     (RunAt date PK, RowsRead number, Upserted number, Errors number, Note text 500)
    Connected App with the Client Credentials flow enabled, run-as user with Create/Edit on SMS__c and
    all mapped fields (API SFMC User).
  Times: SFMC stores CreateDateTime in server time (UTC-6, no DST). Converted to UTC here.
*/
Platform.Load("Core", "1.1.1");

var CONFIG_DE = "SalesCloud_API_Config";
var SOURCE_DE = "smsmessagetracking";
var ERROR_DE  = "SMS_SalesCloud_Errors";
var LOG_DE    = "SMS_SalesCloud_Log";
var BATCH     = 200;
var SERVER_OFFSET_HOURS = 6;

var runAt = new Date();
var rowsRead = 0, upserted = 0, errors = 0, note = "";

try {
  var cfgRows = Platform.Function.LookupRows(CONFIG_DE, "Name", "Prod");
  if (!cfgRows || cfgRows.length == 0) throw "no config row";
  var cfg = cfgRows[0];
  var apiVersion = cfg.ApiVersion || "v64.0";

  // ---- 1. token (client credentials) ----
  var tokReq = new Script.Util.HttpRequest(cfg.LoginUrl + "/services/oauth2/token");
  tokReq.emptyContentHandling = 0;
  tokReq.retries = 2;
  tokReq.continueOnError = true;
  tokReq.contentType = "application/x-www-form-urlencoded";
  tokReq.method = "POST";
  tokReq.postData = "grant_type=client_credentials&client_id=" + encodeURIComponent(cfg.ClientId)
                  + "&client_secret=" + encodeURIComponent(cfg.ClientSecret);
  var tokResp = tokReq.send();
  var tok = Platform.Function.ParseJSON(String(tokResp.content));
  if (!tok || !tok.access_token) throw "token failed: " + String(tokResp.content).substring(0, 300);
  var instanceUrl = tok.instance_url;
  var upsertUrl = instanceUrl + "/services/data/" + apiVersion + "/composite/sobjects/SMS__c/SMS_Key__c";

  // ---- 2. read the staging DE (all rows; the query activity controls the window) ----
  var prox = new Script.Util.WSProxy();
  var cols = ["SubscriberKey", "SMSJobID", "Name", "CreateDateTime", "Description", "SMSStandardStatusCodeId",
              "ShortCode", "Sent", "Delivered", "Undelivered"];
  var res = prox.retrieve("DataExtensionObject[" + SOURCE_DE + "]", cols);
  var batch = [];

  function prop(item, name) {
    for (var i = 0; i < item.Properties.length; i++) if (item.Properties[i].Name == name) return item.Properties[i].Value;
    return null;
  }
  function toUtcIso(s) {
    if (!s) return null;
    var d = new Date(s);
    if (isNaN(d.getTime())) return null;
    d.setHours(d.getHours() + SERVER_OFFSET_HOURS);
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + "T" + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds()) + ".000Z";
  }
  function isTrue(v) { return v === true || v == "True" || v == "true" || v == "1"; }

  function flush() {
    if (batch.length == 0) return;
    var req = new Script.Util.HttpRequest(upsertUrl);
    req.emptyContentHandling = 0;
    req.retries = 2;
    req.continueOnError = true;
    req.contentType = "application/json";
    req.method = "PATCH";
    req.setHeader("Authorization", "Bearer " + tok.access_token);
    req.postData = Stringify({ allOrNone: false, records: batch });
    var resp = req.send();
    var out = Platform.Function.ParseJSON(String(resp.content));
    if (!out || out.length === undefined) {
      errors += batch.length;
      Platform.Function.InsertData(ERROR_DE, ["RunAt", "SMSKey", "ErrorCode", "Message"],
        [runAt, "BATCH", String(resp.statusCode), String(resp.content).substring(0, 1000)]);
    } else {
      for (var i = 0; i < out.length; i++) {
        if (out[i].success) { upserted++; }
        else {
          errors++;
          var e = out[i].errors && out[i].errors.length ? out[i].errors[0] : { statusCode: "?", message: "?" };
          Platform.Function.InsertData(ERROR_DE, ["RunAt", "SMSKey", "ErrorCode", "Message"],
            [runAt, batch[i].SMS_Key__c, String(e.statusCode).substring(0, 100), String(e.message).substring(0, 1000)]);
        }
      }
    }
    batch = [];
  }

  while (res && res.Results && res.Results.length > 0) {
    for (var r = 0; r < res.Results.length; r++) {
      var it = res.Results[r];
      var key = prop(it, "SubscriberKey"), job = prop(it, "SMSJobID");
      if (!key || !job) continue;
      rowsRead++;
      var delivered = isTrue(prop(it, "Delivered")), undelivered = isTrue(prop(it, "Undelivered"));
      var rec = {
        attributes: { type: "SMS__c" },
        SMS_Key__c: (key + "|" + job).substring(0, 80),
        Name: String(prop(it, "Name") || "SMS").substring(0, 80),
        SubscriberKey__c: String(key).substring(0, 254),
        CreateDate__c: toUtcIso(prop(it, "CreateDateTime")),
        Description__c: prop(it, "Description") ? String(prop(it, "Description")).substring(0, 254) : null,
        ShortCode__c: prop(it, "ShortCode"),
        SMSStandardStatusCodeId__c: prop(it, "SMSStandardStatusCodeId") ? Number(prop(it, "SMSStandardStatusCodeId")) : null,
        Status__c: delivered ? "Delivered" : (undelivered ? "Undeliverable" : "Enroute")
      };
      if (String(key).indexOf("00Q") == 0) rec.Lead__c = key;
      else if (String(key).indexOf("003") == 0) rec.Contact__c = key;
      batch.push(rec);
      if (batch.length >= BATCH) flush();
    }
    if (res.HasMoreRows) res = prox.getNextBatch("DataExtensionObject[" + SOURCE_DE + "]", res.RequestID);
    else break;
  }
  flush();
} catch (ex) {
  note = "EXCEPTION: " + String(ex).substring(0, 480);
  errors++;
}

Platform.Function.UpsertData(LOG_DE, ["RunAt"], [runAt], ["RowsRead", "Upserted", "Errors", "Note"], [rowsRead, upserted, errors, note]);
</script>
