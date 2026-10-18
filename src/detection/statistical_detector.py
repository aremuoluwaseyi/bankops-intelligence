"""Robust statistical anomaly detector for BankOps.
Normal baselines use median/IQR. A signal is high when x > Q3 + 3*IQR.
At least two abnormal evidence signals are required for an incident prediction.
"""
import numpy as np
FEATURES=["failure_rate_pct","p95_response_ms","max_component_metric_ratio","warn_error_logs"]

def fit_baseline(normal_df):
    rows=[]
    for f in FEATURES:
        s=normal_df[f].dropna()
        q1,q3=s.quantile(.25),s.quantile(.75)
        rows.append((f,q1,q3,q3-q1))
    return rows

def detect(df, baseline):
    out=df.copy()
    signals=[]
    for f,q1,q3,iqr in baseline:
        c="stat_"+f
        out[c]=out[f].notna() & (out[f] > q3+3*iqr)
        signals.append(c)
    out["stat_failure_rate_pct"]=out["stat_failure_rate_pct"] & (out.transaction_volume>=10)
    out["stat_signal_count"]=out[signals].sum(axis=1)
    out["stat_predicted_incident"]=(out.stat_signal_count>=2).astype(int)
    return out
