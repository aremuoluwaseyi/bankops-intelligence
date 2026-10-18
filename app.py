"""BankOps Intelligence: local, read-only analyst dashboard (Phase 10 Step 5).

Run from the project root: streamlit run app.py
"""
from pathlib import Path
import streamlit as st
from src.dashboard_data import load_alerts, overview, filter_alerts
from src.investigation_view import load_investigation_details, match_detail
from src.incident_analytics import build_analytics
from src.dashboard_presentation import read_catalog, display_name, chart_rows
from src.dashboard_drilldown import drilldown_rows, selectable_catalog
import altair as alt
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUTBOX = ROOT / 'data/processed/phase9_step3_alert_outbox.sqlite'
st.set_page_config(page_title='BankOps Intelligence | Analyst Console', page_icon='🏦', layout='wide')
st.title('BankOps Intelligence')
st.caption('NovaTrust Bank • Historical synthetic incident demonstration • Read-only analyst console')
st.warning('Historical synthetic alert windows — NOT live outages. Suspected failure domains are NOT confirmed root causes. Human verification is required. No external notifications or remediation actions are performed.')
@st.cache_data(show_spinner=False, ttl=30)
def cached_alerts(path, modified):
    return load_alerts(path)

@st.cache_data(show_spinner=False, ttl=300)
def cached_details(root):
    return load_investigation_details(root)

@st.cache_data(show_spinner=False, ttl=300)
def cached_catalog(root):
    return read_catalog(root)

try:
    items = cached_alerts(OUTBOX, OUTBOX.stat().st_mtime_ns if OUTBOX.exists() else None)
except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
    st.error(f'Unable to load verified local alerts: {exc}')
    st.info('From the project root, run: python -m src.orchestration.proactive')
    st.stop()

try:
    investigation_details = cached_details(ROOT)
except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
    st.error(f'Investigation evidence unavailable or invalid: {exc}')
    st.stop()

try:
    service_names, component_names = cached_catalog(ROOT)
except (FileNotFoundError, ValueError, OSError) as exc:
    st.error(f'Synthetic service catalog unavailable: {exc}')
    st.stop()

# Widget keys are only updated by callbacks (before widgets instantiate).
# Chart selection events are kept separate and processed exactly once.
from src.dashboard_interaction import chart_selection_action

for key, default in [('drill_service', None), ('drill_domain', None),
                     ('drill_queue', 'ALL'), ('drill_query', ''),
                     ('chart_revision', 0), ('last_service_click', None),
                     ('last_domain_click', None)]:
    if key not in st.session_state:
        st.session_state[key] = default

def reset_chart_selection():
    st.session_state.chart_revision += 1
    st.session_state.last_service_click = None
    st.session_state.last_domain_click = None

def clear_drilldown():
    st.session_state.drill_service = None
    st.session_state.drill_domain = None
    st.session_state.drill_queue = 'ALL'
    st.session_state.drill_query = ''
    st.session_state.pop('pending_chart_service', None)
    st.session_state.pop('pending_chart_domain', None)
    reset_chart_selection()

def select_queue(queue_name):
    clear_drilldown()
    st.session_state.drill_queue = queue_name

def manual_filter_change():
    st.session_state.pop('pending_chart_service', None)
    st.session_state.pop('pending_chart_domain', None)
    # A manual 'All' choice must not be overridden by an old chart event.
    reset_chart_selection()

# Pending events are applied at the beginning of a fresh script run,
# before Streamlit constructs the keyed selectbox widgets.
for pending, widget in [('pending_chart_service', 'drill_service'),
                        ('pending_chart_domain', 'drill_domain')]:
    if pending in st.session_state:
        st.session_state[widget] = st.session_state.pop(pending)

summary = overview(items)
c1, c2, c3, c4 = st.columns(4)
c1.metric('Historical synthetic alerts', summary['total'])
c1.button('View all alerts', on_click=clear_drilldown, use_container_width=True)
c2.metric('Pending local review', summary['pending_review'])
c2.button('View pending review', on_click=select_queue, args=('ANALYST_REVIEW',), use_container_width=True)
c3.metric('Validation exceptions', summary['exceptions'])
c3.button('View exceptions', on_click=select_queue, args=('VALIDATION_EXCEPTION',), use_container_width=True)
c4.metric('External notifications', summary['notifications_sent'])
c4.caption('No external dispatch in this offline demo')
st.divider()
st.subheader('Incident explorer — click a button or chart bar to filter')
st.caption('Click a bar in either chart to filter this queue. You can combine a service with a possible failure domain. Use Clear all filters to reset. Chart selections represent synthetic alert windows, not confirmed root causes.')
services = selectable_catalog(investigation_details, service_names)
domains = sorted({d['proposed_failure_domain'] for d in investigation_details.values() if d.get('proposed_failure_domain')})
filter_a, filter_b, filter_c = st.columns([2, 2, 1])
with filter_a:
    service_choice = st.selectbox('Affected service', [None] + services, key='drill_service', on_change=manual_filter_change, format_func=lambda v: 'All affected services' if v is None else display_name(v, service_names))
with filter_b:
    domain_choice = st.selectbox('Possible failure domain (unconfirmed)', [None] + domains, key='drill_domain', on_change=manual_filter_change, format_func=lambda v: 'All possible domains' if v is None else v)
with filter_c:
    st.write('')
    st.write('')
    st.button('Clear all filters', on_click=clear_drilldown, use_container_width=True)
left, right = st.columns([1, 2])
with left:
    queue = st.selectbox('Queue', ['ALL', 'ANALYST_REVIEW', 'VALIDATION_EXCEPTION'], key='drill_queue')
with right:
    query = st.text_input('Search alert ID or narrative', placeholder='e.g. DB_TIMEOUT', key='drill_query')
try:
    matched = drilldown_rows(items, investigation_details, service_choice, domain_choice, queue, query)
except (ValueError, KeyError) as exc:
    st.error(f'Unable to filter verified incident records: {exc}')
    st.stop()
visible = [item for item, _ in matched]
st.success(f'**Showing {len(visible)} of {len(items)} verified historical alert records** · Queue: {queue} · Service: {display_name(service_choice, service_names) if service_choice else 'All'} · Possible domain: {domain_choice or 'All'}')
if not visible:
    st.info('No matching alerts.')
else:
    table_rows = [{'Alert': x['alert_id'], 'Service': display_name(d['service_id'], service_names) if d else 'Withheld',
                   'Possible failure domain': d['proposed_failure_domain'] if d else 'Withheld',
                   'Monitoring window': d['window_start'] if d else 'Unavailable',
                   'Queue': x['queue'], 'Status': x['local_status'], 'Human review': x['review_state']}
                  for x, d in matched]
    # Selecting a row reruns Streamlit and shows its investigation immediately below.
    table_event = st.dataframe(table_rows, use_container_width=True, hide_index=True,
                               on_select='rerun', selection_mode='single-row',
                               key='incident_table')
    selected_rows = table_event.selection.rows
    alert_ids = [x['alert_id'] for x in visible]
    if selected_rows and 0 <= selected_rows[0] < len(alert_ids):
        selected_id = alert_ids[selected_rows[0]]
        st.caption('Showing the investigation for the selected table row.')
    else:
        selected_id = st.selectbox('Inspect an alert (or click a table row)', alert_ids,
                                   key='incident_detail_selector')
    selected = next(x for x in visible if x['alert_id'] == selected_id)
    st.subheader(f'Incident: {selected_id}')
    st.write('**Current stage:**', selected['current_stage'])
    st.write('**Review state:**', selected['review_state'])
    st.write('**External dispatch:**', selected['dispatch_status'])
    if selected['queue'] == 'VALIDATION_EXCEPTION':
        st.error('Explanation withheld because validation failed. Do not use as diagnostic guidance.')
        st.write('Validation issues:', selected.get('validation_issues', []))
    else:
        try:
            detail = match_detail(selected, investigation_details)
        except ValueError as exc:
            st.error(f'Cannot display unverified investigation evidence: {exc}')
            st.stop()
        st.markdown('#### Investigation evidence drill-down')
        meta1, meta2, meta3 = st.columns(3)
        meta1.metric('Service', detail['service_id'] or 'Unknown')
        st.caption('Service name: ' + display_name(detail['service_id'], service_names))
        meta2.metric('Suspected component', detail['proposed_component_id'] or 'Unresolved')
        st.caption('Component name: ' + display_name(detail['proposed_component_id'], component_names))
        meta3.metric('Evidence observations', len(detail['observed_evidence']))
        st.caption(f"Monitoring window: {detail['window_start']} to {detail['window_end']}")
        st.warning(f"Possible failure domain: {detail['proposed_failure_domain'] or 'Unresolved'}. This is NOT a confirmed root cause.")
        if detail['ambiguity_flag']:
            st.warning('The source investigation marks this hypothesis as ambiguous.')
        evidence_tab, checks_tab, runbooks_tab, gaps_tab = st.tabs(['Observed evidence', 'Diagnostic checks', 'Runbook references', 'Evidence gaps'])
        with evidence_tab:
            if detail['observed_evidence']:
                for observation in detail['observed_evidence']:
                    st.markdown('- ' + observation)
            else:
                st.info('No verified observations available in the source contract.')
        with checks_tab:
            if detail['diagnostic_checks']:
                for number, check in enumerate(detail['diagnostic_checks'], 1):
                    st.write(f'{number}. {check}')
            else:
                st.info('No validated diagnostic checks available. Escalate for human investigation.')
        with runbooks_tab:
            if detail['runbook_citations']:
                for citation in detail['runbook_citations']:
                    st.markdown(f"**{citation.get('document_id', 'Unknown')}** — {citation.get('title', 'Untitled')}")
                    st.caption(f"Source digest: {citation.get('document_sha256', 'Not provided')}")
            else:
                st.info('No validated runbook references available.')
        with gaps_tab:
            if detail['evidence_gaps']:
                for gap in detail['evidence_gaps']:
                    st.markdown('- ' + gap)
            else:
                st.info('No gaps recorded in the source contract. This does not establish complete telemetry.')
        st.markdown('#### Evidence-grounded analyst narrative')
        st.write(selected['analyst_narrative'])
        st.info('This narrative contains observations, a possible failure domain, and suggested diagnostic checks. It does not establish causation.')
    # Integrated historical incident-to-infrastructure workspace.
    if selected['queue'] != 'VALIDATION_EXCEPTION':
        st.markdown('### Incident infrastructure & dependency health')
        st.caption('Historical synthetic observations for the selected monitoring window; not live availability. Gray means unknown, not healthy. Edges are declared dependencies, not observed API traces.')
        from src.dependency_topology import load_topology, related_components
        from src.incident_topology_workspace import load_health, health_at, incident_dot
        @st.cache_data(show_spinner=False, ttl=300)
        def incident_workspace_sources(root):
            return (*load_topology(root), load_health(root))
        try:
            ws_services, ws_components, ws_edges, ws_health_rows = incident_workspace_sources(ROOT)
            ws_service = next((s for s in ws_services if s['service_id'] == detail['service_id']), None)
            if ws_service is None:
                st.info('Selected service is not present in the validated dependency catalog.')
            else:
                ws_links = related_components(detail['service_id'], ws_edges)
                ws_component_ids = [link['component_id'] for link in ws_links]
                ws_health = health_at(ws_health_rows, ws_component_ids, detail['window_start'], detail['window_end'])
                st.graphviz_chart(incident_dot(ws_service, ws_components, ws_links, ws_health, detail['proposed_component_id']), use_container_width=True)
                ws_names = {c['component_id']: c['component_name'] for c in ws_components}
                ws_table = []
                for link in ws_links:
                    cid = link['component_id']
                    observed = ws_health[cid]
                    ws_table.append({'Component': ws_names[cid], 'ID': cid, 'Health at window': observed['status'],
                                     'Source health status': observed['source_status'] or 'Not observed',
                                     'Last observed (synthetic)': observed['timestamp'] or 'No recent observation',
                                     'Availability %': observed['availability_pct'] or 'Not observed',
                                     'Health check ms': observed['health_check_ms'] or 'Not observed',
                                     'Dependency': link['dependency_type'],
                                     'Investigation hypothesis': 'Suspected (unconfirmed)' if cid == detail['proposed_component_id'] else 'Not proposed'})
                st.dataframe(ws_table, hide_index=True, use_container_width=True)
                st.caption('Yellow = degraded, red = unavailable/down, green = observed healthy, gray = unknown. Only evidence recorded within 10 minutes before the incident window end is considered recent.')
                # Phase 10 Step 7: replay historical synthetic health observations only.
                st.markdown('#### Synthetic health-check replay — not live API monitoring')
                st.caption('Advance through recorded synthetic observations for this incident. The diagram updates from historical timestamps; no network probes, live API requests or per-request traces are performed.')
                from src.synthetic_health_replay import prepare_replay, snapshot_at, replay_summary
                from datetime import datetime, timedelta
                replay_begin = datetime.fromisoformat(detail['window_start']) - timedelta(minutes=10)
                replay_end = datetime.fromisoformat(detail['window_end'])
                replay_events = prepare_replay(ws_health_rows, ws_component_ids, replay_begin.isoformat(sep=' '), replay_end.isoformat(sep=' '))
                replay_times = sorted({e['timestamp'] for e in replay_events})
                if not replay_times:
                    st.info('No recorded health-check events for the selected dependencies in this replay interval.')
                else:
                    # Streamlit owns the selector state; changing incidents changes the key.
                    # No background timer or fake live-status animation.
                    replay_index = st.slider('Recorded observation step', 0, len(replay_times) - 1,
                                             len(replay_times) - 1, key='replay_' + selected_id)
                    replay_time = replay_times[replay_index]
                    replay_health = snapshot_at(replay_events, ws_component_ids, replay_time)
                    replay_counts = replay_summary(replay_health)
                    st.write('**Historical observation time:**', replay_time.isoformat(sep=' '))
                    hc1, hc2, hc3, hc4 = st.columns(4)
                    hc1.metric('Healthy', replay_counts['healthy'])
                    hc2.metric('Degraded', replay_counts['degraded'])
                    hc3.metric('Unavailable', replay_counts['unavailable'])
                    hc4.metric('Unknown / not observed', replay_counts['unknown'])
                    st.graphviz_chart(incident_dot(ws_service, ws_components, ws_links, replay_health,
                                                   detail['proposed_component_id']), use_container_width=True)
                    st.dataframe([{'Component': ws_names[cid], 'ID': cid,
                                   'Observed status': replay_health[cid]['status'],
                                   'Original source status': replay_health[cid]['source_status'] or 'Not observed',
                                   'Last recorded': replay_health[cid]['timestamp'] or 'No recent observation',
                                   'Availability %': replay_health[cid]['availability_pct'],
                                   'Check latency (ms)': replay_health[cid]['health_check_ms']}
                                  for cid in ws_component_ids], hide_index=True, use_container_width=True)
                    st.caption('The selected time is historical. A red or yellow component is a diagnostic lead, not a verified root cause. Connections represent declared dependencies, not actual request traces.')

                st.info('A degraded dependency is an investigation pointer, not proof of causation. Synthetic source data has no correlated per-request API trace; connection arrows must not be interpreted as measured traffic.')
        except (FileNotFoundError, ValueError, KeyError, TypeError, OSError) as exc:
            st.error(f'Incident infrastructure view unavailable: {exc}')

    with st.expander('Audit and provenance identifiers'):
        st.json({k: selected.get(k) for k in ('work_item_id', 'work_item_sha256',
                'source_handoff_sha256', 'narrative_sha256', 'workflow_stages')})

st.subheader('Incident analytics — click a chart bar to filter the incident explorer above')
st.caption('Each count is a detected monitoring-window alert, not a unique outage. Suspected domains are hypotheses, not confirmed causes.')
try:
    analytics = build_analytics(items, investigation_details)
    charts = chart_rows(analytics, service_names, component_names)
except (ValueError, KeyError, TypeError) as exc:
    st.error(f'Unable to produce source-verified analytics: {exc}')
    st.stop()
a1, a2, a3, a4 = st.columns(4)
a1.metric('Detected alert windows', analytics['total_alert_windows'])
a2.metric('Recorded observations', analytics['observations_in_contracts'])
a3.metric('Alerts with evidence gaps', analytics['alerts_with_recorded_gaps'])
a4.metric('Ambiguous hypotheses', analytics['ambiguous_hypotheses'])
st.caption('Charts count historical synthetic alert windows; they do not show active incidents, affected customers, or confirmed root causes.')
chart1, chart2 = st.columns(2)
with chart1:
    st.markdown('**Alerts by affected service**')
    if charts['services']:
        df = pd.DataFrame(charts['services'])
        graph = alt.Chart(df).mark_bar().encode(
            x=alt.X('Alert windows:Q', title='Detected alert windows'),
            y=alt.Y('Service:N', sort='-x', title=None, axis=alt.Axis(labelLimit=300)),
            tooltip=['Service:N', 'Alert windows:Q']).properties(height=max(220, 34 * len(df)))
        event = st.altair_chart(graph.add_params(alt.selection_point(name='service_click', fields=['Service'], on='click')), use_container_width=True, on_select='rerun', key=f'service_bar_{st.session_state.chart_revision}')
        picked = event.selection.get('service_click', [])
        chosen = picked[0].get('Service') if picked else None
        service_lookup = {display_name(k, service_names): k for k in service_names}
        selected_service = service_lookup.get(chosen)
        action = chart_selection_action(selected_service, st.session_state.last_service_click,
                                        st.session_state.drill_service)
        if action == 'apply':
            st.session_state.last_service_click = selected_service
            # Update widget state on the next run, before the widget exists.
            st.session_state.pending_chart_service = selected_service
            st.rerun()
    else:
        st.info('No verified alerts to plot.')
with chart2:
    st.markdown('**Alerts by possible failure domain (unconfirmed)**')
    if charts['domains']:
        df = pd.DataFrame(charts['domains'])
        graph = alt.Chart(df).mark_bar().encode(
            x=alt.X('Alert windows:Q', title='Detected alert windows'),
            y=alt.Y('Possible failure domain:N', sort='-x', title=None, axis=alt.Axis(labelLimit=320)),
            tooltip=['Possible failure domain:N', 'Alert windows:Q']).properties(height=max(220, 34 * len(df)))
        event = st.altair_chart(graph.add_params(alt.selection_point(name='domain_click', fields=['Possible failure domain'], on='click')), use_container_width=True, on_select='rerun', key=f'domain_bar_{st.session_state.chart_revision}')
        picked = event.selection.get('domain_click', [])
        chosen = picked[0].get('Possible failure domain') if picked else None
        action = chart_selection_action(chosen, st.session_state.last_domain_click,
                                        st.session_state.drill_domain)
        if action == 'apply':
            st.session_state.last_domain_click = chosen
            st.session_state.pending_chart_domain = chosen
            st.rerun()
    else:
        st.info('No verified alerts to plot.')
st.markdown('**Historical synthetic alert windows by hour**')
if charts['hourly']:
    df = pd.DataFrame(charts['hourly'])
    graph = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X('Hour:N', title='Monitoring hour (synthetic dataset)', axis=alt.Axis(labelAngle=-35, labelLimit=125)),
        y=alt.Y('Alert windows:Q', title='Detected alert windows'),
        tooltip=['Hour:N', 'Alert windows:Q']).properties(height=260)
    st.altair_chart(graph, use_container_width=True)
else:
    st.info('No verified time-series observations.')
with st.expander('View analytics source counts'):
    st.dataframe(charts['components'], hide_index=True, use_container_width=True)
    st.caption(f"Alerts with runbook references: {analytics['alerts_with_runbook_references']}. These are deterministic references, not independently confirmed solutions.")
st.divider()
st.caption('Source: historical synthetic telemetry and local SQLite outbox from the Phase 9 offline pipeline. Queue timestamps indicate local processing, not current outage status. The dashboard does not edit alerts, approve investigations, or connect to a live bank.')


st.divider()
st.header('Service Dependency & Infrastructure Intelligence')
st.caption('Documented synthetic architecture only. Connections show declared dependencies, not live network traffic, current health, or confirmed causes. Select a service or component to inspect its relationships.')
from src.dependency_topology import load_topology, related_components, dependent_services, topology_dot

@st.cache_data(show_spinner=False, ttl=300)
def cached_topology(root):
    return load_topology(root)

try:
    topology_services, topology_components, topology_edges = cached_topology(ROOT)
    topology_service_names = {row['service_id']: row['service_name'] for row in topology_services}
    topology_component_names = {row['component_id']: row['component_name'] for row in topology_components}
    topology_left, topology_right = st.columns(2)
    with topology_left:
        focus_service = st.selectbox('Focus on a banking service', [None] + list(topology_service_names),
                                     format_func=lambda value: 'All services' if value is None else display_name(value, topology_service_names),
                                     key='topology_service')
    with topology_right:
        focus_component = st.selectbox('Focus on an infrastructure component or API', [None] + list(topology_component_names),
                                       format_func=lambda value: 'All components' if value is None else display_name(value, topology_component_names),
                                       key='topology_component')
    st.graphviz_chart(topology_dot(topology_services, topology_components, topology_edges,
                                   focus_service, focus_component), use_container_width=True)
    t1, t2, t3 = st.columns(3)
    t1.metric('Cataloged banking services', len(topology_services))
    t2.metric('Cataloged infrastructure components', len(topology_components))
    t3.metric('Declared dependency links', len(topology_edges))
    if focus_service:
        st.subheader('Components required by ' + display_name(focus_service, topology_service_names))
        st.dataframe([{'Component': display_name(r['component_id'], topology_component_names),
                       'Dependency': r['dependency_type'], 'Catalog criticality': r['criticality']}
                      for r in related_components(focus_service, topology_edges)],
                     hide_index=True, use_container_width=True)
    if focus_component:
        st.subheader('Services depending on ' + display_name(focus_component, topology_component_names))
        st.dataframe([{'Service': display_name(r['service_id'], topology_service_names),
                       'Dependency': r['dependency_type'], 'Catalog criticality': r['criticality']}
                      for r in dependent_services(focus_component, topology_edges)],
                     hide_index=True, use_container_width=True)
        associated = [(item, detail) for item, detail in matched
                      if detail and detail.get('proposed_component_id') == focus_component]
        st.caption(f'{len(associated)} matching alert windows in the CURRENT Incident Explorer filters propose this component; these are hypotheses, not verified faults.')
        if associated:
            st.dataframe([{'Alert': item['alert_id'], 'Service': display_name(detail['service_id'], topology_service_names),
                           'Possible failure domain': detail['proposed_failure_domain']}
                          for item, detail in associated], hide_index=True, use_container_width=True)
    st.info('Component status is not shown as Healthy/Degraded/Down: this phase provides catalog-backed topology only. API tracing and evidence-timestamped health indicators are planned for Step 7.')
except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
    st.error(f'Synthetic topology unavailable or invalid: {exc}')
