# Cross-system parity contract

All three source adapters normalize a tax case into jurisdiction, tax year, currency,
taxable income, and provenance. This establishes field parity, not legal-tax parity:
the three repositories' real schemas and calculation engines were not present in the
provided input archive. An owner-approved mapping review is required before wiring
these adapters into live repositories.

The sample schedules are deliberately separate from this normalized case contract.
Do not infer statutory tax treatment from the sample schedule IDs.
