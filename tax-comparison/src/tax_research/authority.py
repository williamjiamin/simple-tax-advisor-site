"""Citation screening and stable research ordering, never a legal odds calculator.

The numeric priorities are editorial navigation aids. They cannot establish
substantial authority, override judicial review, or adjudicate conflicting law.
"""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[2] / "data" / "tax_research"
AS_OF = "2026-11-22"
CIRCUITS = {f"{n:02d}" for n in range(1, 12)} | {"dc", "fed", "unknown"}
RECORD_FIELDS = {"id", "kind", "issue_match", "status", "applies_to_period",
                 "issued_on", "circuit", "same_taxpayer", "conflicting_authority",
                 "faq_linked_news_release"}
CONTEXT_FIELDS = {"purpose", "forum", "appellate_circuit", "as_of"}


def _date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field} must be YYYY-MM-DD")
    return parsed


def _optional_bool(value: Any, field: str) -> None:
    if value is not None and type(value) is not bool:
        raise ValueError(f"{field} must be true, false, or null")


def _catalog() -> dict[str, dict]:
    return {r["kind"]: r for r in json.loads((DATA / "authority_model.json").read_text())["categories"]}


def evaluate_authority(record: dict, context: dict | None = None) -> dict:
    """Classify one cited item using explicitly supplied facts and research date.

    Unknown facts remain unknown. Output describes potential use, not a binding
    conclusion that a cited holding controls an actual taxpayer's dispute.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be an object")
    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if set(record) - RECORD_FIELDS or set(context) - CONTEXT_FIELDS:
        raise ValueError("unknown input field")
    item_id = record.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise ValueError("id must be nonempty text")
    catalog = _catalog()
    kind = record.get("kind")
    if not isinstance(kind, str) or kind not in catalog:
        raise ValueError("unrecognized authority kind")
    purpose = context.get("purpose", "merits")
    forum = context.get("forum", "unknown")
    circuit = context.get("appellate_circuit", "unknown")
    if not isinstance(purpose, str) or purpose not in {"merits", "substantial_authority"}:
        raise ValueError("purpose must be merits or substantial_authority")
    if not isinstance(forum, str) or forum not in {"tax_court", "district_court", "claims_court", "administrative", "unknown"}:
        raise ValueError("unrecognized forum")
    if not isinstance(circuit, str) or circuit not in CIRCUITS or not isinstance(record.get("circuit", "unknown"), str) or record.get("circuit", "unknown") not in CIRCUITS:
        raise ValueError("unrecognized appellate circuit")
    if forum == "claims_court" and circuit not in {"fed", "unknown"}:
        raise ValueError("claims_court requires the federal appellate route")
    if forum == "tax_court" and circuit == "fed":
        raise ValueError("tax_court does not use the federal appellate route")
    as_of = _date(context.get("as_of", AS_OF), "as_of")
    issued = _date(record["issued_on"], "issued_on") if record.get("issued_on") is not None else None
    match = record.get("issue_match", "unknown")
    status = record.get("status", "unknown")
    if not isinstance(match, str) or match not in {"direct", "analogous", "remote", "unknown"}:
        raise ValueError("unrecognized issue_match")
    if not isinstance(status, str) or status not in {"current", "superseded", "withdrawn", "unknown"}:
        raise ValueError("unrecognized status")
    for field in ("applies_to_period", "same_taxpayer", "conflicting_authority", "faq_linked_news_release"):
        _optional_bool(record.get(field), field)
    category = catalog[kind]
    gaps: list[str] = []
    reasons: list[str] = []
    cautions = ["Research priority is editorial; never sum scores to establish substantial authority."]
    if status == "unknown":
        gaps.append("Validate current status and subsequent treatment.")
    if match == "unknown":
        gaps.append("Compare the legal issue and material facts.")
    if record.get("applies_to_period") is None:
        gaps.append("Verify effective dates for the taxpayer's period.")
    if issued is None:
        gaps.append("Record the issuance or enactment date.")
    excluded = status in {"superseded", "withdrawn"} or record.get("applies_to_period") is False
    if excluded:
        reasons.append("Current-law reliance is blocked by supplied status or period facts; preserve historical context separately.")
    if issued and issued > as_of:
        excluded = True
        reasons.append("The source was issued after the supplied research date.")
    role = category["legal_role"]
    court_priority = 1
    if kind == "supreme_court":
        role = "potential_nationwide_controlling_interpretation"
        court_priority = 0
    elif kind == "circuit_court":
        source_circuit = record.get("circuit", "unknown")
        if circuit == "unknown" or source_circuit == "unknown":
            role = "jurisdiction_requires_review"
            gaps.append("Identify the court of appeals that would review this dispute.")
        elif source_circuit == circuit and forum != "unknown":
            role = "potential_controlling_appellate_interpretation"
            court_priority = 0 if purpose == "merits" else 1
        else:
            role = "potential_persuasive_judicial_interpretation"
        if purpose == "substantial_authority":
            cautions.append("Geographic applicability is generally disregarded for the regulatory weight test; controlling appellate support has a separate rule.")
    elif kind in {"tax_court_regular", "tax_court_memorandum"}:
        role = "potential_precedential_trial_court_analysis" if kind == "tax_court_regular" else "potential_persuasive_trial_court_analysis"
        cautions.append("Check appellate venue, opinion type, later treatment, and factual fit; no universal numerical court rank applies.")
    elif kind == "tax_court_summary":
        role = "nonprecedential_small_case_decision"
    elif kind in {"plr", "tam"}:
        role = "taxpayer_specific_nonprecedential_determination"
        if record.get("same_taxpayer") is None:
            gaps.append("Determine whether the ruling addresses this taxpayer and these facts.")
        cautions.append("Public disclosure does not authorize precedential use for another taxpayer.")
    if kind == "cca":
        cautions.append("Chief counsel advice is nonprecedential and is not expressly listed as its own category in the substantial-authority regulation.")
    if kind in {"irm", "publication"}:
        cautions.append("Agency operational or explanatory material does not replace controlling statutes, regulations, or judicial holdings.")
    if record.get("conflicting_authority") is not False:
        gaps.append("Identify and analyze adverse authority and conflicts.")
    substantial = category["substantial_authority_use"]
    if kind in {"plr", "tam"}:
        if record.get("same_taxpayer") is True:
            substantial = "taxpayer_specific_written_determination_special_rule_review"
            gaps.append("Verify the written-determination conditions, factual accuracy, and no subsequent modification under the special regulatory rule.")
        elif issued is None:
            substantial = "issuance_date_required"
        elif issued >= date(1976, 11, 1):
            substantial = "enumerated_nonprecedential_material_subject_to_weight_analysis"
        else:
            substantial = "not_within_enumerated_post_1976_category"
    if kind == "faq":
        if record.get("faq_linked_news_release") is True:
            substantial = "qualifying_fact_sheet_faq_penalty_authority_review"
        elif record.get("faq_linked_news_release") is None:
            substantial = "fact_sheet_news_release_link_requires_verification"
            gaps.append("Verify whether the FAQ is in a Fact Sheet linked to an agency news release.")
        else:
            substantial = "ordinary_faq_not_substantial_authority_by_itself"
        cautions.append("The Fact Sheet exception concerns penalty-authority analysis; it does not turn an FAQ into binding law or automatically establish substantial authority.")
    if excluded:
        substantial = "blocked_by_screening_facts"
    if match == "remote":
        cautions.append("Remote factual or legal relevance may carry little or no weight despite the source category.")
    reasons.append("Evaluate supporting and contrary authorities by relevance, persuasiveness, and source type.")
    # Lower tier first, then issue fit, then curated category order; unique id is a
    # deterministic tie-breaker, never a conclusion about the legal dispute.
    tier = 3 if excluded else 2 if gaps else court_priority
    priority = category["research_priority"]
    fit = {"direct": 0, "analogous": 1, "unknown": 2, "remote": 3}[match]
    return {
        "id": item_id, "kind": kind, "purpose": purpose, "as_of": as_of.isoformat(),
        "screening_status": "exclude_current_reliance" if excluded else "review_required" if gaps else "ready_for_analysis",
        "legal_role": role, "substantial_authority_use": substantial,
        "editorial_priority": priority, "sort_key": [tier, fit, priority, item_id],
        "missing_evidence": gaps, "reasons": reasons, "cautions": cautions,
        "source_ids": category["source_ids"],
        "legal_conclusion": "not_determined", "probability": None,
    }


def rank_authorities(records: list[dict], context: dict | None = None) -> dict:
    if not isinstance(records, list):
        raise ValueError("records must be an array")
    results = [evaluate_authority(r, context) for r in records]
    ids = [r["id"] for r in results]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate authority id")
    return {
        "schema_version": "1.0", "method": "editorial_research_queue_not_legal_weight_test",
        "authorities": sorted(results, key=lambda item: tuple(item["sort_key"])),
        "substantial_authority_established": None,
        "instruction": "Read relevant contrary authority; resolve hierarchy and jurisdiction qualitatively.",
    }
