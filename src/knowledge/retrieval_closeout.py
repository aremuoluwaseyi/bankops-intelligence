"""Phase 7 closeout: integrity-checked deterministic runbook retrieval.

The trusted manifest is created from a reviewed knowledge base, then stored
separately. Rebuilding the manifest after a suspicious edit defeats the check.
"""
import argparse
import hashlib
import json
from pathlib import Path

from src.knowledge.retrieve_runbooks import retrieve, digest

ROOT = Path(__file__).resolve().parents[2]


def build_manifest(runbooks):
    """Produce an independently reviewable baseline of document digests."""
    if not isinstance(runbooks, list) or not runbooks:
        raise ValueError('Knowledge base must be a nonempty list')
    records = {}
    for doc in runbooks:
        if not isinstance(doc, dict):
            raise ValueError('Runbook must be an object')
        doc_id = doc.get('document_id')
        if not isinstance(doc_id, str) or not doc_id.strip() or doc_id in records:
            raise ValueError('Missing or duplicate document ID')
        records[doc_id] = {'version': doc.get('version'), 'sha256': digest(doc)}
    return {'schema_version': '1.0', 'hash_algorithm': 'sha256',
            'documents': dict(sorted(records.items()))}


def validate_integrity(runbooks, manifest):
    """Fail closed if any document was added, removed or modified."""
    if not isinstance(manifest, dict) or manifest.get('hash_algorithm') != 'sha256':
        raise ValueError('Invalid trusted manifest')
    observed = build_manifest(runbooks)
    if observed['documents'] != manifest.get('documents'):
        raise ValueError('Knowledge-base integrity mismatch: review source and manifest')
    return True


def retrieve_checked(handoff, runbooks, manifest, limit=3):
    """Validate provenance before retrieving; never infer confirmed root cause."""
    validate_integrity(runbooks, manifest)
    if not isinstance(handoff, dict) or not handoff.get('alert_id'):
        raise ValueError('A structured investigation handoff with alert_id is required')
    result = retrieve(handoff, runbooks, limit=limit)
    result['knowledge_integrity_status'] = 'VERIFIED'
    result['knowledge_manifest_sha256'] = digest(manifest)
    result['schema_version'] = '1.1'
    result.pop('retrieval_sha256', None)
    result['retrieval_sha256'] = digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runbooks', type=Path, default=ROOT/'knowledge/runbooks.json')
    parser.add_argument('--manifest', type=Path, default=ROOT/'knowledge/runbooks_manifest.json')
    parser.add_argument('--handoffs', type=Path, default=ROOT/'data/processed/phase6_step4_investigation_handoff.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT/'data/processed/phase7_step4_verified_retrieval.jsonl')
    args = parser.parse_args()
    docs = json.loads(args.runbooks.read_text(encoding='utf-8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    validate_integrity(docs, manifest)
    handoffs = [json.loads(s) for s in args.handoffs.read_text(encoding='utf-8').splitlines() if s.strip()]
    results = [retrieve_checked(h, docs, manifest) for h in handoffs]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in results), encoding='utf-8')
    print(json.dumps({'handoffs': len(results), 'matched': sum(r['retrieval_status']=='MATCHED' for r in results),
                      'unmatched': sum(r['retrieval_status']=='NO_MATCH' for r in results),
                      'integrity_verified': True, 'llm_used': False}, indent=2))


if __name__ == '__main__':
    main()
