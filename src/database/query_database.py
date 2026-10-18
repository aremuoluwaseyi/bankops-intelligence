from pathlib import Path
import sqlite3, pandas as pd

def connect(db_path):
    con=sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    return con

def service_performance(con):
    return pd.read_sql_query("""SELECT s.service_name, COUNT(*) transactions, ROUND(100.0*SUM(CASE WHEN t.status='FAILED' THEN 1 ELSE 0 END)/COUNT(*),2) failure_pct, ROUND(AVG(t.response_time_ms),1) avg_response_ms FROM transactions t JOIN services s ON s.service_id=t.service_id GROUP BY s.service_name ORDER BY transactions DESC""",con)

if __name__ == "__main__":
    root=Path(__file__).resolve().parents[2]
    con=connect(root/"database"/"bankops.db")
    print(service_performance(con).to_string(index=False))
    con.close()
