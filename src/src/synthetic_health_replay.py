"""Deterministic, offline replay of recorded synthetic component health checks.

No live network calls, no invented API traces, no inference of root cause.
"""
from datetime import datetime, timedelta
from collections import defaultdict

VALID = {'UP', 'HEALTHY', 'DEGRADED', 'DOWN', 'UNAVAILABLE', 'UNKNOWN'}
DISPLAY = {'UP':'HEALTHY', 'HEALTHY':'HEALTHY', 'DEGRADED':'DEGRADED',
           'DOWN':'DOWN', 'UNAVAILABLE':'UNAVAILABLE', 'UNKNOWN':'UNKNOWN'}

def prepare_replay(rows, component_ids, start, end):
    """Return timestamped records for the selected service, in inclusive interval."""
    begin, finish = datetime.fromisoformat(start), datetime.fromisoformat(end)
    if finish < begin:
        raise ValueError('Reversed replay interval')
    ids = set(component_ids)
    if not ids:
        raise ValueError('Replay needs at least one declared component')
    result = []
    seen = set()
    for row in rows:
        if row.get('component_id') not in ids:
            continue
        timestamp = datetime.fromisoformat(row['timestamp'])
        if not begin <= timestamp <= finish:
            continue
        state = row.get('status', '').strip().upper()
        if state not in VALID:
            raise ValueError('Unsupported replay status')
        key = (row['component_id'], timestamp)
        if key in seen:
            raise ValueError('Duplicate component timestamp in replay')
        seen.add(key)
        result.append({'component_id': row['component_id'], 'timestamp': timestamp,
                       'status': DISPLAY[state], 'source_status': state,
                       'availability_pct': row.get('availability_pct'),
                       'health_check_ms': row.get('health_check_ms')})
    return sorted(result, key=lambda x: (x['timestamp'], x['component_id']))

def snapshot_at(events, component_ids, at, max_age_minutes=10):
    """Use only previously observed, fresh events. Never forward-fill stale health."""
    moment = datetime.fromisoformat(at) if isinstance(at, str) else at
    if max_age_minutes < 0:
        raise ValueError('max_age_minutes cannot be negative')
    state = {cid: {'status': 'UNKNOWN', 'timestamp': None, 'source_status': None,
                   'availability_pct': None, 'health_check_ms': None} for cid in component_ids}
    for event in events:
        cid = event['component_id']
        if cid not in state or event['timestamp'] > moment:
            continue
        if moment - event['timestamp'] > timedelta(minutes=max_age_minutes):
            continue
        previous = state[cid]['timestamp']
        if previous is None or event['timestamp'] >= datetime.fromisoformat(previous):
            state[cid] = {'status': event['status'], 'timestamp': event['timestamp'].isoformat(sep=' '),
                          'source_status': event['source_status'],
                          'availability_pct': event['availability_pct'],
                          'health_check_ms': event['health_check_ms']}
    return state

def replay_summary(snapshot):
    counts = defaultdict(int)
    for record in snapshot.values():
        counts[record['status']] += 1
    return {'total': len(snapshot), 'healthy': counts['HEALTHY'],
            'degraded': counts['DEGRADED'], 'unavailable': counts['DOWN'] + counts['UNAVAILABLE'],
            'unknown': counts['UNKNOWN']}
