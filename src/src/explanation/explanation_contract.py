"""Phase 8 Step 1: evidence-grounded explanation contract (no LLM calls)."""
import argparse
import hashlib
import json
from pathlib import Path

CONTRACT_VERSION = "1.0"
REQUIRED = ("alert_id", "monitoring_window_id", "service_id", "window_start", "window_end")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate_and_prepare(investigation, retrieval):
    """Fail closed on mismatched or unverified evidence; never assert causality."""
    if not isinstance(investigation, dict) or not isinstance(retrieval, dict):
        raise ValueError("Both inputs must be objects")
    for key in REQUIRED:
        if not investigation.get(key):
            raise ValueError(f"Missing investigation field: {key}")
    if investigation["alert_id"] != retrieval.get("alert_id"):
        raise ValueError("Alert IDs do not match")
    if retrieval.get("investigation_handoff_sha256") != investigation.get("handoff_sha256"):
        raise ValueError("Retrieval is not linked to this investigation handoff")
    if retrieval.get("knowledge_integrity_status") != "VERIFIED":
        raise ValueError("Knowledge integrity not verified")
    if investigation.get("root_cause_confirmed") is not False or retrieval.get("root_cause_confirmed") is not False:
        raise ValueError("This stage accepts unconfirmed hypotheses only")
    candidates = investigation.get("ranked_candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("Candidates must be a list")
    documents = retrieval.get("documents", [])
    if not isinstance(documents, list):
        raise ValueError("Documents must be a list")
    for doc in documents:
        if not doc.get("document_id") or not doc.get("document_sha256"):
            raise ValueError("Missing document provenance")
        if doc.get("automated_remediation_allowed") is True:
            raise ValueError("Automated remediation is not allowed")
        if doc.get("matched_component_id") not in {c.get("component_id") for c in candidates}:
            raise ValueError("Runbook is not linked to a ranked candidate")
    top = candidates[0] if candidates else None
    observations = [str(x) for x in (top or {}).get("supporting_observations", [])]
    gaps = sorted(set(str(x) for x in investigation.get("evidence_gaps", []) + retrieval.get("evidence_gaps", [])))
    status = "GUIDANCE_AVAILABLE" if documents and retrieval.get("retrieval_status") == "MATCHED" else "INSUFFICIENT_KNOWLEDGE"
    if status == "GUIDANCE_AVAILABLE" and not documents:
        raise ValueError("Inconsistent retrieval status")
    result = {
        "schema_version": CONTRACT_VERSION,
        "alert_id": investigation["alert_id"],
        "monitoring_window_id": investigation["monitoring_window_id"],
        "service_id": investigation["service_id"],
        "window_start": investigation["window_start"],
        "window_end": investigation["window_end"],
        "explanation_status": status,
        "proposed_failure_domain": (top or {}).get("component_name"),
        "proposed_component_id": (top or {}).get("component_id"),
        "observed_evidence": observations,
        "evidence_gaps": gaps,
        "ambiguity_flag": bool(investigation.get("ambiguity", {}).get("flag") or retrieval.get("ambiguity_flag")),
        "runbook_citations": [{"document_id": d["document_id"], "document_sha256": d["document_sha256"], "title": d.get("title"), "matched_component_id": d["matched_component_id"]} for d in documents],
        "suggested_diagnostic_checks": [step for d in documents for step in d.get("investigation_steps", [])],
        "investigation_handoff_sha256": investigation["handoff_sha256"],
        "retrieval_sha256": retrieval.get("retrieval_sha256"),
        "root_cause_confirmed": False,
        "human_verification_required": True,
        "automated_remediation_allowed": False,
        "explanation_method": "evidence_contract_no_llm",
        "limitations": ["Proposed failure domain is not a confirmed root cause.", "Runbooks and telemetry are synthetic.", "Document matching is deterministic, not semantic RAG."]
    }
    result["explanation_contract_sha256"] = digest(result)
    return result


def run(investigation_path, retrieval_path, output_path):
    def load(path):
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    investigations = load(investigation_path)
    retrievals = load(retrieval_path)
    if len({r.get("alert_id") for r in retrievals}) != len(retrievals):
        raise ValueError("Duplicate retrieval alert IDs")
    lookup = {r["alert_id"]: r for r in retrievals}
    if len(lookup) != len(investigations):
        raise ValueError("Input record counts differ")
    outputs = []
    for inv in investigations:
        if inv["alert_id"] not in lookup:
            raise ValueError("Missing retrieval for alert")
        outputs.append(validate_and_prepare(inv, lookup[inv["alert_id"]]))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in outputs), encoding="utf-8")
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--investigations", default="data/processed/phase6_step4_investigation_handoff.jsonl")
    parser.add_argument("--retrieval", default="data/processed/phase7_step4_verified_retrieval.jsonl")
    parser.add_argument("--output", default="data/processed/phase8_step1_explanation_contracts.jsonl")
    args = parser.parse_args()
    outputs = run(args.investigations, args.retrieval, args.output)
    print(f"Validated {len(outputs)} evidence explanation contracts")
