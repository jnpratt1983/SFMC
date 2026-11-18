#!/usr/bin/env python3
"""Which fields move the Einstein Lead Score, and do they also move purchase. Reconstruction from Lead data; Einstein
Lead Scoring exposes no factor object. Export first:

  sf data query -o blueowl-prod --result-format csv -q "SELECT Id, CreatedDate, Lead_Score__c, Max_Quote_Step__c, purchased__c,
    Purchased_Date__c, Declined__c, Saved_Quote__c, of_Calls_to_CC__c, of_Emails_Received__c, of_Sessions__c, of_SMS_Delivered__c,
    Auto_Renters_Bundle_OptIn_Flag__c, Credit_Score__c, Currently_Insured_Status__c, First_Month_Discount_Amount__c, Five_Year_LTV__c,
    Five_Year_PLE__c, LeadSource, Projected_Bundled_Dollars_Off__c, Projected_Bundled_First_Month_Bill__c, Projected_First_Month_Bill__c,
    Underwriting_Score__c, utm_campaign__c, utm_content__c, utm_medium__c, utm_source__c, utm_term__c, Vehicle_Make__c, Vehicle_Model__c,
    State__c, LandingPageID__c, Status FROM Lead WHERE CreatedDate >= 2026-10-01T00:00:00Z" > factors/leads.csv
  venv/bin/python -I scripts/lead_score_factors.py   (reads factors/leads.csv; add has_mobile/has_email columns or drop them)
"""
import pandas as pd, numpy as np
pd.set_option('display.width',220); pd.set_option('display.max_rows',200)
def sp(a,b):
    x=pd.DataFrame({'a':a,'b':b}).dropna()
    return x.a.rank().corr(x.b.rank()) if len(x)>30 and x.a.nunique()>1 and x.b.nunique()>1 else np.nan
d=pd.read_csv('factors/leads.csv', dtype=str)
d['cd']=pd.to_datetime(d.CreatedDate,utc=True); d['score']=pd.to_numeric(d.Lead_Score__c); d['step']=pd.to_numeric(d.Max_Quote_Step__c,errors='coerce')
d['age']=(pd.Timestamp.now('UTC')-d.cd).dt.days
d['buy']=(d.purchased__c=='true').astype(int)
num=['of_Calls_to_CC__c','of_Emails_Received__c','of_SMS_Delivered__c','Credit_Score__c','First_Month_Discount_Amount__c','Five_Year_LTV__c','Five_Year_PLE__c','Projected_First_Month_Bill__c','Underwriting_Score__c']
for c in num: d[c]=pd.to_numeric(d[c],errors='coerce')
d['disc_pct']=d.First_Month_Discount_Amount__c/(d.First_Month_Discount_Amount__c+d.Projected_First_Month_Bill__c)
cat=['Auto_Renters_Bundle_OptIn_Flag__c','Currently_Insured_Status__c','Declined__c','Saved_Quote__c','LeadSource','utm_medium__c','utm_source__c','utm_campaign__c','utm_content__c','utm_term__c','Vehicle_Make__c','Vehicle_Model__c','State__c','LandingPageID__c']
def auc(s,y):
    x=pd.DataFrame({'s':s,'y':y}).dropna()
    if x.y.nunique()<2 or len(x)<30: return np.nan
    r=x.s.rank(); n1=x.y.sum(); n0=len(x)-n1; return (r[x.y==1].sum()-n1*(n1+1)/2)/(n1*n0)
s=d[d.score.notna()].copy()
print('scored leads', len(s), ' purchased', s.buy.sum(), ' mean score', round(s.score.mean(),1))
print('\n== Numeric fields: rank corr with score | AUC for score>=96 | rank corr with purchase | AUC purchase')
rows=[]
for c in num+['disc_pct','step','age']:
    x=s.dropna(subset=[c])
    rows.append(dict(field=c, n=len(x), rho_score=round(sp(x[c],x.score),2), auc_top=round(auc(x[c],(x.score>=96).astype(int)),2), rho_buy=round(sp(x[c],x.buy),2), auc_buy=round(auc(x[c],x.buy),2)))
print(pd.DataFrame(rows).sort_values('rho_score',key=abs,ascending=False).to_string(index=False))
print('\n== Categorical fields: spread of mean score across levels (eta^2), and purchase spread (levels with n>=50)')
rows=[]
for c in cat:
    g=s.groupby(s[c].fillna('(blank)'))
    m=g.agg(n=('score','size'),score=('score','mean'),buy=('buy','mean')); m=m[m.n>=50]
    if len(m)<2: continue
    eta=((m.score-s.score.mean())**2*m.n).sum()/((s.score-s.score.mean())**2).sum()
    rows.append(dict(field=c, levels=len(m), eta2_score=round(eta,3), score_lo=f"{str(m.score.idxmin())[:18]} {m.score.min():.0f}", score_hi=f"{str(m.score.idxmax())[:18]} {m.score.max():.0f}", buy_lo=f"{m.buy.min()*100:.1f}%", buy_hi=f"{m.buy.max()*100:.1f}%"))
print(pd.DataFrame(rows).sort_values('eta2_score',ascending=False).to_string(index=False))
print('\n== Mean score and purchase by level, key fields')
for c in ['Currently_Insured_Status__c','Saved_Quote__c','Declined__c','Auto_Renters_Bundle_OptIn_Flag__c','utm_medium__c','LeadSource','has_mobile']:
    m=s.groupby(s[c].fillna('(blank)')).agg(n=('score','size'),score=('score','mean'),top=('score',lambda v:(v>=96).mean()*100),buy=('buy','mean')); m=m[m.n>=50]; m['buy']=(m.buy*100).round(1); print(f'-- {c}'); print(m.round(1).sort_values('score',ascending=False).head(8).to_string())
print('\n== Quartiles (scored leads at step>=4): mean score, % at 96+, purchase %')
h=s[s.step>=4]
for c in ['Credit_Score__c','Underwriting_Score__c','disc_pct','Projected_First_Month_Bill__c','Five_Year_PLE__c','Five_Year_LTV__c','of_Emails_Received__c','of_SMS_Delivered__c']:
    x=h.dropna(subset=[c]).copy()
    try: x['q']=pd.qcut(x[c],4,duplicates='drop')
    except Exception: continue
    m=x.groupby('q',observed=True).agg(n=('score','size'),score=('score','mean'),top=('score',lambda v:(v>=96).mean()*100),buy=('buy','mean')); m['buy']*=100; print(f'-- {c}'); print(m.round(1).to_string())
print('\n== Within step x age-bucket cells (n>=40): median rank corr of field with score, share of cells positive')
s['ageb']=pd.cut(s.age,[-1,3,7,14,30,60]); rows=[]
for c in num+['disc_pct']:
    vals=[sp(g[c],g.score) for _,g in s.dropna(subset=[c]).groupby(['step','ageb'],observed=True) if len(g)>=40 and g[c].nunique()>3]
    vals=[v for v in vals if not np.isnan(v)]
    if vals: rows.append(dict(field=c,cells=len(vals),median_rho=round(np.median(vals),2),share_pos=round(np.mean([v>0 for v in vals]),2)))
print(pd.DataFrame(rows).sort_values('median_rho',key=abs,ascending=False).to_string(index=False))
