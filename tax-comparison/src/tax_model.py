from __future__ import annotations
from typing import Any

def progressive_tax(income: float, brackets: list[dict[str, Any]]) -> float:
    if income < 0:
        raise ValueError("income must be non-negative")
    tax, lower = 0.0, 0.0
    for bracket in brackets:
        upper, rate = bracket["up_to"], bracket["rate"]
        if not 0 <= rate <= 1:
            raise ValueError("rate must be between 0 and 1")
        taxable = max(0.0, income-lower) if upper is None else max(0.0, min(income, upper)-lower)
        tax += taxable * rate
        if upper is None or income <= upper:
            break
        lower = upper
    return round(tax, 2)

def effective_rate(income: float, brackets: list[dict[str, Any]]) -> float:
    return 0.0 if income == 0 else progressive_tax(income, brackets) / income

def tax_wedge(income: float, income_tax: float, payroll_or_social: float = 0.0,
              consumption_tax: float = 0.0, benefit_offset: float = 0.0) -> float:
    """Teaching metric: net modeled tax components divided by gross income."""
    if income <= 0:
        raise ValueError("income must be positive")
    if any(v < 0 for v in (income_tax, payroll_or_social, consumption_tax, benefit_offset)):
        raise ValueError("components must be non-negative")
    return (income_tax + payroll_or_social + consumption_tax - benefit_offset) / income


def partnership_loss_waterfall(
    loss: float,
    outside_basis: float,
    at_risk: float,
    passive_income: float,
    is_passive: bool = True,
    section_754_step_up: float = 0.0,
) -> dict[str, float]:
    """Educational Sec. 704(d) + Sec. 754 step-up, Sec. 465 at-risk, and Sec. 469 passive gates."""
    if any(v < 0 for v in (loss, outside_basis, at_risk, passive_income, section_754_step_up)):
        raise ValueError("inputs must be non-negative")
    effective_basis = outside_basis + section_754_step_up
    after_basis = min(loss, effective_basis)
    basis_suspended = loss - after_basis
    after_at_risk = min(after_basis, at_risk)
    at_risk_suspended = after_basis - after_at_risk
    allowed = min(after_at_risk, passive_income) if is_passive else after_at_risk
    passive_suspended = after_at_risk - allowed
    return {
        "effective_basis": round(effective_basis, 2),
        "after_basis": round(after_basis, 2),
        "basis_suspended": round(basis_suspended, 2),
        "after_at_risk": round(after_at_risk, 2),
        "at_risk_suspended": round(at_risk_suspended, 2),
        "allowed": round(allowed, 2),
        "passive_suspended": round(passive_suspended, 2),
    }


def section_199a_qbi(
    qbi: float,
    taxable_before_qbi: float,
    net_capital_gain: float = 0.0,
    w2_wages: float = 0.0,
    ubia: float = 0.0,
    is_sstb: bool = False,
    threshold_start: float = 197300.0,
    phase_range: float = 50000.0,
) -> dict[str, float]:
    """Illustrative TY2025 Sec. 199A QBI 20% deduction with W-2/UBIA and taxable-income cap."""
    if any(v < 0 for v in (taxable_before_qbi, net_capital_gain, w2_wages, ubia)) or phase_range <= 0:
        raise ValueError("invalid QBI parameters")
    tentative = max(0.0, qbi) * 0.20
    wage_cap = max(w2_wages * 0.50, w2_wages * 0.25 + ubia * 0.025)
    excess = max(0.0, taxable_before_qbi - threshold_start)
    phase = min(1.0, excess / phase_range)
    if is_sstb and phase >= 1.0:
        component = 0.0
    else:
        scale = (1.0 - phase) if is_sstb else 1.0
        scaled_tentative = tentative * scale
        scaled_cap = wage_cap * scale
        reduction = max(0.0, scaled_tentative - scaled_cap) * phase
        component = max(0.0, scaled_tentative - reduction)
    income_cap = max(0.0, taxable_before_qbi - net_capital_gain) * 0.20
    return {
        "tentative_qbi": round(tentative, 2),
        "wage_ubia_cap": round(wage_cap, 2),
        "phase_fraction": round(phase, 4),
        "qbi_deduction": round(min(component, income_cap), 2),
        "taxable_income_cap": round(income_cap, 2),
    }


def oic_collection_potential(equity: float, monthly_disposable: float, mode: str = "lump_sum") -> dict[str, float]:
    """Offer in Compromise RCP worksheet model: 12-month lump sum (20% down) vs 24-month periodic."""
    if equity < 0 or monthly_disposable < 0:
        raise ValueError("equity and monthly_disposable must be non-negative")
    if mode not in ("lump_sum", "periodic"):
        raise ValueError("mode must be 'lump_sum' or 'periodic'")
    months = 12 if mode == "lump_sum" else 24
    future_income = monthly_disposable * months
    rcp = equity + future_income
    initial_payment = rcp * 0.20 if mode == "lump_sum" else (rcp / months)
    return {
        "months": float(months),
        "future_income_component": round(future_income, 2),
        "reasonable_collection_potential": round(rcp, 2),
        "initial_payment": round(initial_payment, 2),
    }


def circular_230_scope_check(
    form_type: str,
    listed_years: list[int],
    target_year: int,
    action: str,
) -> dict[str, Any]:
    """Verify Form 2848 (representation) vs Form 8821 (information only) and listed tax period."""
    norm_form = form_type.strip()
    if norm_form not in ("2848", "8821"):
        raise ValueError("form_type must be '2848' or '8821'")
    if action not in ("inspect", "represent"):
        raise ValueError("action must be 'inspect' or 'represent'")
    year_ok = target_year in listed_years
    role_ok = (norm_form == "2848") or (action == "inspect")
    return {
        "form_type": norm_form,
        "year_covered": year_ok,
        "action_authorized": year_ok and role_ok,
        "circular_230_rule": "Form 8821 grants information access only; Form 2848 is required for representation.",
    }
