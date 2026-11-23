"""Stable adapter contracts. No target repository source was supplied."""
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TaxCase:
    jurisdiction: str
    tax_year: int
    currency: str
    gross_income: float
    deductions: float = 0.0
    source: str = "synthetic-demo"

    def normalized(self) -> dict[str, Any]:
        if self.gross_income < 0 or self.deductions < 0 or self.deductions > self.gross_income:
            raise ValueError("invalid income/deduction values")
        return {"jurisdiction": self.jurisdiction, "tax_year": self.tax_year,
                "currency": self.currency, "taxable_income": self.gross_income-self.deductions,
                "source": self.source}

def _adapt(record: dict[str, Any], default: str) -> TaxCase:
    return TaxCase(record["jurisdiction"], int(record["tax_year"]), record["currency"],
                   float(record["gross_income"]), float(record.get("deductions", 0)),
                   record.get("source", default))

def from_tax_filer(record): return _adapt(record, "tax-filer")
def from_shuiwushi(record): return _adapt(record, "shuiwushi")
def from_acadifi(record): return _adapt(record, "acadifi")
