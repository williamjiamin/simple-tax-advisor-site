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
