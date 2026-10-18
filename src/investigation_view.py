"""Read-only investigation drill-down with source-integrity cross-checks."""
import json
from pathlib import Path
from src.explanation.explanation_contract import digest
from src.explanation.generate_explanations import explain


def _load_unique(path):
    result = {}
    with open(path, encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            key = record.get('alert_id')
            if not key or key in result:
                raise ValueError(f'Missing or duplicate alert identifier in {path}')
            result[key] = record
    return result


def load_investigation_details(root):
    """Read validated contracts and narratives; reject mismatches instead of guessing."""
    base = Path(root) / 'data' / 'processed'
    contracts = _load_unique(base / 'phase8_step1_explanation_contracts.jsonl')
    narratives = _load_unique(base / 'phase8_step2_analyst_explanations.jsonl')
    if contracts.keys() != narratives.keys():
        raise ValueError('Investigation contracts and explanations do not have matching alert IDs')
    details = {}
    for alert_id, contract in contracts.items():
        narrative = narratives[alert_id]
        source = {k: v for k, v in contract.items() if k != 'explanation_contract_sha256'}
        if digest(source) != contract.get('explanation_contract_sha256'):
            raise ValueError(f'Contract digest mismatch: {alert_id}')
        expected = explain(contract)
        if narrative != expected:
            raise ValueError(f'Explanation content or provenance mismatch: {alert_id}')
        details[alert_id] = {
            'alert_id': alert_id,
            'service_id': contract.get('service_id'),
            'monitoring_window_id': contract.get('monitoring_window_id'),
            'window_start': contract.get('window_start'),
            'window_end': contract.get('window_end'),
            'observed_evidence': list(contract.get('observed_evidence') or []),
            'proposed_failure_domain': contract.get('proposed_failure_domain'),
            'proposed_component_id': contract.get('proposed_component_id'),
            'evidence_gaps': list(contract.get('evidence_gaps') or []),
            'ambiguity_flag': bool(contract.get('ambiguity_flag')),
            'diagnostic_checks': list(contract.get('suggested_diagnostic_checks') or []),
            'runbook_citations': list(contract.get('runbook_citations') or []),
            'explanation_status': contract.get('explanation_status'),
            'explanation_contract_sha256': contract['explanation_contract_sha256'],
            'narrative_sha256': narrative['narrative_sha256'],
            'narrative': narrative['narrative'],
            'human_verification_required': True,
            'root_cause_confirmed': False,
        }
    return details


def match_detail(item, details):
    """Cross-check work queue provenance; return None for withheld exceptions."""
    if item['queue'] == 'VALIDATION_EXCEPTION':
        return None
    detail = details.get(item['alert_id'])
    if detail is None:
        raise ValueError('No verified investigation details for alert ' + item['alert_id'])
    if (detail['narrative_sha256'] != item['narrative_sha256'] or
            detail['narrative'] != item['analyst_narrative']):
        raise ValueError('Work queue narrative differs from verified investigation')
    return detail
