"""Validate curated synthetic runbook records; does not implement retrieval or RAG."""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = {'document_id','version','status','title','component_ids','document_type','owner','source_type','last_reviewed','summary','symptoms','investigation_steps','verification_required','automated_remediation_allowed','limitations'}


def validate(records, known_components):
    errors=[]; ids=set(); coverage=set()
    for i, record in enumerate(records):
        missing=REQUIRED-set(record)
        if missing: errors.append(f'Row {i}: missing {sorted(missing)}'); continue
        docid=record['document_id']
        if docid in ids: errors.append(f'Duplicate document ID: {docid}')
        ids.add(docid)
        if not record['component_ids'] or not isinstance(record['component_ids'],list):
            errors.append(f'{docid}: component_ids must be nonempty list')
            continue
        unknown=set(record['component_ids'])-known_components
        if unknown: errors.append(f'{docid}: unknown components {sorted(unknown)}')
        coverage.update(set(record['component_ids'])&known_components)
        if record['verification_required'] is not True or record['automated_remediation_allowed'] is not False:
            errors.append(f'{docid}: unsafe verification/remediation flags')
        if record['source_type'] != 'synthetic_authoring' or record['status'] != 'synthetic_demo':
            errors.append(f'{docid}: provenance must disclose synthetic demo')
        if not record['investigation_steps'] or not record['limitations']:
            errors.append(f'{docid}: steps and limitations required')
    missing_coverage=known_components-coverage
    if missing_coverage: errors.append(f'Missing component coverage: {sorted(missing_coverage)}')
    return {'valid':not errors,'documents':len(records),'component_coverage':len(coverage),'known_components':len(known_components),'errors':errors}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',default=str(ROOT/'data/processed/phase7_step1_knowledge_validation.json'))
    args=parser.parse_args()
    with (ROOT/'data/raw/components.csv').open(newline='') as f:
        known={r['component_id'] for r in csv.DictReader(f)}
    records=json.loads((ROOT/'knowledge/runbooks.json').read_text())
    result=validate(records,known)
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['valid']: raise SystemExit(1)

if __name__=='__main__': main()
