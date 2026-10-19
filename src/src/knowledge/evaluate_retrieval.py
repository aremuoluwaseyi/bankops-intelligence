"""Evaluate exact-component runbook retrieval on synthetic alerts and robustness probes.

Ground truth is used only by this evaluation script, never the retriever.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from src.knowledge.retrieve_runbooks import retrieve

ROOT = Path(__file__).resolve().parents[2]


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def evaluate(handoffs, runbooks, expected_by_window):
    rows = []
    for handoff in handoffs:
        window_id = handoff['monitoring_window_id']
        expected = expected_by_window.get(window_id)
        result = retrieve(handoff, runbooks)
        documents = result['documents']
        ids = [d['matched_component_id'] for d in documents]
        rows.append({
            'alert_id': handoff['alert_id'], 'monitoring_window_id': window_id,
            'expected_component_id': expected or '',
            'retrieval_status': result['retrieval_status'],
            'retrieved_count': len(documents),
            'top1_component_id': ids[0] if ids else '',
            'top1_relevant': int(bool(expected and ids and ids[0] == expected)),
            'hit_at_3': int(bool(expected and expected in ids[:3])),
            'reciprocal_rank': round(1/(ids.index(expected)+1), 6) if expected in ids else 0,
            'has_traceable_source': int(bool(documents) and all(d.get('document_sha256') and d.get('supporting_observations') is not None for d in documents)),
            'human_verification_required': int(result['human_verification_required']),
        })
    labeled = [r for r in rows if r['expected_component_id']]
    total = len(rows)
    metrics = {
        'alerts_evaluated': total, 'alerts_with_expected_component': len(labeled),
        'match_rate': sum(r['retrieval_status']=='MATCHED' for r in rows)/total if total else None,
        'top1_relevance_on_labeled_alerts': sum(r['top1_relevant'] for r in labeled)/len(labeled) if labeled else None,
        'hit_at_3_on_labeled_alerts': sum(r['hit_at_3'] for r in labeled)/len(labeled) if labeled else None,
        'mrr_on_labeled_alerts': sum(r['reciprocal_rank'] for r in labeled)/len(labeled) if labeled else None,
        'traceability_rate': sum(r['has_traceable_source'] for r in rows)/total if total else None,
        'verification_required_rate': sum(r['human_verification_required'] for r in rows)/total if total else None,
        'expected_component_counts': dict(sorted(Counter(r['expected_component_id'] for r in labeled).items())),
        'interpretation': 'In-sample synthetic, exact component-ID matching; correctness largely inherits Phase 6 candidate rankings. Not an independent test of semantic relevance or real-world RAG.',
    }
    return rows, metrics


def robustness_probes(runbooks):
    base = {'alert_id':'PROBE','handoff_sha256':'synthetic','ranked_candidates':[], 'evidence_gaps':[]}
    def candidate(cid, rank=1):
        return {'component_id':cid,'supporting_observations':['Synthetic observed log'],'evidence_types':['error_logs']}
    probes = {}
    probes['no_candidates'] = retrieve(base,runbooks)['retrieval_status']=='NO_MATCH'
    probes['unknown_component'] = retrieve({**base,'ranked_candidates':[candidate('C999')]},runbooks)['retrieval_status']=='NO_MATCH'
    probes['unsafe_document_excluded'] = retrieve({**base,'ranked_candidates':[candidate('C003')]},[{**r,'automated_remediation_allowed':True} for r in runbooks])['retrieval_status']=='NO_MATCH'
    probes['ambiguous_candidates_ordered'] = [d['matched_component_id'] for d in retrieve({**base,'ranked_candidates':[candidate('C004'),candidate('C003')],'ambiguity':{'flag':True}},runbooks)['documents']][:2] == ['C004','C003']
    probes['repeatable_hash'] = retrieve({**base,'ranked_candidates':[candidate('C003')]},runbooks)['retrieval_sha256'] == retrieve({**base,'ranked_candidates':[candidate('C003')]},runbooks)['retrieval_sha256']
    probes['no_confirmation'] = all(not retrieve({**base,'ranked_candidates':[candidate('C003')]},runbooks)[k] for k in ['root_cause_confirmed','automated_remediation_allowed'])
    probes['no_ground_truth_needed'] = retrieve({**base,'ranked_candidates':[candidate('C003')]},runbooks)['retrieval_status']=='MATCHED'
    return probes


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--handoffs',type=Path,default=ROOT/'data/processed/phase6_step4_investigation_handoff.jsonl')
    parser.add_argument('--runbooks',type=Path,default=ROOT/'knowledge/runbooks.json')
    parser.add_argument('--evaluation-labels',type=Path,default=ROOT/'data/processed/phase6_step3_alert_evaluation.csv')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'data/processed')
    args=parser.parse_args()
    handoffs=read_jsonl(args.handoffs)
    runbooks=json.loads(args.runbooks.read_text(encoding='utf-8'))
    with args.evaluation_labels.open(newline='',encoding='utf-8') as f:
        labels={r['monitoring_window_id']:r['expected_component_id'] for r in csv.DictReader(f)}
    rows,metrics=evaluate(handoffs,runbooks,labels)
    probes=robustness_probes(runbooks)
    metrics['robustness_probes']=probes
    metrics['robustness_passed']=sum(probes.values())
    metrics['robustness_total']=len(probes)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    with (args.output_dir/'phase7_step3_retrieval_evaluation.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['alert_id']);writer.writeheader();writer.writerows(rows)
    (args.output_dir/'phase7_step3_evaluation_summary.json').write_text(json.dumps(metrics,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(metrics,indent=2))
    if not all(probes.values()):
        raise SystemExit('Robustness probe failed')

if __name__=='__main__':
    main()
