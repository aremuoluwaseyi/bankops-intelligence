"""Phase 10 Step 3: read-only incident analytics from verified source contracts.

Counts represent detected alert windows in synthetic data, not unique outages.
No inferred severity, causation, incident duration or production performance.
"""
from collections import Counter
from datetime import datetime


def _parse_time(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Missing monitoring window timestamp')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid monitoring window timestamp') from exc


def build_analytics(items, details):
    """Only count alerts matched to integrity-verified investigation details."""
    if not isinstance(items, list) or not isinstance(details, dict):
        raise ValueError('Invalid analytics input')
    seen = set()
    by_service, by_domain, by_day, by_hour, by_component = (Counter() for _ in range(5))
    evidence_total = 0
    gap_alerts = 0
    ambiguous = 0
    runbook_alerts = 0
    reviewed = 0
    for item in items:
        if item['queue'] != 'ANALYST_REVIEW':
            continue
        aid = item['alert_id']
        if aid in seen:
            raise ValueError('Duplicate alert in analytics input')
        seen.add(aid)
        detail = details.get(aid)
        if not detail:
            raise ValueError('Verified investigation details missing: ' + aid)
        if detail['alert_id'] != aid or detail['narrative_sha256'] != item['narrative_sha256'] or detail['narrative'] != item['analyst_narrative']:
            raise ValueError('Alert and verified investigation do not match: ' + aid)
        if detail['human_verification_required'] is not True or detail['root_cause_confirmed'] is not False:
            raise ValueError('Unsafe source investigation status')
        when = _parse_time(detail['window_start'])
        by_service[detail.get('service_id') or 'Unknown'] += 1
        by_domain[detail.get('proposed_failure_domain') or 'Unresolved'] += 1
        by_component[detail.get('proposed_component_id') or 'Unresolved'] += 1
        by_day[when.strftime('%Y-%m-%d')] += 1
        by_hour[when.strftime('%Y-%m-%d %H:00')] += 1
        evidence_total += len(detail['observed_evidence'])
        gap_alerts += bool(detail['evidence_gaps'])
        ambiguous += bool(detail['ambiguity_flag'])
        runbook_alerts += bool(detail['runbook_citations'])
        reviewed += 1
    def rows(counter, key):
        return [{key: name, 'Alert windows': count} for name, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {
        'total_alert_windows': reviewed,
        'observations_in_contracts': evidence_total,
        'alerts_with_recorded_gaps': gap_alerts,
        'ambiguous_hypotheses': ambiguous,
        'alerts_with_runbook_references': runbook_alerts,
        'service_counts': rows(by_service, 'Service'),
        'domain_counts': rows(by_domain, 'Suspected failure domain'),
        'component_counts': rows(by_component, 'Suspected component'),
        'daily_counts': sorted(rows(by_day, 'Day'), key=lambda x: x['Day']),
        'hourly_counts': sorted(rows(by_hour, 'Hour'), key=lambda x: x['Hour']),
    }
