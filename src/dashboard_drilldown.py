"""Phase 10 Step 5: verified, read-only cross-filtering of synthetic alerts."""
from src.investigation_view import match_detail


def drilldown_rows(items, details, service=None, domain=None, queue='ALL', query=''):
    """Return matched alert/detail pairs; never infer incident causes from filters."""
    if not isinstance(items, list) or not isinstance(details, dict):
        raise ValueError('Invalid drill-down sources')
    if queue not in ('ALL', 'ANALYST_REVIEW', 'VALIDATION_EXCEPTION'):
        raise ValueError('Invalid queue selection')
    if not isinstance(query, str):
        raise ValueError('Invalid search query')
    known_services = {d['service_id'] for d in details.values() if d.get('service_id')}
    known_domains = {d['proposed_failure_domain'] for d in details.values() if d.get('proposed_failure_domain')}
    if service is not None and service not in known_services:
        raise ValueError('Unknown service filter')
    if domain is not None and domain not in known_domains:
        raise ValueError('Unknown possible failure-domain filter')
    result = []
    seen = set()
    for item in items:
        aid = item['alert_id']
        if aid in seen:
            raise ValueError('Duplicate alert ID in drill-down')
        seen.add(aid)
        if queue != 'ALL' and item['queue'] != queue:
            continue
        if query.strip() and query.casefold().strip() not in (aid + ' ' + item.get('analyst_narrative', '')).casefold():
            continue
        detail = match_detail(item, details)
        if (service is not None or domain is not None) and detail is None:
            continue
        if service is not None and detail['service_id'] != service:
            continue
        if domain is not None and detail['proposed_failure_domain'] != domain:
            continue
        result.append((item, detail))
    return result


def selectable_catalog(details, service_names):
    """Use only service IDs present in verified contracts and the real catalog."""
    ids = {d['service_id'] for d in details.values() if d.get('service_id')}
    if not ids.issubset(service_names):
        raise ValueError('Unknown service ID in verified details')
    return sorted(ids, key=lambda sid: (service_names[sid], sid))
