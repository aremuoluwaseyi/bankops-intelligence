"""Read-only verified data adapter for the BankOps demo dashboard."""
import json
import sqlite3
from collections import Counter
from pathlib import Path
from src.orchestration.proactive import verify_item


def load_alerts(db_path):
    """Load a local outbox, validate each payload and cross-check its stored identity."""
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"Local alert outbox not found: {path}")
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT work_item_id, alert_id, source_hash, queue, status, created_at_utc, payload_json FROM alert_outbox ORDER BY created_at_utc DESC, alert_id").fetchall()
    results = []
    for work_id, alert_id, source_hash, queue, status, created_at, raw in rows:
        item = json.loads(raw)
        verify_item(item)
        if (item['work_item_id'], item['alert_id'], item['work_item_sha256'], item['queue']) != (work_id, alert_id, source_hash, queue):
            raise ValueError(f"Outbox identity mismatch: {alert_id}")
        if status not in ('PENDING_LOCAL_REVIEW', 'VALIDATION_EXCEPTION'):
            raise ValueError('Unexpected local status')
        results.append({**item, 'local_status': status, 'queued_at_utc': created_at})
    return results


def overview(items):
    return {'total': len(items), 'pending_review': sum(x['queue']=='ANALYST_REVIEW' for x in items),
            'exceptions': sum(x['queue']=='VALIDATION_EXCEPTION' for x in items),
            'notifications_sent': 0, 'remediations_executed': 0,
            'by_queue': dict(Counter(x['queue'] for x in items))}


def filter_alerts(items, queue='ALL', query=''):
    q = query.strip().casefold()
    return [x for x in items if (queue == 'ALL' or x['queue'] == queue) and
            (not q or q in x['alert_id'].casefold() or q in x.get('analyst_narrative', '').casefold())]
