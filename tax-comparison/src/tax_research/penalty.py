"""Deterministic educational penalty-relief screening; original MIT source.

Inputs are evidence assertions, not verified tax-account data. An ``eligible``
result means only that the implemented screening gates are satisfied. It never
grants relief. Unknown facts remain unknown; no network or clock is consulted.
"""

from __future__ import annotations

from datetime import date
from typing import Any

RESEARCH_AS_OF = "2026-11-22"
FTA_CODES = frozenset({"6651(a)(1)", "6651(a)(2)", "6651(a)(3)",
                       "6656", "6698(a)(1)", "6699(a)(1)"})
SUPPORTED_CODES = FTA_CODES | {"6698(a)(2)", "6699(a)(2)", "6662", "6654", "6721", "6722", "other"}
FORMS = frozenset({"1040", "1065", "1120", "1120-S", "940", "941", "943", "944", "945", "CT-1",
                   "706", "709", "990", "1099", "5471", "5472", "other"})
AEP_FORMS = frozenset({"1040", "1065", "1120", "1120-S", "940", "941", "943", "944", "945", "CT-1"})
EMPLOYMENT_FORMS = frozenset({"940", "941", "943", "944", "945", "CT-1"})
EXCLUDED_FTA_FORMS = frozenset({"706", "709", "990", "1099", "5471", "5472"})
BOOL_FIELDS = frozenset({"is_original_return", "aep_considered", "aep_transcript_verified",
    "related_accounts_reviewed", "currently_required_returns_filed_or_extended", "paid_or_arranged_to_pay",
    "tax_fully_paid", "irs_error", "aep_prevented_by_irs_error", "penalty_factually_valid", "future_aep_history_clear",
    "return_filed_late"})
RC_BOOLS = frozenset({"ordinary_care", "causal_link", "willful_neglect", "good_faith",
    "prompt_correction", "supporting_records", "grounds_exhaustive", "adviser_qualified",
    "adviser_fully_informed", "reasonable_adviser_reliance"})
RC_REASONS = frozenset({"serious_illness", "death", "disaster", "records_unavailable", "system_failure",
    "lack_of_funds", "ignorance", "mistake", "forgetfulness", "deadline_delegation",
    "substantive_tax_advice", "other"})
ACCURACY_COMPONENTS = frozenset({"ordinary", "economic_substance", "deduction_6662_b10",
    "gross_charitable_valuation", "substantial_charitable_valuation", "tax_shelter", "other", "unknown"})
ESTIMATED_FIELDS = frozenset({"casualty_disaster_unusual", "equity_good_conscience",
    "retired_at_62_or_disabled", "event_in_current_or_prior_year", "reasonable_cause", "willful_neglect"})
FIELDS = BOOL_FIELDS | {"penalty_code", "return_form", "tax_year", "quarter", "original_due_date",
    "received_date", "history", "deposit_waivers", "electronic_deposit_avoidance", "rc", "estimated"}


def _boolean(value: Any, field: str) -> None:
    if value is not None and type(value) is not bool:
        raise ValueError(f"{field} must be true, false, or null")


def _parse_date(value: Any, field: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"{field} must be an ISO calendar date")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO calendar date") from exc
    if result.isoformat() != value:
        raise ValueError(f"{field} must be an ISO calendar date")
    if not 1900 <= result.year <= 9996:
        raise ValueError(f"{field} year must be from 1900 to 9996")
    return result


def _validate(case: Any) -> None:
    if not isinstance(case, dict):
        raise ValueError("case must be an object")
    if any(not isinstance(key, str) for key in case):
        raise ValueError("case keys must be text")
    unknown = set(case) - FIELDS
    if unknown:
        raise ValueError("unknown case fields: " + ", ".join(sorted(unknown)))
    if not isinstance(case.get("penalty_code"), str) or case["penalty_code"] not in SUPPORTED_CODES:
        raise ValueError("penalty_code must be an exact supported statutory identifier")
    if case.get("return_form") is not None and (not isinstance(case["return_form"], str) or case["return_form"] not in FORMS):
        raise ValueError("return_form is not recognized; use other for an unmodeled form")
    for key in BOOL_FIELDS:
        _boolean(case.get(key), key)
    year = case.get("tax_year")
    if year is not None and (type(year) is not int or not 1900 <= year <= 9996):
        raise ValueError("tax_year must be an integer from 1900 to 9996")
    quarter = case.get("quarter")
    if quarter is not None and (type(quarter) is not int or quarter not in (1, 2, 3, 4)):
        raise ValueError("quarter must be 1, 2, 3, 4, or null")
    if quarter is not None and case.get("return_form") not in (None, "941"):
        raise ValueError("only Form 941 uses a quarterly period in this model")
    for key in ("original_due_date", "received_date"):
        _parse_date(case.get(key), key)
    waivers = case.get("deposit_waivers")
    if waivers is not None and (type(waivers) is not int or waivers < 0):
        raise ValueError("deposit_waivers must be a nonnegative integer or null")
    if case.get("electronic_deposit_avoidance") not in (None, "none", "partial", "all", "unknown"):
        raise ValueError("electronic_deposit_avoidance must be none, partial, all, or unknown")
    for name, allowed, booleans in (("rc", RC_BOOLS | {"reasons", "accuracy_component"}, RC_BOOLS),
                                    ("estimated", ESTIMATED_FIELDS, ESTIMATED_FIELDS)):
        obj = case.get(name)
        if obj is None:
            continue
        if not isinstance(obj, dict) or any(not isinstance(key, str) for key in obj) or set(obj) - allowed:
            raise ValueError(f"{name} contains unrecognized fields or is not an object")
        for key in booleans:
            _boolean(obj.get(key), f"{name}.{key}")
    rc = case.get("rc") or {}
    reasons = rc.get("reasons", [])
    if not isinstance(reasons, list) or any(not isinstance(x, str) or x not in RC_REASONS for x in reasons):
        raise ValueError("rc.reasons must be a list of recognized reason identifiers")
    if len(reasons) != len(set(reasons)):
        raise ValueError("rc.reasons must not contain duplicates")
    if rc.get("accuracy_component") is not None and (not isinstance(rc["accuracy_component"], str) or rc["accuracy_component"] not in ACCURACY_COMPONENTS):
        raise ValueError("rc.accuracy_component is not recognized")
    history = case.get("history")
    if history is not None:
        if not isinstance(history, list):
            raise ValueError("history must be a list or null")
        seen: set[str] = set()
        for row in history:
            if not isinstance(row, dict) or set(row) != {"period", "filing", "penalty"}:
                raise ValueError("each history row needs period, filing, and penalty only")
            period = row["period"]
            if not isinstance(period, str) or period in seen:
                raise ValueError("history period must be unique text")
            annual = len(period) == 4 and period.isdigit()
            quarterly = len(period) == 7 and period[:4].isdigit() and period[4:6] == "-Q" and period[-1] in "1234"
            if not (annual or quarterly):
                raise ValueError("history period must be YYYY or YYYY-Qn")
            if not 1900 <= int(period[:4]) <= 9996:
                raise ValueError("history year is outside the supported range")
            if not isinstance(row["filing"], str) or row["filing"] not in {"timely", "late", "not_required", "missing", "unknown"}:
                raise ValueError("history filing status is not recognized")
            if not isinstance(row["penalty"], str) or row["penalty"] not in {"none", "estimated_only", "abated_reasonable_cause", "abated_irs_error",
                                      "prior_fta", "prior_aep", "tolerance", "unreversed", "unknown"}:
                raise ValueError("history penalty status is not recognized")
            if row["filing"] == "not_required" and row["penalty"] not in {"none", "abated_irs_error", "unknown"}:
                raise ValueError("not_required history must have no penalty, an error reversal, or unknown status")
            seen.add(period)
    form, code = case.get("return_form"), case["penalty_code"]
    if code.startswith("6698") and form not in (None, "1065", "other"):
        raise ValueError("section 6698 must use the partnership return or an unmodeled report")
    if code.startswith("6699") and form not in (None, "1120-S"):
        raise ValueError("section 6699 must use the S corporation return")


def _route(status: str, reasons: list[str], citations: list[str], missing: list[str] | None = None) -> dict:
    return {"status": status, "reasons": reasons, "missing_evidence": sorted(set(missing or [])),
            "citations": sorted(set(citations))}


def _required(value: Any, field: str, missing: list[str], failures: list[str], message: str) -> None:
    if value is None:
        missing.append(field)
    elif value is False:
        failures.append(message)


def _history(case: dict, missing: list[str], failures: list[str], *, aep: bool = False) -> None:
    year, form, quarter = case.get("tax_year"), case.get("return_form"), case.get("quarter")
    if year is None:
        missing.append("tax_year")
    if form is None:
        missing.append("return_form")
    if form == "941" and quarter is None:
        missing.append("quarter")
    rows = case.get("history")
    if rows is None:
        missing.append("history")
        return
    if year is None or form is None or (form == "941" and quarter is None):
        return
    if form == "941":
        current = year * 4 + quarter - 1
        periods = {f"{x // 4}-Q{x % 4 + 1}" for x in range(current - 12, current)}
    else:
        periods = {str(x) for x in range(year - 3, year)}
    supplied = {row["period"] for row in rows}
    if supplied - periods:
        raise ValueError("history contains periods outside the exact applicable lookback")
    missing.extend("history." + p for p in sorted(periods - supplied))
    for row in sorted(rows, key=lambda item: item["period"]):
        key = "history." + row["period"]
        if row["filing"] == "unknown":
            missing.append(key + ".filing")
        elif row["filing"] == "missing":
            failures.append(key + ": a required return is missing")
        elif row["filing"] == "late":
            if row["penalty"] not in {"abated_reasonable_cause", "abated_irs_error"}:
                if form in {"1120", "1120-S"} and not aep:
                    failures.append(key + ": prior corporate late filing is a stated FTA exclusion; confirm AEP account treatment separately")
                else:
                    missing.append(key + ".late_filing_account_review")
        if row["penalty"] == "unknown":
            missing.append(key + ".penalty")
        elif row["penalty"] in {"prior_fta", "prior_aep", "tolerance", "unreversed"}:
            failures.append(key + ": disqualifying penalty history is recorded")
    if case.get("related_accounts_reviewed") is not True:
        missing.append("related_accounts_reviewed")


def _business(case: dict, missing: list[str], failures: list[str], *, aep: bool) -> bool:
    """Return whether a partial avoidance assessment needs manual allocation."""
    form = case.get("return_form")
    applies = form in EMPLOYMENT_FORMS if aep else form in AEP_FORMS - {"1040"}
    if not applies:
        return False
    count = case.get("deposit_waivers")
    if count is None:
        missing.append("deposit_waivers")
    elif count >= 4:
        failures.append("Four or more counted deposit waivers appear in the applicable lookback")
    avoidance = case.get("electronic_deposit_avoidance")
    if avoidance in (None, "unknown"):
        missing.append("electronic_deposit_avoidance")
    elif avoidance == "all":
        failures.append("The deposit penalty is attributable entirely to electronic-deposit avoidance")
    elif avoidance == "partial":
        if aep:
            failures.append("The current deposit penalty includes electronic-deposit avoidance")
        else:
            return True
    return False


def _fta(case: dict) -> dict:
    cites = ["PEN_FTA_IRM", "PEN_AEP_FACT", "PEN_FTA_COMPLIANCE"]
    if case["penalty_code"] not in FTA_CODES:
        return _route("not_applicable", ["This exact penalty provision is outside FTA scope"], cites)
    if case.get("irs_error") is True or case.get("penalty_factually_valid") is False:
        return _route("not_applicable", ["Correct an erroneous penalty before considering a history-based waiver"], cites)
    form = case.get("return_form")
    if form in EXCLUDED_FTA_FORMS:
        return _route("not_applicable", ["The return has excluded event-based or information-reporting characteristics"], cites)
    due = _parse_date(case.get("original_due_date"), "original_due_date")
    if due is not None and due >= date(2027, 1, 1):
        return _route("not_applicable", ["FTA ends for original return due dates on or after 2027-01-01"], cites)
    missing: list[str] = []
    failures: list[str] = []
    if due is None:
        missing.append("original_due_date")
    if form == "other":
        missing.append("return_form_scope_review")
    year = case.get("tax_year")
    if year is not None and year <= 2000:
        return _route("not_applicable", ["FTA applies to periods ending after 2000-12-31; tax_year denotes the period-ending year"], cites)
    transition = year is not None and year >= (2026 if form == "941" else 2025)
    if transition:
        if case.get("aep_considered") is True:
            return _route("not_applicable", ["AEP was already considered; assess correction or reasonable cause rather than substituting FTA"], cites)
        if case.get("aep_considered") is None:
            missing.append("aep_considered")
    _history(case, missing, failures)
    for field in ("currently_required_returns_filed_or_extended", "paid_or_arranged_to_pay"):
        _required(case.get(field), field, missing, failures, field + " is not established")
    partial = _business(case, missing, failures, aep=False)
    if failures:
        return _route("not_eligible", failures, cites, missing)
    if missing or partial:
        reasons = ["Complete the evidence and account review before deciding FTA eligibility"]
        if partial:
            reasons.append("Only the non-avoidance portion may qualify; allocation requires manual review")
        return _route("review_required", reasons, cites, missing)
    return _route("eligible", ["Implemented FTA screening criteria are met; IRS confirmation remains necessary"], cites)


def _aep(case: dict) -> dict:
    cites = ["PEN_AEP_UPDATE", "PEN_AEP_FACT", "PEN_AEP_PUBLIC"]
    if case["penalty_code"] not in FTA_CODES:
        return _route("not_applicable", ["This exact penalty provision is outside AEP scope"], cites)
    form = case.get("return_form")
    if form is not None and form not in AEP_FORMS:
        return _route("not_applicable", ["The return type is outside the implemented AEP eligible-return list"], cites)
    year = case.get("tax_year")
    if year is not None and year < (2026 if form == "941" else 2025):
        return _route("not_applicable", ["The period precedes the AEP transition"], cites)
    if case.get("penalty_factually_valid") is False:
        return _route("not_applicable", ["Correct the underlying invalid penalty rather than consume relief"], cites)
    missing: list[str] = []
    failures: list[str] = []
    _required(case.get("is_original_return"), "is_original_return", missing, failures, "AEP consideration is tied to an original return")
    due = _parse_date(case.get("original_due_date"), "original_due_date")
    received = _parse_date(case.get("received_date"), "received_date")
    if due is None:
        missing.append("original_due_date")
    if received is None:
        missing.append("received_date")
    if due and received:
        try:
            limit = due.replace(year=due.year + 3)
        except ValueError:
            # A leap-day anniversary is deliberately referred for legal review.
            limit = None
            missing.append("three_year_window_leap_day_review")
        if limit and received > limit:
            failures.append("The original return arrived more than three years after its original due date")
    _history(case, missing, failures, aep=True)
    _business(case, missing, failures, aep=True)
    if case.get("aep_transcript_verified") is not True:
        missing.append("aep_transcript_verified")
    manual = form == "CT-1" or case.get("aep_prevented_by_irs_error") is True
    if manual:
        if case.get("return_filed_late") is None:
            missing.append("return_filed_late")
        elif case.get("return_filed_late") is True:
            _required(case.get("future_aep_history_clear"), "future_aep_history_clear", missing, failures,
                      "A later three-year module contains disqualifying AEP or prior FTA relief")
    elif case.get("aep_considered") is False:
        missing.append("aep_original_processing_or_manual_error_review")
    elif case.get("aep_considered") is None:
        missing.append("aep_considered")
    if failures:
        return _route("not_eligible", failures, cites, missing)
    if missing:
        return _route("review_required", ["Verify original-return processing, complete history, and account indicators"], cites, missing)
    mode = "manual account correction" if manual else "original-return processing"
    return _route("eligible", [f"Implemented AEP screening criteria are met for {mode}; this is not an IRS grant"], cites)


def _reasonable_cause(case: dict) -> dict:
    code, rc = case["penalty_code"], case.get("rc") or {}
    cites = ["PEN_RC_PUBLIC", "PEN_RC_REG"]
    if code == "6654":
        return _route("not_applicable", ["There is no general reasonable-cause waiver; examine section 6654(e)(3) instead"], ["PEN_6654_STAT", "PEN_6654_IRM"])
    if code == "other":
        return _route("review_required", ["Identify the exact penalty and its statutory relief standard"], ["PEN_RC_PUBLIC"], ["exact_penalty_provision"])
    if code in {"6721", "6722"}:
        return _route("review_required", ["Information-return reasonable cause has a separate section 6724 and regulation 301.6724-1 standard"], ["PEN_6724_STAT", "PEN_6724_REG"], ["information_return_specialist_review"])
    if code.startswith("6698"):
        cites = ["PEN_6698_STAT", "PEN_RC_PUBLIC"]
    elif code.startswith("6699"):
        cites = ["PEN_6699_STAT", "PEN_RC_PUBLIC"]
    elif code == "6656":
        cites = ["PEN_6656_STAT", "PEN_RC_PUBLIC"]
    elif code.startswith("6651"):
        cites.append("PEN_6651_STAT")
    if code == "6662":
        cites = ["PEN_6664_STAT", "PEN_6664_REG"]
        component = rc.get("accuracy_component")
        if component in {"economic_substance", "deduction_6662_b10", "gross_charitable_valuation"}:
            return _route("not_applicable", ["The identified component has a statutory exception to ordinary reasonable-cause relief"], cites)
        if component != "ordinary":
            return _route("review_required", ["Identify the component and apply its specific limitations before the ordinary reasonable-cause screen"], cites, ["accuracy_component_review"])
    missing: list[str] = []
    reasons = rc.get("reasons", [])
    if not reasons:
        missing.append("rc.reasons")
    for field in ("ordinary_care", "causal_link", "supporting_records", "prompt_correction"):
        if rc.get(field) is not True:
            missing.append("rc." + field)
    if code.startswith("6651") or code == "6656":
        if rc.get("willful_neglect") is True:
            return _route("not_eligible", ["The supplied facts admit willful neglect, inconsistent with this statutory exception"], cites)
        if rc.get("willful_neglect") is None:
            missing.append("rc.willful_neglect")
    if code == "6662":
        if rc.get("good_faith") is False:
            return _route("not_eligible", ["The supplied facts do not establish the required good faith"], cites)
        if rc.get("good_faith") is None:
            missing.append("rc.good_faith")
    if "substantive_tax_advice" in reasons:
        for field in ("adviser_qualified", "adviser_fully_informed", "reasonable_adviser_reliance"):
            if rc.get(field) is not True:
                missing.append("rc." + field)
    additional_context = any(rc.get(field) is True for field in ("ordinary_care", "causal_link", "supporting_records"))
    if (rc.get("grounds_exhaustive") is True and reasons
            and set(reasons) <= {"lack_of_funds", "forgetfulness", "deadline_delegation"}
            and not additional_context):
        return _route("not_eligible", ["The only stated grounds ordinarily do not establish reasonable cause; additional facts could change the review"], cites, missing)
    text = "Evaluate dates, inability to comply, care exercised, corrective steps, and evidence together; an event label alone proves no exception"
    return _route("review_required", [text], cites, missing)


def _estimated(case: dict) -> dict:
    cites = ["PEN_6654_STAT", "PEN_6654_IRM"]
    if case["penalty_code"] != "6654":
        return _route("not_applicable", ["This route is specific to individual estimated-tax additions"], cites)
    e = case.get("estimated") or {}
    missing: list[str] = []
    for field in ESTIMATED_FIELDS:
        if e.get(field) is None:
            missing.append("estimated." + field)
    unusual = e.get("casualty_disaster_unusual") is True and e.get("equity_good_conscience") is True
    recent = e.get("retired_at_62_or_disabled") is True and e.get("event_in_current_or_prior_year") is True
    if unusual or (recent and e.get("reasonable_cause") is True and e.get("willful_neglect") is False):
        return _route("review_required", ["A potentially applicable statutory waiver is identified; submit a supported request for the statutory determination"], cites)
    # A closed factual record can rule out these two waivers without ruling out
    # other exceptions, safe harbors, or computation corrections in section 6654.
    unusual_blocked = e.get("casualty_disaster_unusual") is False or e.get("equity_good_conscience") is False
    recent_blocked = (e.get("retired_at_62_or_disabled") is False or e.get("event_in_current_or_prior_year") is False
                      or e.get("reasonable_cause") is False or e.get("willful_neglect") is True)
    if unusual_blocked and recent_blocked:
        return _route("not_eligible", ["Neither modeled section 6654(e)(3) waiver fits the supplied facts; other statutory exceptions and computation issues remain outside this result"], cites, missing)
    return _route("review_required", ["Collect facts for the unusual-circumstances and recent retirement/disability statutory waivers"], cites, missing)


def assess_penalty(case: dict) -> dict:
    """Screen one penalty, one return, and one period without mutating input."""
    _validate(case)
    correction = _route("review_required", ["Verify the assessment, payments, filing proof, and notice before seeking discretionary relief"], ["PEN_FTA_IRM"], ["penalty_factually_valid"])
    if case.get("irs_error") is True or case.get("penalty_factually_valid") is False:
        correction = _route("review_required", ["Resolve the identified assessment or processing error first; do not consume FTA to correct an error"], ["PEN_FTA_IRM", "PEN_AEP_UPDATE"])
    elif case.get("penalty_factually_valid") is True:
        correction = _route("not_applicable", ["No assessment error is asserted in the supplied facts"], ["PEN_FTA_IRM"])
    routes = {"correction": correction, "aep": _aep(case), "fta": _fta(case),
              "reasonable_cause": _reasonable_cause(case), "estimated_tax_waiver": _estimated(case)}
    preferred = "correction" if correction["status"] == "review_required" else None
    if preferred is None:
        preferred = next((name for name in ("aep", "fta") if routes[name]["status"] == "eligible"), None)
    if preferred is None:
        preferred = next((name for name in ("aep", "fta", "estimated_tax_waiver", "reasonable_cause")
                          if routes[name]["status"] == "review_required"), "manual_review")
    warnings = ["Educational screening only; eligibility is not an IRS decision.",
                "Separate notice, appeal, refund-claim, payment, and court deadlines require independent review.",
                "This model does not compute tax, penalties, interest, or statutory filing deadlines."]
    if case["penalty_code"] in {"6651(a)(2)", "6651(a)(3)"} and case.get("tax_fully_paid") is not True:
        warnings.append("Under FTA, failure-to-pay charges can continue on unpaid tax; qualifying AEP has different accrual treatment.")
    if case.get("tax_year") is not None and case["tax_year"] > 2026:
        warnings.append("A future-period result uses the known 2026 rules; refresh authority before real-world use.")
    return {"schema_version": "1.0", "research_as_of": RESEARCH_AS_OF,
            "penalty_code": case["penalty_code"], "routes": routes,
            "preferred_route": preferred, "warnings": warnings}
