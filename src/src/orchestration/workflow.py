"""Phase 9 Step 1: deterministic, fail-closed analyst work queue.

No live scheduler, outgoing notification, LLM or automatic remediation.
"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def create_work_item(handoff):
    if not isinstance(handoff, dict) or not isinstance(handoff.get('alert_id'), str) or not handoff['alert_id']:
        raise ValueError('Invalid handoff or alert ID')
    if handoff.get('handoff_sha256') != digest({k: v for k, v in handoff.items() if k != 'handoff_sha256'}):
        raise ValueError('Handoff integrity failure')
    if (handoff.get('human_verification_required') is not True or
        handoff.get('root_cause_confirmed') is not False or
        handoff.get('automated_remediation_allowed') is not False or
        handoff.get('review_state') != 'PENDING_HUMAN_REVIEW'):
        raise ValueError('Unsafe or unexpected review policy')
    status = handoff.get('delivery_status')
    if status not in ('READY_FOR_ANALYST_REVIEW', 'WITHHELD_VALIDATION_FAILED'):
        raise ValueError('Unknown handoff status')
    ready = status == 'READY_FOR_ANALYST_REVIEW'
    if ready and (not handoff.get('analyst_narrative') or not handoff.get('narrative_sha256')):
        raise ValueError('Ready handoff has missing narrative')
    if not ready and (handoff.get('analyst_narrative') is not None or not handoff.get('validation_issues')):
        raise ValueError('Unsafe withheld handoff')
    item = {
        'schema_version': '1.0',
        'work_item_id': 'WORK-' + digest({'alert_id': handoff['alert_id']})[:16],
        'alert_id': handoff['alert_id'],
        'workflow_stages': ['MONITOR', 'DETECT', 'INVESTIGATE', 'RETRIEVE', 'EXPLAIN', 'ALERT', 'VERIFY'],
        'current_stage': 'ALERT' if ready else 'EXCEPTION_REVIEW',
        'queue': 'ANALYST_REVIEW' if ready else 'VALIDATION_EXCEPTION',
        'dispatch_status': 'QUEUED_NOT_SENT',
        'review_state': 'PENDING_HUMAN_REVIEW',
        'root_cause_confirmed': False,
        'automated_remediation_allowed': False,
        'source_handoff_sha256': handoff['handoff_sha256'],
        'narrative_sha256': handoff.get('narrative_sha256') if ready else None,
        'analyst_narrative': handoff.get('analyst_narrative') if ready else None,
        'validation_issues': handoff.get('validation_issues', []),
    }
    item['work_item_sha256'] = digest(item)
    return item


def build_queue(handoffs):
    items = [create_work_item(h) for h in handoffs]
    ids = [i['alert_id'] for i in items]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate alert IDs')
    return sorted(items, key=lambda i: i['alert_id'])


def run(source, output, summary):
    handoffs = [json.loads(line) for line in Path(source).read_text(encoding='utf-8').splitlines() if line.strip()]
    items = build_queue(handoffs)
    Path(output).write_text(''.join(json.dumps(item, sort_keys=True) + '\n' for item in items), encoding='utf-8')
    result = {'total': len(items),
              'queued_for_analyst_review': sum(i['queue'] == 'ANALYST_REVIEW' for i in items),
              'validation_exceptions': sum(i['queue'] == 'VALIDATION_EXCEPTION' for i in items),
              'external_notifications_sent': 0, 'automated_remediations': 0,
              'scope': 'Offline workflow design and analyst work-queue creation only; scheduling and notification integration are not implemented.'}
    Path(summary).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', default='data/processed/phase8_step4_review_handoffs.jsonl')
    p.add_argument('--output', default='data/processed/phase9_step1_work_queue.jsonl')
    p.add_argument('--summary', default='data/processed/phase9_step1_summary.json')
    a = p.parse_args()
    print(json.dumps(run(a.source, a.output, a.summary), indent=2))
