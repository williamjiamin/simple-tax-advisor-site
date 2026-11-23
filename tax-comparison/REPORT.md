# REPORT — SURVEY-32-SIMPLETAX-SITE-SEO

## Delivered
- Local-first, multilingual (English / Simplified Chinese / Japanese) comparative tax education site.
- Progressive bracket engine, three synthetic teaching schedules, responsive results and chart.
- Multi-bracket comparison rendered as 300-DPI PNG and vector SVG.
- FAQPage JSON-LD and SEO title/description/canonical placeholder with `noindex,nofollow` to prevent accidental indexing.
- Shared normalized `TaxCase` contract with adapters for tax-filer, shuiwushi and acadifi; parity regression tests.
- No live deploy, publish, push, external network dependency or data transmission.

## Material limitations
The input archive supplied no `tax-filer` or `acadifi` repository source, and only a `shuiwushi` README/root listing (no study materials). Consequently adapters are boundary contracts, not verified integrations or edits to those repositories. No live statutory rate dataset, tax-year source citations, official exchange-rate conversion, treaty rules, residency rules, or payroll/social-benefit datasets were supplied. All graph values are synthetic and explicitly labeled illustrative. Do not replace the warnings or use the output for filing or advice until qualified review and primary-source validation are complete.

## Quality checks
- Python model tests cover progressive bracket boundaries, monotonicity, effective rate, wedge components, adapter parity and invalid inputs.
- Node tests validate FAQ JSON-LD, locale coverage and local dataset labeling.
- Chart generation is reproducible via `python tools/render_graphs.py`.

## Safety and deployment
Private draft only. `noindex,nofollow`; canonical URL is a reserved placeholder and must be replaced before any publication. No credentials, production configuration, deployment scripts or live integrations included.
