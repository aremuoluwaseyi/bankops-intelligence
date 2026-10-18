"""Interpretable BankOps rule baseline; evaluation labels are external."""
MIN_VOLUME=10
def detect(df):
    out=df.copy()
    out["rule_failure_rate"]=(out.transaction_volume>=MIN_VOLUME)&(out.failure_rate_pct>=5)
    out["rule_latency"]=(out.transaction_volume>=MIN_VOLUME)&(out.p95_response_ms>=3000)
    out["rule_component"]=(out.technical_evidence_available==1)&((out.max_component_metric_ratio>=3)|(out.degraded_components>0)|(out.down_components>0))
    out["rule_logs"]=out.warn_error_logs>=8
    cols=["rule_failure_rate","rule_latency","rule_component","rule_logs"]
    out["rule_signal_count"]=out[cols].sum(axis=1)
    out["predicted_incident"]=(out.rule_signal_count>=2).astype(int)
    return out
