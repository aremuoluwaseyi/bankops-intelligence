"""Phase 10 Step 4: display-only helpers grounded in the synthetic service catalog.

Do not infer active outages or confirmed root causes from review-queue counts.
"""
import csv
from datetime import datetime
from pathlib import Path


def read_catalog(root):
    base = Path(root) / 'data' / 'raw'
    def load(filename, key, label):
        result = {}
        with (base / filename).open(newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                identifier, name = row.get(key), row.get(label)
                if not identifier or not name or identifier in result:
                    raise ValueError(f'Invalid or duplicate catalog entry in {filename}')
                result[identifier] = name
        return result
    return load('services.csv', 'service_id', 'service_name'), load('components.csv', 'component_id', 'component_name')


def display_name(identifier, catalog):
    if not identifier:
        return 'Unresolved'
    return f'{catalog[identifier]} ({identifier})' if identifier in catalog else f'Unknown catalog ID ({identifier})'


def readable_hour(iso_hour):
    return datetime.strptime(iso_hour, '%Y-%m-%d %H:%M').strftime('%b %d, %H:%M')


def chart_rows(analytics, service_names, component_names):
    services = [{'Service': display_name(row['Service'], service_names), 'Alert windows': row['Alert windows']}
                for row in analytics['service_counts']]
    components = [{'Component': display_name(row['Suspected component'], component_names), 'Alert windows': row['Alert windows']}
                  for row in analytics['component_counts']]
    domains = [{'Possible failure domain': row['Suspected failure domain'], 'Alert windows': row['Alert windows']}
               for row in analytics['domain_counts']]
    hourly = [{'Hour': readable_hour(row['Hour']), 'Alert windows': row['Alert windows']}
              for row in analytics['hourly_counts']]
    for collection in (services, components, domains, hourly):
        if any(not isinstance(r['Alert windows'], int) or r['Alert windows'] < 0 for r in collection):
            raise ValueError('Invalid alert count for chart')
    if sum(row['Alert windows'] for row in services) != analytics['total_alert_windows']:
        raise ValueError('Service counts do not reconcile to validated alert total')
    if sum(row['Alert windows'] for row in domains) != analytics['total_alert_windows']:
        raise ValueError('Domain counts do not reconcile to validated alert total')
    if sum(row['Alert windows'] for row in hourly) != analytics['total_alert_windows']:
        raise ValueError('Hourly counts do not reconcile to validated alert total')
    return {'services': services, 'components': components, 'domains': domains, 'hourly': hourly}
