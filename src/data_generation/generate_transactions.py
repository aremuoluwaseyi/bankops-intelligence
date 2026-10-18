"""Generate NORMAL synthetic digital-banking transactions for NovaTrust Bank.

Purpose:
- establish a reproducible baseline before incidents are injected;
- provide customer-facing operational events for BankOps monitoring.

No real customer or production banking data is used.
"""
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42

SERVICE_CONFIG = {
    "S001": {"name": "Interbank Transfer", "weight": 0.22, "success_rate": 0.985, "latency_mean": 1150, "latency_sd": 260},
    "S002": {"name": "Intrabank Transfer", "weight": 0.18, "success_rate": 0.992, "latency_mean": 720,  "latency_sd": 170},
    "S003": {"name": "Authentication",      "weight": 0.20, "success_rate": 0.995, "latency_mean": 420,  "latency_sd": 100},
    "S004": {"name": "OTP",                 "weight": 0.12, "success_rate": 0.990, "latency_mean": 650,  "latency_sd": 150},
    "S005": {"name": "Bill Payment",        "weight": 0.12, "success_rate": 0.987, "latency_mean": 980,  "latency_sd": 220},
    "S006": {"name": "Airtime and Data",    "weight": 0.09, "success_rate": 0.991, "latency_mean": 760,  "latency_sd": 180},
    "S007": {"name": "Account Services",    "weight": 0.07, "success_rate": 0.994, "latency_mean": 500,  "latency_sd": 120},
}

ERRORS = {
    "S001": ["NETWORK_TIMEOUT", "PROVIDER_TEMP_ERROR"],
    "S002": ["CORE_TEMP_ERROR", "NETWORK_TIMEOUT"],
    "S003": ["AUTH_TEMP_ERROR", "SESSION_ERROR"],
    "S004": ["OTP_DELAY", "OTP_TEMP_ERROR"],
    "S005": ["BILLER_TEMP_ERROR", "NETWORK_TIMEOUT"],
    "S006": ["PROVIDER_TEMP_ERROR", "NETWORK_TIMEOUT"],
    "S007": ["ACCOUNT_API_TEMP_ERROR", "SESSION_ERROR"],
}

CHANNELS = ["Mobile Banking", "Internet Banking", "API"]
CHANNEL_WEIGHTS = [0.68, 0.22, 0.10]

def generate_normal_transactions(n=12000, start="2026-10-01 00:00:00", hours=24, output_path=None):
    rng = np.random.default_rng(SEED)

    service_ids = list(SERVICE_CONFIG)
    service_weights = [SERVICE_CONFIG[s]["weight"] for s in service_ids]
    selected_services = rng.choice(service_ids, size=n, p=service_weights)

    # Spread events across the day. This is a controlled demonstration baseline.
    seconds = np.sort(rng.integers(0, hours * 3600, size=n))
    timestamps = pd.Timestamp(start) + pd.to_timedelta(seconds, unit="s")

    rows = []
    for i, (timestamp, service_id) in enumerate(zip(timestamps, selected_services), start=1):
        cfg = SERVICE_CONFIG[service_id]
        success = rng.random() < cfg["success_rate"]
        latency = max(80, int(rng.normal(cfg["latency_mean"], cfg["latency_sd"])))

        # A failed transaction is normally slower, even in the healthy baseline.
        if not success:
            latency = int(latency * rng.uniform(1.3, 2.0))
            error_code = rng.choice(ERRORS[service_id])
            status = "FAILED"
        else:
            error_code = ""
            status = "SUCCESS"

        rows.append({
            "transaction_id": f"TX{i:07d}",
            "timestamp": timestamp,
            "service_id": service_id,
            "customer_ref": f"CUST{rng.integers(1, 2501):05d}",
            "channel": rng.choice(CHANNELS, p=CHANNEL_WEIGHTS),
            "status": status,
            "response_time_ms": latency,
            "error_code": error_code,
            "correlation_id": f"CORR{i:07d}",
            "scenario": "NORMAL"
        })

    df = pd.DataFrame(rows)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

    return df

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    output = root / "data" / "raw" / "transactions_normal.csv"
    df = generate_normal_transactions(output_path=output)
    print(f"Created {len(df):,} normal synthetic transactions.")
    print(f"Overall success rate: {(df['status'].eq('SUCCESS').mean()*100):.2f}%")
    print(f"Saved to: {output}")
