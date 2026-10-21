import sys, json, time
from sfh import *
objs=sys.argv[1:]
flds=json.load(open('custom_fields.json'))
for obj in objs:
    out={}
    try:
        fd=q(f"SELECT QualifiedApiName, DataType, IsCalculated, Label, IsIndexed, LastModifiedDate FROM FieldDefinition WHERE EntityDefinitionId='{obj}'",tooling=True)
    except Exception as e:
        print(obj,'fielddef err',e); fd=[]
    types={f['QualifiedApiName']:f for f in fd}
    names=[f['field'] for f in flds if f['object']==obj]
    for fname in names:
        t=types.get(fname,{})
        rec={'type':t.get('DataType'),'calc':t.get('IsCalculated'),'label':t.get('Label')}
        if t.get('IsCalculated'):
            rec['note']='formula'; out[fname]=rec; continue
        dt=(t.get('DataType') or '')
        try:
            if dt.startswith('Long Text') or dt.startswith('Rich Text') or dt.startswith('Text Area(Long') or 'Text Area' in dt and 'Long' in dt or dt in ('Html','Address','Location'):
                # can't filter on long text; sample via ORDER BY and count not possible -> use LIMIT scan
                r=q(f"SELECT COUNT() FROM {obj}")
                rec['note']='long text: not filterable'
            else:
                r=q(f"SELECT COUNT(Id) c, MAX(CreatedDate) mc, MAX(LastModifiedDate) mm, MIN(CreatedDate) fc FROM {obj} WHERE {fname} != null")
                rec.update({'populated':r[0]['c'],'last_created_with_value':(r[0]['mc'] or '')[:10],'last_modified_with_value':(r[0]['mm'] or '')[:10],'first_created_with_value':(r[0]['fc'] or '')[:10]})
        except Exception as e:
            msg=str(e)
            if 'QUERY_TIMEOUT' in msg or 'timeout' in msg.lower():
                try:
                    r=q(f"SELECT CreatedDate FROM {obj} WHERE {fname} != null ORDER BY CreatedDate DESC LIMIT 1")
                    rec['last_created_with_value']=r[0]['CreatedDate'][:10] if r else None
                    rec['populated']='timeout' if r else 0
                except Exception as e2: rec['err']=str(e2)[:150]
            else: rec['err']=msg[:150]
        out[fname]=rec
        time.sleep(0.05)
    json.dump(out,open(f'pop_{obj}.json','w'),indent=1)
    print(obj,'done',len(out),flush=True)
