"""Behavioral tests for the evidence-aware relief screen."""

import copy
import json

import pytest

from tax_research.penalty import assess_penalty


def annual_case(year=2024, code="6651(a)(1)"):
    return {
        "penalty_code": code, "return_form": "1040", "tax_year": year,
        "original_due_date": f"{year + 1}-04-15", "received_date": f"{year + 1}-08-20",
        "is_original_return": True, "aep_considered": False, "aep_transcript_verified": True,
        "history": [{"period": str(y), "filing": "timely", "penalty": "none"}
                    for y in range(year - 3, year)],
        "related_accounts_reviewed": True, "currently_required_returns_filed_or_extended": True,
        "paid_or_arranged_to_pay": True, "tax_fully_paid": False,
        "irs_error": False, "penalty_factually_valid": True,
    }


def quarterly_case():
    case = annual_case(2026, "6656")
    case.update(return_form="941", quarter=2, original_due_date="2026-07-31",
                received_date="2026-08-17", aep_considered=True,
                deposit_waivers=0, electronic_deposit_avoidance="none")
    index = 2026 * 4 + 1
    case["history"] = [{"period": f"{x // 4}-Q{x % 4 + 1}", "filing": "timely", "penalty": "none"}
                       for x in range(index - 12, index)]
    return case


def status(case, route):
    return assess_penalty(case)["routes"][route]["status"]


def test_clean_legacy_fta():
    case = annual_case()
    assert status(case, "fta") == "eligible"
    assert status(case, "aep") == "not_applicable"
    assert assess_penalty(case)["preferred_route"] == "fta"


@pytest.mark.parametrize("code", ["6651(a)(1)", "6651(a)(2)", "6651(a)(3)"])
def test_three_failure_codes_are_individually_supported(code):
    assert status(annual_case(code=code), "fta") == "eligible"


@pytest.mark.parametrize("code,form", [("6698(a)(1)", "1065"), ("6699(a)(1)", "1120-S")])
def test_partnership_and_corporation_late_return_scope(code, form):
    case = annual_case(code=code)
    case.update(return_form=form, deposit_waivers=0, electronic_deposit_avoidance="none")
    assert status(case, "fta") == "eligible"


@pytest.mark.parametrize("code,form", [("6698(a)(2)", "1065"), ("6699(a)(2)", "1120-S")])
def test_incomplete_return_penalties_are_not_fta(code, form):
    case = annual_case(code=code)
    case["return_form"] = form
    assert status(case, "fta") == "not_applicable"
    assert status(case, "reasonable_cause") == "review_required"


@pytest.mark.parametrize("penalty", ["estimated_only", "abated_reasonable_cause", "abated_irs_error"])
def test_nonblocking_history_categories(penalty):
    case = annual_case()
    case["history"][0]["penalty"] = penalty
    assert status(case, "fta") == "eligible"


@pytest.mark.parametrize("penalty", ["prior_fta", "prior_aep", "tolerance", "unreversed"])
def test_blocking_history_categories(penalty):
    case = annual_case()
    case["history"][0]["penalty"] = penalty
    assert status(case, "fta") == "not_eligible"


def test_no_prior_filing_requirement_is_not_bad_history():
    case = annual_case()
    for row in case["history"]:
        row["filing"] = "not_required"
    assert status(case, "fta") == "eligible"


@pytest.mark.parametrize("field", ["history", "tax_year", "return_form", "original_due_date",
    "related_accounts_reviewed", "currently_required_returns_filed_or_extended", "paid_or_arranged_to_pay"])
def test_missing_fta_evidence_is_not_silently_true(field):
    case = annual_case()
    del case[field]
    assert status(case, "fta") == "review_required"


def test_empty_history_does_not_mean_clean_history():
    case = annual_case()
    case["history"] = []
    assert len(assess_penalty(case)["routes"]["fta"]["missing_evidence"]) == 3


def test_wrong_lookback_year_rejected():
    case = annual_case()
    case["history"][0]["period"] = "2024"
    with pytest.raises(ValueError, match="lookback"):
        assess_penalty(case)


def test_unknown_history_status_requires_review():
    case = annual_case()
    case["history"][0]["penalty"] = "unknown"
    assert status(case, "fta") == "review_required"


def test_related_accounts_not_yet_reviewed_is_evidence_gap():
    case = annual_case()
    case["related_accounts_reviewed"] = False
    assert status(case, "fta") == "review_required"


def test_correct_error_without_consuming_fta():
    case = annual_case()
    case["penalty_factually_valid"] = False
    result = assess_penalty(case)
    assert result["preferred_route"] == "correction"
    assert result["routes"]["fta"]["status"] == "not_applicable"


def test_2026_transition_without_aep_consideration_allows_fta():
    case = annual_case(2025)
    assert status(case, "fta") == "eligible"
    case["aep_considered"] = None
    assert status(case, "fta") == "review_required"
    case["aep_considered"] = True
    assert status(case, "fta") == "not_applicable"


@pytest.mark.parametrize("due,expected", [("2026-12-31", "eligible"), ("2027-01-01", "not_applicable")])
def test_exact_fta_cutoff(due, expected):
    case = annual_case(2026)
    case["original_due_date"] = due
    assert status(case, "fta") == expected


def test_aep_complete_original_return_screen():
    case = annual_case(2025)
    case["aep_considered"] = True
    assert status(case, "aep") == "eligible"


@pytest.mark.parametrize("delta,expected", [(0, "eligible"), (1, "not_eligible")])
def test_aep_three_year_boundary_uses_original_due_date(delta, expected):
    case = annual_case(2025)
    case.update(aep_considered=True, received_date=f"2029-04-{15 + delta}")
    assert status(case, "aep") == expected


def test_aep_not_for_amended_return():
    case = annual_case(2025)
    case.update(aep_considered=True, is_original_return=False)
    assert status(case, "aep") == "not_eligible"


def test_aep_needs_transcript_evidence():
    case = annual_case(2025)
    case.update(aep_considered=True, aep_transcript_verified=False)
    assert status(case, "aep") == "review_required"


def test_quarterly_aep_uses_twelve_periods():
    case = quarterly_case()
    assert status(case, "aep") == "eligible"
    case["history"].pop()
    assert status(case, "aep") == "review_required"


def test_fta_single_quarter_does_not_waive_entire_year():
    case = quarterly_case()
    case.update(aep_considered=False)
    assert status(case, "fta") == "eligible"
    case["history"][-1]["penalty"] = "prior_fta"
    assert status(case, "fta") == "not_eligible"


def test_ct1_manual_aep_needs_later_history():
    case = annual_case(2025, "6656")
    case.update(return_form="CT-1", aep_considered=False, deposit_waivers=0,
                electronic_deposit_avoidance="none", return_filed_late=True)
    assert status(case, "aep") == "review_required"
    case["future_aep_history_clear"] = True
    assert status(case, "aep") == "eligible"
    case["future_aep_history_clear"] = False
    assert status(case, "aep") == "not_eligible"


def test_extended_timely_manual_return_is_not_presumed_late():
    case = annual_case(2025, "6656")
    case.update(return_form="CT-1", aep_considered=False, deposit_waivers=0,
                electronic_deposit_avoidance="none", return_filed_late=False)
    assert status(case, "aep") == "eligible"
    del case["return_filed_late"]
    assert status(case, "aep") == "review_required"


@pytest.mark.parametrize("year", [1999, 2000])
def test_fta_not_available_before_starting_period(year):
    assert status(annual_case(year), "fta") == "not_applicable"


@pytest.mark.parametrize("count,expected", [(3, "eligible"), (4, "not_eligible")])
def test_deposit_waiver_threshold(count, expected):
    case = quarterly_case()
    case["deposit_waivers"] = count
    assert status(case, "aep") == expected


def test_partial_deposit_avoidance_is_allocated_not_fully_abated():
    case = quarterly_case()
    case.update(aep_considered=False, electronic_deposit_avoidance="partial")
    assert status(case, "fta") == "review_required"
    assert status(case, "aep") == "not_eligible"


def test_unpaid_tax_does_not_block_fta_when_arranged():
    case = annual_case(code="6651(a)(2)")
    result = assess_penalty(case)
    assert result["routes"]["fta"]["status"] == "eligible"
    assert any("continue" in x for x in result["warnings"])


@pytest.mark.parametrize("reason", ["serious_illness", "disaster", "records_unavailable", "ignorance", "mistake"])
def test_event_labels_never_automatically_grant_reasonable_cause(reason):
    case = {"penalty_code": "6651(a)(1)", "rc": {"reasons": [reason], "ordinary_care": True,
        "causal_link": True, "willful_neglect": False, "supporting_records": True, "prompt_correction": True}}
    assert status(case, "reasonable_cause") == "review_required"


def test_lack_of_funds_only_vs_unknown_additional_facts():
    case = {"penalty_code": "6651(a)(2)", "rc": {"reasons": ["lack_of_funds"]}}
    assert status(case, "reasonable_cause") == "review_required"
    case["rc"]["grounds_exhaustive"] = True
    assert status(case, "reasonable_cause") == "not_eligible"
    case["rc"].update(ordinary_care=True, causal_link=True, supporting_records=True,
                      willful_neglect=False, prompt_correction=True)
    assert status(case, "reasonable_cause") == "review_required"


def test_accuracy_requires_good_faith_and_component():
    case = {"penalty_code": "6662", "rc": {"accuracy_component": "ordinary", "good_faith": False}}
    assert status(case, "reasonable_cause") == "not_eligible"
    case["rc"]["good_faith"] = True
    assert status(case, "reasonable_cause") == "review_required"


@pytest.mark.parametrize("component", ["economic_substance", "deduction_6662_b10", "gross_charitable_valuation"])
def test_accuracy_statutory_exclusions(component):
    case = {"penalty_code": "6662", "rc": {"accuracy_component": component}}
    assert status(case, "reasonable_cause") == "not_applicable"


def test_estimated_tax_has_no_general_reasonable_cause_route():
    case = {"penalty_code": "6654", "rc": {"reasons": ["serious_illness"]}}
    result = assess_penalty(case)
    assert result["routes"]["fta"]["status"] == "not_applicable"
    assert result["routes"]["reasonable_cause"]["status"] == "not_applicable"
    assert result["routes"]["estimated_tax_waiver"]["status"] == "review_required"


def test_recent_retirement_statutory_route_still_requires_determination():
    case = {"penalty_code": "6654", "estimated": {"retired_at_62_or_disabled": True,
        "event_in_current_or_prior_year": True, "reasonable_cause": True, "willful_neglect": False}}
    assert status(case, "estimated_tax_waiver") == "review_required"


def test_no_estimated_waiver_does_not_claim_no_other_exception():
    case = {"penalty_code": "6654", "estimated": {"casualty_disaster_unusual": False,
        "retired_at_62_or_disabled": False}}
    route = assess_penalty(case)["routes"]["estimated_tax_waiver"]
    assert route["status"] == "not_eligible"
    assert "other statutory exceptions" in route["reasons"][0]


@pytest.mark.parametrize("payload", [None, [], {}, {"penalty_code": []}, {"penalty_code": "6651"},
    {"penalty_code": "6656", "return_form": []}, {"penalty_code": "6656", "tax_year": True},
    {"penalty_code": "6656", "quarter": 0}, {"penalty_code": "6656", "paid_or_arranged_to_pay": "yes"},
    {"penalty_code": "6656", "original_due_date": "2026-02-30"}, {"penalty_code": "6656", "typo": True},
    {"penalty_code": "6656", "rc": {"accuracy_component": []}},
    {"penalty_code": "6656", "history": [{"period": "2024", "filing": [], "penalty": "none"}]},
    {"penalty_code": "6656", "deposit_waivers": -1}])
def test_invalid_input_fails_explicitly(payload):
    with pytest.raises(ValueError):
        assess_penalty(payload)


def test_canonical_result_is_input_order_independent_and_nonmutating():
    case = annual_case()
    before = copy.deepcopy(case)
    first = assess_penalty(case)
    reordered = dict(reversed(list(case.items())))
    reordered["history"] = list(reversed(case["history"]))
    assert first == assess_penalty(reordered)
    assert case == before
    assert json.loads(json.dumps(first)) == first


def test_minimal_missing_case_never_approved():
    result = assess_penalty({"penalty_code": "6651(a)(1)"})
    assert all(route["status"] != "eligible" for route in result["routes"].values())


def test_route_citations_and_statuses_are_explicit():
    for code in ["6656", "6662", "6654", "6721", "other"]:
        for route in assess_penalty({"penalty_code": code})["routes"].values():
            assert route["status"] in {"eligible", "not_eligible", "review_required", "not_applicable"}
            assert route["citations"]
            assert route["reasons"]
