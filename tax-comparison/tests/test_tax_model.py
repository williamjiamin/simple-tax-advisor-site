import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from src.tax_model import progressive_tax, effective_rate, tax_wedge
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
