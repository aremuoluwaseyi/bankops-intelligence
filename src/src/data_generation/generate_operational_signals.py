"""Generate normal operational evidence around NovaTrust transactions.

Creates:
- application logs
- component health observations
- component metrics

All data is synthetic.
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42

def generate_normal_operational_signals(root):
    root = Path(root)
    raw = root / "data" / "raw"
    rng = np.random.default_rng(SEED)

    components = pd.read_csv(raw / "components.csv")
    deps = pd.read_csv(raw / "service_dependencies.csv")
    tx = pd.read_csv(raw / "transactions_normal.csv", parse_dates=["timestamp"])

    profiles = {
        "C001": ("latency_ms", 520, 90), "C002": ("latency_ms", 430, 70),
        "C003": ("latency_ms", 900, 160), "C004": ("latency_ms", 600, 120),
        "C005": ("latency_ms", 300, 55), "C006": ("query_latency_ms", 110, 25),
        "C007": ("latency_ms", 180, 35), "C008": ("latency_ms", 760, 140),
        "C009": ("latency_ms", 680, 125), "C010": ("latency_ms", 360, 65),
    }

    times = pd.date_range("2026-10-01 00:00:00", periods=288, freq="5min")
    metric_rows, health_rows = [], []
    mid = hid = 1

    for _, comp in components.iterrows():
        metric_name, mean, sd = profiles[comp.component_id]
        for timestamp in times:
            value = max(20, float(rng.normal(mean, sd)))
            metric_rows.append([f"M{mid:07d}", timestamp, comp.component_id,
                                metric_name, round(value,2), "ms", "NORMAL"])
            health_ms = max(10, int(rng.normal(
                85 if "External" not in comp.component_type else 130, 22)))
            availability = round(float(rng.uniform(99.90, 100.00)), 3)
            health_rows.append([f"H{hid:07d}", timestamp, comp.component_id,
                                "UP", availability, health_ms, "NORMAL"])
            mid += 1; hid += 1

    metrics = pd.DataFrame(metric_rows, columns=[
        "metric_id","timestamp","component_id","metric_name","metric_value","unit","scenario"])
    health = pd.DataFrame(health_rows, columns=[
        "health_id","timestamp","component_id","status","availability_pct",
        "health_check_ms","scenario"])

    dep_map = deps.groupby("service_id")["component_id"].apply(list).to_dict()
    log_rows=[]; lid=1
    success_sample = tx[tx.status=="SUCCESS"].sample(n=900, random_state=SEED)

    for _, row in success_sample.iterrows():
        cid = rng.choice(dep_map[row.service_id])
        log_rows.append([f"L{lid:07d}",row.timestamp,row.service_id,cid,
                         row.correlation_id,"INFO","","Request processed successfully","NORMAL"])
        lid += 1

    for _, row in tx[tx.status=="FAILED"].iterrows():
        cid = rng.choice(dep_map[row.service_id])
        level = "WARN" if rng.random() < 0.65 else "ERROR"
        log_rows.append([f"L{lid:07d}",row.timestamp,row.service_id,cid,
                         row.correlation_id,level,row.error_code,
                         f"Temporary processing issue: {row.error_code}","NORMAL"])
        lid += 1

    logs = pd.DataFrame(log_rows, columns=[
        "log_id","timestamp","service_id","component_id","correlation_id",
        "log_level","error_code","message","scenario"]).sort_values("timestamp")

    metrics.to_csv(raw/"component_metrics_normal.csv", index=False)
    health.to_csv(raw/"service_health_normal.csv", index=False)
    logs.to_csv(raw/"application_logs_normal.csv", index=False)
    return logs, health, metrics

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    logs, health, metrics = generate_normal_operational_signals(project_root)
    print(f"Created {len(logs):,} logs, {len(health):,} health records, "
          f"and {len(metrics):,} metric records.")
