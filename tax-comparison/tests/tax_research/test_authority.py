from itertools import permutations
import pytest

from tax_research.authority import evaluate_authority, rank_authorities
from tax_research.flags import augment, enabled


def record(kind="statutory", **kwargs):
    return {"id": "item", "kind": kind, "status": "current", "issue_match": "direct",
            "applies_to_period": True, "issued_on": "2020-01-01",
            "conflicting_authority": False, **kwargs}


def test_no_additive_weight_or_automatic_legal_conclusion():
    r = rank_authorities([record()])
    assert r["substantial_authority_established"] is None
    assert r["authorities"][0]["legal_conclusion"] == "not_determined"
    assert r["authorities"][0]["probability"] is None


def test_plr_nonprecedent_is_separate_from_penalty_authority():
    r = evaluate_authority(record("plr", same_taxpayer=False), {"purpose": "substantial_authority"})
    assert "nonprecedential" in r["legal_role"]
    assert r["substantial_authority_use"] == "enumerated_nonprecedential_material_subject_to_weight_analysis"


@pytest.mark.parametrize("issued,expected", [
    ("1976-10-31", "not_within_enumerated_post_1976_category"),
    ("1976-11-01", "enumerated_nonprecedential_material_subject_to_weight_analysis"),
    (None, "issuance_date_required"),
])
def test_private_ruling_issuance_boundary(issued, expected):
    assert evaluate_authority(record("tam", issued_on=issued))["substantial_authority_use"] == expected


@pytest.mark.parametrize("kind", ["irm", "publication"])
def test_administrative_explanations_not_enumerated(kind):
    assert evaluate_authority(record(kind))["substantial_authority_use"] == "not_enumerated"


def test_cca_is_not_silently_treated_as_plr():
    assert evaluate_authority(record("cca"))["substantial_authority_use"] == "not_expressly_enumerated_manual_review"


def test_recipient_private_ruling_has_separate_special_rule():
    r = evaluate_authority(record("plr", same_taxpayer=True, issued_on="1970-01-01"))
    assert r["substantial_authority_use"] == "taxpayer_specific_written_determination_special_rule_review"
    assert r["screening_status"] == "review_required"


@pytest.mark.parametrize("linked,expected", [
    (True, "qualifying_fact_sheet_faq_penalty_authority_review"),
    (False, "ordinary_faq_not_substantial_authority_by_itself"),
    (None, "fact_sheet_news_release_link_requires_verification"),
])
def test_faq_news_release_fact_sheet_exception(linked, expected):
    r = evaluate_authority(record("faq", faq_linked_news_release=linked))
    assert r["substantial_authority_use"] == expected
    assert r["legal_role"] == "informational_nonprecedential_faq"


@pytest.mark.parametrize("forum,circuit", [("claims_court", "09"), ("tax_court", "fed")])
def test_incompatible_appellate_routes_rejected(forum, circuit):
    with pytest.raises(ValueError):
        evaluate_authority(record("circuit_court", circuit=circuit), {"forum": forum, "appellate_circuit": circuit})


def test_small_tax_case_is_not_precedent():
    assert evaluate_authority(record("tax_court_summary"))["legal_role"] == "nonprecedential_small_case_decision"


def test_matching_appeal_circuit_and_forum_required():
    source = record("circuit_court", circuit="09")
    same = evaluate_authority(source, {"forum": "tax_court", "appellate_circuit": "09"})
    other = evaluate_authority(source, {"forum": "tax_court", "appellate_circuit": "02"})
    unknown = evaluate_authority(source)
    assert same["legal_role"] == "potential_controlling_appellate_interpretation"
    assert other["legal_role"] == "potential_persuasive_judicial_interpretation"
    assert unknown["legal_role"] == "jurisdiction_requires_review"


def test_penalty_analysis_has_geographic_exception_caution():
    r = evaluate_authority(record("circuit_court", circuit="09"), {"purpose": "substantial_authority", "forum": "tax_court", "appellate_circuit": "02"})
    assert any("Geographic applicability" in c for c in r["cautions"])
    assert r["substantial_authority_use"] == "enumerated_subject_to_weight_analysis"


@pytest.mark.parametrize("change", [
    {"status": "superseded"}, {"status": "withdrawn"},
    {"applies_to_period": False}, {"issued_on": "2027-01-01"},
])
def test_invalid_reliance_blocked(change):
    assert evaluate_authority(record(**change))["screening_status"] == "exclude_current_reliance"


def test_unknowns_and_conflicts_never_become_ready():
    r = evaluate_authority({"id": "s", "kind": "statutory"})
    assert r["screening_status"] == "review_required"
    assert len(r["missing_evidence"]) >= 4
    r = evaluate_authority(record(conflicting_authority=True))
    assert r["screening_status"] == "review_required"


def test_stable_order_independent_of_input_order():
    values = [record("statutory", id="s"), record("plr", id="p", same_taxpayer=False),
              record("supreme_court", id="c")]
    expected = rank_authorities(values)
    for sequence in permutations(values):
        assert rank_authorities(list(sequence)) == expected
    assert expected["authorities"][0]["id"] == "c"


@pytest.mark.parametrize("change", [
    {"id": ""}, {"kind": "mystery"}, {"applies_to_period": 1},
    {"issued_on": "2026-02-30"}, {"status": "probably"}, {"unexpected": True},
])
def test_invalid_records_rejected(change):
    with pytest.raises(ValueError):
        evaluate_authority(record(**change))


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        rank_authorities([record(), record()])


def test_default_on_and_kill_bypass_malformed_feature_data():
    assert enabled(environment={}) is True
    base = bytes([0, 128, 255, 13, 10])
    def should_not_run(_):
        raise RuntimeError("disabled feature must not be evaluated")
    result = augment(base, should_not_run, environment={"TAX_RESEARCH_DISABLED": "1"})
    assert result is base
    assert result == bytes([0, 128, 255, 13, 10])
    assert enabled({"tax_research/enabled": False}, {}) is False


def test_enabled_augmentation_called_once():
    seen = []
    base = {"existing": "untouched"}
    result = augment(base, lambda value: seen.append(value) or {**value, "research": True}, environment={})
    assert seen == [base]
    assert result == {"existing": "untouched", "research": True}
    assert base == {"existing": "untouched"}
