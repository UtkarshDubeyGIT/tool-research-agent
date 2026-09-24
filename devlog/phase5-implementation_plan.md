# Phase 5 Implementation Plan: Analytics, Case Study Frontend & Test Suite

## Objective
Aggregate cross-category findings from the 90-app evaluation, build the responsive Composio-styled single-page case study web application, and implement a comprehensive automated unit test suite.

## Proposed Modifications
1. **Analytics Engine (`src/analyze.py`)**:
   - Compute coverage stats, buildability breakdown, auth protocol distribution, category matrix, and audit before/after accuracy.
   - Export structured data to `site/data/summary.json`, `site/data/records.json`, `site/data/records.csv`, and `site/data/bundle.js` for zero-CORS browser resilience.
2. **Case Study Frontend (`site/index.html`, `site/style.css`, `site/app.js`)**:
   - Create a modern, dark-themed Composio aesthetic interface.
   - Display prominent scope discrepancy banner explaining the 90 vs 100 app PDF boundary.
   - Implement hero KPI metrics cards, authentication protocol visual bars, and category breakdown matrix.
   - Implement interactive 90-app directory with live search, verdict filter pills, category filter pills, and slide-over evidence drawer.
   - Feature human audit before/after accuracy cards and concrete baseline miss case studies.
   - Provide runnable CLI triggers and architecture workflow documentation.
3. **Automated Unit Tests (`tests/`)**:
   - `tests/test_schema.py`: Verify strict Pydantic model validation and serialization.
   - `tests/test_rules.py`: Verify code-owned buildability and api_breadth rule composition.
   - `tests/test_audit.py`: Verify stratified sample integrity, numerators, denominators, and accuracy math.

## Verification Plan
- Run `python -m src.analyze` and inspect all output files in `site/data/`.
- Run `pytest` across all test files to verify 100% pass rate.
- Validate DOM bindings and offline resilience of `site/index.html`.
