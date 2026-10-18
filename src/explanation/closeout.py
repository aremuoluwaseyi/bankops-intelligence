"""Phase 8 Step 4: fail-closed, auditable explanation delivery handoff.

No LLM, root-cause confirmation, or automated remediation is performed.
"""
import argparse
import json
from pathlib import Path
from src.explanation.evaluate_explanations import evaluate_one
from src.explanation.explanation_contract import digest


def closeout(contract, narrative):
    """Return a safe delivery decision, never an unvalidated narrative."""
    alert_id = contract.get('alert_id') if isinstance(contract, dict) else None
    issues = []
    if not isinstance(contract, dict) or not isinstance(narrative, dict):
        issues = ['INVALID_INPUT_TYPE']
    else:
        try:
            issues = evaluate_one(contract, narrative)['issues']
        except (TypeError, ValueError, KeyError, AttributeError):
            issues = ['VALIDATION_EXCEPTION']
        if not issues:
            for key in ('narrative', 'observed_evidence', 'evidence_gaps', 'suggested_diagnostic_checks'):
                value = narrative.get(key)
                entries = value if isinstance(value, list) else [value]
                if not all(isinstance(x, str) for x in entries):
                    issues.append('INVALID_TEXT_TYPE:' + key)
                elif any(any(ord(ch) < 32 and ch not in '\n\t' for ch in x) for x in entries):
                    issues.append('CONTROL_CHARACTER:' + key)
            if len(narrative.get('narrative', '')) > 12000:
                issues.append('EXCESSIVE_NARRATIVE_LENGTH')
    safe = not issues
    record = {
        'schema_version': '1.0', 'alert_id': alert_id,
        'delivery_status': 'READY_FOR_ANALYST_REVIEW' if safe else 'WITHHELD_VALIDATION_FAILED',
        'validation_issues': sorted(set(issues)),
        'human_verification_required': True,
        'root_cause_confirmed': False,
        'automated_remediation_allowed': False,
        'explanation_contract_sha256': contract.get('explanation_contract_sha256') if safe else None,
        'narrative_sha256': narrative.get('narrative_sha256') if safe else None,
        'analyst_narrative': narrative.get('narrative') if safe else None,
        'source_runbooks': narrative.get('runbook_citations', []) if safe else [],
        'evidence_gaps': narrative.get('evidence_gaps', []) if safe else [],
        'review_state': 'PENDING_HUMAN_REVIEW',
    }
    record['handoff_sha256'] = digest(record)
    return record


def run(contracts_path, narratives_path, output_path, summary_path):
    def load(path):
        with open(path, encoding='utf-8') as stream:
            return [json.loads(line) for line in stream if line.strip()]
    contracts, narratives = load(contracts_path), load(narratives_path)
    def index(items, label):
        result = {}
        for item in items:
            key = item.get('alert_id') if isinstance(item, dict) else None
            if not isinstance(key, str) or not key or key in result:
                raise ValueError('Missing or duplicate ' + label + ' alert ID')
            result[key] = item
        return result
    c, n = index(contracts, 'contract'), index(narratives, 'narrative')
    results = []
    for alert_id in sorted(set(c) | set(n)):
        if alert_id in c and alert_id in n:
            results.append(closeout(c[alert_id], n[alert_id]))
        else:
            record = {
                'schema_version': '1.0', 'alert_id': alert_id,
                'delivery_status': 'WITHHELD_VALIDATION_FAILED',
                'validation_issues': ['MISSING_NARRATIVE' if alert_id in c else 'ORPHAN_NARRATIVE'],
                'human_verification_required': True, 'root_cause_confirmed': False,
                'automated_remediation_allowed': False, 'explanation_contract_sha256': None,
                'narrative_sha256': None, 'analyst_narrative': None, 'source_runbooks': [],
                'evidence_gaps': [], 'review_state': 'PENDING_HUMAN_REVIEW',
            }
            record['handoff_sha256'] = digest(record)
            results.append(record)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in results), encoding='utf-8')
    ready = sum(r['delivery_status'] == 'READY_FOR_ANALYST_REVIEW' for r in results)
    summary = {'total': len(results), 'ready_for_analyst_review': ready,
               'withheld': len(results) - ready,
               'limitations': 'Deterministic source-fidelity gate only; no independent expert review or production security certification.'}
    target = Path(summary_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--contracts', default='data/processed/phase8_step1_explanation_contracts.jsonl')
    p.add_argument('--narratives', default='data/processed/phase8_step2_analyst_explanations.jsonl')
    p.add_argument('--output', default='data/processed/phase8_step4_review_handoffs.jsonl')
    p.add_argument('--summary', default='data/processed/phase8_step4_closeout_summary.json')
    a = p.parse_args()
    print(json.dumps(run(a.contracts, a.narratives, a.output, a.summary), indent=2))
