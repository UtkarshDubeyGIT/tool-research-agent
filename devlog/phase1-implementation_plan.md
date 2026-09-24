# Phase 1 Implementation Plan: Scaffolding, Data Contract & Canonical Dataset

## Scope & Objective
Establish the foundational scaffolding for the Composio AI Product Ops research agent and case study.
1. Transcribe the canonical list of 90 apps from PDF pages 2-6 across 9 categories.
2. Explicitly document and preserve the 90 vs 100 app discrepancy.
3. Define strict Pydantic schemas in `src/models.py` matching the specification (`CredentialAccess`, `EvidenceItem`, `AppRecord`, Jev decision models).
4. Configure project dependencies, `.env.example`, `.gitignore`, and `vercel.json`.

## Deliverables
- `data/apps.json`: 90 apps with IDs 1 to 90.
- `src/models.py`: Pydantic models for typesafe research results and validation.
- `requirements.txt`: Python package requirements.
- `.gitignore`: Ignore secrets and temporary artifacts.
- `.env.example`: Template for API keys.
- `vercel.json`: Zero-config static output configuration.

## Verification
- Verify 90 items in `data/apps.json` with python script checking length, ID sequence, and category diversity.
- Validate that models import and instantiate without errors.
