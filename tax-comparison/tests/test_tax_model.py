import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.tax_model import (
    circular_230_scope_check,
    effective_rate,
    oic_collection_potential,
    partnership_loss_waterfall,
    progressive_tax,
    section_199a_qbi,
    tax_wedge,
)
from src.adapters import from_tax_filer, from_shuiwushi, from_acadifi

DATA = json.loads((pathlib.Path(__file__).parents[1] / "data/tax_schedules.json").read_text())

def test_progressive_marginal_brackets():
    b = [{"up_to": 100, "rate": .1}, {"up_to": None, "rate": .2}]
    assert progressive_tax(50, b) == 5
    assert progressive_tax(150, b) == 20
    assert effective_rate(150, b) == 20/150

def test_bracket_monotonicity_and_zero():
    for j in DATA["jurisdictions"]:
        b = j["brackets"]
        vals = [progressive_tax(x, b) for x in (0, 1, 10000, 40000, 100000, 250000)]
        assert vals == sorted(vals)
        assert vals[0] == 0

def test_tax_wedge_components():
    assert round(tax_wedge(100, 10, 5, 3, 2), 6) == .16

def test_adapter_parity_across_three_sources():
    row = {"jurisdiction":"US","tax_year":2026,"currency":"USD","gross_income":120000,"deductions":20000}
    normalized = [f(row).normalized() for f in (from_tax_filer, from_shuiwushi, from_acadifi)]
    assert [x["taxable_income"] for x in normalized] == [100000]*3
    assert [x["tax_year"] for x in normalized] == [2026]*3

def test_invalid_inputs():
    import pytest
    with pytest.raises(ValueError): progressive_tax(-1, DATA["jurisdictions"][0]["brackets"])
    with pytest.raises(ValueError): tax_wedge(0, 0)


def test_d32_partnership_qbi_oic_and_circular_230():
    k1 = partnership_loss_waterfall(4800, 3600, 2500, 1200, is_passive=True)
    assert k1["basis_suspended"] == 1200.0
    assert k1["at_risk_suspended"] == 1100.0
    assert k1["passive_suspended"] == 1300.0
    assert k1["allowed"] == 1200.0

    k1_754 = partnership_loss_waterfall(4800, 3600, 4800, 4800, is_passive=True, section_754_step_up=1200)
    assert k1_754["effective_basis"] == 4800.0
    assert k1_754["allowed"] == 4800.0

    qbi = section_199a_qbi(29000, 150000)
    assert qbi["qbi_deduction"] == 5800.0

    lump = oic_collection_potential(9800, 475, mode="lump_sum")
    assert lump["reasonable_collection_potential"] == 15500.0
    assert lump["initial_payment"] == 3100.0

    per = oic_collection_potential(2350, 315, mode="periodic")
    assert per["reasonable_collection_potential"] == 9910.0

    assert circular_230_scope_check("8821", [2025], 2025, "represent")["action_authorized"] is False
    assert circular_230_scope_check("2848", [2025], 2025, "represent")["action_authorized"] is True
    assert circular_230_scope_check("2848", [2024], 2025, "represent")["action_authorized"] is False
