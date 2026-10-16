# Read-only. Requires ~/.config/sfmc/env and c360-sfdx/scripts/lifecycle_watch.py (MC client). Run from this folder; outputs land in the working directory.
import json, re, sys, mc, urllib.request
m = mc.client()
def retrieve_rows(key, cols):
    out=[]; rid=None; st="MoreDataAvailable"
    while st=="MoreDataAvailable":
        m.auth()
        inner = (f"<ContinueRequest>{rid}</ContinueRequest>" if rid else f"<ObjectType>DataExtensionObject[{key}]</ObjectType>"+''.join(f'<Properties>{c}</Properties>' for c in cols))
        env=(f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" xmlns:a="http://schemas.xmlsoap.org/ws/2004/08/addressing"><s:Header><fueloauth xmlns="http://exacttarget.com">{m.token}</fueloauth><a:Action s:mustUnderstand="1">Retrieve</a:Action><a:To s:mustUnderstand="1">{m.soap}</a:To></s:Header><s:Body><RetrieveRequestMsg xmlns="http://exacttarget.com/wsdl/partnerAPI" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><RetrieveRequest>{inner}</RetrieveRequest></RetrieveRequestMsg></s:Body></s:Envelope>')
        req=urllib.request.Request(m.soap, data=env.encode(), headers={"Content-Type":"application/soap+xml; charset=utf-8","SOAPAction":"Retrieve"})
        x=urllib.request.urlopen(req, timeout=180).read().decode()
        st=(re.search(r"<OverallStatus>([^<]*)",x) or [None,"?"])[1]; rid=(re.search(r"<RequestID>([^<]*)",x) or [None,None])[1]
        if st not in ("OK","MoreDataAvailable"): raise RuntimeError(x[:400])
        for blk in re.findall(r"<Results[^>]*>(.*?)</Results>", x, re.S):
            out.append(dict(re.findall(r"<Property><Name>([^<]*)</Name><Value>([^<]*)</Value></Property>", blk)))
    return out
if __name__=="__main__":
    for name,key in [("TR_NonpaymentJourney_AF_01262026","1446BC34-E0EF-4B04-B33E-5BC83CB6EB37"),("NonPay_Paid","6EFABE9F-193A-4658-9E85-4F0C8F44291E")]:
        st, rid, frows = m.retrieve("DataExtensionField", ["Name"], mc.simple("DataExtension.CustomerKey","equals",[key]))
        cols=[f['Name'] for f in frows]
        rows=retrieve_rows(key, cols); json.dump(rows, open(f"de_{name}.json","w"), indent=0)
        print(name, len(rows)); 
        import collections
        for c in cols:
            vals=collections.Counter(r.get(c,'') for r in rows)
            if len(vals)<=12: print('  ',c, vals.most_common(12))
            else: print('  ',c, 'distinct', len(vals), 'sample', list(vals)[:3])
