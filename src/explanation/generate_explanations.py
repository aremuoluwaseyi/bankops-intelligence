"""Phase 8 Step 2: deterministic, evidence-grounded analyst narratives.

No language model is called. The validated Phase 8 Step 1 contract is the
only permitted source of claims. This module never confirms a root cause.
"""
import argparse
import json
from pathlib import Path

from src.explanation.explanation_contract import digest


def explain(contract):
    if not isinstance(contract, dict) or not contract.get('alert_id'):
        raise ValueError('A valid explanation contract is required')
    claimed = contract.get('explanation_contract_sha256')
    payload = {k: v for k, v in contract.items() if k != 'explanation_contract_sha256'}
    if claimed != digest(payload):
        raise ValueError('Explanation contract integrity check failed')
    if contract.get('root_cause_confirmed') is not False or contract.get('human_verification_required') is not True:
        raise ValueError('Human review and unconfirmed root cause are mandatory')
    if contract.get('automated_remediation_allowed') is not False:
        raise ValueError('Automated remediation is prohibited')
    status = contract.get('explanation_status')
    if status not in ('GUIDANCE_AVAILABLE', 'INSUFFICIENT_KNOWLEDGE'):
        raise ValueError('Unknown knowledge status')
    citations = contract.get('runbook_citations', [])
    checks = contract.get('suggested_diagnostic_checks', [])
    if status == 'INSUFFICIENT_KNOWLEDGE' and (citations or checks):
        raise ValueError('Cannot recommend unverified guidance without matching knowledge')
    if status == 'GUIDANCE_AVAILABLE' and not citations:
        raise ValueError('Guidance must have cited runbooks')
    for c in citations:
        if not c.get('document_id') or not c.get('document_sha256'):
            raise ValueError('Runbook citation lacks provenance')
    evidence = contract.get('observed_evidence', [])
    gaps = contract.get('evidence_gaps', [])
    if not all(isinstance(x, str) for x in evidence + gaps + checks):
        raise ValueError('Evidence, gaps, and checks must be text')
    suspected = contract.get('proposed_failure_domain')
    component = contract.get('proposed_component_id')
    if suspected and component:
        hypothesis = f'The current investigation ranks {suspected} ({component}) as a possible failure domain, not a confirmed root cause.'
    else:
        hypothesis = 'The available evidence does not support naming a leading failure domain.'
    if contract.get('ambiguity_flag'):
        hypothesis += ' Other candidates remain plausible; the ranking is ambiguous.'
    evidence_text = '; '.join(evidence) if evidence else 'No supporting observations were supplied.'
    gap_text = '; '.join(gaps) if gaps else 'No gaps were recorded in the supplied contract; this does not guarantee complete telemetry.'
    source_text = '; '.join(f"{c['document_id']} ({c.get('title') or 'untitled'})" for c in citations)
    if status == 'GUIDANCE_AVAILABLE':
        guidance_text = 'Runbook guidance for analyst review: ' + '; '.join(checks) if checks else 'No diagnostic checks were supplied.'
        guidance_text += f' Sources: {source_text}.'
    else:
        guidance_text = 'No verified matching runbook guidance is available. Escalate for manual investigation; do not infer missing steps.'
    narrative = (
        f"Alert {contract['alert_id']} for service {contract.get('service_id', 'unknown')} "
        f"during {contract.get('window_start', 'unknown')} to {contract.get('window_end', 'unknown')}. "
        f"Observed evidence: {evidence_text}. {hypothesis} "
        f"Evidence gaps: {gap_text}. {guidance_text} "
        'A human analyst must verify the findings before confirming a root cause or taking remediation action.'
    )
    result = {
        'schema_version': '1.0', 'alert_id': contract['alert_id'],
        'service_id': contract.get('service_id'),
        'explanation_status': status, 'narrative': narrative,
        'observed_evidence': evidence, 'proposed_failure_domain': suspected,
        'proposed_component_id': component, 'ambiguity_flag': bool(contract.get('ambiguity_flag')),
        'evidence_gaps': gaps, 'runbook_citations': citations,
        'suggested_diagnostic_checks': checks if status == 'GUIDANCE_AVAILABLE' else [],
        'explanation_contract_sha256': claimed, 'root_cause_confirmed': False,
        'human_verification_required': True, 'automated_remediation_allowed': False,
        'explanation_method': 'deterministic_template_no_llm',
    }
    result['narrative_sha256'] = digest(result)
    return result


def run(input_path, output_path):
    records = [json.loads(line) for line in Path(input_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if len({r.get('alert_id') for r in records}) != len(records):
        raise ValueError('Duplicate alert IDs in contracts')
    outputs = [explain(r) for r in records]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in outputs), encoding='utf-8')
    return outputs


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='data/processed/phase8_step1_explanation_contracts.jsonl')
    p.add_argument('--output', default='data/processed/phase8_step2_analyst_explanations.jsonl')
    a = p.parse_args()
    print(f'Generated {len(run(a.input, a.output))} evidence-grounded narratives')
