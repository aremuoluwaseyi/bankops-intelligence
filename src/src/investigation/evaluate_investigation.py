"""Evaluate correlated evidence against withheld synthetic ground truth.

Ground truth is read ONLY here; never imported by the investigation engine.
"""
import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'database/bankops.db'
INPUT = ROOT / 'data/processed/phase6_step2_correlated_evidence.jsonl'
OUT = ROOT / 'data/processed'


def evaluate(db_path=DB, input_path=INPUT, output_dir=OUT):
    output_dir = Path(output_dir)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        truth = [dict(r) for r in conn.execute('SELECT * FROM incident_ground_truth')]
    predictions = [json.loads(line) for line in Path(input_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    assert len({r['monitoring_window_id'] for r in predictions}) == len(predictions), 'Duplicate alert windows'
    rows = []
    for p in predictions:
        start = datetime.fromisoformat(p['window_start'])
        end = datetime.fromisoformat(p['window_end'])
        matches = [g for g in truth if p['service_id'] in g['affected_services'].split(';') and start < datetime.fromisoformat(g['ended_at']) and end > datetime.fromisoformat(g['started_at'])]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one incident for alert {p['alert_id']}; got {len(matches)}")
        g = matches[0]
        candidates = p.get('ranked_candidates', [])
        ids = [c['component_id'] for c in candidates]
        actual = g['affected_component']
        rows.append({
            'alert_id': p['alert_id'], 'monitoring_window_id': p['monitoring_window_id'],
            'incident_id': g['incident_id'], 'service_id': p['service_id'],
            'window_start': p['window_start'], 'expected_component_id': actual,
            'predicted_component_id': p.get('likely_component_id') or '',
            'top1_correct': int(p.get('likely_component_id') == actual),
            'top3_correct': int(actual in ids[:3]),
            'expected_rank': ids.index(actual)+1 if actual in ids else '',
            'evidence_strength': p.get('evidence_strength',''),
            'candidate_count': len(candidates),
            'root_cause_confirmed': bool(p.get('root_cause_confirmed', False)),
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir/'phase6_step3_alert_evaluation.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    by_incident=[]
    for g in truth:
        group=[r for r in rows if r['incident_id']==g['incident_id']]
        by_incident.append({'incident_id':g['incident_id'],'expected_component_id':g['affected_component'],
                            'alerts_evaluated':len(group),'top1_correct':sum(r['top1_correct'] for r in group),
                            'top1_accuracy':round(sum(r['top1_correct'] for r in group)/len(group),4) if group else None,
                            'top3_correct':sum(r['top3_correct'] for r in group)})
    with (output_dir/'phase6_step3_by_incident.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(by_incident[0]));w.writeheader();w.writerows(by_incident)
    n=len(rows)
    summary={'alerts_evaluated':n,'top1_correct':sum(r['top1_correct'] for r in rows),
             'top1_accuracy':round(sum(r['top1_correct'] for r in rows)/n,4),
             'top3_correct':sum(r['top3_correct'] for r in rows),
             'top3_accuracy':round(sum(r['top3_correct'] for r in rows)/n,4),
             'multi_source_alerts':sum(r['evidence_strength']=='MULTI_SOURCE' for r in rows),
             'unconfirmed_root_cause_alerts':sum(not r['root_cause_confirmed'] for r in rows),
             'incident_families_with_alerts':sum(bool(r['alerts_evaluated']) for r in by_incident),
             'known_injected_incident_families':len(truth),
             'missed_incident_windows_in_detection':1,
             'evaluation_scope':'Controlled synthetic incident windows with a Phase 5 alert only',
             'limitations':['Alert-level metrics exclude the missed detection window.',
                            'Windows from one incident are correlated, not independent test cases.',
                            'Candidate ranking uses synthetic error/health/metric signatures.',
                            'No production diagnosis accuracy or causal verification is claimed.']}
    (output_dir/'phase6_step3_evaluation_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    with (output_dir/'phase6_step3_investigation_errors.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(r for r in rows if not r['top1_correct'])
    return summary,by_incident

if __name__=='__main__':
    summary,details=evaluate()
    print(json.dumps(summary,indent=2))
    print(details)
