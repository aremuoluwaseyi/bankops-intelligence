"""Reproducible Phase 5 alert handoff; no ground-truth labels enter detection.
Run from repository root: python src/detection/run_detection_handoff.py
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rule_based_detector import detect

REQUIRED = ["monitoring_window_id", "service_id", "window_start", "window_end", "transaction_volume", "failed_transactions", "failure_rate_pct", "p95_response_ms", "max_component_metric_ratio", "degraded_components", "down_components", "warn_error_logs", "technical_evidence_available", "evidence_sources_present"]
SIGNALS = ["rule_failure_rate", "rule_latency", "rule_component", "rule_logs"]

def build_handoff(features: pd.DataFrame, secondary: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = sorted(set(REQUIRED) - set(features.columns))
    if missing: raise ValueError(f"Missing required monitoring fields: {missing}")
    if features.monitoring_window_id.isna().any() or features.monitoring_window_id.duplicated().any():
        raise ValueError("monitoring_window_id must be unique and non-null")
    # Ground truth is deliberately not used in the detector input.
    if "expected_incident" in features.columns or "scenario" in features.columns:
        raise ValueError("Remove evaluation labels before calling the detector")
    scored = detect(features.copy())
    if secondary is not None:
        ml = secondary[["monitoring_window_id", "ml_anomaly_score", "ml_threshold"]].drop_duplicates("monitoring_window_id")
        scored = scored.merge(ml, on="monitoring_window_id", how="left", validate="one_to_one")
    else:
        scored["ml_anomaly_score"] = float("nan")
        scored["ml_threshold"] = float("nan")
    alerts = scored.loc[scored.predicted_incident == 1].copy()
    alerts["alert_id"] = "ALERT_" + alerts.monitoring_window_id.astype(str)
    alerts["detection_method"] = "rule_based_v1"
    alerts["alert_status"] = "PENDING_INVESTIGATION"
    alerts["signal_names"] = alerts.apply(lambda row: ",".join(s for s in SIGNALS if bool(row[s])), axis=1)
    alerts["likely_failure_domain"] = "UNDETERMINED"
    alerts["human_verification_required"] = True
    cols = ["alert_id", "monitoring_window_id", "service_id", "window_start", "window_end", "alert_status", "detection_method", "signal_names", "rule_signal_count", "transaction_volume", "failed_transactions", "failure_rate_pct", "p95_response_ms", "max_component_metric_ratio", "degraded_components", "down_components", "warn_error_logs", "technical_evidence_available", "evidence_sources_present", "ml_anomaly_score", "ml_threshold", "likely_failure_domain", "human_verification_required"]
    return scored, alerts[cols].sort_values(["window_start", "service_id", "alert_id"]).reset_index(drop=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, default=ROOT / "data/processed/phase5_detection_feature_handoff.csv")
    parser.add_argument("--secondary", type=Path, default=ROOT / "data/processed/isolation_forest_tuned_predictions.csv")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/processed")
    args = parser.parse_args()
    features = pd.read_csv(args.features)
    secondary = pd.read_csv(args.secondary) if args.secondary.is_file() else None
    scored, alerts = build_handoff(features, secondary)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scored.to_csv(args.output_dir / "phase5_final_scored_windows.csv", index=False)
    alerts.to_csv(args.output_dir / "phase5_investigation_handoff.csv", index=False)
    report = {"monitoring_windows": len(scored), "alerts": len(alerts), "non_alert_windows": int((scored.predicted_incident == 0).sum()), "primary_detector": "rule_based_v1", "secondary_scores_present": int(scored.ml_anomaly_score.notna().sum()), "evaluation_labels_used_for_detection": False, "human_verification_required": True}
    (args.output_dir / "phase5_step5_summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
if __name__ == "__main__": main()
