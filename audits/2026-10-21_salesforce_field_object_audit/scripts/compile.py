import json, csv, os, re, datetime as dt
from collections import defaultdict, Counter
TODAY=dt.date(2026,10,21); D12=str(TODAY-dt.timedelta(days=365)); D6=str(TODAY-dt.timedelta(days=182))
KEY=['Contact','Lead','Account','Opportunity','Case','Task','Campaign','CampaignMember','User','AccountContactRelation','Bill__c','Claim__c','MobileApp__c','Monthly_Driving_Stat__c','SMS__c','Streak__c','Zen_Desk_Ticket__c','Session_ID__c','Records__c','Referral__c','Survey__c','Forsta_Survey__c','Renewal_Offer__c','Cookie__c','Chatbot__c','Lead_Behavior__c','Process_Error__c','Meta_API_Log__c','TestExternalObject__c','Journey_Monitor_Run__c','Journey_Monitor_Result__c']
flds=[f for f in json.load(open('custom_fields.json')) if f['object'] in KEY]
usage=json.load(open('usage_index.json')); act=json.load(open('object_activity.json')); hist=json.load(open('history.json'))
lts=json.load(open('longtext_sample.json'))
pop={o:json.load(open(f'pop_{o}.json')) for o in KEY if os.path.exists(f'pop_{o}.json')}
rep=json.load(open('report_fields.json'))
rep_use=defaultdict(lambda:{'recent':set(),'old':set()})
for rid,r in rep.items():
    for c in r.get('columns',[]):
        m=re.match(r'^([A-Za-z0-9_]+?)\.([A-Za-z0-9_]+__c)$',c)
        if not m: continue
        rep_use[(m.group(1),m.group(2))]['recent' if (r.get('lastRun') or '')>=D12 else 'old'].add(r['name'])
sfmc=json.load(open('sfmc_synced.json'))
sfmc_map={'Contact':'Contact_Salesforce','Lead':'Lead_Salesforce','Account':'Account_Salesforce','Case':'Case_Salesforce','User':'User_Salesforce','Survey__c':'Survey__c_Salesforce','Streak__c':'Streak__c_Salesforce','Referral__c':'Referral__c_Salesforce','SMS__c':'SMS__c_Salesforce','Monthly_Driving_Stat__c':'Monthly_Driving_Stat__c_Salesforce','Bill__c':'Bill__c_Salesforce','Renewal_Offer__c':'Renewal_Offer__c_Salesforce'}
sfmc_fields={o:set(sfmc[d]['fields']) for o,d in sfmc_map.items() if d in sfmc}
dc=json.load(open('dc_streams.json')); dc_fields={}
def dcname(n): return re.sub(r'_c$','__c',n)
for n,s in dc.items():
    if s['connector']=='SalesforceDotCom' and s['source']: dc_fields[s['source']]={dcname(x) for x in s['fields']}
STRONG={'classes','triggers','flow_active','object_validationRules','formula_field','field_other_object','wave','lwc','aura','workflows','duplicateRules','matchingRules','assignmentRules','email','pages','components','api_ApexClass','api_ApexTrigger','api_Flow','api_WaveRecipe','api_LightningComponentBundle','api_ApexPage','api_ApexComponent','api_ValidationRule','api_EmailTemplate','api_CustomField'}
WEAK={'layouts','object_listViews','object_compactLayouts','object_fieldSets','object_recordTypes','object_webLinks','flow_inactive','workflow_inactive','flexipages','quickActions','api_Layout','api_FlexiPage','api_Report','platformEventChannelMembers','object_object'}
rows=[]
for f in flds:
    o=f['object']; n=f['field']; key=f"{o}.{n}"; u=usage.get(key,{})
    strong={k:v for k,v in u.items() if k in STRONG}; weak={k:v for k,v in u.items() if k in WEAK}; other={k:v for k,v in u.items() if k not in STRONG and k not in WEAK}
    p=dict(pop.get(o,{}).get(n,{})); rr=rep_use.get((o,n),{'recent':set(),'old':set()})
    rep_recent=sorted(rr['recent']); rep_old=sorted(rr['old'])
    in_sfmc=n in sfmc_fields.get(o,set()); in_dc=n in dc_fields.get(o,set())
    h=hist.get(o+'History',{}).get(n)
    objcount=act.get(o,{}).get('count'); obj_last=act.get(o,{}).get('last_created') or ''
    objcount=objcount if isinstance(objcount,int) else None
    measure='full'
    if key in lts:
        s=lts[key]; p['populated']=s['populated_in_sample']; p['last_created_with_value']=s['last_new_value']; measure=f"sample of newest {s['sampled']} records"
        if s['populated_in_sample']==0 and objcount and s['sampled']<objcount: measure+=' (0 in sample; older records not checked)'
    populated=p.get('populated'); lastval=p.get('last_created_with_value') or ''; lastmod=p.get('last_modified_with_value') or ''
    pct=round(100*populated/objcount,1) if isinstance(populated,int) and objcount else None
    is_formula=bool(p.get('calc'))
    has_strong=bool(strong) or bool(rep_recent) or bool(other)
    weak_or_sync=bool(weak) or in_sfmc or in_dc
    obj_active=obj_last>=D6
    err=p.get('err','')
    if err and 'Geolocation' not in (p.get('type') or ''): cls='NO ACCESS: field not readable even by System Administrator (no FLS) - nothing can be using it'
    elif err: cls='UNKNOWN: compound field (geolocation), not measurable'
    elif objcount==0: cls='OBJECT EMPTY: object has no records'
    elif not obj_active and objcount: cls='OBJECT DORMANT: no new records in 6+ months'
    elif is_formula:
        cls='DEPRECATE: formula referenced nowhere' if not has_strong and not weak_or_sync else ('REVIEW: formula shown only on layouts/list views' if not has_strong else 'KEEP')
    elif populated==0:
        cls='DEPRECATE: never populated' if not has_strong else 'REVIEW: empty but referenced by automation/code'
    elif isinstance(populated,int) and lastval and lastval<D12:
        cls='STALE: no new values in 12+ months, still referenced' if has_strong else 'DEPRECATE: stale 12+ months, no automation/report references'
    elif isinstance(populated,int) and lastval and lastval<D6:
        cls='STALE: no new values in 6-12 months, still referenced' if has_strong else 'REVIEW: no new values in 6-12 months, no references'
    elif not has_strong and not weak_or_sync: cls='REVIEW: populated but nothing in the org reads it'
    elif not has_strong: cls='REVIEW: populated, only displayed or synced (no automation/code/report)'
    else: cls='KEEP'
    rows.append({'object':o,'field':n,'label':p.get('label') or '','type':p.get('type') or '','created':f['created'],'created_by':f.get('createdBy') or '','object_records':objcount,'populated':populated if populated is not None else '','pct_populated':pct if pct is not None else '','measure':measure,'first_value':p.get('first_created_with_value') or '','last_new_value':lastval,'last_touched':lastmod,'history_last_change':(h or {}).get('last',''),
        'apex':';'.join(sorted(set(strong.get('classes',[])+strong.get('triggers',[])+strong.get('api_ApexClass',[])+strong.get('api_ApexTrigger',[])))),
        'flows_active':';'.join(sorted(set(strong.get('flow_active',[])+strong.get('api_Flow',[])))),'flows_inactive':';'.join(weak.get('flow_inactive',[])),
        'validation_rules':';'.join(strong.get('object_validationRules',[])),'formulas_using_it':';'.join(sorted(set(strong.get('formula_field',[])+strong.get('field_other_object',[])))),
        'wave':';'.join(sorted(set(strong.get('wave',[])+strong.get('api_WaveRecipe',[])))),'lwc_vf':';'.join(sorted(set(strong.get('lwc',[])+strong.get('aura',[])+strong.get('pages',[])+strong.get('components',[])+strong.get('api_LightningComponentBundle',[])+strong.get('api_ApexPage',[])+strong.get('api_ApexComponent',[])))),
        'workflow_dup_assign_rules':';'.join(sorted(set(strong.get('workflows',[])+strong.get('duplicateRules',[])+strong.get('matchingRules',[])+strong.get('assignmentRules',[])))),
        'reports_run_last12m':';'.join(rep_recent),'reports_older':';'.join(rep_old),'layouts':len(weak.get('layouts',[])),'list_views':';'.join(weak.get('object_listViews',[])),'flexipages_quickactions':';'.join(sorted(set(weak.get('flexipages',[])+weak.get('quickActions',[])))),
        'synced_to_sfmc':in_sfmc,'ingested_to_data_cloud':in_dc,'classification':cls,'description':f.get('desc') or ''})
rows.sort(key=lambda r:(KEY.index(r['object']),r['classification'],r['field']))
with open('field_audit.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
json.dump(rows,open('field_audit.json','w'),indent=1)
# ---- object audit ----
ents={r['QualifiedApiName']:r for r in json.load(open('entities.json'))['result']['records']}
cf=Counter(f['object'] for f in json.load(open('custom_fields.json')))
orows=[]
for n,r in act.items():
    e=ents.get(n,{}); cnt=r.get('count'); cnt=cnt if isinstance(cnt,int) else ''
    last=r.get('last_created') or ''; ns=e.get('NamespacePrefix') or ''
    if r.get('count_err'): verdict='NOT QUERYABLE (custom setting / protected)'
    elif cnt==0: verdict='EMPTY'
    elif last and last<D12: verdict='DORMANT 12+ months'
    elif last and last<D6: verdict='DORMANT 6-12 months'
    else: verdict='ACTIVE'
    orows.append({'object':n,'label':e.get('Label',''),'namespace':ns,'custom_setting':e.get('IsCustomSetting',''),'custom_fields':cf.get(n,0),'records':cnt,'first_record':r.get('first_created') or '','last_record_created':last,'last_record_modified':r.get('last_modified') or '','in_sfmc_sync':any(n==k.replace('_Salesforce','') for k in sfmc),'in_data_cloud':n in dc_fields,'verdict':verdict})
orows.sort(key=lambda r:(r['namespace']!='',r['namespace'],r['object']))
with open('object_audit.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=list(orows[0].keys())); w.writeheader(); w.writerows(orows)
json.dump(orows,open('object_audit.json','w'),indent=1)
print(len(rows),'fields;',len(orows),'objects')
print(Counter(r['classification'].split(':')[0] for r in rows))
for o in KEY:
    rs=[r for r in rows if r['object']==o]
    if rs: print(f"{o:28s} n={len(rs):4d} "+' '.join(f"{k}={v}" for k,v in sorted(Counter(r['classification'].split(':')[0] for r in rs).items())))
print('dc flags set:',sum(1 for r in rows if r['ingested_to_data_cloud']),'sfmc flags:',sum(1 for r in rows if r['synced_to_sfmc']))
