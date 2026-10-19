"""Phase 8 Step 3: deterministic source-fidelity evaluation, not expert review."""
import argparse
import json
from collections import Counter
from pathlib import Path
from src.explanation.explanation_contract import digest
from src.explanation.generate_explanations import explain

FIELDS = ('observed_evidence', 'evidence_gaps', 'runbook_citations',
          'suggested_diagnostic_checks', 'proposed_component_id',
          'proposed_failure_domain', 'explanation_status', 'ambiguity_flag')


def evaluate_one(contract, output):
    issues = []
    if contract.get('alert_id') != output.get('alert_id'):
        issues.append('ALERT_MISMATCH')
    if digest({k: v for k, v in contract.items() if k != 'explanation_contract_sha256'}) != contract.get('explanation_contract_sha256'):
        issues.append('CONTRACT_INTEGRITY_FAILURE')
    if output.get('explanation_contract_sha256') != contract.get('explanation_contract_sha256'):
        issues.append('SOURCE_LINK_MISMATCH')
    if digest({k: v for k, v in output.items() if k != 'narrative_sha256'}) != output.get('narrative_sha256'):
        issues.append('OUTPUT_INTEGRITY_FAILURE')
    for key in FIELDS:
        if output.get(key) != contract.get(key):
            issues.append('FIELD_MISMATCH:' + key)
    if output.get('root_cause_confirmed') is not False or output.get('human_verification_required') is not True:
        issues.append('UNSAFE_CAUSAL_STATUS')
    if output.get('automated_remediation_allowed') is not False:
        issues.append('UNSAFE_REMEDIATION')
    if output.get('explanation_method') != 'deterministic_template_no_llm':
        issues.append('INCORRECT_METHOD')
    try:
        if explain(contract)['narrative'] != output.get('narrative'):
            issues.append('NARRATIVE_NOT_REPRODUCIBLE')
    except (ValueError, KeyError, TypeError) as exc:
        issues.append('INVALID_CONTRACT:' + type(exc).__name__)
    return {'alert_id': contract.get('alert_id'), 'passed': not issues, 'issues': sorted(set(issues))}


def run(contracts_path, narratives_path, output_path):
    def load(path):
        with open(path, encoding='utf-8') as f:
            return [json.loads(line) for line in f if line.strip()]
    contracts, narratives = load(contracts_path), load(narratives_path)
    def index(records, name):
        ids = [r.get('alert_id') for r in records]
        if None in ids or len(ids) != len(set(ids)):
            raise ValueError('Missing or duplicate ' + name + ' alert IDs')
        return {r['alert_id']: r for r in records}
    c, n = index(contracts, 'contract'), index(narratives, 'narrative')
    results = []
    for alert_id in sorted(set(c) | set(n)):
        if alert_id not in c:
            results.append({'alert_id': alert_id, 'passed': False, 'issues': ['ORPHAN_NARRATIVE']})
        elif alert_id not in n:
            results.append({'alert_id': alert_id, 'passed': False, 'issues': ['MISSING_NARRATIVE']})
        else:
            results.append(evaluate_one(c[alert_id], n[alert_id]))
    counts = Counter(issue for r in results for issue in r['issues'])
    report = {
        'scope': 'deterministic_source_fidelity_not_independent_semantic_quality',
        'contracts': len(contracts), 'narratives': len(narratives),
        'evaluated_alerts': len(results),
        'passed': sum(r['passed'] for r in results),
        'failed': sum(not r['passed'] for r in results),
        'issue_counts': dict(sorted(counts.items())),
        'limitations': [
            'Exact template reproduction is checked against the same generator, not independent expert judgment.',
            'Synthetic data and deterministic component matching cannot establish production accuracy.',
            'No verification of whether the original telemetry is factually correct.'
        ], 'per_alert': results,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--contracts', default='data/processed/phase8_step1_explanation_contracts.jsonl')
    p.add_argument('--narratives', default='data/processed/phase8_step2_analyst_explanations.jsonl')
    p.add_argument('--output', default='data/processed/phase8_step3_explanation_quality.json')
    a = p.parse_args()
    report = run(a.contracts, a.narratives, a.output)
    print(f"Evaluated {report['evaluated_alerts']} alerts: {report['passed']} passed, {report['failed']} failed")
