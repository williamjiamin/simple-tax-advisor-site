from collections import Counter
import json
from math import erfc, exp, pi, sqrt
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tax_research"


def source_records():
    obj = json.loads((DATA / "sources.json").read_text())
    return obj["sources"] if isinstance(obj, dict) else obj


def bank():
    return json.loads((DATA / "questions.json").read_text())["questions"]


def test_exact_bank_count_unique_stems_and_balanced_answer_keys():
    questions = bank()
    assert len(questions) == 80
    assert len({q["id"] for q in questions}) == 80
    assert len({q["stem"].strip().casefold() for q in questions}) == 80
    counts = Counter(q["answer"] for q in questions)
    assert counts == {"A": 20, "B": 20, "C": 20, "D": 20}
    chi2 = sum((counts[k] - 20) ** 2 / 20 for k in "ABCD")
    p = erfc(sqrt(chi2 / 2)) + sqrt(2 * chi2 / pi) * exp(-chi2 / 2)
    assert p > 0.25


def test_every_question_has_explanation_citations_and_length_matched_options():
    known = {s["id"] for s in source_records()}
    for q in bank():
        assert [o["key"] for o in q["options"]] == list("ABCD"), q["id"]
        texts = [o["text"].strip() for o in q["options"]]
        assert len(set(texts)) == 4, q["id"]
        chars = [len(t) for t in texts]
        words = [len(re.findall(r"\S+", t)) for t in texts]
        assert min(chars) > 0 and max(chars) / min(chars) <= 1.15, (q["id"], chars)
        assert min(words) > 0 and max(words) / min(words) <= 1.15, (q["id"], words)
        assert len(q["explanation"].split()) >= 12, q["id"]
        assert q["source_ids"] and set(q["source_ids"]) <= known, q["id"]


def test_primary_source_register_resolves_model_citations():
    records = source_records()
    ids = {s["id"] for s in records}
    assert len(ids) == len(records)
    for source in records:
        assert source["url"].startswith("https://")
        assert source["pinpoint"]
        assert source["checked_on"] == "2026-11-22"
    model = json.loads((DATA / "authority_model.json").read_text())
    for category in model["categories"]:
        assert set(category["source_ids"]) <= ids


def test_default_on_manifest_and_reproducible_derived_cards():
    manifest = json.loads((DATA / "integration_manifest.json").read_text())
    assert manifest["default_enabled"] is True
    assert manifest["kill_switch"] == "TAX_RESEARCH_DISABLED"
    assert manifest["deployment"] == "private_local_staging_only"
    cards = json.loads((DATA / "reference_cards.json").read_text())
    assert cards["schema_version"] == "1.0"
    ids = {s["id"] for s in source_records()}
    assert all(set(c["source_ids"]) <= ids for c in cards["cards"])


def test_saved_penalty_examples_replay_the_expected_routes():
    from tax_research.penalty import assess_penalty
    examples = json.loads((DATA / "penalty_examples.json").read_text())
    assert len(examples) == 5
    ids = {s["id"] for s in source_records()}
    for example in examples:
        result = assess_penalty(example["input"])
        assert {k: v["status"] for k, v in result["routes"].items()} == {
            k: v["status"] for k, v in example["expected"]["routes"].items()
        }, example["id"]
        for route in result["routes"].values():
            assert route["citations"] and set(route["citations"]) <= ids
