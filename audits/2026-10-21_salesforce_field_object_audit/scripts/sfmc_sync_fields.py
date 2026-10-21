import sys, json, re, urllib.request, time
sys.path.insert(0,'/Users/jennifer.pratt/Desktop/c360-sfdx/scripts'); import lifecycle_watch as lw
mc=lw.MC(lw.load_env()); mc.auth()
def retrieve_all(obj, props, filter_xml):
    mc.auth()
    inner=f"<ObjectType>{obj}</ObjectType>{''.join(f'<Properties>{p}</Properties>' for p in props)}{filter_xml}<QueryAllAccounts>true</QueryAllAccounts>"
    def call(inner):
        env=(f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing">'
             f'<s:Header><fueloauth xmlns="http://exacttarget.com">{mc.token}</fueloauth><a:Action s:mustUnderstand="1">Retrieve</a:Action>'
             f'<a:To s:mustUnderstand="1">{mc.soap}</a:To></s:Header><s:Body><RetrieveRequestMsg xmlns="http://exacttarget.com/wsdl/partnerAPI" '
             f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><RetrieveRequest>{inner}</RetrieveRequest></RetrieveRequestMsg></s:Body></s:Envelope>')
        req=urllib.request.Request(mc.soap,data=env.encode(),headers={"Content-Type":"application/soap+xml; charset=utf-8","SOAPAction":"Retrieve"})
        with urllib.request.urlopen(req,timeout=180) as r: x=r.read().decode()
        status=(re.search(r"<OverallStatus>([^<]*)",x) or [None,"?"])[1]; rid=(re.search(r"<RequestID>([^<]*)",x) or [None,None])[1]
        blocks=re.findall(r"<Results[^>]*>(.*?)</Results>",x,re.S)
        rows=[]
        for b in blocks:
            b2=re.sub(r"<(DataExtension|SendableSubscriberField|SendableDataExtensionField|Client)>.*?</\1>","",b,flags=re.S)
            rows.append(dict(re.findall(r"<(\w+)>([^<]*)</\1>",b2)))
        if status not in ("OK","MoreDataAvailable"): raise RuntimeError(status+x[:300])
        return status,rid,rows
    st,rid,rows=call(inner); allr=list(rows)
    while st=="MoreDataAvailable":
        st,rid,rows=call(f"<ContinueRequest>{rid}</ContinueRequest>"); allr+=rows
    return allr
des=retrieve_all("DataExtension",["Name","CustomerKey","ObjectID","ModifiedDate","CreatedDate"],lw.simple("Name","like",["%_Salesforce"]))
print(len(des),'synced DEs')
out={}
for d in des:
    fl=retrieve_all("DataExtensionField",["Name","FieldType","IsPrimaryKey","ModifiedDate"],lw.simple("DataExtension.CustomerKey","equals",[d['CustomerKey']]))
    out[d['Name']]={'key':d['CustomerKey'],'modified':d.get('ModifiedDate'),'fields':[f['Name'] for f in fl]}
    print(' ',d['Name'],len(fl),'fields')
json.dump(out,open('sfmc_synced.json','w'),indent=1)
