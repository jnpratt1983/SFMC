import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import dc, pandas as pd, time

def pull(name, order="Lead_Id__c", where=""):
    rows=[]; off=0; cols=None
    while True:
        r = dc.sql(f"SELECT * FROM {name} {where} ORDER BY {order} LIMIT 50000 OFFSET {off}")
        cols = cols or r[0]; rows += r[1]; off += len(r[1])
        print(name, off, len(rows), flush=True)
        if len(r[1]) == 0: break
    df = pd.DataFrame(rows, columns=cols); df.to_pickle(f"pit/{name}.pkl"); print(name, "saved", df.shape, flush=True)
pull("Email_Response_Training_Set__cio")
pull("SMS_Response_Training_Set__cio")
pull("Phone_Response_Training_Set__cio")
