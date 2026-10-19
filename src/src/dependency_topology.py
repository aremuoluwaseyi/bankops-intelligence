"""Read-only, catalog-validated synthetic banking dependency graph."""
import csv
from pathlib import Path

ALLOWED_TYPES = {'Direct', 'External', 'Data'}

def load_topology(root):
    base = Path(root) / 'data/raw'
    def rows(name):
        with (base / name).open(encoding='utf-8-sig', newline='') as handle:
            return list(csv.DictReader(handle))
    services = rows('services.csv')
    components = rows('components.csv')
    dependencies = rows('service_dependencies.csv')
    service_ids = {r['service_id'] for r in services}
    component_ids = {r['component_id'] for r in components}
    if len(service_ids) != len(services) or len(component_ids) != len(components) or not services or not components:
        raise ValueError('Duplicate or missing service/component catalog entries')
    seen = set()
    for row in dependencies:
        if (not row['dependency_id'] or row['dependency_id'] in seen
            or row['service_id'] not in service_ids
            or row['component_id'] not in component_ids
            or row['dependency_type'] not in ALLOWED_TYPES):
            raise ValueError('Invalid, duplicate, or unknown synthetic dependency')
        seen.add(row['dependency_id'])
    return services, components, dependencies

def related_components(service_id, dependencies):
    return [r for r in dependencies if r['service_id'] == service_id]

def dependent_services(component_id, dependencies):
    return [r for r in dependencies if r['component_id'] == component_id]

def topology_dot(services, components, dependencies, selected_service=None, selected_component=None):
    """DOT uses fixed validated IDs as node names, quoted labels as text."""
    if selected_service is not None and selected_service not in {r['service_id'] for r in services}:
        raise ValueError('Unknown selected service')
    if selected_component is not None and selected_component not in {r['component_id'] for r in components}:
        raise ValueError('Unknown selected component')
    import json
    lines = ['digraph topology {', 'rankdir=LR;', 'graph [bgcolor="transparent", pad="0.3", nodesep="0.4", ranksep="1.0"];',
             'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11, color="#cbd5e1", fillcolor="#f8fafc"];',
             'edge [color="#64748b", arrowsize=0.65];']
    for row in services:
        sid = row['service_id']
        selected = sid == selected_service
        lines.append(f'{json.dumps(sid)} [label={json.dumps(row["service_name"] + "\n" + sid)}, fillcolor="{ "#bfdbfe" if selected else "#e0f2fe"}", shape=box];')
    for row in components:
        cid = row['component_id']
        selected = cid == selected_component
        lines.append(f'{json.dumps(cid)} [label={json.dumps(row["component_name"] + "\n" + cid)}, fillcolor="{ "#fde68a" if selected else "#f1f5f9"}"];')
    for row in dependencies:
        focused = (selected_service is None or row['service_id'] == selected_service) and (selected_component is None or row['component_id'] == selected_component)
        lines.append(f'{json.dumps(row["service_id"])} -> {json.dumps(row["component_id"])} [label={json.dumps(row["dependency_type"])}, color="{ "#2563eb" if focused else "#cbd5e1"}", penwidth={2.2 if focused else 1.0}];')
    return '\n'.join(lines + ['}'])


def compact_topology_dot(services, components, dependencies, selected_service=None, selected_component=None):
    """Only selected neighborhood, or a compact service inventory when no focus is selected."""
    import json
    service_by_id = {s['service_id']: s for s in services}
    component_by_id = {c['component_id']: c for c in components}
    if selected_service is not None and selected_service not in service_by_id:
        raise ValueError('Unknown service')
    if selected_component is not None and selected_component not in component_by_id:
        raise ValueError('Unknown component')
    if selected_service is None and selected_component is None:
        lines = ['digraph inventory {', 'rankdir=LR;', 'graph [bgcolor="transparent",nodesep="0.2",ranksep="0.35"];',
                 'node [shape=box,style="rounded,filled",fillcolor="#e0f2fe",fontname="Arial"];']
        for s in services:
            lines.append(f'{json.dumps(s["service_id"])} [label={json.dumps(s["service_name"] + chr(10) + s["service_id"])}];')
        return '\n'.join(lines + ['}'])
    filtered = [d for d in dependencies if (selected_service is None or d['service_id'] == selected_service)
                and (selected_component is None or d['component_id'] == selected_component)]
    if not filtered:
        raise ValueError('No declared relationship for combined filters')
    used_services = {d['service_id'] for d in filtered}
    used_components = {d['component_id'] for d in filtered}
    return topology_dot([s for s in services if s['service_id'] in used_services],
                        [c for c in components if c['component_id'] in used_components], filtered,
                        selected_service, selected_component)
