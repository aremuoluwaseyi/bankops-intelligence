"""Deterministic, evidence-linked retrieval of synthetic runbooks (not LLM/RAG)."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def retrieve(handoff, runbooks, limit=3):
    """Return component-matched documents with traceable supporting observations."""
    if not isinstance(handoff, dict) or not isinstance(runbooks, list):
        raise ValueError('Expected a handoff dictionary and a runbook list')
    if not isinstance(limit, int) or limit < 1:
        raise ValueError('limit must be a positive integer')
    candidates = handoff.get('ranked_candidates') or []
    ranked = []
    seen = set()
    for rank, candidate in enumerate(candidates, start=1):
        cid = candidate.get('component_id')
        if not cid or cid in seen:
            continue
        seen.add(cid)
        ranked.append((cid, rank, candidate))
    matches = []
    for doc in runbooks:
        if doc.get('status') != 'synthetic_demo' or doc.get('source_type') != 'synthetic_authoring':
            continue
        if doc.get('verification_required') is not True or doc.get('automated_remediation_allowed') is not False:
            continue
        for cid, rank, candidate in ranked:
            if cid not in doc.get('component_ids', []):
                continue
            matches.append({
                'document_id': doc['document_id'], 'version': doc['version'],
                'title': doc['title'], 'matched_component_id': cid,
                'candidate_rank': rank, 'retrieval_method': 'exact_component_id',
                'supporting_observations': candidate.get('supporting_observations', []),
                'evidence_types': candidate.get('evidence_types', []),
                'investigation_steps': doc.get('investigation_steps', []),
                'limitations': doc.get('limitations', []),
                'document_sha256': digest(doc), 'human_verification_required': True,
                'source_type': doc['source_type'],
            })
    matches.sort(key=lambda m: (m['candidate_rank'], m['document_id']))
    matches = matches[:limit]
    gaps = list(handoff.get('evidence_gaps') or [])
    if not ranked:
        gaps.append('No ranked candidate component was available for runbook matching')
    if ranked and not matches:
        gaps.append('No eligible runbook matched the ranked candidate components')
    result = {
        'schema_version': '1.0', 'alert_id': handoff.get('alert_id'),
        'investigation_handoff_sha256': handoff.get('handoff_sha256'),
        'retrieval_status': 'MATCHED' if matches else 'NO_MATCH',
        'retrieval_method': 'deterministic_component_lookup',
        'documents': matches, 'evidence_gaps': gaps,
        'ambiguity_flag': bool((handoff.get('ambiguity') or {}).get('flag')),
        'root_cause_confirmed': False, 'human_verification_required': True,
        'automated_remediation_allowed': False,
        'cautions': ['Runbooks are synthetic demonstrations, not verified bank procedures.',
                     'Document matching does not confirm the suspected failure domain.',
                     'No language model or semantic vector retrieval is used.'],
    }
    result['retrieval_sha256'] = digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoffs', type=Path, default=ROOT/'data/processed/phase6_step4_investigation_handoff.jsonl')
    parser.add_argument('--runbooks', type=Path, default=ROOT/'knowledge/runbooks.json')
    parser.add_argument('--output', type=Path, default=ROOT/'data/processed/phase7_step2_retrieval.jsonl')
    parser.add_argument('--summary', type=Path, default=ROOT/'data/processed/phase7_step2_summary.json')
    args = parser.parse_args()
    runbooks = json.loads(args.runbooks.read_text(encoding='utf-8'))
    handoffs = [json.loads(line) for line in args.handoffs.read_text(encoding='utf-8').splitlines() if line.strip()]
    results = [retrieve(item, runbooks) for item in handoffs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(item, sort_keys=True)+'\n' for item in results), encoding='utf-8')
    summary = {'handoffs': len(results), 'matched': sum(x['retrieval_status']=='MATCHED' for x in results),
               'unmatched': sum(x['retrieval_status']=='NO_MATCH' for x in results),
               'unique_documents': sorted({doc['document_id'] for x in results for doc in x['documents']}),
               'method': 'deterministic_component_lookup', 'llm_used': False}
    args.summary.write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
