"""Phase 4 Step 1 - operational KPI calculation for BankOps Intelligence.

Uses only synthetic BankOps data. KPI windows summarize operational behaviour;
they do not declare incidents or root causes.
"""
from pathlib import Path
import sqlite3
import pandas as pd

WINDOW_MINUTES = 5

def load_transactions(conn):
    df = pd.read_sql_query("SELECT timestamp, service_id, status, response_time_ms, error_code, scenario FROM transactions", conn)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def calculate_service_kpis(df, window_minutes=WINDOW_MINUTES):
    x = df.copy()
    x["window_start"] = x["timestamp"].dt.floor(f"{window_minutes}min")
    x["failed_flag"] = (x["status"] == "FAILED").astype(int)
    x["success_flag"] = (x["status"] == "SUCCESS").astype(int)
    kpi = x.groupby(["scenario", "service_id", "window_start"], as_index=False).agg(
        transaction_volume=("status", "size"), successful_transactions=("success_flag", "sum"),
        failed_transactions=("failed_flag", "sum"), avg_response_ms=("response_time_ms", "mean"),
        p95_response_ms=("response_time_ms", lambda s: s.quantile(0.95)),
        max_response_ms=("response_time_ms", "max"),
        unique_error_codes=("error_code", lambda s: s.replace("", pd.NA).dropna().nunique()))
    kpi["success_rate_pct"] = 100 * kpi["successful_transactions"] / kpi["transaction_volume"]
    kpi["failure_rate_pct"] = 100 * kpi["failed_transactions"] / kpi["transaction_volume"]
    for col in ["avg_response_ms", "p95_response_ms", "success_rate_pct", "failure_rate_pct"]:
        kpi[col] = kpi[col].round(2)
    kpi["window_end"] = kpi["window_start"] + pd.Timedelta(minutes=window_minutes)
    return kpi[["scenario","service_id","window_start","window_end","transaction_volume",
        "successful_transactions","failed_transactions","success_rate_pct","failure_rate_pct",
        "avg_response_ms","p95_response_ms","max_response_ms","unique_error_codes"]]

def calculate_error_kpis(df, window_minutes=WINDOW_MINUTES):
    x = df[(df["status"] == "FAILED") & df["error_code"].notna() & (df["error_code"] != "")].copy()
    x["window_start"] = x["timestamp"].dt.floor(f"{window_minutes}min")
    return (x.groupby(["scenario","service_id","window_start","error_code"]).size()
             .reset_index(name="error_count")
             .sort_values(["scenario","service_id","window_start","error_count"], ascending=[True,True,True,False]))

def main():
    root = Path(__file__).resolve().parents[2]
    out = root / "data" / "processed"
    conn = sqlite3.connect(root / "database" / "bankops.db")
    tx = load_transactions(conn)
    service = calculate_service_kpis(tx)
    errors = calculate_error_kpis(tx)
    service.to_csv(out / "monitoring_service_kpis_5min.csv", index=False)
    errors.to_csv(out / "monitoring_error_kpis_5min.csv", index=False)
    print(f"Created {len(service):,} service KPI windows and {len(errors):,} error KPI rows.")
    conn.close()

if __name__ == "__main__": main()
