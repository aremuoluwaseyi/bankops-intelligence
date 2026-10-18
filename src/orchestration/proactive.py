"""Phase 9 Step 3: on-demand monitoring cycles with idempotent local alert outbox.

A cycle may optionally run the offline pipeline, then validates its audit and
queues alerts in SQLite. No scheduler, real-time stream or external delivery.
"""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from src.orchestration.workflow import digest
from src.orchestration.pipeline import orchestrate, ROOT

SCHEMA = """CREATE TABLE IF NOT EXISTS alert_outbox (
    work_item_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL UNIQUE,
    source_hash TEXT NOT NULL,
    queue TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING_LOCAL_REVIEW','VALIDATION_EXCEPTION')),
    created_at_utc TEXT NOT NULL,
    payload_json TEXT NOT NULL
)"""

def verify_item(item):
    if item.get('work_item_sha256') != digest({k:v for k,v in item.items() if k!='work_item_sha256'}):
        raise ValueError('Work-item integrity failure')
    if item.get('root_cause_confirmed') is not False or item.get('automated_remediation_allowed') is not False:
        raise ValueError('Unsafe work item')
    if item.get('review_state') != 'PENDING_HUMAN_REVIEW' or item.get('dispatch_status') != 'QUEUED_NOT_SENT':
        raise ValueError('Unexpected review or dispatch state')
    if item.get('queue') not in ('ANALYST_REVIEW','VALIDATION_EXCEPTION'):
        raise ValueError('Unknown queue')
    if item['queue'] == 'ANALYST_REVIEW' and not item.get('analyst_narrative'):
        raise ValueError('Missing analyst narrative')
    return True

def enqueue(db_path, items, now=None):
    items=list(items)
    ids=[i.get('work_item_id') for i in items]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate work items in cycle')
    for item in items: verify_item(item)
    now=now or datetime.now(timezone.utc).isoformat()
    path=Path(db_path); path.parent.mkdir(parents=True,exist_ok=True)
    inserted=duplicates=0
    with sqlite3.connect(path) as con:
        con.execute(SCHEMA)
        for item in items:
            payload=json.dumps(item,sort_keys=True)
            existing=con.execute('SELECT source_hash FROM alert_outbox WHERE work_item_id=?', (item['work_item_id'],)).fetchone()
            if existing:
                if existing[0]!=item['work_item_sha256']:
                    raise ValueError('Conflicting payload for existing work item: '+item['work_item_id'])
                duplicates+=1
                continue
            con.execute('INSERT INTO alert_outbox VALUES (?,?,?,?,?,?,?)',(
                item['work_item_id'],item['alert_id'],item['work_item_sha256'],item['queue'],
                'PENDING_LOCAL_REVIEW' if item['queue']=='ANALYST_REVIEW' else 'VALIDATION_EXCEPTION',now,payload))
            inserted+=1
    return {'received':len(items),'newly_queued':inserted,'already_queued':duplicates,
            'external_notifications_sent':0,'automatic_remediations':0}

def cycle(root=ROOT, run_pipeline=False, db_path=None):
    root=Path(root)
    if run_pipeline:
        audit=orchestrate(root=root)
    else:
        audit_path=root/'data/processed/phase9_step2_pipeline_audit.json'
        if not audit_path.exists(): raise FileNotFoundError('Missing pipeline audit; run with --run-pipeline')
        audit=json.loads(audit_path.read_text(encoding='utf-8'))
    if audit.get('status')!='SUCCEEDED': raise RuntimeError('Pipeline not successful; refusing to queue alerts')
    path=root/'data/processed/phase9_step1_work_queue.jsonl'
    items=[json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    if audit.get('work_items')!=len(items): raise ValueError('Queue count does not match pipeline audit')
    result=enqueue(db_path or root/'data/processed/phase9_step3_alert_outbox.sqlite',items)
    result.update({'mode':'on_demand_cycle','pipeline_rerun':run_pipeline,'scheduler_running':False,
                   'alert_delivery':'local_sqlite_outbox_only'})
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-pipeline',action='store_true')
    parser.add_argument('--db',type=Path)
    args=parser.parse_args()
    print(json.dumps(cycle(run_pipeline=args.run_pipeline,db_path=args.db),indent=2))
