"""Phase 9 Step 4: bounded local scheduler, lease, and delivery-readiness audit.

This is an opt-in foreground runner. It does not install a background service,
connect to banking infrastructure, or transmit any notifications.
"""
import argparse
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from src.orchestration.proactive import cycle, SCHEMA
from src.orchestration.pipeline import ROOT


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def readiness(db_path):
    """Inspect local outbox; only analyst-review items are notification candidates."""
    with sqlite3.connect(db_path) as con:
        con.execute(SCHEMA)
        rows = con.execute('SELECT queue,status,COUNT(*) FROM alert_outbox GROUP BY queue,status').fetchall()
    candidates = sum(n for queue, status, n in rows if queue == 'ANALYST_REVIEW' and status == 'PENDING_LOCAL_REVIEW')
    exceptions = sum(n for queue, status, n in rows if queue == 'VALIDATION_EXCEPTION' and status == 'VALIDATION_EXCEPTION')
    return {'local_notification_candidates': candidates, 'validation_exceptions': exceptions,
            'external_notifications_sent': 0, 'delivery_enabled': False,
            'human_review_required': True}


def run_cycles(root=ROOT, iterations=1, interval_seconds=0, run_pipeline=False, db_path=None, sleep=time.sleep):
    if not isinstance(iterations, int) or not 1 <= iterations <= 100:
        raise ValueError('iterations must be between 1 and 100')
    if not isinstance(interval_seconds, (int,float)) or not 0 <= interval_seconds <= 86400:
        raise ValueError('interval_seconds must be between 0 and 86400')
    root = Path(root)
    db = Path(db_path) if db_path else root/'data/processed/phase9_step3_alert_outbox.sqlite'
    db.parent.mkdir(parents=True, exist_ok=True)
    lock = db.with_suffix(db.suffix + '.runner.lock')
    # Atomic single-process lease. Stale locks require deliberate manual investigation.
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError('Another cycle runner may be active; inspect lock before retrying') from exc
    history = []
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(json.dumps({'pid': os.getpid(), 'started_at_utc': utcnow()})+'\n')
        for index in range(iterations):
            entry = {'cycle_number': index+1, 'started_at_utc': utcnow()}
            try:
                result = cycle(root=root, run_pipeline=run_pipeline, db_path=db)
                entry.update({'status': 'SUCCEEDED', 'result': result, 'readiness': readiness(db)})
            except Exception as exc:
                entry.update({'status': 'FAILED_CLOSED', 'error_type': type(exc).__name__,
                              'error': str(exc)[:300]})
                history.append(entry)
                break
            history.append(entry)
            if index+1 < iterations:
                sleep(interval_seconds)
    finally:
        lock.unlink(missing_ok=True)
    summary = {'mode': 'bounded_foreground_local_runner', 'requested_cycles': iterations,
               'completed_cycles': len(history), 'status': 'SUCCEEDED' if len(history)==iterations and all(x['status']=='SUCCEEDED' for x in history) else 'FAILED_CLOSED',
               'external_notifications_sent': 0, 'automatic_remediations': 0,
               'cycles': history}
    return summary


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--iterations',type=int,default=1)
    p.add_argument('--interval-seconds',type=float,default=0)
    p.add_argument('--run-pipeline',action='store_true')
    p.add_argument('--db',type=Path)
    p.add_argument('--audit',type=Path,default=Path('data/processed/phase9_step4_scheduler_audit.json'))
    args=p.parse_args()
    report=run_cycles(iterations=args.iterations,interval_seconds=args.interval_seconds,run_pipeline=args.run_pipeline,db_path=args.db)
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='cycles'},indent=2))
    if report['status']!='SUCCEEDED': raise SystemExit(1)
