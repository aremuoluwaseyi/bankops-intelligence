"""Transparent, deterministic what-if scenarios for a synthetic recruiter demonstration.

No probes, traces, live telemetry, or confirmed incident diagnoses are produced.
"""
from copy import deepcopy

SCENARIOS = {
    'Baseline (recorded snapshot)': None,
    'Simulate dependency degradation': 'DEGRADED',
    'Simulate dependency outage': 'UNAVAILABLE',
    'Simulate recovery': 'HEALTHY',
}


def simulate(snapshot, component_id, scenario):
    if scenario not in SCENARIOS:
        raise ValueError('Unknown simulation scenario')
    if component_id not in snapshot:
        raise ValueError('Component not in the selected dependency map')
    updated = deepcopy(snapshot)
    target = SCENARIOS[scenario]
    if target is not None:
        updated[component_id].update(status=target, timestamp=None,
                                     source_status='SIMULATED', availability_pct=None,
                                     health_check_ms=None,
                                     evidence='What-if scenario only; not an observed health check')
    return updated


def assess(snapshot, suspected_component=None):
    """Summarize visibility and evidence conflicts without claiming causation."""
    if not snapshot:
        raise ValueError('At least one component is required')
    allowed = {'HEALTHY', 'DEGRADED', 'DOWN', 'UNAVAILABLE', 'UNKNOWN'}
    if any(v.get('status') not in allowed for v in snapshot.values()):
        raise ValueError('Unsupported status in snapshot')
    total = len(snapshot)
    observed = [k for k, v in snapshot.items() if v['status'] != 'UNKNOWN' and v.get('source_status') != 'SIMULATED']
    leads = [k for k, v in snapshot.items() if v['status'] in {'DEGRADED', 'DOWN', 'UNAVAILABLE'}]
    conflict = suspected_component in snapshot and snapshot[suspected_component]['status'] == 'HEALTHY'
    return {'total': total, 'observed': len(observed), 'unknown': sum(v['status'] == 'UNKNOWN' for v in snapshot.values()),
            'coverage_pct': round(100 * len(observed) / total, 1), 'unhealthy': leads,
            'suspect_healthy': conflict}
