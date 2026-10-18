"""Formal data-quality gate for the BankOps synthetic environment.
Run before SQL loading or modelling.
"""
from pathlib import Path
import pandas as pd

def validate(root):
    root=Path(root); raw=root/"data"/"raw"
    services=pd.read_csv(raw/"services.csv")
    components=pd.read_csv(raw/"components.csv")
    deps=pd.read_csv(raw/"service_dependencies.csv")
    normal=pd.read_csv(raw/"transactions_normal.csv")
    incidents=pd.read_csv(raw/"transactions_incidents.csv")
    controls=pd.read_csv(raw/"healthy_control_transactions.csv")
    results=[]
    def check(name, condition): results.append((name,"PASS" if condition else "FAIL"))
    check("service IDs unique", services.service_id.is_unique)
    check("component IDs unique", components.component_id.is_unique)
    check("dependency service references valid", set(deps.service_id)<=set(services.service_id))
    check("dependency component references valid", set(deps.component_id)<=set(components.component_id))
    check("normal transaction IDs unique", normal.transaction_id.is_unique)
    check("incident transaction IDs unique", incidents.transaction_id.is_unique)
    check("control transaction IDs unique", controls.transaction_id.is_unique)
    check("normal labels correct", set(normal.scenario)=={"NORMAL"})
    check("control labels correct", set(controls.scenario)=={"HEALTHY_CONTROL"})
    return pd.DataFrame(results,columns=["check","status"])

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    result=validate(root)
    print(result.to_string(index=False))
    if (result.status=="FAIL").any(): raise SystemExit(1)
