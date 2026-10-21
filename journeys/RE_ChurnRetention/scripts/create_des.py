#!/usr/bin/env python3
"""Creates the four RE_ChurnRetention data extensions (and the config row) in Marketing Cloud via SOAP.

Naming: RE_ChurnRetention_<Role>_AF_MMDDYYYY in the "Airflow Data" folder (CategoryID 101156), matching the
tenant convention (TR_NonpaymentJourney_AF_01262026, EN_HiGoals..._AF_07312025).

WRITE action, run once. Uses the HiRoad API installed package (needs ~/.config/sfmc/env and
c360-sfdx/scripts/lifecycle_watch.py for auth). Idempotent: an extension that already exists is
reported and skipped. Schemas match de/data_extensions.md and the three query activities.
"""
import importlib.util, re, sys, urllib.request
spec = importlib.util.spec_from_file_location("lw", "/Users/jennifer.pratt/Desktop/c360-sfdx/scripts/lifecycle_watch.py")
lw = importlib.util.module_from_spec(spec); spec.loader.exec_module(lw)
m = lw.MC(lw.load_env()); m.auth()
DATE = "10202026"; FOLDER = 101156   # Airflow Data
def n(role): return f"RE_ChurnRetention_{role}_AF_{DATE}"

def soap(action, body):
    m.auth()
    env = (f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
           f'<s:Header><fueloauth xmlns="http://exacttarget.com">{m.token}</fueloauth><a:Action s:mustUnderstand="1">{action}</a:Action><a:To s:mustUnderstand="1">{m.soap}</a:To></s:Header>'
           f'<s:Body>{body}</s:Body></s:Envelope>')
    req = urllib.request.Request(m.soap, data=env.encode(), headers={"Content-Type": "application/soap+xml; charset=utf-8", "SOAPAction": action})
    return urllib.request.urlopen(req, timeout=180).read().decode()

def exists(key):
    x = soap("Retrieve", f'<RetrieveRequestMsg xmlns="http://exacttarget.com/wsdl/partnerAPI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><RetrieveRequest><ObjectType>DataExtension</ObjectType><Properties>Name</Properties><Properties>CustomerKey</Properties><Filter xsi:type="SimpleFilterPart"><Property>CustomerKey</Property><SimpleOperator>equals</SimpleOperator><Value>{key}</Value></Filter></RetrieveRequest></RetrieveRequestMsg>')
    return f"<CustomerKey>{key}</CustomerKey>" in x

def field(name, ftype, length=None, pk=False, scale=None, required=False):
    f = f"<Field><CustomerKey>{name}</CustomerKey><Name>{name}</Name><FieldType>{ftype}</FieldType>"
    if length is not None: f += f"<MaxLength>{length}</MaxLength>"
    if scale is not None: f += f"<Scale>{scale}</Scale>"
    f += f"<IsPrimaryKey>{'true' if pk else 'false'}</IsPrimaryKey><IsRequired>{'true' if (pk or required) else 'false'}</IsRequired></Field>"
    return f

def create_de(key, name, fields, sendable=False, subscriber_field=None, description=""):
    if exists(key): print(f"{name}: already exists, skipped"); return
    send = (f"<IsSendable>true</IsSendable><SendableDataExtensionField><CustomerKey>{subscriber_field}</CustomerKey><Name>{subscriber_field}</Name><FieldType>Text</FieldType></SendableDataExtensionField>"
            f"<SendableSubscriberField><Name>Subscriber Key</Name><Value>Subscriber Key</Value></SendableSubscriberField>") if sendable else "<IsSendable>false</IsSendable>"
    body = (f'<CreateRequest xmlns="http://exacttarget.com/wsdl/partnerAPI"><Options/><Objects xsi:type="DataExtension" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f"<CustomerKey>{key}</CustomerKey><Name>{name}</Name><Description>{description}</Description><CategoryID>{FOLDER}</CategoryID>{send}<Fields>{''.join(fields)}</Fields></Objects></CreateRequest>")
    x = soap("Create", body)
    st = (re.search(r"<StatusCode>([^<]*)", x) or [None, "?"])[1]; msg = (re.search(r"<StatusMessage>([^<]*)", x) or [None, ""])[1]
    print(f"{name}: {st} {msg}")
    if st != "OK": print(x[:800])

create_de(n("Config"), n("Config"), [
    field("ConfigKey", "Text", 20, pk=True), field("HighCut", "Decimal", 5, scale=2), field("ModerateCut", "Decimal", 5, scale=2), field("BatchDate", "Date")],
    description="One row: v3 score cut points from the latest scoring batch")
create_de(n("Entry"), n("Entry"), [
    field("Id", "Text", 18, pk=True), field("Customer_Number__c", "Text", 50), field("account_id__c", "Text", 50), field("FirstName", "Text", 100),
    field("Email", "EmailAddress", 254), field("Phone", "Phone"), field("MailingState", "Text", 10), field("HasOptedOutOfEmail", "Text", 10),
    field("et4ae5__HasOptedOutOfMobile__c", "Text", 10), field("SMS_Policy_Opt_In__c", "Text", 10), field("Score", "Decimal", 5, scale=2), field("Band", "Text", 10),
    field("ChurnReason", "Text", 20), field("OfferChange", "Decimal", 10, scale=2), field("DiscountChange", "Decimal", 10, scale=2), field("DrivingScore", "Decimal", 10, scale=2),
    field("Track", "Text", 10), field("TermEndAtEntry", "Date"), field("TermStartAtEntry", "Date"), field("TenureDays", "Number"), field("EntryDate", "Date"), field("Arm", "Text", 10)],
    sendable=True, subscriber_field="Id", description="Journey entry audience, overwritten daily by RE_ChurnRetention_Entry query")
create_de(n("History"), n("History"), [
    field("Id", "Text", 18, pk=True), field("TermEndAtEntry", "Date", pk=True), field("EntryDate", "Date"), field("Band", "Text", 10), field("Track", "Text", 10),
    field("Score", "Decimal", 5, scale=2), field("Arm", "Text", 10)],
    description="Every entry with its arm; suppression and measurement spine")
create_de(n("Exit"), n("Exit"), [
    field("Id", "Text", 18, pk=True), field("TermEndAtEntry", "Date"), field("ExitReason", "Text", 20), field("ExitDate", "Date")],
    description="Journey exit criteria: cancelled, pending cancel, non-pay notice after entry, or renewed")

# config row
x = soap("Create", '<CreateRequest xmlns="http://exacttarget.com/wsdl/partnerAPI"><Options/>'
         f'<Objects xsi:type="DataExtensionObject" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><CustomerKey>{n("Config")}</CustomerKey>'
         '<Properties><Property><Name>ConfigKey</Name><Value>current</Value></Property><Property><Name>HighCut</Name><Value>59.99</Value></Property>'
         '<Property><Name>ModerateCut</Name><Value>49.05</Value></Property><Property><Name>BatchDate</Name><Value>2026-10-20</Value></Property></Properties></Objects></CreateRequest>')
print("config row:", (re.search(r"<StatusCode>([^<]*)", x) or [None, "?"])[1], (re.search(r"<StatusMessage>([^<]*)", x) or [None, ""])[1])
