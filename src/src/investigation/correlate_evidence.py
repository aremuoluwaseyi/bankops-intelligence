"""Phase 6 Step 2: explainable evidence correlation, no scenario labels or LLM.

Scores are heuristic investigation priorities, not probabilities or confirmed causes.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'data/processed/phase6_step1_evidence_packages.jsonl'
OUTPUT = ROOT / 'data/processed/phase6_step2_correlated_evidence.jsonl'


def correlate(package):
    dependencies = {r['component_id']: r for r in package.get('dependencies', [])}
    scores = defaultdict(int)
    reasons = defaultdict(list)
    evidence = defaultdict(set)

    for row in package.get('application_log_patterns', []):
        cid = row.get('component_id')
        if cid not in dependencies:
            continue
        count = int(row.get('count') or 0)
        if row.get('log_level') == 'ERROR' and count:
            points = 4 if count >= 3 else 2
            scores[cid] += points
            reasons[cid].append(f"{count} ERROR log(s), code {row.get('error_code') or 'unspecified'}")
            evidence[cid].add('error_logs')
        elif row.get('log_level') == 'WARN' and count >= 3:
            scores[cid] += 1
            reasons[cid].append(f'{count} WARN log(s)')
            evidence[cid].add('warning_logs')

    for row in package.get('component_health', []):
        cid = row.get('component_id')
        if cid not in dependencies:
            continue
        if row.get('status') in ('DEGRADED', 'DOWN'):
            scores[cid] += 3
            reasons[cid].append(f"Health observed as {row['status']}")
            evidence[cid].add('component_health')

    for row in package.get('component_metrics', []):
        cid = row.get('component_id')
        if cid not in dependencies:
            continue
        if 'latency' in str(row.get('metric_name', '')).lower() and float(row.get('max_value') or 0) >= 1500:
            scores[cid] += 2
            reasons[cid].append(f"Observed {row['metric_name']} maximum {row['max_value']} {row.get('unit', '')}".strip())
            evidence[cid].add('component_metrics')

    for row in package.get('recent_changes_30min', []):
        cid = row.get('component_id')
        if cid in dependencies:
            scores[cid] += 1
            reasons[cid].append(f"Recent {row.get('change_type', 'change')} event (temporal association only)")
            evidence[cid].add('recent_change')

    candidates = []
    for cid, score in scores.items():
        if score <= 0:
            continue
        component = dependencies[cid]
        candidates.append({
            'component_id': cid,
            'component_name': component['component_name'],
            'component_type': component.get('component_type'),
            'priority_score': score,
            'independent_evidence_types': len(evidence[cid]),
            'evidence_types': sorted(evidence[cid]),
            'supporting_observations': reasons[cid],
        })
    candidates.sort(key=lambda c: (-c['priority_score'], -c['independent_evidence_types'], c['component_id']))
    winner = candidates[0] if candidates else None
    # Never turn one weak signal into a definitive root cause.
    supported = bool(winner and winner['priority_score'] >= 4 and winner['independent_evidence_types'] >= 2)
    output = {
        'alert_id': package['alert_id'],
        'monitoring_window_id': package['monitoring_window_id'],
        'service_id': package['service_id'],
        'window_start': package['window_start'],
        'window_end': package['window_end'],
        'likely_failure_domain': winner['component_name'] if supported else 'UNDETERMINED',
        'likely_component_id': winner['component_id'] if supported else None,
        'evidence_strength': 'MULTI_SOURCE' if supported else 'INSUFFICIENT',
        'ranked_candidates': candidates,
        'root_cause_confirmed': False,
        'human_verification_required': True,
        'limitations': [
            'Scores are heuristic priorities, not calibrated probabilities.',
            'Missing telemetry does not establish component health.',
            'A recent change is correlation, not proof of causation.',
            'Shared component evidence may include other services and needs verification.',
        ],
    }
    return output


def run(input_path=INPUT, output_path=OUTPUT):
    input_path, output_path = Path(input_path), Path(output_path)
    results = [correlate(json.loads(line)) for line in input_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in results), encoding='utf-8')
    return results


if __name__ == '__main__':
    results = run()
    print(f'Correlated {len(results)} alerts; {sum(r["likely_component_id"] is not None for r in results)} have multi-source candidates')
