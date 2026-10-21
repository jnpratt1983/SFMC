import json, subprocess, urllib.request, urllib.parse
_org = json.loads(subprocess.run(['sf','org','display','-o','blueowl-prod','--json'],capture_output=True,text=True).stdout)['result']
TOKEN=_org['accessToken']; BASE=_org['instanceUrl']; V='v62.0'
def get(path, **params):
    url=BASE+path
    if params: url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+TOKEN})
    try:
        with urllib.request.urlopen(req,timeout=300) as r: return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{e.code} {e.read()[:500]}')
def q(soql, tooling=False):
    path=f'/services/data/{V}/'+('tooling/' if tooling else '')+'query'
    d=get(path,q=soql); recs=d['records']
    while not d.get('done') and d.get('nextRecordsUrl'):
        d=get(d['nextRecordsUrl']); recs+=d['records']
    return recs
