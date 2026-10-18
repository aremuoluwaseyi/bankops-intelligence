"""Phase 6 Step 1: bounded, read-only operational evidence retrieval.

No incident_ground_truth or healthy_control_ground_truth tables are accessed.
"""
import json
import sqlite3
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "database" / "bankops.db"
ALERTS = ROOT / "data" / "processed" / "phase5_investigation_handoff.csv"
OUT = ROOT / "data" / "processed" / "phase6_step1_evidence_packages.jsonl"

def collect_evidence(conn, alert):
    service = str(alert["service_id"])
    start, end = str(alert["window_start"]), str(alert["window_end"])
    if start >= end:
        raise ValueError("Invalid alert time window")
    component_rows = conn.execute("""SELECT c.component_id,c.component_name,c.component_type
      FROM service_dependencies d JOIN components c ON c.component_id=d.component_id
      WHERE d.service_id=? ORDER BY c.component_id""", (service,)).fetchall()
    components = [dict(row) for row in component_rows]
    component_ids = [x["component_id"] for x in components]
    tx = conn.execute("""SELECT COUNT(*) AS total, SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed,
      ROUND(AVG(response_time_ms),2) AS avg_response_ms
      FROM transactions WHERE service_id=? AND timestamp>=? AND timestamp<?""",(service,start,end)).fetchone()
    errors = conn.execute("""SELECT error_code,COUNT(*) AS count FROM transactions
      WHERE service_id=? AND timestamp>=? AND timestamp<? AND status='FAILED'
      GROUP BY error_code ORDER BY count DESC,error_code LIMIT 5""",(service,start,end)).fetchall()
    logs = conn.execute("""SELECT component_id,log_level,error_code,COUNT(*) AS count
      FROM application_logs WHERE service_id=? AND timestamp>=? AND timestamp<?
      GROUP BY component_id,log_level,error_code ORDER BY count DESC LIMIT 12""",(service,start,end)).fetchall()
    # Shared components may also support other services; do not use scenario labels as filters.
    health=[]; metrics=[]; changes=[]
    if component_ids:
        placeholders=','.join('?' for _ in component_ids)
        health=conn.execute(f"""SELECT component_id,status,ROUND(AVG(availability_pct),3) AS avg_availability_pct,
           MAX(health_check_ms) AS max_health_check_ms,COUNT(*) AS samples FROM service_health
           WHERE component_id IN ({placeholders}) AND timestamp>=? AND timestamp<?
           GROUP BY component_id,status ORDER BY component_id,status""",(*component_ids,start,end)).fetchall()
        metrics=conn.execute(f"""SELECT component_id,metric_name,ROUND(MAX(metric_value),3) AS max_value,
           ROUND(AVG(metric_value),3) AS avg_value,unit,COUNT(*) AS samples FROM component_metrics
           WHERE component_id IN ({placeholders}) AND timestamp>=? AND timestamp<?
           GROUP BY component_id,metric_name,unit ORDER BY component_id,metric_name""",(*component_ids,start,end)).fetchall()
        # 30-minute lookback: contextual, not causal proof.
        changes=conn.execute(f"""SELECT change_id,timestamp,component_id,change_type,version,status
           FROM change_events WHERE component_id IN ({placeholders})
           AND timestamp>=datetime(?,'-30 minutes') AND timestamp<? ORDER BY timestamp DESC LIMIT 10""",(*component_ids,start,start)).fetchall()
    package={
       "alert_id":str(alert["alert_id"]),"monitoring_window_id":str(alert["monitoring_window_id"]),
       "service_id":service,"window_start":start,"window_end":end,
       "detection_signals":str(alert["signal_names"]).split(','),
       "alert_metrics":{"transaction_volume":int(alert["transaction_volume"]),
                        "failed_transactions":int(alert["failed_transactions"]),
                        "failure_rate_pct":float(alert["failure_rate_pct"])},
       "dependencies":components,
       "transactions":{"total":int(tx["total"] or 0),"failed":int(tx["failed"] or 0),
                       "avg_response_ms":tx["avg_response_ms"]},
       "dominant_transaction_errors":[dict(z) for z in errors],
       "application_log_patterns":[dict(z) for z in logs],
       "component_health":[dict(z) for z in health],
       "component_metrics":[dict(z) for z in metrics],
       "recent_changes_30min":[dict(z) for z in changes],
       "source_coverage":{"transaction_rows":int(tx["total"] or 0),"log_groups":len(logs),
                          "health_groups":len(health),"metric_groups":len(metrics)},
       "likely_failure_domain":"UNDETERMINED", "root_cause_confirmed":False,
       "human_verification_required":True,
       "interpretation_note":"Raw evidence only; missing rows do not prove component health. Change proximity does not prove causation."
    }
    return package

def run(alerts_path=ALERTS, db_path=DB, output_path=OUT):
    alerts=pd.read_csv(alerts_path).fillna("")
    output_path=Path(output_path);output_path.parent.mkdir(parents=True,exist_ok=True)
    packages=[]
    with sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro",uri=True) as conn:
        conn.row_factory=sqlite3.Row
        for _,alert in alerts.iterrows():
            packages.append(collect_evidence(conn,alert))
    with output_path.open('w',encoding='utf-8') as f:
        for package in packages:f.write(json.dumps(package,ensure_ascii=False)+'\n')
    return packages

if __name__=='__main__':
    result=run()
    print(f"Generated {len(result)} evidence packages: {OUT}")
