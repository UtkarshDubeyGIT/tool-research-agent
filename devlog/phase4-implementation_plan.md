# Phase 4 Implementation Plan: Deterministic Validation & Stratified Human Audit

## Scope & Objective
1. Implement deterministic validator (`src/validate.py`) checking schema completeness, missing/duplicate IDs, exact quote substrings, URL validity, and logical contradictions.
2. Implement reproducible human audit engine (`src/audit.py`) and dataset (`data/audit.json`).
3. Define stratified sample of 18 apps across all 9 categories and verdict types.
4. Establish baseline freeze (`data/first_pass.json`) and measure field-level and app-level accuracy progression to final pass with explicit numerators and denominators.

## Verification
- Run `python -m src.validate --input data/final_results.json` confirming 90/90 valid records with zero contradictions.
- Run `python -m src.audit --report` verifying accuracy computation and miss analysis.
- Run `pytest tests/test_audit.py` to confirm denominator arithmetic.
