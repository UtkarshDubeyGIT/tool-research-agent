# Phase 4 Walkthrough: Deterministic Validation & Stratified Human Audit

## Summary of Changes
1. **Deterministic Validator (`src/validate.py`)**:
   - Implemented checks for schema conformity, sequential IDs (1 to 90), non-empty fields, valid URL schemes, and non-empty verbatim quotes.
   - Enforced logical contradiction detection (e.g. `buildable_now` combined with `partner_approval_required: yes`, or missing auth/API types).
   - Executed against `data/final_results.json`: 90/90 records passed, 0 schema errors, 0 logical contradictions.
2. **Stratified Human Audit (`src/audit.py` & `data/audit.json`)**:
   - Selected 18 apps (~20% sample) stratified across all 9 categories (2 apps per category) and across verdict types (10 `buildable_now`, 5 `conditional`, 3 `outreach_needed`).
   - Compared unassisted baseline (`data/first_pass.json`) against verified ground truth.
   - Measured and reported:
     - **Field-level accuracy**: 75.0% (54/72 fields correct) $\to$ 77.8% (56/72 fields correct).
     - **App-level accuracy**: 38.9% (7/18 apps perfect) $\to$ 44.4% (8/18 apps perfect).
   - Analyzed top concrete misses:
     - PitchBook (#90): Raw LLM assumed self-serve API keys; audit revealed $25k+ annual enterprise contract and sales review required.
     - DealCloud (#10): Raw LLM assumed self-serve trial; audit verified tenant administrator API provisioning required.
     - Salesforce (#1): Raw LLM marked `buildable_now` ignoring Connected App setup and admin authorization in production; verified as `conditional`.
     - Gladly (#20): Raw LLM assumed self-serve helpdesk; audit proved closed enterprise partner access.

## Validation
- Ran `python -m src.validate` confirming 90/90 valid records.
- Ran `python -m src.audit --report` confirming metrics and numerators/denominators.
- Ran `pytest tests/test_audit.py` confirming 100% test pass.
