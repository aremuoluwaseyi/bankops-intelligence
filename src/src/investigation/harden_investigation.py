"""Phase 6 Step 4: cautious, auditable investigation handoff.

This layer consumes the Phase 6 Step 1 evidence package and Phase 6 Step 2
correlation logic. It never accesses synthetic incident ground truth.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from src.investigation.correlate_evidence import correlate

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'data/processed/phase6_step1_evidence_packages.jsonl'
OUTPUT = ROOT / 'data/processed/phase6_step4_investigation_handoff.jsonl'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def harden(package):
    """Build a traceable, conservative decision without modifying source evidence."""
    required = ('alert_id', 'monitoring_window_id', 'service_id', 'window_start', 'window_end')
    missing = [key for key in required if not package.get(key)]
    if missing:
        raise ValueError('Evidence package missing identifiers: ' + ', '.join(missing))
    correlated = correlate(package)
    candidates = correlated['ranked_candidates']
    coverage = package.get('source_coverage') or {}
    technical_keys = ('application_log_patterns', 'component_health', 'component_metrics')
    available = {key: bool(package.get(key)) for key in technical_keys}
    available['recent_changes_30min'] = bool(package.get('recent_changes_30min'))
    available['transactions'] = bool(package.get('transactions'))
    available['dependencies'] = bool(package.get('dependencies'))
    evidence_gaps = [key for key in technical_keys if not available[key]]

    winner = candidates[0] if candidates else None
    runner_up = candidates[1] if len(candidates) > 1 else None
    ambiguous = bool(winner and runner_up and
                     winner['priority_score'] - runner_up['priority_score'] <= 1)
    multi_source = bool(winner and winner['independent_evidence_types'] >= 2 and
                        winner['priority_score'] >= 4)
    # Log or metric evidence is necessary; a change event and health alone are not enough.
    direct_technical = bool(winner and
                            set(winner['evidence_types']) & {'error_logs', 'component_metrics'})
    qualified = multi_source and direct_technical and not ambiguous
    if not winner:
        status = 'INSUFFICIENT_EVIDENCE'
    elif ambiguous:
        status = 'AMBIGUOUS_REQUIRES_REVIEW'
    elif not qualified:
        status = 'INSUFFICIENT_EVIDENCE'
    else:
        status = 'CANDIDATE_REQUIRES_VERIFICATION'

    trace = []
    for candidate in candidates:
        trace.append({
            'component_id': candidate['component_id'],
            'priority_score': candidate['priority_score'],
            'evidence_types': candidate['evidence_types'],
            'observations': candidate['supporting_observations'],
        })
    handoff = {
        'schema_version': '1.0',
        'alert_id': package['alert_id'],
        'monitoring_window_id': package['monitoring_window_id'],
        'service_id': package['service_id'],
        'window_start': package['window_start'],
        'window_end': package['window_end'],
        'decision_status': status,
        'proposed_component_id': winner['component_id'] if qualified else None,
        'proposed_failure_domain': winner['component_name'] if qualified else 'UNDETERMINED',
        'top_candidate_for_review': winner['component_id'] if winner else None,
        'ranked_candidates': candidates,
        'evidence_trace': trace,
        'evidence_availability': available,
        'evidence_gaps': evidence_gaps,
        'source_coverage': coverage,
        'ambiguity': {'flag': ambiguous, 'runner_up_component_id': runner_up['component_id'] if runner_up else None,
                      'score_margin': winner['priority_score'] - runner_up['priority_score'] if runner_up else None},
        'evidence_package_sha256': digest(package),
        'correlation_result_sha256': digest(correlated),
        'root_cause_confirmed': False,
        'human_verification_required': True,
        'knowledge_retrieval_ready': qualified,
        'cautions': [
            'Priority scores are heuristics, not probabilities.',
            'No observed telemetry does not mean the component is healthy.',
            'Deployment timing alone does not prove causation.',
            'A proposed failure domain is not a confirmed root cause.',
        ],
    }
    handoff['handoff_sha256'] = digest(handoff)
    return handoff


def run(input_path=INPUT, output_path=OUTPUT):
    input_path, output_path = Path(input_path), Path(output_path)
    seen = set()
    results = []
    for line_no, line in enumerate(input_path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        package = json.loads(line)
        if package.get('alert_id') in seen:
            raise ValueError(f'Duplicate alert_id on line {line_no}')
        seen.add(package.get('alert_id'))
        results.append(harden(package))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(''.join(canonical(r) + '\n' for r in results), encoding='utf-8')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=INPUT)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    rows = run(args.input, args.output)
    from collections import Counter
    print(f'Processed {len(rows)} alerts; status distribution: {dict(Counter(r["decision_status"] for r in rows))}')
