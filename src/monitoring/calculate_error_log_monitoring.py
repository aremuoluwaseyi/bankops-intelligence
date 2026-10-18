"""Phase 4 Step 3: error and log monitoring for BankOps Intelligence."""
from pathlib import Path
import pandas as pd

def build_error_log_monitoring(root):
    root=Path(root); proc=root/"data"/"processed"
    tx=pd.read_csv(proc/"transactions_all.csv",parse_dates=["timestamp"])
    logs=pd.read_csv(proc/"application_logs_all.csv",parse_dates=["timestamp"])
    tx["window_start"]=tx.timestamp.dt.floor("5min")
    logs["window_start"]=logs.timestamp.dt.floor("5min")
    failed=tx[tx.status=="FAILED"].copy()
    tx_errors=failed.groupby(["window_start","scenario","service_id","error_code"],dropna=False).agg(
        error_count=("transaction_id","count"),affected_customers=("customer_ref","nunique")).reset_index()
    logs["is_warn"]=(logs.log_level=="WARN").astype(int)
    logs["is_error"]=(logs.log_level=="ERROR").astype(int)
    log_view=logs.groupby(["window_start","scenario","service_id","component_id"],dropna=False).agg(
        total_logs=("log_id","count"),warn_logs=("is_warn","sum"),error_logs=("is_error","sum")).reset_index()
    return tx_errors, log_view

if __name__=="__main__":
    root=Path(__file__).resolve().parents[2]
    tx_errors,log_view=build_error_log_monitoring(root)
    tx_errors.to_csv(root/"data"/"processed"/"transaction_error_monitoring_5min.csv",index=False)
    log_view.to_csv(root/"data"/"processed"/"log_monitoring_5min.csv",index=False)
