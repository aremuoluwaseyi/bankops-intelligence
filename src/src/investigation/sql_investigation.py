"""Evidence-first SQL investigation helper for BankOps Intelligence.

This module does not claim a root cause. It retrieves evidence that later
analytics/ML/RAG/LLM layers can evaluate.
"""
from pathlib import Path
import sqlite3
import pandas as pd

def customer_impact(conn, start_time, end_time, service_id, scenario):
    query = """
    SELECT COUNT(*) AS transactions,
           SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed,
           ROUND(100.0*SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END)/COUNT(*),2) AS failure_rate_pct,
           COUNT(DISTINCT CASE WHEN status='FAILED' THEN customer_ref END) AS affected_customers,
           ROUND(AVG(response_time_ms),1) AS avg_response_ms
    FROM transactions
    WHERE timestamp BETWEEN ? AND ?
      AND service_id=?
      AND scenario=?
    """
    return pd.read_sql_query(query, conn, params=[start_time,end_time,service_id,scenario])

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    conn = sqlite3.connect(root/"database"/"bankops.db")
    example = customer_impact(conn,
        "2026-10-01 10:40:00","2026-10-01 11:10:00","S001","INC001")
    print(example.to_string(index=False))
    conn.close()
