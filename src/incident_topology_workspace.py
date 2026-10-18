"""Historical synthetic incident-centred dependency health, never live telemetry."""
import csv
from datetime import datetime, timedelta
from pathlib import Path
import json

STATUS_MAP = {'UP': 'HEALTHY', 'HEALTHY': 'HEALTHY', 'DEGRADED': 'DEGRADED',
              'DOWN': 'DOWN', 'UNAVAILABLE': 'UNAVAILABLE', 'UNKNOWN': 'UNKNOWN'}

def _read(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))

def load_health(root):
    return _read(Path(root) / 'data/raw/service_health_incidents.csv')

def health_at(health_rows, component_ids, window_start, window_end, max_age_minutes=10):
    """Latest observation per component at/before selected historical window end.

    Unknown is mandatory for missing/stale evidence; no extrapolated 'healthy'.
    """
    start = datetime.fromisoformat(window_start)
    end = datetime.fromisoformat(window_end)
    if end < start:
        raise ValueError('Reversed incident monitoring window')
    ids = set(component_ids)
    result = {cid: {'status': 'UNKNOWN', 'timestamp': None, 'availability_pct': None,
                    'health_check_ms': None, 'source_status': None,
                    'evidence': 'No recent synthetic health observation'} for cid in ids}
    latest = {}
    for row in health_rows:
        cid = row.get('component_id')
        if cid not in ids:
            continue
        timestamp = datetime.fromisoformat(row['timestamp'])
        if timestamp > end or end - timestamp > timedelta(minutes=max_age_minutes):
            continue
        status = row.get('status', '').strip().upper()
        if status not in STATUS_MAP:
            raise ValueError('Unsupported health status')
        if cid not in latest or timestamp > latest[cid][0]:
            latest[cid] = (timestamp, row)
    for cid, (ts, row) in latest.items():
        result[cid] = {'status': STATUS_MAP[row['status'].strip().upper()],
                       'source_status': row['status'].strip().upper(), 'timestamp': ts.isoformat(sep=' '),
                       'availability_pct': row.get('availability_pct'),
                       'health_check_ms': row.get('health_check_ms'),
                       'evidence': 'Historical synthetic health check'}
    return result

def incident_dot(service, components, edges, health, suspected_component=None):
    """Evidence-timestamped historical status and declared edges only."""
    if service['service_id'] not in {r['service_id'] for r in edges}:
        raise ValueError('Selected service has no declared dependencies')
    colors = {'HEALTHY':'#dcfce7', 'DEGRADED':'#fef08a', 'DOWN':'#fecaca',
              'UNAVAILABLE':'#fecaca', 'UNKNOWN':'#e5e7eb'}
    lines = ['digraph incident {', 'rankdir=LR;', 'graph [bgcolor="transparent",pad="0.25",nodesep="0.5",ranksep="1.0"];',
             'node [shape=box,style="rounded,filled",fontname="Arial",fontsize=11];',
             f'{json.dumps(service["service_id"])} [label={json.dumps(service["service_name"]+"\\n"+service["service_id"])},fillcolor="#bfdbfe"];']
    component_by_id = {r['component_id']: r for r in components}
    for edge in edges:
        cid = edge['component_id']
        if cid not in component_by_id or cid not in health:
            raise ValueError('Missing catalog or health component')
        state = health[cid]['status']
        label = component_by_id[cid]['component_name'] + '\n' + cid + ' | ' + state
        penwidth = 3 if cid == suspected_component else 1
        lines.append(f'{json.dumps(cid)} [label={json.dumps(label)},fillcolor="{colors[state]}",penwidth={penwidth}];')
        lines.append(f'{json.dumps(service["service_id"])} -> {json.dumps(cid)} [label={json.dumps(edge["dependency_type"])}];')
    return '\n'.join(lines + ['}'])
