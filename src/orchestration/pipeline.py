"""Phase 9 Step 2: reproducible offline stage orchestration.

Runs the existing modules in dependency order, stops on failures, validates
record counts and handoff safety, and records a stage audit. No live scheduler,
external notifications, LLM, or automatic remediation.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGES = [
    ('detection', 'src.detection.run_detection_handoff'),
    ('evidence_collection', 'src.investigation.collect_evidence'),
    ('evidence_correlation', 'src.investigation.correlate_evidence'),
    ('investigation_handoff', 'src.investigation.harden_investigation'),
    ('knowledge_retrieval', 'src.knowledge.retrieval_closeout'),
    ('explanation_contract', 'src.explanation.explanation_contract'),
    ('explanation_generation', 'src.explanation.generate_explanations'),
    ('explanation_validation', 'src.explanation.closeout'),
    ('analyst_queue', 'src.orchestration.workflow'),
]
ARTIFACTS = [
    'phase5_investigation_handoff.csv',
    'phase6_step1_evidence_packages.jsonl',
    'phase6_step2_correlated_evidence.jsonl',
    'phase6_step4_investigation_handoff.jsonl',
    'phase7_step4_verified_retrieval.jsonl',
    'phase8_step1_explanation_contracts.jsonl',
    'phase8_step2_analyst_explanations.jsonl',
    'phase8_step4_review_handoffs.jsonl',
    'phase9_step1_work_queue.jsonl',
]

def count_rows(path):
    if path.suffix == '.csv':
        import csv
        with path.open(encoding='utf-8', newline='') as f:
            return sum(1 for _ in csv.DictReader(f))
    with path.open(encoding='utf-8') as f:
        return sum(bool(line.strip()) for line in f)

def orchestrate(root=ROOT, stages=STAGES, output=None, executor=None):
    root = Path(root).resolve()
    output = Path(output) if output else root/'data/processed/phase9_step2_pipeline_audit.json'
    audit = {'schema_version':'1.0', 'mode':'offline_batch', 'status':'RUNNING',
             'started_at_utc':datetime.now(timezone.utc).isoformat(), 'stages':[],
             'external_notifications_sent':0, 'automated_remediations':0,
             'limitations':'No continuous monitoring, autonomous scheduling, external alerts or remediation.'}
    execute = executor or subprocess.run
    try:
        for idx, (name, module) in enumerate(stages):
            cmd = [sys.executable, '-m', module]
            result = execute(cmd, cwd=str(root), capture_output=True, text=True)
            entry = {'stage':name, 'module':module, 'returncode':result.returncode,
                     'stdout_tail':result.stdout[-1200:], 'stderr_tail':result.stderr[-1200:]}
            audit['stages'].append(entry)
            if result.returncode:
                raise RuntimeError(f'{name} failed with exit code {result.returncode}: {result.stderr[-350:]}')
            if stages is STAGES:
                artifact = root/'data/processed'/ARTIFACTS[idx]
                if not artifact.is_file():
                    raise RuntimeError(f'{name} missing artifact: {artifact.name}')
                entry['artifact'] = artifact.name
                entry['record_count'] = count_rows(artifact)
                if idx and entry['record_count'] != audit['stages'][0]['record_count']:
                    raise RuntimeError(f'{name} count mismatch: {entry["record_count"]} vs detection {audit["stages"][0]["record_count"]}')
        if stages is STAGES:
            from src.orchestration.workflow import build_queue
            source = root/'data/processed/phase8_step4_review_handoffs.jsonl'
            items = build_queue([json.loads(s) for s in source.read_text(encoding='utf-8').splitlines() if s.strip()])
            queue_path = root/'data/processed/phase9_step1_work_queue.jsonl'
            queue = [json.loads(s) for s in queue_path.read_text(encoding='utf-8').splitlines() if s.strip()]
            if queue != items:
                raise RuntimeError('Queue output does not match validated handoffs')
            audit['work_items'] = len(items)
            audit['queued_for_review'] = sum(x['queue']=='ANALYST_REVIEW' for x in items)
            audit['exceptions'] = sum(x['queue']=='VALIDATION_EXCEPTION' for x in items)
        audit['status'] = 'SUCCEEDED'
    except Exception as exc:
        audit['status'] = 'FAILED_CLOSED'
        audit['error'] = str(exc)
    finally:
        audit['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
    return audit

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = orchestrate(output=args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='stages'}, indent=2))
    sys.exit(0 if result['status']=='SUCCEEDED' else 1)
